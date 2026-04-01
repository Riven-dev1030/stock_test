"""
validation/monte_carlo.py — Monte Carlo simulation on trade sequences.

Randomly shuffles the trade PnL sequence N times and measures the
distribution of total return and max drawdown to quantify luck vs. edge.
"""
import random
import math


def run_monte_carlo(trades: list, simulations: int = 5000,
                    ruin_threshold: float = -30.0,
                    seed=None) -> dict:
    """
    Run Monte Carlo simulation by shuffling trade results.

    Args:
        trades:         List of trade dicts (must have 'pnl_pct' field).
        simulations:    Number of shuffle iterations.
        ruin_threshold: Equity drawdown level (%) considered "ruin".
        seed:           Random seed for reproducibility.

    Returns:
        Monte Carlo result dict as specified in SDD §5.1.
    """
    if not trades:
        return _empty_result(simulations, ruin_threshold)

    rng    = random.Random(seed)
    pnls   = [t["pnl_pct"] for t in trades]
    n      = len(pnls)

    total_returns  = []
    max_drawdowns  = []
    ruin_count     = 0

    for _ in range(simulations):
        shuffled = pnls[:]
        rng.shuffle(shuffled)

        equity   = 0.0
        peak     = 0.0
        max_dd   = 0.0
        ruined   = False

        for pnl in shuffled:
            equity += pnl
            if equity > peak:
                peak = equity
            dd = equity - peak
            if dd < max_dd:
                max_dd = dd
            if dd <= ruin_threshold and not ruined:
                ruined = True

        total_returns.append(equity)
        max_drawdowns.append(max_dd)
        if ruined:
            ruin_count += 1

    return {
        "simulations":  simulations,
        "percentiles": {
            "p5":  _percentile_pair(total_returns, max_drawdowns, 5),
            "p25": _percentile_pair(total_returns, max_drawdowns, 25),
            "p50": _percentile_pair(total_returns, max_drawdowns, 50),
            "p75": _percentile_pair(total_returns, max_drawdowns, 75),
            "p95": _percentile_pair(total_returns, max_drawdowns, 95),
        },
        "ruin_probability": round(ruin_count / simulations * 100, 4),
        "ruin_threshold":   ruin_threshold,
    }


def _percentile_pair(returns: list, drawdowns: list, p: int) -> dict:
    return {
        "total_return": round(_percentile(returns,   p), 4),
        "max_drawdown": round(_percentile(drawdowns, p), 4),
    }


def _percentile(data: list, p: int) -> float:
    """Return the p-th percentile of a sorted data list."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    n = len(sorted_data)
    idx = (p / 100) * (n - 1)
    lo  = int(idx)
    hi  = min(lo + 1, n - 1)
    frac = idx - lo
    return sorted_data[lo] * (1 - frac) + sorted_data[hi] * frac


def _empty_result(simulations: int, ruin_threshold: float) -> dict:
    pair = {"total_return": 0.0, "max_drawdown": 0.0}
    return {
        "simulations": simulations,
        "percentiles": {
            "p5": pair, "p25": pair, "p50": pair, "p75": pair, "p95": pair,
        },
        "ruin_probability": 0.0,
        "ruin_threshold":   ruin_threshold,
    }
