"""
core/engine.py — Backtesting engine.

Iterates bar-by-bar over an OHLCV array, applies the strategy's
entry/exit conditions, and produces a structured result dict.

Supports multiple simultaneous positions via config["max_positions"]
(default: 1, backward-compatible with single-position strategies).
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
                           Optional key: "max_positions" (int, default 1).
        custom_conditions: Optional dict of {type_name: CustomCondition instance}.

    Returns:
        {
          "metadata":  {...},
          "trades":    [...],
          "scan_log":  [...],
          "summary":   None   <- populated by output/summary.py
        }

    scan_log entry format:
        {
          "index": int,
          "date": str,
          "ohlcv": dict,
          "indicators": dict,
          "entry_triggered": bool,
          "entry_conditions": dict | None,
          "positions": [          # list of all open positions at end of bar
            {
              "trade_id": int,
              "entry_price": float,
              "entry_index": int,
              "current_pnl_pct": float,
              "peak_price": float,
              "bars_held": int,
            }, ...
          ],
          "exit_triggered": bool,   # True if ANY position exited this bar
          "exit_reason": str | None,
          "exits_this_bar": [       # list of exits that happened this bar
            {"trade_id": int, "exit_reason": str, "pnl_pct": float}, ...
          ],
        }

    Backward-compat note: when max_positions=1 the engine behaves identically
    to the original single-position engine. Callers that previously accessed
    scan_log[i]["position"] (singular) should switch to scan_log[i]["positions"][0]
    (or check the list).
    """
    n             = len(ohlcv)
    warmup        = get_warmup_period(config)
    ind           = compute_indicators(ohlcv, config)
    max_positions = config.get("max_positions", 1)

    scan_log  = []
    trades    = []
    positions = []   # list of open position dicts
    trade_id  = 0

    for i in range(warmup, n):
        bar         = ohlcv[i]
        ind_snapshot = {k: (v[i] if i < len(v) else None) for k, v in ind.items()}
        exits_this_bar = []

        # ----------------------------------------------------------------
        # 1. Update state + evaluate exit for every open position
        # ----------------------------------------------------------------
        still_open = []
        for pos in positions:
            pos["bars_held"] += 1
            current_price = bar["close"]

            if current_price > pos["peak_price"]:
                pos["peak_price"] = current_price

            exit_eval = evaluate_exit(
                ohlcv, i, ind, config, pos, custom_conditions
            )

            if exit_eval["triggered"]:
                pnl_pct = (current_price - pos["entry_price"]) / pos["entry_price"] * 100
                exits_this_bar.append({
                    "trade_id":   pos["trade_id"],
                    "exit_reason": exit_eval["exit_reason"],
                    "pnl_pct":    round(pnl_pct, 4),
                })
                _close_trade(trades, pos, i, bar["date"],
                             current_price, exit_eval["exit_reason"])
            else:
                still_open.append(pos)

        positions = still_open

        # ----------------------------------------------------------------
        # 2. Evaluate entry if room for another position
        # ----------------------------------------------------------------
        entry_eval = None
        if len(positions) < max_positions:
            entry_eval = evaluate_entry(ohlcv, i, ind, config, custom_conditions)
            if entry_eval["triggered"]:
                trade_id += 1
                new_pos = {
                    "trade_id":    trade_id,
                    "entry_index": i,
                    "entry_date":  bar["date"],
                    "entry_price": bar["close"],
                    "peak_price":  bar["close"],
                    "bars_held":   0,
                }
                positions.append(new_pos)

        # ----------------------------------------------------------------
        # 3. Build scan_log snapshot
        # ----------------------------------------------------------------
        positions_snapshot = [
            {
                "trade_id":        pos["trade_id"],
                "entry_price":     pos["entry_price"],
                "entry_index":     pos["entry_index"],
                "current_pnl_pct": round(
                    (bar["close"] - pos["entry_price"]) / pos["entry_price"] * 100, 4
                ),
                "peak_price":      pos["peak_price"],
                "bars_held":       pos["bars_held"],
            }
            for pos in positions
        ]

        scan_log.append({
            "index":            i,
            "date":             bar["date"],
            "ohlcv":            bar,
            "indicators":       ind_snapshot,
            "entry_triggered":  entry_eval["triggered"] if entry_eval else False,
            "entry_conditions": entry_eval["conditions"] if entry_eval else None,
            "positions":        positions_snapshot,
            "exit_triggered":   len(exits_this_bar) > 0,
            "exit_reason":      exits_this_bar[0]["exit_reason"] if exits_this_bar else None,
            "exits_this_bar":   exits_this_bar,
        })

    # --------------------------------------------------------------------
    # End of data — force-close all remaining open positions
    # --------------------------------------------------------------------
    if positions and n > 0:
        last_bar = ohlcv[n - 1]
        for pos in positions:
            _close_trade(trades, pos, n - 1, last_bar["date"],
                         last_bar["close"], "end_of_data")
        positions = []

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

    max_dd = (exit_price - peak_price) / peak_price * 100 if peak_price > 0 else 0

    trades.append({
        "id":                        position["trade_id"],
        "entry_index":               position["entry_index"],
        "entry_date":                position["entry_date"],
        "entry_price":               entry_price,
        "exit_index":                exit_index,
        "exit_date":                 exit_date,
        "exit_price":                round(exit_price, 4),
        "exit_reason":               exit_reason,
        "bars_held":                 bars_held,
        "pnl_pct":                   round(pnl_pct, 4),
        "pnl_abs":                   round(pnl_abs, 4),
        "peak_price":                peak_price,
        "max_drawdown_during_trade": round(max_dd, 4),
    })
