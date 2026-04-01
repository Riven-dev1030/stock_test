"""
run_turtle.py — Turtle System 1 backtest demo

Rules:
  Entry : Close breaks above 20-day high
  Exit  : Close drops below 10-day low  (custom condition)
           OR 2x ATR stop               (built-in)
"""
import json
from core.data_gen import generate
import json
from core.engine import run_backtest
from core.indicators import lowest_low
from output.summary import compute_summary
from validation.monte_carlo import run_monte_carlo
from validation.monkey_test import run_monkey_test


# ---------------------------------------------------------------------------
# Custom exit condition: 10-day lowest low
# ---------------------------------------------------------------------------
class LowestLowExit:
    def __init__(self, params=None):
        self.period = (params or {}).get("period", 10)

    def check(self, ohlcv, index, position=None):
        if position is None or index < self.period:
            return False
        lows = [b["low"] for b in ohlcv]
        ll = lowest_low(lows, self.period)
        if ll[index - 1] is None:
            return False
        current_close = ohlcv[index]["close"]
        prev_ll = ll[index - 1]
        return current_close < prev_ll


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
def main():
    print("=" * 55)
    print("  Turtle System 1 Backtest")
    print("  Entry : 20-day high breakout")
    print("  Exit  : 10-day low breakdown | 2x ATR stop")
    print("=" * 55)

    modes = ["bull", "bear", "choppy", "random"]
    for mode in modes:
        ohlcv = generate(n=500, mode=mode, seed=42)
        with open("config/turtle_strategy.json", encoding="utf-8") as f:
            config = json.load(f)

        custom = {
            "lowest_low_exit": LowestLowExit({"period": 10})
        }

        result = run_backtest(ohlcv, config, custom_conditions=custom)
        result["summary"] = compute_summary(result["trades"])
        s = result["summary"]
        trades = result["trades"]

        print(f"\n[{mode.upper():7s}] bars=500 seed=42")
        print(f"  Trades        : {s['total_trades']}")
        if s["total_trades"] == 0:
            print("  (no trades generated)")
            continue
        print(f"  Win rate      : {s['win_rate']:.1f}%")
        print(f"  Total return  : {s['total_return_pct']:.2f}%")
        print(f"  Max drawdown  : {s['max_drawdown_pct']:.2f}%")
        print(f"  Profit factor : {s['profit_factor']}")
        print(f"  Sharpe ratio  : {s['sharpe_ratio']:.2f}")
        print(f"  Avg bars held : {s['avg_bars_held']:.1f}")
        print(f"  Exit reasons  : {s['exit_reason_breakdown']}")

        # Quick Monte Carlo (1000 sims)
        if s["total_trades"] >= 2:
            mc = run_monte_carlo(trades, simulations=1000, seed=42)
            p = mc["percentiles"]
            print(f"  MC p5/p50/p95 return: "
                  f"{p['p5']['total_return']:.1f}% / "
                  f"{p['p50']['total_return']:.1f}% / "
                  f"{p['p95']['total_return']:.1f}%")
            print(f"  MC ruin prob  : {mc['ruin_probability']:.1f}%")

        # Monkey Test
        mt = run_monkey_test(ohlcv, strategy_return=s["total_return_pct"],
                             simulations=1000, seed=42)
        print(f"  Monkey rank   : {mt['percentile_rank']:.1f}th pct  "
              f"p={mt['p_value']:.3f}  "
              f"sig={'YES' if mt['significant'] else 'NO'}")

    print("\n" + "=" * 55)
    print("Done.")


if __name__ == "__main__":
    main()
