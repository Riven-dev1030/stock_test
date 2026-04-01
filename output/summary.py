"""
output/summary.py — Compute statistical summary from a list of trades.
"""
import math


def compute_summary(trades: list) -> dict:
    """
    Compute trading statistics from a completed trades list.

    Args:
        trades: List of trade dicts as produced by engine.run_backtest().

    Returns:
        Summary dict matching the SDD specification.
    """
    total = len(trades)
    if total == 0:
        return _empty_summary()

    wins   = [t for t in trades if t["pnl_pct"] > 0]
    losses = [t for t in trades if t["pnl_pct"] <= 0]

    win_count  = len(wins)
    loss_count = len(losses)
    win_rate   = win_count / total * 100

    avg_win  = sum(t["pnl_pct"] for t in wins)  / win_count  if wins   else 0.0
    avg_loss = sum(t["pnl_pct"] for t in losses) / loss_count if losses else 0.0

    gross_profit = sum(t["pnl_pct"] for t in wins)   if wins   else 0.0
    gross_loss   = abs(sum(t["pnl_pct"] for t in losses)) if losses else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Expectancy = win_rate * avg_win + loss_rate * avg_loss
    expectancy = (win_count / total) * avg_win + (loss_count / total) * avg_loss

    # Consecutive streaks
    max_consec_wins   = _max_consecutive(trades, win=True)
    max_consec_losses = _max_consecutive(trades, win=False)

    # Cumulative equity curve for drawdown
    cum_return, max_drawdown = _max_drawdown(trades)
    total_return = cum_return

    # Sharpe ratio (annualised, assume daily bars, 252 trading days)
    returns = [t["pnl_pct"] for t in trades]
    sharpe  = _sharpe_ratio(returns)

    avg_bars      = sum(t["bars_held"] for t in trades) / total
    avg_bars_win  = sum(t["bars_held"] for t in wins)  / win_count  if wins   else 0.0
    avg_bars_loss = sum(t["bars_held"] for t in losses) / loss_count if losses else 0.0

    # Exit reason breakdown
    exit_breakdown: dict = {}
    for t in trades:
        reason = t.get("exit_reason", "unknown") or "unknown"
        exit_breakdown[reason] = exit_breakdown.get(reason, 0) + 1

    return {
        "total_trades":           total,
        "winning_trades":         win_count,
        "losing_trades":          loss_count,
        "win_rate":               round(win_rate, 4),
        "avg_win_pct":            round(avg_win,  4),
        "avg_loss_pct":           round(avg_loss, 4),
        "profit_factor":          round(profit_factor, 4) if profit_factor != float("inf") else None,
        "expectancy_pct":         round(expectancy, 4),
        "max_consecutive_wins":   max_consec_wins,
        "max_consecutive_losses": max_consec_losses,
        "max_drawdown_pct":       round(max_drawdown, 4),
        "total_return_pct":       round(total_return, 4),
        "sharpe_ratio":           round(sharpe, 4),
        "avg_bars_held":          round(avg_bars, 4),
        "avg_bars_held_win":      round(avg_bars_win,  4),
        "avg_bars_held_loss":     round(avg_bars_loss, 4),
        "exit_reason_breakdown":  exit_breakdown,
    }


def _empty_summary() -> dict:
    return {
        "total_trades": 0, "winning_trades": 0, "losing_trades": 0,
        "win_rate": 0.0, "avg_win_pct": 0.0, "avg_loss_pct": 0.0,
        "profit_factor": None, "expectancy_pct": 0.0,
        "max_consecutive_wins": 0, "max_consecutive_losses": 0,
        "max_drawdown_pct": 0.0, "total_return_pct": 0.0,
        "sharpe_ratio": 0.0, "avg_bars_held": 0.0,
        "avg_bars_held_win": 0.0, "avg_bars_held_loss": 0.0,
        "exit_reason_breakdown": {},
    }


def _max_consecutive(trades: list, win: bool) -> int:
    max_streak = 0
    streak     = 0
    for t in trades:
        is_win = t["pnl_pct"] > 0
        if is_win == win:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    return max_streak


def _max_drawdown(trades: list) -> tuple:
    """
    Compute total return and maximum drawdown from sequential trade PnL.

    Returns:
        (total_return_pct, max_drawdown_pct)
    """
    equity  = 0.0
    peak    = 0.0
    max_dd  = 0.0

    for t in trades:
        equity += t["pnl_pct"]
        if equity > peak:
            peak = equity
        dd = equity - peak  # always <= 0
        if dd < max_dd:
            max_dd = dd

    return equity, max_dd


def _sharpe_ratio(returns: list, risk_free: float = 0.0) -> float:
    n = len(returns)
    if n < 2:
        return 0.0
    mean = sum(returns) / n
    variance = sum((r - mean) ** 2 for r in returns) / (n - 1)
    std = math.sqrt(variance) if variance > 0 else 0.0
    if std == 0:
        return 0.0
    return (mean - risk_free) / std
