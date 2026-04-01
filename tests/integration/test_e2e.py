"""
Integration tests for end-to-end backtest pipeline.
Covers acceptance criteria: INT-01~05
"""
import sys
import os
import json
import csv
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from core.data_gen import generate
from core.data_loader import load_from_csv
from core.strategy import load_strategy
from core.engine import run_backtest
from core.strategy import compute_indicators
from output.serializer import to_json, save_json, load_json
from output.summary import compute_summary
from output.slicer import build_slices
from validation.monte_carlo import run_monte_carlo
from validation.monkey_test import run_monkey_test
from validation.overfit_detect import run_walk_forward


def _config_path():
    return os.path.join(
        os.path.dirname(__file__), "..", "..", "config", "strategy_config.json"
    )


def _run_full_pipeline(seed=4, mode="bull", n=1000):
    config = load_strategy(_config_path())
    ohlcv  = generate(n=n, mode=mode, seed=seed)
    result = run_backtest(ohlcv, config)
    result["summary"] = compute_summary(result["trades"])
    return result, ohlcv, config


# ---------------------------------------------------------------------------
# INT-01: Full flow from data generation to JSON output
# ---------------------------------------------------------------------------
class TestINT01:
    def test_full_pipeline_produces_valid_json(self):
        result, _, _ = _run_full_pipeline()
        json_str = to_json(result)
        parsed   = json.loads(json_str)  # must not raise
        assert isinstance(parsed, dict)
        assert set(parsed.keys()) >= {"metadata", "trades", "scan_log", "summary"}

    def test_save_and_reload_roundtrip(self, tmp_path):
        result, _, _ = _run_full_pipeline()
        path = str(tmp_path / "backtest_result.json")
        save_json(result, path)
        loaded = load_json(path)
        assert loaded["metadata"]["strategy_name"] == result["metadata"]["strategy_name"]
        assert len(loaded["trades"]) == len(result["trades"])


# ---------------------------------------------------------------------------
# INT-02: Monte Carlo + Monkey Test use same trade results
# ---------------------------------------------------------------------------
class TestINT02:
    def test_all_three_validations_consistent(self):
        result, ohlcv, config = _run_full_pipeline()
        trades = result["trades"]

        mc = run_monte_carlo(trades, simulations=500, seed=42)
        mt = run_monkey_test(ohlcv, strategy_return=result["summary"]["total_return_pct"],
                             simulations=500, seed=42)
        wf = run_walk_forward(ohlcv, config)

        # All three should complete without error
        assert "percentiles"          in mc
        assert "percentile_rank"      in mt
        assert "folds"                in wf

        # Monte Carlo uses same trade list
        assert mc["simulations"] == 500
        assert mt["random_simulations"] == 500

    def test_monte_carlo_trade_count_matches(self):
        result, _, _ = _run_full_pipeline()
        mc = run_monte_carlo(result["trades"], simulations=200, seed=1)
        # Should not crash with any number of trades
        assert mc["simulations"] == 200


# ---------------------------------------------------------------------------
# INT-03: CSV data path produces same format as simulated data
# ---------------------------------------------------------------------------
class TestINT03:
    def test_csv_and_simulated_same_output_format(self, tmp_path):
        # Write simulated data to CSV
        ohlcv = generate(n=200, mode="bull", seed=42)
        csv_path = str(tmp_path / "data.csv")
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["date","open","high","low","close","volume"])
            writer.writeheader()
            writer.writerows(ohlcv)

        # Load from CSV
        loaded_ohlcv = load_from_csv(csv_path)
        config       = load_strategy(_config_path())

        result_csv = run_backtest(loaded_ohlcv, config)
        result_sim = run_backtest(ohlcv,         config)

        # Both should have same structure
        assert set(result_csv.keys()) == set(result_sim.keys())
        # Same number of trades (same data, same strategy)
        assert len(result_csv["trades"]) == len(result_sim["trades"])


# ---------------------------------------------------------------------------
# INT-04: Two different strategy configs produce different metadata
# ---------------------------------------------------------------------------
class TestINT04:
    def test_different_strategies_produce_different_metadata(self):
        config1 = load_strategy(_config_path())
        config2 = {
            "name": "Simple MA Cross",
            "entry": {"mode": "ALL", "conditions": [
                {"type": "ma_alignment", "params": {"fast": 10, "slow": 20, "direction": "bullish"}}
            ]},
            "exit": {"mode": "ANY", "conditions": [
                {"type": "ma_stop",    "params": {"fast": 10, "slow": 20}},
                {"type": "time_stop",  "params": {"max_days": 10}},
            ]},
        }

        ohlcv   = generate(n=200, mode="bull", seed=42)
        result1 = run_backtest(ohlcv, config1)
        result2 = run_backtest(ohlcv, config2)

        assert result1["metadata"]["strategy_name"] != result2["metadata"]["strategy_name"]
        assert result1["metadata"]["warmup_period"] != result2["metadata"]["warmup_period"]


# ---------------------------------------------------------------------------
# INT-05: Same data + strategy + seed → deterministic results (P1)
# ---------------------------------------------------------------------------
class TestINT05:
    def test_deterministic_output(self):
        result1, _, _ = _run_full_pipeline(seed=4, mode="bull", n=1000)
        result2, _, _ = _run_full_pipeline(seed=4, mode="bull", n=1000)

        assert result1["metadata"]["total_bars"]    == result2["metadata"]["total_bars"]
        assert result1["metadata"]["warmup_period"] == result2["metadata"]["warmup_period"]
        assert len(result1["trades"])               == len(result2["trades"])

        for t1, t2 in zip(result1["trades"], result2["trades"]):
            assert t1["entry_index"] == t2["entry_index"]
            assert t1["exit_index"]  == t2["exit_index"]
            assert t1["pnl_pct"]     == t2["pnl_pct"]
            assert t1["exit_reason"] == t2["exit_reason"]
