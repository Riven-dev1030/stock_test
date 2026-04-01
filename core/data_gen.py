import random
from datetime import datetime, timedelta


def generate(n: int, mode: str = "random", seed=None) -> list:
    """
    Generate simulated OHLCV data.

    Args:
        n:    Number of bars to generate
        mode: Market mode — "random" | "bull" | "bear" | "choppy" | "diverge"
        seed: Optional random seed for reproducibility

    Returns:
        List of dicts, each with keys: date, open, high, low, close, volume
    """
    rng = random.Random(seed)

    trend_drift = {
        "random":  0.0,
        "bull":    0.005,
        "bear":   -0.005,
        "choppy":  0.0,
        "diverge": 0.001,
    }

    base_vol = {
        "random":  0.015,
        "bull":    0.015,
        "bear":    0.015,
        "choppy":  0.010,
        "diverge": 0.008,
    }

    drift = trend_drift.get(mode, 0.0)
    volatility = base_vol.get(mode, 0.015)

    price = 100.0
    start_price = price
    base_volume = 10_000
    start_date = datetime(2026, 1, 1)
    bars = []

    for i in range(n):
        # diverge: volatility grows linearly over time
        if mode == "diverge":
            bar_vol = volatility + 0.022 * (i / max(n - 1, 1))
        else:
            bar_vol = volatility

        # choppy: mean-reversion pull toward start_price
        bar_drift = drift
        if mode == "choppy":
            bar_drift += 0.12 * (start_price - price) / start_price

        # open: small gap from previous close (capped at ±1.5%)
        gap = rng.uniform(-0.015, 0.015)
        open_price = price * (1 + gap)

        # close: open + trend drift + gaussian noise
        move = rng.gauss(bar_drift, bar_vol)
        close_price = max(open_price * (1 + move), 0.01)

        # high / low: add upper and lower shadows
        body_hi = max(open_price, close_price)
        body_lo = min(open_price, close_price)
        upper = abs(rng.gauss(0, bar_vol * 0.4))
        lower = abs(rng.gauss(0, bar_vol * 0.4))
        high_price = body_hi * (1 + upper)
        low_price  = max(body_lo * (1 - lower), 0.01)

        # round to 2 decimal places
        o = round(open_price,  2)
        c = round(close_price, 2)
        h = round(high_price,  2)
        l = round(low_price,   2)

        # enforce OHLCV constraints after rounding
        h = max(h, o, c)
        l = min(l, o, c)
        l = max(l, 0.01)

        # volume: larger on bigger price moves
        move_pct = abs(c - o) / max(o, 0.01)
        volume = max(1, int(base_volume * (1 + move_pct * 8) * rng.uniform(0.7, 1.3)))

        bars.append({
            "date":   (start_date + timedelta(days=i)).strftime("%Y-%m-%d"),
            "open":   o,
            "high":   h,
            "low":    l,
            "close":  c,
            "volume": volume,
        })

        # use rounded close as base for next bar (ensures DAT-03 on stored values)
        price = c

    return bars
