"""
core/indicators.py — Pure-function technical indicators.

All functions accept plain Python lists and return plain Python lists.
Positions without enough data are filled with None.
No third-party dependencies.
"""


def sma(closes: list, period: int) -> list:
    """
    Simple Moving Average.

    Args:
        closes: List of closing prices (float).
        period: Lookback period.

    Returns:
        List of the same length; first (period-1) values are None.
    """
    if not closes:
        return []
    result = [None] * len(closes)
    for i in range(period - 1, len(closes)):
        result[i] = sum(closes[i - period + 1: i + 1]) / period
    return result


def atr(ohlcv: list, period: int) -> list:
    """
    Average True Range (Wilder's smoothing).

    Args:
        ohlcv: List of OHLCV dicts with keys high, low, close.
        period: Lookback period.

    Returns:
        List of the same length; first (period-1) values are None.
        Index 0 is always None (no previous close for TR calculation).
    """
    if not ohlcv:
        return []

    n = len(ohlcv)
    tr_values = [None] * n

    for i in range(1, n):
        high  = ohlcv[i]["high"]
        low   = ohlcv[i]["low"]
        prev_close = ohlcv[i - 1]["close"]
        tr_values[i] = max(
            high - low,
            abs(high - prev_close),
            abs(low  - prev_close),
        )

    result = [None] * n
    # Need period TR values starting from index 1, so first ATR at index period
    if n <= period:
        return result

    # First ATR: simple average of first `period` TR values (indices 1..period)
    first_sum = sum(tr_values[1: period + 1])
    result[period] = first_sum / period

    # Subsequent ATR: Wilder's smoothing
    for i in range(period + 1, n):
        result[i] = (result[i - 1] * (period - 1) + tr_values[i]) / period

    return result


def volume_ma(volumes: list, period: int) -> list:
    """
    Volume Moving Average (simple).

    Args:
        volumes: List of volume values (int or float).
        period:  Lookback period.

    Returns:
        List of the same length; first (period-1) values are None.
    """
    if not volumes:
        return []
    result = [None] * len(volumes)
    for i in range(period - 1, len(volumes)):
        result[i] = sum(volumes[i - period + 1: i + 1]) / period
    return result


def highest_high(highs: list, period: int) -> list:
    """
    Highest high over the last N bars (inclusive of current bar).

    Args:
        highs:  List of high prices.
        period: Lookback period.

    Returns:
        List of the same length; first (period-1) values are None.
    """
    if not highs:
        return []
    result = [None] * len(highs)
    for i in range(period - 1, len(highs)):
        result[i] = max(highs[i - period + 1: i + 1])
    return result


def lowest_low(lows: list, period: int) -> list:
    """
    Lowest low over the last N bars (inclusive of current bar).

    Args:
        lows:   List of low prices.
        period: Lookback period.

    Returns:
        List of the same length; first (period-1) values are None.
    """
    if not lows:
        return []
    result = [None] * len(lows)
    for i in range(period - 1, len(lows)):
        result[i] = min(lows[i - period + 1: i + 1])
    return result
