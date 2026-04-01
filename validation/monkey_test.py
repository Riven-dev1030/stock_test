"""
validation/monkey_test.py — Monkey Test (random strategy benchmark).

Generates N random strategies by picking random entry points and
random holding periods on the same OHLCV data, then compares the
real strategy's return to this random distribution.
"""
import random
import math


def run_monkey_test(ohlcv: list, strategy_return: float,
                    simulations: int = 10_000,
                    min_hold: int = 1, max_hold: int = 30,
                    seed=None) -> dict:
    """
    Compare a strategy's return against randomly-timed trades.

    Args:
        ohlcv:           Full OHLCV list.
        strategy_return: The real strategy's total return (%).
        simulations:     Number of random strategies to simulate.
        min_hold:        Minimum holding period in bars.
        max_hold:        Maximum holding period in bars.
        seed:            Random seed for reproducibility.

    Returns:
        Monkey test result dict as specified in SDD §5.2.
    """
    n   = len(ohlcv)
    rng = random.Random(seed)

    if n < 2:
        return _empty_result(simulations, strategy_return)

    random_returns = []

    for _ in range(simulations):
        # Pick a random entry and holding period
        hold       = rng.randint(min_hold, max_hold)
        max_entry  = n - hold - 1
        if max_entry < 0:
            random_returns.append(0.0)
            continue
        entry_idx  = rng.randint(0, max_entry)
        exit_idx   = entry_idx + hold

        entry_price = ohlcv[entry_idx]["close"]
        exit_price  = ohlcv[exit_idx]["close"]

        if entry_price <= 0:
            random_returns.append(0.0)
            continue

        pnl_pct = (exit_price - entry_price) / entry_price * 100
        random_returns.append(pnl_pct)

    mean_return = sum(random_returns) / len(random_returns) if random_returns else 0.0
    variance    = (
        sum((r - mean_return) ** 2 for r in random_returns) / max(len(random_returns) - 1, 1)
        if random_returns else 0.0
    )
    std_return  = math.sqrt(variance) if variance > 0 else 0.0

    # Percentile rank: fraction of random returns < strategy_return
    below = sum(1 for r in random_returns if r < strategy_return)
    percentile_rank = below / len(random_returns) * 100 if random_returns else 50.0

    # p-value: 1 - percentile_rank/100 (one-tailed)
    p_value    = 1.0 - percentile_rank / 100
    significant = p_value < 0.05

    sorted_rand = sorted(random_returns)
    p5  = _percentile(sorted_rand, 5)
    p95 = _percentile(sorted_rand, 95)

    return {
        "random_simulations": simulations,
        "random_distribution": {
            "mean_return": round(mean_return, 4),
            "std_return":  round(std_return,  4),
            "p5":          round(p5,  4),
            "p95":         round(p95, 4),
        },
        "strategy_return":  round(strategy_return, 4),
        "percentile_rank":  round(percentile_rank, 4),
        "p_value":          round(p_value, 4),
        "significant":      significant,
    }


def _percentile(sorted_data: list, p: int) -> float:
    if not sorted_data:
        return 0.0
    n   = len(sorted_data)
    idx = (p / 100) * (n - 1)
    lo  = int(idx)
    hi  = min(lo + 1, n - 1)
    return sorted_data[lo] * (1 - idx + lo) + sorted_data[hi] * (idx - lo)


def _empty_result(simulations: int, strategy_return: float) -> dict:
    return {
        "random_simulations": simulations,
        "random_distribution": {
            "mean_return": 0.0, "std_return": 0.0, "p5": 0.0, "p95": 0.0,
        },
        "strategy_return": strategy_return,
        "percentile_rank": 50.0,
        "p_value": 0.5,
        "significant": False,
    }
