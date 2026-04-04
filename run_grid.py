"""
run_grid.py — Grid Trading Strategy demo

Rules:
  - Define a price range (base_price ± range_pct%)
  - Divide into N grid levels
  - Buy 1 unit at each grid level below current price
  - Sell when price rises back to the level above entry
  - Uses max_positions to hold multiple simultaneous positions
"""
import json
from core.data_gen import generate
from core.engine import run_backtest
from core.strategy import ALL_CONDITION_TYPES
from output.summary import compute_summary


# ---------------------------------------------------------------------------
# Custom conditions for grid trading
# ---------------------------------------------------------------------------
class GridEntryCondition:
    """Enter when price is at or below the next unoccupied grid level."""

    def __init__(self, params):
        self.grids      = params["grid_levels"]   # sorted ascending list of prices
        self.tolerance  = params.get("tolerance", 0.005)  # 0.5% band

    def check(self, ohlcv, index, position=None):
        current = ohlcv[index]["close"]
        for level in self.grids:
            lower = level * (1 - self.tolerance)
            upper = level * (1 + self.tolerance)
            if lower <= current <= upper:
                return True
        return False


class GridExitCondition:
    """Exit when price rises to the grid level above the entry price."""

    def __init__(self, params):
        self.grids      = params["grid_levels"]
        self.tolerance  = params.get("tolerance", 0.005)

    def check(self, ohlcv, index, position=None):
        if position is None:
            return False
        current     = ohlcv[index]["close"]
        entry_price = position["entry_price"]

        # Find the grid level just above entry
        for level in sorted(self.grids):
            if level > entry_price * (1 + self.tolerance):
                return current >= level * (1 - self.tolerance)
        return False


# ---------------------------------------------------------------------------
# Build grid config
# ---------------------------------------------------------------------------
def build_grid_config(base_price, range_pct=20, num_grids=8):
    """Generate grid levels and strategy config."""
    step    = base_price * (range_pct / 100) / num_grids
    levels  = [round(base_price - (range_pct / 200) * base_price + step * i, 2)
               for i in range(num_grids + 1)]

    ALL_CONDITION_TYPES.add("grid_entry")
    ALL_CONDITION_TYPES.add("grid_exit")

    config = {
        "name":          f"Grid {num_grids} levels ±{range_pct/2}%",
        "max_positions": num_grids,
        "entry": {
            "mode": "ANY",
            "conditions": [{"type": "grid_entry", "params": {
                "grid_levels": levels, "tolerance": 0.008
            }}]
        },
        "exit": {
            "mode": "ANY",
            "conditions": [
                {"type": "grid_exit",  "params": {"grid_levels": levels, "tolerance": 0.008}},
                {"type": "time_stop",  "params": {"max_days": 60}},
            ]
        },
    }
    return config, levels


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("  Grid Trading Strategy")
    print("=" * 60)

    modes = [("choppy", "震盪"), ("bull", "多頭"), ("bear", "空頭")]

    for mode, label in modes:
        ohlcv  = generate(n=500, mode=mode, seed=42)
        prices = [b["close"] for b in ohlcv]
        base   = sum(prices[:50]) / 50          # use first 50 bars as base

        config, levels = build_grid_config(base_price=base, range_pct=20, num_grids=8)
        print(f"\n[{label.upper()} / {mode}] base={base:.1f}  "
              f"grid range: {levels[0]:.1f} ~ {levels[-1]:.1f}")
        print(f"  Grid levels: {[round(l,1) for l in levels]}")

        custom = {
            "grid_entry": GridEntryCondition(config["entry"]["conditions"][0]["params"]),
            "grid_exit":  GridExitCondition(config["exit"]["conditions"][0]["params"]),
        }

        result = run_backtest(ohlcv, config, custom_conditions=custom)
        result["summary"] = compute_summary(result["trades"])
        s = result["summary"]

        print(f"  Trades        : {s['total_trades']}")
        if s["total_trades"] == 0:
            print("  (no trades — price never hit grid levels)")
            continue
        print(f"  Win rate      : {s['win_rate']:.1f}%")
        print(f"  Total return  : {s['total_return_pct']:.2f}%")
        print(f"  Max drawdown  : {s['max_drawdown_pct']:.2f}%")
        print(f"  Profit factor : {s['profit_factor']}")
        print(f"  Avg bars held : {s['avg_bars_held']:.1f}")
        print(f"  Exit reasons  : {s['exit_reason_breakdown']}")

        # Max simultaneous positions
        max_sim = max(len(log["positions"]) for log in result["scan_log"])
        print(f"  Max sim. pos  : {max_sim}")

    ALL_CONDITION_TYPES.discard("grid_entry")
    ALL_CONDITION_TYPES.discard("grid_exit")
    print("\n" + "=" * 60)
    print("Done.")


if __name__ == "__main__":
    main()
