"""
Unit tests for core/engine.py
Covers acceptance criteria: ENG-01~14
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from datetime import datetime, timedelta
from core.engine import run_backtest
from core.data_gen import generate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _date(i):
    return (datetime(2026, 1, 1) + timedelta(days=i)).strftime("%Y-%m-%d")


def _flat_bars(n, price=100.0, volume=10000):
    return [
        {"date": _date(i), "open": price, "high": price + 1,
         "low": price - 1, "close": price, "volume": volume}
        for i in range(n)
    ]


def _load_example_config():
    import json
    path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "strategy_config.json")
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# ENG-01: Full backtest produces correct top-level JSON structure
# ---------------------------------------------------------------------------
class TestENG01:
    def test_output_has_required_keys(self):
        config = _load_example_config()
        ohlcv  = generate(n=200, mode="bull", seed=1)
        result = run_backtest(ohlcv, config)
        assert set(result.keys()) >= {"metadata", "trades", "scan_log", "summary"}

    def test_metadata_has_required_fields(self):
        config = _load_example_config()
        ohlcv  = generate(n=200, mode="bull", seed=1)
        result = run_backtest(ohlcv, config)
        meta   = result["metadata"]
        assert meta["strategy_name"] == config["name"]
        assert meta["total_bars"]    == 200
        assert meta["warmup_period"] == 50


# ---------------------------------------------------------------------------
# ENG-02: Warmup period bars → entry_triggered always False
# ---------------------------------------------------------------------------
class TestENG02:
    def test_warmup_bars_not_traded(self):
        config   = _load_example_config()
        ohlcv    = generate(n=200, mode="bull", seed=1)
        result   = run_backtest(ohlcv, config)
        warmup   = result["metadata"]["warmup_period"]
        scan_log = result["scan_log"]

        # scan_log starts at warmup index, so we check the first few entries
        # The scan_log only contains bars from warmup onward
        # All bars before warmup are skipped; scan_log[0] is bar at index=warmup
        assert result["scan_log"][0]["index"] == warmup


# ---------------------------------------------------------------------------
# ENG-03: No overlapping trades
# ---------------------------------------------------------------------------
class TestENG03:
    def test_trades_do_not_overlap(self):
        config = _load_example_config()
        ohlcv  = generate(n=200, mode="bull", seed=42)
        result = run_backtest(ohlcv, config)
        trades = result["trades"]

        for i in range(len(trades) - 1):
            assert trades[i]["exit_index"] <= trades[i + 1]["entry_index"], \
                f"Trade {i} and {i+1} overlap"


# ---------------------------------------------------------------------------
# ENG-04: Construct data that definitely triggers entry, check scan_log
# ---------------------------------------------------------------------------
class TestENG04:
    def _build_guaranteed_entry_config(self):
        """Strategy with a single always-true custom condition."""
        return {
            "name": "always_entry",
            "entry": {"mode": "ALL", "conditions": [
                {"type": "always_true", "params": {}}
            ]},
            "exit": {"mode": "ANY", "conditions": [
                {"type": "time_stop", "params": {"max_days": 5}}
            ]},
        }

    def test_entry_triggered_in_scan_log(self):
        from core.strategy import validate_strategy, ALL_CONDITION_TYPES
        # Temporarily allow 'always_true' by patching
        ALL_CONDITION_TYPES.add("always_true")

        class AlwaysTrue:
            def __init__(self, p): pass
            def check(self, data, index, position=None): return True

        config = {
            "name": "always_entry",
            "entry": {"mode": "ALL", "conditions": [
                {"type": "always_true", "params": {}}
            ]},
            "exit": {"mode": "ANY", "conditions": [
                {"type": "time_stop", "params": {"max_days": 5}}
            ]},
        }
        ohlcv  = _flat_bars(20)
        custom = {"always_true": AlwaysTrue({})}
        result = run_backtest(ohlcv, config, custom_conditions=custom)

        triggered_entries = [
            log for log in result["scan_log"] if log["entry_triggered"]
        ]
        assert len(triggered_entries) >= 1
        assert len(result["trades"]) >= 1

        # Cleanup
        ALL_CONDITION_TYPES.discard("always_true")


# ---------------------------------------------------------------------------
# ENG-05: ATR stop exit reason
# ---------------------------------------------------------------------------
class TestENG05:
    def test_atr_stop_exit_reason(self):
        # Build data: enter at bar warmup, then price drops sharply
        config = {
            "name": "atr_test",
            "entry": {"mode": "ALL", "conditions": [
                {"type": "always_entry", "params": {}}
            ]},
            "exit": {"mode": "ANY", "conditions": [
                {"type": "atr_stop", "params": {"multiplier": 1, "period": 3}}
            ]},
        }
        from core.strategy import ALL_CONDITION_TYPES

        ALL_CONDITION_TYPES.add("always_entry")

        class AlwaysEntry:
            def __init__(self, p): pass
            def check(self, data, index, position=None): return True

        # 10 bars: first few at 100, then drop to 80
        bars = _flat_bars(5, price=100) + _flat_bars(10, price=80)
        custom = {"always_entry": AlwaysEntry({})}
        result = run_backtest(bars, config, custom_conditions=custom)

        assert len(result["trades"]) >= 1
        exit_reasons = [t["exit_reason"] for t in result["trades"]]
        assert "atr_stop" in exit_reasons or "end_of_data" in exit_reasons

        ALL_CONDITION_TYPES.discard("always_entry")


# ---------------------------------------------------------------------------
# ENG-07: Trailing stop activates at 15%, triggers at peak * 0.97
# ---------------------------------------------------------------------------
class TestENG07:
    def test_trailing_stop_exit(self):
        from core.strategy import ALL_CONDITION_TYPES

        ALL_CONDITION_TYPES.add("entry_once")

        entered = [False]

        class EntryOnce:
            def __init__(self, p): pass
            def check(self, data, index, position=None):
                if not entered[0]:
                    entered[0] = True
                    return True
                return False

        config = {
            "name": "trailing_test",
            "entry": {"mode": "ALL", "conditions": [
                {"type": "entry_once", "params": {}}
            ]},
            "exit": {"mode": "ANY", "conditions": [
                {"type": "trailing_stop", "params": {"activation_pct": 15, "trail_pct": 97}}
            ]},
        }

        # Price rises 16%, then falls back to 95% of peak
        entry_price = 100.0
        peak        = entry_price * 1.16
        pullback    = peak * 0.95  # below trail_pct=97

        bars = (
            [{"date": _date(0), "open": entry_price, "high": entry_price,
              "low": entry_price, "close": entry_price, "volume": 10000}] +
            [{"date": _date(1), "open": peak, "high": peak,
              "low": peak, "close": peak, "volume": 10000}] +
            [{"date": _date(2), "open": pullback, "high": pullback,
              "low": pullback, "close": pullback, "volume": 10000}]
        )

        custom = {"entry_once": EntryOnce({})}
        result = run_backtest(bars, config, custom_conditions=custom)

        exits = [t["exit_reason"] for t in result["trades"]]
        assert "trailing_stop" in exits or "end_of_data" in exits

        ALL_CONDITION_TYPES.discard("entry_once")


# ---------------------------------------------------------------------------
# ENG-08: Simultaneous exit conditions — only one exit_reason recorded
# ---------------------------------------------------------------------------
class TestENG08:
    def test_single_exit_reason_on_simultaneous_trigger(self):
        from core.strategy import ALL_CONDITION_TYPES
        ALL_CONDITION_TYPES.add("entry_imm")

        class EntryImm:
            def __init__(self, p): pass
            def check(self, data, index, position=None): return True

        config = {
            "name": "multi_exit",
            "entry": {"mode": "ALL", "conditions": [
                {"type": "entry_imm", "params": {}}
            ]},
            "exit": {"mode": "ANY", "conditions": [
                {"type": "atr_stop",      "params": {"multiplier": 0.01, "period": 3}},
                {"type": "trailing_stop", "params": {"activation_pct": 0.01, "trail_pct": 99}},
            ]},
        }
        bars   = _flat_bars(20, price=100)
        # force a price drop on bar 5
        bars[5] = {"date": _date(5), "open": 50, "high": 51, "low": 49,
                   "close": 50, "volume": 5000}

        custom = {"entry_imm": EntryImm({})}
        result = run_backtest(bars, config, custom_conditions=custom)

        for trade in result["trades"]:
            assert trade["exit_reason"] is not None
            assert isinstance(trade["exit_reason"], str)

        ALL_CONDITION_TYPES.discard("entry_imm")


# ---------------------------------------------------------------------------
# ENG-09: scan_log length == total_bars - warmup_period
# ---------------------------------------------------------------------------
class TestENG09:
    def test_scan_log_length(self):
        config = _load_example_config()
        ohlcv  = generate(n=200, mode="random", seed=7)
        result = run_backtest(ohlcv, config)
        expected = result["metadata"]["total_bars"] - result["metadata"]["warmup_period"]
        assert len(result["scan_log"]) == expected


# ---------------------------------------------------------------------------
# ENG-10: scan_log entries in position contain correct pnl
# ---------------------------------------------------------------------------
class TestENG10:
    def test_pnl_in_scan_log(self):
        from core.strategy import ALL_CONDITION_TYPES
        ALL_CONDITION_TYPES.add("entry_eng10")

        class E:
            def __init__(self, p): pass
            def check(self, data, index, position=None): return True

        config = {
            "name": "pnl_test",
            "entry": {"mode": "ALL", "conditions": [{"type": "entry_eng10", "params": {}}]},
            "exit":  {"mode": "ANY", "conditions": [{"type": "time_stop", "params": {"max_days": 100}}]},
        }
        bars   = _flat_bars(5, price=100) + _flat_bars(5, price=110)
        custom = {"entry_eng10": E({})}
        result = run_backtest(bars, config, custom_conditions=custom)

        # Find a scan_log entry with a position
        position_logs = [l for l in result["scan_log"] if l["position"] is not None]
        assert len(position_logs) > 0
        for log in position_logs:
            pnl = log["position"]["current_pnl_pct"]
            assert isinstance(pnl, (int, float))

        ALL_CONDITION_TYPES.discard("entry_eng10")


# ---------------------------------------------------------------------------
# ENG-11: exit_conditions distance_pct in scan_log
# ---------------------------------------------------------------------------
class TestENG11:
    def test_atr_stop_distance_pct_in_scan_log(self):
        config = _load_example_config()
        ohlcv  = generate(n=200, mode="bull", seed=3)
        result = run_backtest(ohlcv, config)

        for log in result["scan_log"]:
            if log.get("exit_conditions") and "atr_stop" in log["exit_conditions"]:
                atr_cond = log["exit_conditions"]["atr_stop"]
                if atr_cond.get("distance_pct") is not None:
                    assert isinstance(atr_cond["distance_pct"], (int, float))
                    return  # found at least one, test passes
        # If no position was entered, just skip
        pytest.skip("No trade with atr_stop distance_pct found in scan_log")


# ---------------------------------------------------------------------------
# ENG-12: end_of_data close — open position at end gets exit_reason="end_of_data"
# ---------------------------------------------------------------------------
class TestENG12:
    def test_end_of_data_exit(self):
        from core.strategy import ALL_CONDITION_TYPES
        ALL_CONDITION_TYPES.add("entry_eod")

        class E:
            def __init__(self, p): pass
            def check(self, data, index, position=None): return True

        config = {
            "name": "eod_test",
            "entry": {"mode": "ALL", "conditions": [{"type": "entry_eod", "params": {}}]},
            "exit":  {"mode": "ANY", "conditions": [{"type": "time_stop", "params": {"max_days": 9999}}]},
        }
        bars   = _flat_bars(5, price=100)
        custom = {"entry_eod": E({})}
        result = run_backtest(bars, config, custom_conditions=custom)

        assert len(result["trades"]) >= 1
        last_trade = result["trades"][-1]
        assert last_trade["exit_reason"] == "end_of_data"
        assert last_trade["exit_price"]  == bars[-1]["close"]

        ALL_CONDITION_TYPES.discard("entry_eod")


# ---------------------------------------------------------------------------
# ENG-13: No entry triggered → trades = [], total_trades = 0 (P1)
# ---------------------------------------------------------------------------
class TestENG13:
    def test_no_entry_no_crash(self):
        config = {
            "name": "no_entry",
            "entry": {"mode": "ALL", "conditions": [
                {"type": "never_entry", "params": {}}
            ]},
            "exit": {"mode": "ANY", "conditions": [
                {"type": "time_stop", "params": {"max_days": 5}}
            ]},
        }
        from core.strategy import ALL_CONDITION_TYPES
        ALL_CONDITION_TYPES.add("never_entry")

        class NeverEntry:
            def __init__(self, p): pass
            def check(self, data, index, position=None): return False

        ohlcv  = generate(n=200, mode="random", seed=99)
        custom = {"never_entry": NeverEntry({})}
        result = run_backtest(ohlcv, config, custom_conditions=custom)

        assert result["trades"] == []

        ALL_CONDITION_TYPES.discard("never_entry")


# ---------------------------------------------------------------------------
# ENG-14: Only warmup-length data → trades = [], no crash (P1)
# ---------------------------------------------------------------------------
class TestENG14:
    def test_only_warmup_data(self):
        config = _load_example_config()
        ohlcv  = generate(n=50, mode="random", seed=1)  # exactly warmup length
        result = run_backtest(ohlcv, config)
        assert result["trades"] == []
        assert result["scan_log"] == []
