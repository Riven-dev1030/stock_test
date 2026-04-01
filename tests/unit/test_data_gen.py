"""
Unit tests for core/data_gen.py
Covers acceptance criteria: DAT-01, DAT-02, DAT-03, DAT-04, DAT-05
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from core.data_gen import generate

REQUIRED_FIELDS = {"date", "open", "high", "low", "close", "volume"}


# ---------------------------------------------------------------------------
# DAT-01: generate(n=200, mode="random") returns list of 200 bars with correct fields
# ---------------------------------------------------------------------------
class TestDAT01:
    def test_length(self):
        bars = generate(n=200, mode="random")
        assert len(bars) == 200

    def test_fields_present(self):
        bars = generate(n=200, mode="random")
        for bar in bars:
            assert REQUIRED_FIELDS.issubset(bar.keys()), \
                f"Missing fields in bar: {bar}"

    def test_various_lengths(self):
        for n in [1, 50, 100, 200]:
            bars = generate(n=n, mode="random")
            assert len(bars) == n


# ---------------------------------------------------------------------------
# DAT-02: low <= open <= high  AND  low <= close <= high  for every bar
# ---------------------------------------------------------------------------
class TestDAT02:
    @pytest.mark.parametrize("mode", ["random", "bull", "bear", "choppy", "diverge"])
    def test_ohlcv_relationship(self, mode):
        bars = generate(n=200, mode=mode, seed=42)
        for i, bar in enumerate(bars):
            assert bar["low"] <= bar["open"] <= bar["high"], \
                f"[{mode}] bar {i}: open={bar['open']} not in [{bar['low']}, {bar['high']}]"
            assert bar["low"] <= bar["close"] <= bar["high"], \
                f"[{mode}] bar {i}: close={bar['close']} not in [{bar['low']}, {bar['high']}]"


# ---------------------------------------------------------------------------
# DAT-03: |open[i] - close[i-1]| <= close[i-1] * 0.10
# ---------------------------------------------------------------------------
class TestDAT03:
    @pytest.mark.parametrize("mode", ["random", "bull", "bear", "choppy", "diverge"])
    def test_continuity(self, mode):
        bars = generate(n=200, mode=mode, seed=42)
        for i in range(1, len(bars)):
            prev_close = bars[i - 1]["close"]
            curr_open  = bars[i]["open"]
            diff = abs(curr_open - prev_close)
            limit = prev_close * 0.10
            assert diff <= limit, (
                f"[{mode}] bar {i}: open {curr_open} deviates {diff:.4f} "
                f"from prev close {prev_close} (limit {limit:.4f})"
            )


# ---------------------------------------------------------------------------
# DAT-04: mode-specific trend direction (P1)
# ---------------------------------------------------------------------------
class TestDAT04:
    def test_bull_final_above_first(self):
        bars = generate(n=200, mode="bull", seed=42)
        assert bars[-1]["close"] > bars[0]["close"], \
            f"bull: final {bars[-1]['close']} not > first {bars[0]['close']}"

    def test_bear_final_below_first(self):
        bars = generate(n=200, mode="bear", seed=42)
        assert bars[-1]["close"] < bars[0]["close"], \
            f"bear: final {bars[-1]['close']} not < first {bars[0]['close']}"

    def test_choppy_within_10_percent(self):
        bars = generate(n=200, mode="choppy", seed=42)
        first = bars[0]["close"]
        last  = bars[-1]["close"]
        diff_pct = abs(last - first) / first
        assert diff_pct <= 0.10, \
            f"choppy: first={first}, last={last}, diff={diff_pct:.2%} > 10%"


# ---------------------------------------------------------------------------
# DAT-05: volume is a positive integer
# ---------------------------------------------------------------------------
class TestDAT05:
    @pytest.mark.parametrize("mode", ["random", "bull", "bear", "choppy", "diverge"])
    def test_volume_positive_integer(self, mode):
        bars = generate(n=200, mode=mode, seed=42)
        for i, bar in enumerate(bars):
            assert isinstance(bar["volume"], int), \
                f"[{mode}] bar {i}: volume is not int (got {type(bar['volume'])})"
            assert bar["volume"] > 0, \
                f"[{mode}] bar {i}: volume={bar['volume']} is not positive"
