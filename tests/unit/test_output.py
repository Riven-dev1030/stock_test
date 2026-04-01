"""
Unit tests for output/ modules
Covers acceptance criteria: OUT-01~08
"""
import sys
import os
import json
import math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from output.serializer import to_json, save_json, load_json
from output.summary import compute_summary
from output.slicer import slice_trade, auto_select_trades, build_slices
from core.data_gen import generate
from core.engine import run_backtest
from core.strategy import compute_indicators


def _load_config():
    path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "strategy_config.json")
    with open(path) as f:
        return json.load(f)


def _run_full(seed=4, mode="bull", n=1000):
    from output.summary import compute_summary
    config = _load_config()
    ohlcv  = generate(n=n, mode=mode, seed=seed)
    result = run_backtest(ohlcv, config)
    result["summary"] = compute_summary(result["trades"])
    return result, ohlcv, config


# ---------------------------------------------------------------------------
# OUT-01: JSON output is valid JSON
# ---------------------------------------------------------------------------
class TestOUT01:
    def test_to_json_is_valid(self):
        result, _, _ = _run_full()
        json_str = to_json(result)
        parsed   = json.loads(json_str)   # must not raise
        assert isinstance(parsed, dict)

    def test_save_and_load_roundtrip(self, tmp_path):
        result, _, _ = _run_full()
        path = str(tmp_path / "output.json")
        save_json(result, path)
        loaded = load_json(path)
        assert loaded["metadata"]["strategy_name"] == result["metadata"]["strategy_name"]


# ---------------------------------------------------------------------------
# OUT-02: JSON schema — required top-level keys and trade fields
# ---------------------------------------------------------------------------
class TestOUT02:
    def test_required_top_level_keys(self):
        result, _, _ = _run_full()
        assert {"metadata", "trades", "scan_log", "summary"}.issubset(result.keys())

    def test_trade_fields(self):
        result, _, _ = _run_full()
        required_trade_fields = {
            "id", "entry_index", "entry_date", "entry_price",
            "exit_index", "exit_date", "exit_price", "exit_reason",
            "bars_held", "pnl_pct", "pnl_abs", "peak_price",
            "max_drawdown_during_trade",
        }
        for trade in result["trades"]:
            assert required_trade_fields.issubset(trade.keys()), \
                f"Trade missing fields: {required_trade_fields - trade.keys()}"


# ---------------------------------------------------------------------------
# OUT-03: win_rate, profit_factor, expectancy hand-calculated
# ---------------------------------------------------------------------------
class TestOUT03:
    def _make_trades(self, pnl_list):
        return [
            {"id": i+1, "pnl_pct": pnl, "pnl_abs": pnl, "bars_held": 5,
             "peak_price": 110, "max_drawdown_during_trade": -1.0,
             "entry_index": i, "exit_index": i+5,
             "entry_date": "2026-01-01", "exit_date": "2026-01-06",
             "entry_price": 100, "exit_price": 100 + pnl,
             "exit_reason": "atr_stop"}
            for i, pnl in enumerate(pnl_list)
        ]

    def test_win_rate(self):
        trades  = self._make_trades([5.0, -2.0, 8.0])   # 2 wins, 1 loss
        summary = compute_summary(trades)
        assert abs(summary["win_rate"] - 66.6667) < 0.001

    def test_profit_factor(self):
        trades  = self._make_trades([5.0, -2.0, 8.0])
        summary = compute_summary(trades)
        # gross_profit = 13, gross_loss = 2, PF = 6.5
        assert abs(summary["profit_factor"] - 6.5) < 0.001

    def test_expectancy(self):
        trades  = self._make_trades([6.0, -3.0, 9.0])
        summary = compute_summary(trades)
        # wins: [6,9] avg=7.5, losses: [-3] avg=-3
        # expectancy = (2/3)*7.5 + (1/3)*(-3) = 5.0 - 1.0 = 4.0
        assert abs(summary["expectancy_pct"] - 4.0) < 0.001


# ---------------------------------------------------------------------------
# OUT-04: exit_reason_breakdown totals == total_trades
# ---------------------------------------------------------------------------
class TestOUT04:
    def test_exit_reason_total(self):
        result, _, _ = _run_full()
        summary  = result["summary"]
        bd_total = sum(summary["exit_reason_breakdown"].values())
        assert bd_total == summary["total_trades"]


