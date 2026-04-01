"""
Unit tests for core/strategy.py
Covers acceptance criteria: STR-01~11
"""
import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from core.strategy import (
    validate_strategy, load_strategy,
    check_breakout, check_volume_above_ma, check_ma_alignment,
    check_trailing_stop, check_atr_stop,
    compute_indicators, evaluate_entry, evaluate_exit,
    get_warmup_period,
)
from core.data_gen import generate


# ---------------------------------------------------------------------------
# STR-01: Load example strategy config from SDD
# ---------------------------------------------------------------------------
class TestSTR01:
    def test_load_example_config(self, tmp_path):
        config_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "config", "strategy_config.json"
        )
        config = load_strategy(config_path)
        assert config["name"] == "Trend Following Breakout v1"
        assert len(config["entry"]["conditions"]) == 4
        assert len(config["exit"]["conditions"])  == 3

    def test_validate_parses_entry_and_exit(self):
        config = {
            "name": "test",
            "entry": {"mode": "ALL", "conditions": [
                {"type": "breakout", "params": {"period": 20, "field": "high"}}
            ]},
            "exit": {"mode": "ANY", "conditions": [
                {"type": "atr_stop", "params": {"multiplier": 3, "period": 14}}
            ]},
        }
        validate_strategy(config)  # should not raise


# ---------------------------------------------------------------------------
# STR-02: Missing required field raises clear validation error
# ---------------------------------------------------------------------------
class TestSTR02:
    def test_missing_exit_raises(self):
        config = {
            "name": "incomplete",
            "entry": {"mode": "ALL", "conditions": []},
        }
        with pytest.raises(ValueError, match="exit"):
            validate_strategy(config)

    def test_missing_name_raises(self):
        config = {
            "entry": {"mode": "ALL", "conditions": []},
            "exit":  {"mode": "ANY", "conditions": []},
        }
        with pytest.raises(ValueError, match="name"):
            validate_strategy(config)


# ---------------------------------------------------------------------------
# STR-03: Unknown condition type raises clear error
# ---------------------------------------------------------------------------
class TestSTR03:
    def test_unknown_condition_type(self):
        config = {
            "name": "bad",
            "entry": {"mode": "ALL", "conditions": [
                {"type": "alien_signal", "params": {}}
            ]},
            "exit": {"mode": "ANY", "conditions": []},
        }
        with pytest.raises(ValueError, match="alien_signal"):
            validate_strategy(config)


# ---------------------------------------------------------------------------
# STR-04: breakout.check() triggers on bar 24 (0-indexed) only
# ---------------------------------------------------------------------------
class TestSTR04:
    def _make_flat_then_breakout(self, breakout_index=24, period=20):
        """
        Generate OHLCV where close[i] = 100 for i < breakout_index,
        then close[breakout_index] = 150 (clearly above highest_high of prev 20).
        """
        bars = []
        base_date_offset = 0
        from datetime import datetime, timedelta
        start = datetime(2026, 1, 1)
        for i in range(breakout_index + 5):
            close = 100.0 if i < breakout_index else 150.0
            bars.append({
                "date":   (start + timedelta(days=i)).strftime("%Y-%m-%d"),
                "open":   close,
                "high":   close + 1,
                "low":    close - 1,
                "close":  close,
                "volume": 10000,
            })
        return bars

    def test_breakout_triggers_at_correct_bar(self):
        period = 20
        breakout_idx = 24
        ohlcv = self._make_flat_then_breakout(breakout_idx, period)

        from core.indicators import highest_high
        highs   = [b["high"] for b in ohlcv]
        hh_vals = highest_high(highs, period)
        ind     = {f"highest_high_{period}": hh_vals}
        params  = {"period": period, "field": "high"}

        # Before breakout: should be False
        result_before = check_breakout(ohlcv, breakout_idx - 1, ind, params)
        assert result_before["result"] is False

        # At breakout: should be True
        result_at = check_breakout(ohlcv, breakout_idx, ind, params)
        assert result_at["result"] is True

        # After breakout: hh_vals[breakout_idx] now includes the high of the breakout bar (151),
        # so close=150 at breakout_idx+1 is <= 151 → no longer a breakout (False)
        result_after = check_breakout(ohlcv, breakout_idx + 1, ind, params)
        assert result_after["result"] is False


