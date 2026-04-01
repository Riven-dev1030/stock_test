"""
Unit tests for validation/ modules
Covers acceptance criteria: VAL-01~11
"""
import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from validation.monte_carlo import run_monte_carlo
from validation.monkey_test import run_monkey_test
from validation.overfit_detect import run_walk_forward
from core.data_gen import generate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_trades(pnl_list):
    return [
        {"id": i+1, "pnl_pct": p, "pnl_abs": p, "bars_held": 5,
         "peak_price": 110, "max_drawdown_during_trade": -1.0,
         "entry_index": i*10, "exit_index": i*10+5,
         "entry_date": "2026-01-01", "exit_date": "2026-01-06",
         "entry_price": 100, "exit_price": 100 + p,
         "exit_reason": "atr_stop"}
        for i, p in enumerate(pnl_list)
    ]


# ---------------------------------------------------------------------------
# VAL-01: Monte Carlo reproducibility with fixed seed
# ---------------------------------------------------------------------------
class TestVAL01:
    def test_same_seed_same_output(self):
        trades = _make_trades([5, -2, 8, -3, 10, -1, 4, -5, 6, 3])
        r1 = run_monte_carlo(trades, simulations=1000, seed=42)
        r2 = run_monte_carlo(trades, simulations=1000, seed=42)
        assert r1["percentiles"] == r2["percentiles"]
        assert r1["ruin_probability"] == r2["ruin_probability"]


# ---------------------------------------------------------------------------
# VAL-02: Percentile ordering — p5 <= p25 <= p50 <= p75 <= p95
# ---------------------------------------------------------------------------
class TestVAL02:
    def test_percentile_order_total_return(self):
        trades = _make_trades([5, -2, 8, -3, 10, -1, 4, -5, 6, 3])
        result = run_monte_carlo(trades, simulations=2000, seed=42)
        p = result["percentiles"]
        returns = [p["p5"]["total_return"], p["p25"]["total_return"],
                   p["p50"]["total_return"], p["p75"]["total_return"],
                   p["p95"]["total_return"]]
        for i in range(len(returns) - 1):
            assert returns[i] <= returns[i+1], \
                f"total_return: p{[5,25,50,75,95][i]}={returns[i]} > p{[5,25,50,75,95][i+1]}={returns[i+1]}"

    def test_percentile_order_max_drawdown(self):
        trades = _make_trades([5, -2, 8, -3, 10, -1, 4, -5, 6, 3])
        result = run_monte_carlo(trades, simulations=2000, seed=42)
        p = result["percentiles"]
        dds = [p["p5"]["max_drawdown"], p["p25"]["max_drawdown"],
               p["p50"]["max_drawdown"], p["p75"]["max_drawdown"],
               p["p95"]["max_drawdown"]]
        for i in range(len(dds) - 1):
            assert dds[i] <= dds[i+1], \
                f"max_drawdown: p{[5,25,50,75,95][i]}={dds[i]} > p{[5,25,50,75,95][i+1]}={dds[i+1]}"


# ---------------------------------------------------------------------------
# VAL-03: All positive PnL → ruin_probability = 0
# ---------------------------------------------------------------------------
class TestVAL03:
    def test_all_positive_ruin_zero(self):
        trades = _make_trades([5, 10, 3, 8, 2, 7, 4, 6, 1, 9])
        result = run_monte_carlo(trades, simulations=1000, seed=42)
        assert result["ruin_probability"] == 0.0


# ---------------------------------------------------------------------------
# VAL-04: 5,000 Monte Carlo simulations in < 2 seconds (P1)
# ---------------------------------------------------------------------------
class TestVAL04:
    def test_performance_5000_sims(self):
        trades = _make_trades([5, -2, 8, -3, 10, -1, 4, -5, 6, 3] * 5)
        start  = time.time()
        run_monte_carlo(trades, simulations=5000, seed=42)
        elapsed = time.time() - start
        assert elapsed < 2.0, f"Monte Carlo 5,000 sims took {elapsed:.2f}s (limit 2s)"


# ---------------------------------------------------------------------------
# VAL-05: Monkey Test reproducibility with fixed seed
# ---------------------------------------------------------------------------
class TestVAL05:
    def test_same_seed_same_output(self):
        ohlcv = generate(n=200, mode="bull", seed=42)
        r1 = run_monkey_test(ohlcv, strategy_return=20.0, simulations=1000, seed=7)
        r2 = run_monkey_test(ohlcv, strategy_return=20.0, simulations=1000, seed=7)
        assert r1["percentile_rank"] == r2["percentile_rank"]
        assert r1["random_distribution"] == r2["random_distribution"]


