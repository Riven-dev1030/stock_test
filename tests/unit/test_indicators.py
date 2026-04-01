"""
Unit tests for core/indicators.py
Covers acceptance criteria: IND-01, IND-02, IND-03, IND-04, IND-05, IND-06, IND-07
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from core.indicators import sma, atr, volume_ma, highest_high


# ---------------------------------------------------------------------------
# IND-01: SMA correctness — hand-calculated reference
# ---------------------------------------------------------------------------
class TestIND01:
    def test_sma3_on_5_bars(self):
        closes = [10.0, 20.0, 30.0, 40.0, 50.0]
        result = sma(closes, 3)
        # SMA(3): first two None, then 20, 30, 40
        assert result[0] is None
        assert result[1] is None
        assert abs(result[2] - 20.0) < 0.0001
        assert abs(result[3] - 30.0) < 0.0001
        assert abs(result[4] - 40.0) < 0.0001

    def test_sma_length_equals_input(self):
        closes = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert len(sma(closes, 3)) == len(closes)

    def test_sma1_equals_input(self):
        closes = [5.0, 10.0, 15.0]
        result = sma(closes, 1)
        for i, v in enumerate(closes):
            assert abs(result[i] - v) < 0.0001


# ---------------------------------------------------------------------------
# IND-02: ATR correctness — hand-calculated reference
# ---------------------------------------------------------------------------
class TestIND02:
    def _make_ohlcv(self, highs, lows, closes):
        """Build minimal OHLCV list from H/L/C arrays."""
        opens = closes[:]  # open == close for simplicity
        return [
            {"open": opens[i], "high": highs[i], "low": lows[i], "close": closes[i], "volume": 1000}
            for i in range(len(closes))
        ]

    def test_atr3_on_5_bars(self):
        # Bar0: H=12, L=8,  C=10
        # Bar1: H=15, L=9,  C=13  → TR = max(15-9, |15-10|, |9-10|)  = max(6,5,1) = 6
        # Bar2: H=14, L=10, C=12  → TR = max(14-10,|14-13|,|10-13|)  = max(4,1,3) = 4
        # Bar3: H=16, L=11, C=14  → TR = max(16-11,|16-12|,|11-12|)  = max(5,4,1) = 5
        # Bar4: H=13, L=9,  C=11  → TR = max(13-9, |13-14|,|9-14|)   = max(4,1,5) = 5
        highs  = [12, 15, 14, 16, 13]
        lows   = [ 8,  9, 10, 11,  9]
        closes = [10, 13, 12, 14, 11]
        ohlcv  = self._make_ohlcv(highs, lows, closes)

        result = atr(ohlcv, 3)

        assert result[0] is None
        assert result[1] is None
        assert result[2] is None
        # First ATR(3) at index 3: avg of TR[1], TR[2], TR[3] = (6+4+5)/3 = 5.0
        assert abs(result[3] - 5.0) < 0.0001
        # ATR[4] = (ATR[3]*(3-1) + TR[4]) / 3 = (5*2 + 5)/3 = 5.0
        assert abs(result[4] - 5.0) < 0.0001

    def test_atr_length_equals_input(self):
        ohlcv = [{"open": 10, "high": 12, "low": 9, "close": 11, "volume": 100}] * 10
        assert len(atr(ohlcv, 3)) == 10


# ---------------------------------------------------------------------------
# IND-03: volume_ma correctness
# ---------------------------------------------------------------------------
class TestIND03:
    def test_volume_ma3_on_5_bars(self):
        volumes = [100, 200, 300, 400, 500]
        result  = volume_ma(volumes, 3)
        assert result[0] is None
        assert result[1] is None
        assert abs(result[2] - 200.0) < 0.0001
        assert abs(result[3] - 300.0) < 0.0001
        assert abs(result[4] - 400.0) < 0.0001

    def test_volume_ma_length_equals_input(self):
        volumes = [1, 2, 3, 4, 5]
        assert len(volume_ma(volumes, 3)) == len(volumes)


# ---------------------------------------------------------------------------
# IND-04: highest_high correctness
# ---------------------------------------------------------------------------
class TestIND04:
    def test_highest_high5_on_10_bars(self):
        highs = [10, 12, 11, 15, 13, 14, 9, 16, 8, 17]
        result = highest_high(highs, 5)
        # First 4 are None
        for i in range(4):
            assert result[i] is None
        # index 4: max(10,12,11,15,13) = 15
        assert result[4] == 15
        # index 5: max(12,11,15,13,14) = 15
        assert result[5] == 15
        # index 7: max(13,14,9,16,8) — wait: index 7 window = [13,14,9,16,8]...
        # indices 3..7 = [15,13,14,9,16] → max=16
        assert result[7] == 16

    def test_highest_high_length_equals_input(self):
        highs = [1, 2, 3, 4, 5]
        assert len(highest_high(highs, 3)) == len(highs)


# ---------------------------------------------------------------------------
# IND-05: SMA(20) on only 10 bars → all None, no error
# ---------------------------------------------------------------------------
class TestIND05:
    def test_insufficient_data_returns_all_none(self):
        closes = [float(i) for i in range(1, 11)]  # 10 bars
        result = sma(closes, 20)
        assert len(result) == 10
        assert all(v is None for v in result)

    def test_atr_insufficient_data_returns_all_none(self):
        ohlcv = [{"open": 10, "high": 12, "low": 9, "close": 11, "volume": 100}] * 5
        result = atr(ohlcv, 20)
        assert len(result) == 5
        assert all(v is None for v in result)


# ---------------------------------------------------------------------------
# IND-06: Empty input → empty output, no error
# ---------------------------------------------------------------------------
class TestIND06:
    def test_sma_empty(self):
        assert sma([], 5) == []

    def test_atr_empty(self):
        assert atr([], 5) == []

    def test_volume_ma_empty(self):
        assert volume_ma([], 5) == []

    def test_highest_high_empty(self):
        assert highest_high([], 5) == []


# ---------------------------------------------------------------------------
# IND-07: Data with zero volume → indicators compute normally, no crash
# ---------------------------------------------------------------------------
class TestIND07:
    def test_zero_volume_does_not_crash(self):
        ohlcv = [
            {"open": 10, "high": 12, "low": 9, "close": 11, "volume": 0},
            {"open": 11, "high": 13, "low": 10, "close": 12, "volume": 0},
            {"open": 12, "high": 14, "low": 11, "close": 13, "volume": 0},
            {"open": 13, "high": 15, "low": 12, "close": 14, "volume": 0},
            {"open": 14, "high": 16, "low": 13, "close": 15, "volume": 0},
        ]
        volumes = [bar["volume"] for bar in ohlcv]
        closes  = [bar["close"] for bar in ohlcv]

        sma_result    = sma(closes, 3)
        atr_result    = atr(ohlcv, 3)
        vma_result    = volume_ma(volumes, 3)

        # Should not raise and should return same-length lists
        assert len(sma_result) == 5
        assert len(atr_result) == 5
        assert len(vma_result) == 5

        # volume_ma of all-zeros should be 0 (not crash due to division-by-zero)
        assert vma_result[2] == 0.0
        assert vma_result[3] == 0.0
        assert vma_result[4] == 0.0
