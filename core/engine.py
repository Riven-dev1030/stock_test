"""
core/engine.py — Backtesting engine.

Iterates bar-by-bar over an OHLCV array, applies the strategy's
entry/exit conditions, and produces a structured result dict.
"""

from core.strategy import (
    compute_indicators,
    evaluate_entry,
    evaluate_exit,
    get_warmup_period,
)


def run_backtest(ohlcv: list, config: dict,
                 custom_conditions: dict = None) -> dict:
    """
    Execute a full backtest.

    Args:
        ohlcv:             List of OHLCV dicts.
        config:            Validated strategy config dict.
        custom_conditions: Optional dict of {type_name: CustomCondition instance}.

    Returns:
        {
          "metadata":  {...},
          "trades":    [...],
          "scan_log":  [...],
          "summary":   None   ← populated by output/summary.py
        }
    """
    n             = len(ohlcv)
    warmup        = get_warmup_period(config)
    ind           = compute_indicators(ohlcv, config)
    scan_log      = []
    trades        = []
    position      = None   # None = flat; dict = in position
    trade_id      = 0

    for i in range(warmup, n):
        bar = ohlcv[i]

        # ----------------------------------------------------------------
        # Build per-bar indicators snapshot
        # ----------------------------------------------------------------
        ind_snapshot = {k: (v[i] if i < len(v) else None) for k, v in ind.items()}

        if position is None:
            # --------------------------------------------------------
            # Not in position — evaluate entry
            # --------------------------------------------------------
            entry_eval = evaluate_entry(ohlcv, i, ind, config, custom_conditions)

            log_entry = {
                "index":            i,
                "date":             bar["date"],
                "ohlcv":            bar,
                "indicators":       ind_snapshot,
                "entry_conditions": entry_eval["conditions"],
                "entry_triggered":  entry_eval["triggered"],
                "position":         None,
                "exit_conditions":  None,
                "exit_triggered":   False,
                "exit_reason":      None,
            }

            if entry_eval["triggered"]:
                trade_id += 1
                position = {
                    "trade_id":   trade_id,
                    "entry_index": i,
                    "entry_date":  bar["date"],
                    "entry_price": bar["close"],
                    "peak_price":  bar["close"],
                    "bars_held":   0,
                }
                log_entry["position"] = {
                    "entry_price":   position["entry_price"],
                    "entry_index":   i,
                    "current_pnl_pct": 0.0,
                    "peak_price":    position["peak_price"],
                    "bars_held":     0,
                }

            scan_log.append(log_entry)

        else:
            # --------------------------------------------------------
            # In position — update position state, evaluate exit
            # --------------------------------------------------------
            position["bars_held"] += 1
            current_price          = bar["close"]

            # Update peak price
            if current_price > position["peak_price"]:
                position["peak_price"] = current_price

            current_pnl_pct = (
                (current_price - position["entry_price"])
                / position["entry_price"] * 100
            )

            exit_eval = evaluate_exit(ohlcv, i, ind, config, position, custom_conditions)

            log_entry = {
                "index":           i,
                "date":            bar["date"],
                "ohlcv":           bar,
                "indicators":      ind_snapshot,
                "entry_conditions": None,
                "entry_triggered": False,
                "position": {
                    "entry_price":     position["entry_price"],
                    "entry_index":     position["entry_index"],
                    "current_pnl_pct": round(current_pnl_pct, 4),
                    "peak_price":      position["peak_price"],
                    "bars_held":       position["bars_held"],
                },
                "exit_conditions": exit_eval["conditions"],
                "exit_triggered":  exit_eval["triggered"],
                "exit_reason":     exit_eval["exit_reason"],
            }
            scan_log.append(log_entry)

            if exit_eval["triggered"]:
                _close_trade(trades, position, i, bar["date"],
                             bar["close"], exit_eval["exit_reason"])
                position = None

    # --------------------------------------------------------------------
    # End of data — force-close any open position
    # --------------------------------------------------------------------
    if position is not None and n > 0:
        last_bar = ohlcv[n - 1]
        _close_trade(trades, position, n - 1, last_bar["date"],
                     last_bar["close"], "end_of_data")
        position = None

    return {
        "metadata": {
            "strategy_name": config.get("name", "unnamed"),
            "data_source":   "unknown",
            "data_range": {
                "start": ohlcv[0]["date"] if ohlcv else None,
                "end":   ohlcv[-1]["date"] if ohlcv else None,
            },
            "total_bars":    n,
            "warmup_period": warmup,
            "params":        config,
        },
        "trades":   trades,
        "scan_log": scan_log,
        "summary":  None,
    }


def _close_trade(trades: list, position: dict, exit_index: int,
                 exit_date: str, exit_price: float, exit_reason: str):
    entry_price = position["entry_price"]
    pnl_pct     = (exit_price - entry_price) / entry_price * 100
    pnl_abs     = exit_price - entry_price
    bars_held   = position["bars_held"]
    peak_price  = position["peak_price"]

    # Max drawdown during trade: deepest close vs peak
    max_dd = (exit_price - peak_price) / peak_price * 100 if peak_price > 0 else 0

    trades.append({
        "id":                       position["trade_id"],
        "entry_index":              position["entry_index"],
        "entry_date":               position["entry_date"],
        "entry_price":              entry_price,
        "exit_index":               exit_index,
        "exit_date":                exit_date,
        "exit_price":               round(exit_price, 4),
        "exit_reason":              exit_reason,
        "bars_held":                bars_held,
        "pnl_pct":                  round(pnl_pct, 4),
        "pnl_abs":                  round(pnl_abs, 4),
        "peak_price":               peak_price,
        "max_drawdown_during_trade": round(max_dd, 4),
    })
