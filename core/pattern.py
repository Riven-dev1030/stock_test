"""
core/pattern.py — Candlestick pattern recognition.

All functions are pure: they accept an OHLCV list and a current index,
and return a result dict. No side effects, no third-party dependencies.
"""


def _body(bar: dict) -> float:
    return abs(bar["close"] - bar["open"])


def _total_range(bar: dict) -> float:
    return bar["high"] - bar["low"]


def _upper_shadow(bar: dict) -> float:
    return bar["high"] - max(bar["open"], bar["close"])


def _lower_shadow(bar: dict) -> float:
    return min(bar["open"], bar["close"]) - bar["low"]


def _is_bullish(bar: dict) -> bool:
    return bar["close"] >= bar["open"]


def _result(detected: bool, pattern: str, confidence: float, detail: str) -> dict:
    return {
        "detected":    detected,
        "pattern":     pattern if detected else None,
        "confidence":  confidence if detected else 0.0,
        "detail":      detail,
    }


# ---------------------------------------------------------------------------
# Hammer (錘子線)
# ---------------------------------------------------------------------------
def hammer(ohlcv: list, index: int) -> dict:
    """
    Hammer: lower shadow > 2× body, upper shadow < 0.3× body.
    Requires 1 bar.
    """
    pattern = "hammer"
    if index < 0 or index >= len(ohlcv):
        return _result(False, pattern, 0.0, "index out of range")

    bar   = ohlcv[index]
    body  = _body(bar)
    lo_sh = _lower_shadow(bar)
    up_sh = _upper_shadow(bar)
    total = _total_range(bar)

    if total == 0:
        return _result(False, pattern, 0.0, "zero-range bar")

    if body == 0:
        return _result(False, pattern, 0.0, "doji — no body for hammer")

    if lo_sh > 2 * body and up_sh < 0.3 * body:
        conf = min(1.0, lo_sh / (2 * body) * 0.7)
        return _result(True, pattern, round(conf, 2),
                       f"lower_shadow={lo_sh:.4f} > 2×body={2*body:.4f}, "
                       f"upper_shadow={up_sh:.4f} < 0.3×body={0.3*body:.4f}")

    return _result(False, pattern, 0.0,
                   f"lower_shadow={lo_sh:.4f}, body={body:.4f}, upper_shadow={up_sh:.4f}")


# ---------------------------------------------------------------------------
# Engulfing (吞噬)
# ---------------------------------------------------------------------------
def engulfing(ohlcv: list, index: int) -> dict:
    """
    Bullish/Bearish Engulfing: current body fully covers previous body,
    with opposite direction.
    Requires 2 bars.
    """
    if index < 1 or index >= len(ohlcv):
        return _result(False, "engulfing", 0.0, "insufficient bars")

    prev = ohlcv[index - 1]
    curr = ohlcv[index]

    prev_body_hi = max(prev["open"], prev["close"])
    prev_body_lo = min(prev["open"], prev["close"])
    curr_body_hi = max(curr["open"], curr["close"])
    curr_body_lo = min(curr["open"], curr["close"])

    covers  = curr_body_hi > prev_body_hi and curr_body_lo < prev_body_lo
    opposite = _is_bullish(curr) != _is_bullish(prev)

    if covers and opposite:
        pname = "engulfing_bullish" if _is_bullish(curr) else "engulfing_bearish"
        return _result(True, pname, 0.85,
                       f"bar[{index}] body [{curr_body_lo:.2f},{curr_body_hi:.2f}] "
                       f"fully covers bar[{index-1}] [{prev_body_lo:.2f},{prev_body_hi:.2f}], "
                       f"{'bullish' if _is_bullish(curr) else 'bearish'} reversal")

    return _result(False, "engulfing", 0.0,
                   f"covers={covers}, opposite_direction={opposite}")