# ---------------------------------------------------------------------------
# OUT-05: max_drawdown computed correctly
# ---------------------------------------------------------------------------
class TestOUT05:
    def test_max_drawdown_manual(self):
        # PnL sequence: +10, +5, -8, +3, -15
        # Cumulative: 10, 15, 7, 10, -5
        # Peak: 10, 15, 15, 15, 15
        # DD:    0,  0, -8, -5, -20
        # max_dd = -20
        pnl_list = [10.0, 5.0, -8.0, 3.0, -15.0]
        trades = [
            {"id": i+1, "pnl_pct": pnl, "pnl_abs": pnl, "bars_held": 5,
             "peak_price": 110, "max_drawdown_during_trade": -1.0,
             "entry_index": i, "exit_index": i+5,
             "entry_date": "2026-01-01", "exit_date": "2026-01-06",
             "entry_price": 100, "exit_price": 100 + pnl,
             "exit_reason": "trailing_stop"}
            for i, pnl in enumerate(pnl_list)
        ]
        summary = compute_summary(trades)
        assert abs(summary["max_drawdown_pct"] - (-20.0)) < 0.001


# ---------------------------------------------------------------------------
# OUT-06: slicer returns correct slice length = context + trade range
# ---------------------------------------------------------------------------
class TestOUT06:
    def test_slice_length(self):
        result, ohlcv, config = _run_full()
        if not result["trades"]:
            pytest.skip("No trades generated")

        ind   = compute_indicators(ohlcv, config)
        trade = result["trades"][0]
        slc   = slice_trade(trade, ohlcv, result["scan_log"], ind, context_bars=15)

        expected_len = (
            slc["context_range"]["end_index"]
            - slc["context_range"]["start_index"] + 1
        )
        assert len(slc["ohlcv_slice"]) == expected_len

        # Each indicator array must match ohlcv_slice length
        for key, arr in slc["indicators_slice"].items():
            assert len(arr) == expected_len, \
                f"Indicator {key} slice length mismatch"

    def test_context_range_respects_boundaries(self):
        """Slice should not go below index 0 or above last bar."""
        result, ohlcv, config = _run_full()
        if not result["trades"]:
            pytest.skip("No trades generated")

        ind  = compute_indicators(ohlcv, config)
        slc  = slice_trade(result["trades"][0], ohlcv, result["scan_log"], ind, context_bars=15)
        assert slc["context_range"]["start_index"] >= 0
        assert slc["context_range"]["end_index"]   <= len(ohlcv) - 1


# ---------------------------------------------------------------------------
# OUT-07: diagnosis_prompt contains key information (P1)
# ---------------------------------------------------------------------------
class TestOUT07:
    def test_diagnosis_prompt_has_key_info(self):
        result, ohlcv, config = _run_full()
        if not result["trades"]:
            pytest.skip("No trades generated")

        ind   = compute_indicators(ohlcv, config)
        trade = result["trades"][0]
        slc   = slice_trade(trade, ohlcv, result["scan_log"], ind, context_bars=15)
        prompt = slc["diagnosis_prompt"]

        assert trade["entry_date"]  in prompt
        assert trade["exit_reason"] in prompt
        assert str(trade["pnl_pct"]) in prompt or f"{trade['pnl_pct']:.2f}" in prompt


# ---------------------------------------------------------------------------
# OUT-08: auto_select returns worst pnl trades (P1)
# ---------------------------------------------------------------------------
class TestOUT08:
    def test_auto_select_worst_pnl(self):
        result, ohlcv, config = _run_full()
        if len(result["trades"]) < 3:
            pytest.skip("Need at least 3 trades")

        ind     = compute_indicators(ohlcv, config)
        slices  = build_slices(result["trades"], ohlcv, result["scan_log"],
                               ind, top_n=3, criteria="worst_pnl")

        assert len(slices) == 3
        pnls = [s["trade_id"] for s in slices]

        # Verify the trade_ids correspond to the 3 worst trades
        sorted_trades = sorted(result["trades"], key=lambda t: t["pnl_pct"])
        worst_ids = [t["id"] for t in sorted_trades[:3]]
        for slc in slices:
            assert slc["trade_id"] in worst_ids