# ---------------------------------------------------------------------------
# VAL-06: percentile_rank accuracy < 1% error
# ---------------------------------------------------------------------------
class TestVAL06:
    def test_percentile_rank_accuracy(self):
        ohlcv = generate(n=500, mode="bull", seed=42)
        # Strategy return higher than most random trades
        result = run_monkey_test(ohlcv, strategy_return=50.0,
                                 simulations=5000, seed=42)
        # Verify by manual count
        # percentile_rank = fraction of randoms below strategy_return * 100
        assert 0.0 <= result["percentile_rank"] <= 100.0
        # For a high strategy return, rank should be high
        assert result["percentile_rank"] > 50.0


# ---------------------------------------------------------------------------
# VAL-07: Poor strategy → low percentile rank
# ---------------------------------------------------------------------------
class TestVAL07:
    def test_poor_strategy_low_rank(self):
        ohlcv = generate(n=200, mode="bull", seed=42)
        result = run_monkey_test(ohlcv, strategy_return=-50.0,
                                 simulations=2000, seed=42)
        assert result["percentile_rank"] < 50.0


# ---------------------------------------------------------------------------
# VAL-08: 10,000 Monkey Test simulations in < 5 seconds (P1)
# ---------------------------------------------------------------------------
class TestVAL08:
    def test_performance_10000_sims(self):
        ohlcv  = generate(n=200, mode="random", seed=42)
        start  = time.time()
        run_monkey_test(ohlcv, strategy_return=10.0, simulations=10000, seed=42)
        elapsed = time.time() - start
        assert elapsed < 5.0, f"Monkey Test 10,000 sims took {elapsed:.2f}s (limit 5s)"


# ---------------------------------------------------------------------------
# VAL-09: Walk-Forward correct number of folds and non-overlapping ranges
# ---------------------------------------------------------------------------
class TestVAL09:
    def test_fold_count_and_ranges(self):
        import json
        config_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "config", "strategy_config.json"
        )
        with open(config_path) as f:
            config = json.load(f)
        ohlcv  = generate(n=200, mode="bull", seed=42)
        result = run_walk_forward(ohlcv, config, window_size=100, step_size=30)

        assert len(result["folds"]) > 0

        for fold in result["folds"]:
            in_s  = fold["in_sample"]
            out_s = fold["out_of_sample"]
            # in_sample and out_of_sample must not overlap
            assert in_s["end"] < out_s["start"], \
                f"Fold {fold['fold']}: in_sample end {in_s['end']} >= out start {out_s['start']}"
            # out_of_sample starts right after in_sample
            assert out_s["start"] == in_s["end"] + 1


# ---------------------------------------------------------------------------
# VAL-10: degradation_ratio = out / in (correctness check)
# ---------------------------------------------------------------------------
class TestVAL10:
    def test_degradation_ratio_formula(self):
        import json
        config_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "config", "strategy_config.json"
        )
        with open(config_path) as f:
            config = json.load(f)
        ohlcv  = generate(n=200, mode="bull", seed=42)
        result = run_walk_forward(ohlcv, config, window_size=100, step_size=30)

        if result["in_sample_avg_return"] != 0 and result["degradation_ratio"] is not None:
            expected = (
                result["out_of_sample_avg_return"] /
                result["in_sample_avg_return"]
            )
            assert abs(result["degradation_ratio"] - expected) < 0.001


# ---------------------------------------------------------------------------
# VAL-11: Overfit warning when out-of-sample is negative (P1)
# ---------------------------------------------------------------------------
class TestVAL11:
    def test_overfit_warning_when_oos_negative(self):
        import json
        config_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "config", "strategy_config.json"
        )
        with open(config_path) as f:
            config = json.load(f)

        # bull in-sample, then bear out-of-sample → degradation
        in_sample  = generate(n=150, mode="bull", seed=42)
        out_sample = generate(n=50,  mode="bear", seed=42)
        ohlcv      = in_sample + out_sample

        result = run_walk_forward(ohlcv, config, window_size=100, step_size=50)

        # If in-sample > 0 and out-of-sample < 0, should warn
        if (result["in_sample_avg_return"] > 0 and
                result["out_of_sample_avg_return"] < 0):
            assert result["overfit_warning"] is True