# ---------------------------------------------------------------------------
# STR-05: volume_above_ma boundary — volume == 1.5× MA → True (inclusive)
# ---------------------------------------------------------------------------
class TestSTR05:
    def test_volume_exactly_1_5x_returns_true(self):
        vma = 1000.0
        vol = int(vma * 1.5)  # exactly 1500
        period = 3
        # Build 5 bars where last volume = vol, previous = vma (roughly)
        ohlcv = [
            {"open": 10, "high": 11, "low": 9, "close": 10, "volume": 1000}
        ] * 4 + [
            {"open": 10, "high": 11, "low": 9, "close": 10, "volume": vol}
        ]
        from core.indicators import volume_ma
        vma_arr = volume_ma([b["volume"] for b in ohlcv], period)
        ind     = {f"volume_ma_{period}": vma_arr}
        params  = {"multiplier": 1.5, "period": period}
        result  = check_volume_above_ma(ohlcv, 4, ind, params)
        # vol(1500) >= vma_arr[4] * 1.5 — volume_ma at 4 may differ; test boundary logic
        # We test that the >= condition is used (inclusive)
        ind2    = {f"volume_ma_{period}": [vma] * 5}
        result2 = check_volume_above_ma(ohlcv, 4, ind2, params)
        assert result2["result"] is True  # 1500 >= 1000*1.5 = 1500 → True


# ---------------------------------------------------------------------------
# STR-06/07: ma_alignment.check()
# ---------------------------------------------------------------------------
class TestSTR0607:
    def test_ma_alignment_bullish_true(self):
        # MA20 > MA50
        ind    = {"sma_20": [None] * 50 + [110.0], "sma_50": [None] * 50 + [100.0]}
        params = {"fast": 20, "slow": 50, "direction": "bullish"}
        result = check_ma_alignment([], 50, ind, params)
        assert result["result"] is True

    def test_ma_alignment_bullish_false(self):
        # MA20 < MA50
        ind    = {"sma_20": [None] * 50 + [90.0], "sma_50": [None] * 50 + [100.0]}
        params = {"fast": 20, "slow": 50, "direction": "bullish"}
        result = check_ma_alignment([], 50, ind, params)
        assert result["result"] is False


# ---------------------------------------------------------------------------
# STR-08: trailing_stop activates at 15% gain, triggers at peak * 0.97
# ---------------------------------------------------------------------------
class TestSTR08:
    def test_trailing_stop_triggers_on_pullback(self):
        entry  = 100.0
        peak   = 116.0   # 16% gain from entry → activation_pct=15 reached
        curr   = peak * 0.96  # 96% of peak = below trail_pct=97 → trigger
        params = {"activation_pct": 15, "trail_pct": 97}
        pos    = {"entry_price": entry, "peak_price": peak}
        bar    = {"open": curr, "high": curr, "low": curr, "close": curr, "volume": 1}
        result = check_trailing_stop([bar], 0, {}, params, pos)
        assert result["triggered"] is True
        assert result["active"] is True

    def test_trailing_stop_not_triggered_before_activation(self):
        entry  = 100.0
        peak   = 110.0   # only 10% gain → below 15% activation
        curr   = 105.0
        params = {"activation_pct": 15, "trail_pct": 97}
        pos    = {"entry_price": entry, "peak_price": peak}
        bar    = {"open": curr, "high": curr, "low": curr, "close": curr, "volume": 1}
        result = check_trailing_stop([bar], 0, {}, params, pos)
        assert result["triggered"] is False
        assert result["active"] is False


# ---------------------------------------------------------------------------
# STR-09: (already covered in STR-08 second test)
# STR-10: atr_stop triggers when price <= entry - 3*ATR
# ---------------------------------------------------------------------------
class TestSTR10:
    def test_atr_stop_triggers(self):
        entry   = 100.0
        atr_val = 2.0
        # stop = 100 - 3*2 = 94; current = 93 → trigger
        current = 93.0
        ind     = {"atr_14": [None] * 5 + [atr_val]}
        pos     = {"entry_price": entry, "peak_price": entry}
        bar     = {"open": current, "high": current, "low": current,
                   "close": current, "volume": 1}
        params  = {"multiplier": 3, "period": 14}
        ohlcv   = [bar] * 6
        result  = check_atr_stop(ohlcv, 5, ind, params, pos)
        assert result["triggered"] is True
        assert abs(result["stop_price"] - 94.0) < 0.001


# ---------------------------------------------------------------------------
# STR-11: Custom condition interface (P1)
# ---------------------------------------------------------------------------
class TestSTR11:
    def test_custom_condition_is_called(self):
        called = []

        class EvenCloseCondition:
            def __init__(self, params):
                self.params = params
            def check(self, data, index, position=None):
                called.append(index)
                return int(data[index]["close"]) % 2 == 0

        config = {
            "name": "custom_test",
            "entry": {"mode": "ANY", "conditions": [
                {"type": "even_close", "params": {}}
            ]},
            "exit": {"mode": "ANY", "conditions": [
                {"type": "atr_stop", "params": {"multiplier": 3, "period": 14}}
            ]},
        }
        ohlcv  = [{"open": 10, "high": 11, "low": 9, "close": 10, "volume": 1}]
        ind    = {}
        custom = {"even_close": EvenCloseCondition({})}
        result = evaluate_entry(ohlcv, 0, ind, config, custom)
        assert len(called) == 1
        assert result["triggered"] is True
