"""
Performance tests
Covers acceptance criteria: PRF-01 ~ PRF-05

PRF-01 (P1): 200-bar data generation      < 10ms
PRF-02 (P1): single backtest (200 bars)   < 50ms
PRF-03 (P1): Monte Carlo 5,000 sims       < 2s
PRF-04 (P1): Monkey Test 10,000 sims      < 5s
PRF-05 (P2): Walk-Forward 10 folds        < 10s
"""
import sys
import os
import time
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from core.data_gen import generate
from core.engine import run_backtest
from validation.monte_carlo import run_monte_carlo
from validation.monkey_test import run_monkey_test
from validation.overfit_detect import run_walk_forward


def _load_config():
    path = os.path.join(
        os.path.dirname(__file__), "..", "..", "config", "strategy_config.json"
    )
    with open(path) as f:
        return json.load(f)


def _make_trades(pnl_list):
    return [
        {"id": i+1, "pnl_pct": p, "pnl_abs": p, "bars_held": 5,
         "peak_price": 110, "max_drawdown_during_trade": -1.0,
         "entry_index": i*10, "exit_index": i*10+5,
         "entry_date": "2026-01-01", "exit_date": "2026-01-06",
         "entry_price": 100, "exit_price": 100+p, "exit_reason": "atr_stop"}
        for i, p in enumerate(pnl_list)
    ]


# ---------------------------------------------------------------------------
# PRF-01: 200-bar data generation < 10ms
# ---------------------------------------------------------------------------
class TestPRF01:
    def test_data_generation_under_10ms(self):
        start   = time.perf_counter()
        bars    = generate(n=200, mode="random", seed=42)
        elapsed = (time.perf_counter() - start) * 1000  # ms
        assert len(bars) == 200
        assert elapsed < 10, f"Data generation took {elapsed:.2f}ms (limit 10ms)"


# ---------------------------------------------------------------------------
# PRF-02: Single backtest on 200 bars < 50ms
# ---------------------------------------------------------------------------
class TestPRF02:
    def test_single_backtest_under_50ms(self):
        config = _load_config()
        ohlcv  = generate(n=200, mode="bull", seed=42)

        start   = time.perf_counter()
        run_backtest(ohlcv, config)
        elapsed = (time.perf_counter() - start) * 1000  # ms
        assert elapsed < 50, f"Backtest took {elapsed:.2f}ms (limit 50ms)"


# ---------------------------------------------------------------------------
# PRF-03: Monte Carlo 5,000 simulations < 2s
# ---------------------------------------------------------------------------
class TestPRF03:
    def test_monte_carlo_5000_under_2s(self):
        trades  = _make_trades([5, -2, 8, -3, 10, -1, 4, -5, 6, 3] * 5)
        start   = time.perf_counter()
        run_monte_carlo(trades, simulations=5000, seed=42)
        elapsed = time.perf_counter() - start
        assert elapsed < 2.0, f"Monte Carlo 5,000 sims took {elapsed:.3f}s (limit 2s)"


# ---------------------------------------------------------------------------
# PRF-04: Monkey Test 10,000 simulations < 5s
# ---------------------------------------------------------------------------
class TestPRF04:
    def test_monkey_test_10000_under_5s(self):
        ohlcv   = generate(n=200, mode="random", seed=42)
        start   = time.perf_counter()
        run_monkey_test(ohlcv, strategy_return=10.0, simulations=10000, seed=42)
        elapsed = time.perf_counter() - start
        assert elapsed < 5.0, f"Monkey Test 10,000 sims took {elapsed:.3f}s (limit 5s)"


# ---------------------------------------------------------------------------
# PRF-05: Walk-Forward 10 folds < 10s (P2)
# ---------------------------------------------------------------------------
class TestPRF05:
    def test_walk_forward_10_folds_under_10s(self):
        config = _load_config()
        # Need enough bars to produce ~10 folds: window=100, step=30 → need ~400 bars
        ohlcv  = generate(n=400, mode="bull", seed=42)

        start   = time.perf_counter()
        result  = run_walk_forward(ohlcv, config, window_size=100, step_size=30)
        elapsed = time.perf_counter() - start

        assert elapsed < 10.0, f"Walk-Forward took {elapsed:.3f}s (limit 10s)"
        assert len(result["folds"]) >= 5, \
            f"Expected ≥5 folds, got {len(result['folds'])} (check window/step params)"