# ---------------------------------------------------------------------------
# Doji (十字星)
# ---------------------------------------------------------------------------
def doji(ohlcv: list, index: int) -> dict:
    """
    Doji: body < 15% of total range.
    Requires 1 bar.
    """
    pattern = "doji"
    if index < 0 or index >= len(ohlcv):
        return _result(False, pattern, 0.0, "index out of range")

    bar   = ohlcv[index]
    body  = _body(bar)
    total = _total_range(bar)

    if total == 0:
        return _result(True, pattern, 1.0, "zero-range bar is a perfect doji")

    ratio = body / total
    if ratio < 0.15:
        conf = round(1.0 - ratio / 0.15, 2)
        return _result(True, pattern, conf,
                       f"body/range={ratio:.3f} < 0.15")

    return _result(False, pattern, 0.0,
                   f"body/range={ratio:.3f} >= 0.15")


# ---------------------------------------------------------------------------
# Morning Star (晨星)
# ---------------------------------------------------------------------------
def morning_star(ohlcv: list, index: int) -> dict:
    """
    Morning Star: long bearish bar + small body (with gap) + long bullish bar.
    Requires 3 bars (index-2, index-1, index).
    """
    pattern = "morning_star"
    if index < 2 or index >= len(ohlcv):
        return _result(False, pattern, 0.0, "insufficient bars")

    bar1 = ohlcv[index - 2]  # long bearish
    bar2 = ohlcv[index - 1]  # small body
    bar3 = ohlcv[index]      # long bullish

    total1 = _total_range(bar1)
    total3 = _total_range(bar3)

    if total1 == 0 or total3 == 0:
        return _result(False, pattern, 0.0, "zero-range bar")

    long_bearish = not _is_bullish(bar1) and _body(bar1) / total1 > 0.5
    small_body   = _total_range(bar2) == 0 or _body(bar2) / _total_range(bar2) < 0.3
    long_bullish = _is_bullish(bar3) and _body(bar3) / total3 > 0.5

    if long_bearish and small_body and long_bullish:
        return _result(True, pattern, 0.80,
                       f"long_bearish={long_bearish}, small_middle={small_body}, "
                       f"long_bullish={long_bullish}")

    return _result(False, pattern, 0.0,
                   f"long_bearish={long_bearish}, small_middle={small_body}, "
                   f"long_bullish={long_bullish}")


# ---------------------------------------------------------------------------
# Volume Surge Candle (放量長紅 / 長黑)
# ---------------------------------------------------------------------------
def volume_surge_candle(ohlcv: list, index: int, vol_ma_values: list) -> dict:
    """
    Volume Surge Candle: body > 60% of total range AND volume > 1.5× volume MA.

    Args:
        ohlcv:         OHLCV list.
        index:         Current bar index.
        vol_ma_values: Pre-computed volume MA array (same length as ohlcv).

    Returns:
        Result dict with pattern = "volume_surge_bullish" or "volume_surge_bearish".
    """
    if index < 0 or index >= len(ohlcv):
        return _result(False, "volume_surge", 0.0, "index out of range")

    bar    = ohlcv[index]
    total  = _total_range(bar)
    vma    = vol_ma_values[index] if index < len(vol_ma_values) else None

    if total == 0:
        return _result(False, "volume_surge", 0.0, "zero-range bar")
    if vma is None:
        return _result(False, "volume_surge", 0.0, "volume MA not available at this index")

    body_ratio  = _body(bar) / total
    vol_ratio   = bar["volume"] / vma if vma > 0 else 0

    if body_ratio > 0.6 and vol_ratio > 1.5:
        pname = "volume_surge_bullish" if _is_bullish(bar) else "volume_surge_bearish"
        return _result(True, pname, round(min(1.0, vol_ratio / 3), 2),
                       f"body/range={body_ratio:.2f}>0.6, "
                       f"vol={bar['volume']} > 1.5×vma={vma:.0f} (ratio={vol_ratio:.2f})")

    return _result(False, "volume_surge", 0.0,
                   f"body/range={body_ratio:.2f}, vol_ratio={vol_ratio:.2f}")
