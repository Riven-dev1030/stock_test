"""
output/slicer.py — Extract OHLCV context slices around problem trades for AI diagnosis.
"""


def slice_trade(trade: dict, ohlcv: list, scan_log: list,
                indicators: dict, context_bars: int = 15) -> dict:
    """
    Build a diagnostic slice for one trade.

    Args:
        trade:        A trade dict from engine output.
        ohlcv:        Full OHLCV list.
        scan_log:     Full scan_log list from engine output.
        indicators:   Pre-computed indicator arrays (from strategy.compute_indicators).
        context_bars: Number of bars to include before entry and after exit.

    Returns:
        A diagnosis dict as specified in SDD §4.3.
    """
    entry_idx = trade["entry_index"]
    exit_idx  = trade["exit_index"]

    start_idx = max(0, entry_idx - context_bars)
    end_idx   = min(len(ohlcv) - 1, exit_idx + context_bars)

    ohlcv_slice = ohlcv[start_idx: end_idx + 1]

    # Build indicator slices for the same range
    indicators_slice = {
        key: arr[start_idx: end_idx + 1]
        for key, arr in indicators.items()
    }

    # Find entry and exit scan_log entries
    # scan_log is indexed from warmup onward; each entry has an "index" field
    log_by_index = {log["index"]: log for log in scan_log}
    entry_scan   = log_by_index.get(entry_idx)
    exit_scan    = log_by_index.get(exit_idx)

    diagnosis_prompt = _build_prompt(trade)

    return {
        "trade_id":       trade["id"],
        "context_range":  {"start_index": start_idx, "end_index": end_idx},
        "ohlcv_slice":    ohlcv_slice,
        "indicators_slice": indicators_slice,
        "entry_scan":     entry_scan,
        "exit_scan":      exit_scan,
        "diagnosis_prompt": diagnosis_prompt,
    }


def auto_select_trades(trades: list, top_n: int = 3,
                       criteria: str = "worst_pnl") -> list:
    """
    Auto-select the most diagnostically interesting trades.

    Args:
        trades:   Full trades list.
        top_n:    Number of trades to return.
        criteria: Selection strategy:
                  - "worst_pnl":       bottom N by pnl_pct
                  - "shortest_held":   bottom N by bars_held (false breakouts)
                  - "largest_drawdown": bottom N by max_drawdown_during_trade

    Returns:
        Sorted list of up to top_n trade dicts.
    """
    if not trades:
        return []

    if criteria == "worst_pnl":
        sorted_trades = sorted(trades, key=lambda t: t["pnl_pct"])
    elif criteria == "shortest_held":
        sorted_trades = sorted(trades, key=lambda t: t["bars_held"])
    elif criteria == "largest_drawdown":
        sorted_trades = sorted(trades, key=lambda t: t["max_drawdown_during_trade"])
    else:
        sorted_trades = sorted(trades, key=lambda t: t["pnl_pct"])

    return sorted_trades[:top_n]


def build_slices(trades: list, ohlcv: list, scan_log: list,
                 indicators: dict, top_n: int = 3,
                 criteria: str = "worst_pnl",
                 context_bars: int = 15) -> list:
    """
    Convenience: auto-select trades and return their slices.

    Returns:
        List of slice dicts.
    """
    selected = auto_select_trades(trades, top_n=top_n, criteria=criteria)
    return [
        slice_trade(t, ohlcv, scan_log, indicators, context_bars)
        for t in selected
    ]


def _build_prompt(trade: dict) -> str:
    pnl      = trade["pnl_pct"]
    entry_d  = trade["entry_date"]
    exit_d   = trade["exit_date"]
    reason   = trade["exit_reason"]
    bars     = trade["bars_held"]
    sign     = "+" if pnl >= 0 else ""

    return (
        f"此筆交易損益 {sign}{pnl:.2f}%，"
        f"進場日期 {entry_d}，出場日期 {exit_d}，"
        f"持倉 {bars} 根，出場原因：{reason}。"
        f"請分析進場時的量價狀態是否支持突破有效性，"
        f"以及出場機制是否合理設定。"
    )
