"""
Unit tests for core/pattern.py
Covers basic correctness of all five built-in candlestick patterns.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from core.pattern import hammer, engulfing, doji, morning_star, volume_surge_candle


def _bar(o, h, l, c, v=10000):
    return {"open": o, "high": h, "low": l, "close": c, "volume": v}


# ---------------------------------------------------------------------------
# Hammer
# ---------------------------------------------------------------------------
class TestHammer:
    def test_detects_hammer(self):
        # body=1 (10→11), lower_shadow=8 (2→10), upper_shadow=0.1 (11→11.1)
        bar = _bar(o=10, h=11.1, l=2, c=11)
        result = hammer([bar], 0)
        assert result["detected"] is True
        assert result["pattern"] == "hammer"
        assert result["confidence"] > 0

    def test_rejects_normal_bar(self):
        # balanced candle — not a hammer
        bar = _bar(o=10, h=15, l=8, c=14)
        result = hammer([bar], 0)
        assert result["detected"] is False

    def test_out_of_range_returns_false(self):
        result = hammer([], 0)
        assert result["detected"] is False


# ---------------------------------------------------------------------------
# Engulfing
# ---------------------------------------------------------------------------
class TestEngulfing:
    def test_bullish_engulfing(self):
        prev = _bar(o=12, h=13, l=9,  c=10)   # bearish: open=12, close=10
        curr = _bar(o=9,  h=14, l=8,  c=13)   # bullish: open=9, close=13, covers prev
        result = engulfing([prev, curr], 1)
        assert result["detected"] is True
        assert result["pattern"] == "engulfing_bullish"

    def test_bearish_engulfing(self):
        prev = _bar(o=10, h=14, l=9,  c=13)   # bullish
        curr = _bar(o=14, h=15, l=8,  c=9)    # bearish, covers prev
        result = engulfing([prev, curr], 1)
        assert result["detected"] is True
        assert result["pattern"] == "engulfing_bearish"

    def test_same_direction_not_engulfing(self):
        prev = _bar(o=10, h=14, l=9, c=13)    # bullish
        curr = _bar(o=9,  h=15, l=8, c=14)    # also bullish — same direction
        result = engulfing([prev, curr], 1)
        assert result["detected"] is False

    def test_insufficient_bars(self):
        bar = _bar(o=10, h=12, l=9, c=11)
        result = engulfing([bar], 0)
        assert result["detected"] is False


# ---------------------------------------------------------------------------
# Doji
# ---------------------------------------------------------------------------
class TestDoji:
    def test_detects_doji(self):
        # body=0.05, total=5 → ratio=0.01 < 0.15
        bar = _bar(o=10.0, h=12.5, l=7.5, c=10.05)
        result = doji([bar], 0)
        assert result["detected"] is True
        assert result["pattern"] == "doji"

    def test_rejects_large_body(self):
        # body=4, total=5 → ratio=0.8 > 0.15
        bar = _bar(o=10, h=12, l=7, c=14)
        result = doji([bar], 0)
        assert result["detected"] is False

    def test_zero_range_is_doji(self):
        bar = _bar(o=10, h=10, l=10, c=10)
        result = doji([bar], 0)
        assert result["detected"] is True


# ---------------------------------------------------------------------------
# Morning Star
# ---------------------------------------------------------------------------
class TestMorningStar:
    def test_detects_morning_star(self):
        # bar1: long bearish (body/range > 0.5)
        bar1 = _bar(o=20, h=21, l=10, c=11)   # body=9, range=11 → 0.82
        # bar2: small body
        bar2 = _bar(o=10.5, h=11, l=9, c=10.6)  # body=0.1, range=2 → 0.05
        # bar3: long bullish
        bar3 = _bar(o=11, h=21, l=10, c=20)   # body=9, range=11 → 0.82
        result = morning_star([bar1, bar2, bar3], 2)
        assert result["detected"] is True
        assert result["pattern"] == "morning_star"

    def test_insufficient_bars(self):
        bar = _bar(o=10, h=12, l=9, c=11)
        result = morning_star([bar, bar], 1)
        assert result["detected"] is False


# ---------------------------------------------------------------------------
# Volume Surge Candle
# ---------------------------------------------------------------------------
class TestVolumeSurgeCandle:
    def _make_ohlcv_with_vma(self, body_ratio=0.7, vol_ratio=2.0):
        """Return (ohlcv list, vol_ma list) where bar at index 0 has desired ratios."""
        total = 10.0
        body  = total * body_ratio
        bar   = _bar(o=100, h=100 + total, l=100, c=100 + body, v=int(1000 * vol_ratio))
        vma   = [1000.0]
        return [bar], vma

    def test_detects_bullish_surge(self):
        ohlcv, vma = self._make_ohlcv_with_vma(body_ratio=0.75, vol_ratio=2.0)
        result = volume_surge_candle(ohlcv, 0, vma)
        assert result["detected"] is True
        assert result["pattern"] == "volume_surge_bullish"

    def test_rejects_low_volume(self):
        ohlcv, _ = self._make_ohlcv_with_vma(body_ratio=0.75, vol_ratio=1.2)
        vma = [1000.0]
        result = volume_surge_candle(ohlcv, 0, vma)
        assert result["detected"] is False

    def test_rejects_small_body(self):
        ohlcv, _ = self._make_ohlcv_with_vma(body_ratio=0.3, vol_ratio=2.5)
        vma = [1000.0]
        result = volume_surge_candle(ohlcv, 0, vma)
        assert result["detected"] is False

    def test_no_vma_returns_false(self):
        bar = _bar(o=100, h=110, l=100, c=108, v=20000)
        result = volume_surge_candle([bar], 0, [None])
        assert result["detected"] is False
