"""
main.py — Entry point for the OHLCV Strategy Backtester.

Usage:
    python main.py                          # run with default simulated data
    python main.py --csv path/to/data.csv   # run with real CSV data
    python main.py --strategy config/my_strategy.json
    python main.py --seed 42 --mode bull --bars 500
    python main.py --no-validation          # skip statistical validation
    python main.py --output results.json    # save output to file
    python main.py --compare                # compare 4 built-in strategies
    python main.py --compare --mode choppy  # compare on specific market mode
    python main.py --compare --bars 1000    # compare with more bars
"""
import argparse
import json
import sys
import os

from core.data_gen import generate
from core.data_loader import load_from_csv
from core.strategy import load_strategy, validate_strategy
from core.engine import run_backtest
from output.serializer import to_json, save_json
from output.summary import compute_summary
from output.slicer import build_slices
from core.strategy import compute_indicators, ALL_CONDITION_TYPES
from validation.monte_carlo import run_monte_carlo
from validation.monkey_test import run_monkey_test
from validation.overfit_detect import run_walk_forward

DEFAULT_STRATEGY_PATH = os.path.join(
    os.path.dirname(__file__), "config", "strategy_config.json"
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="OHLCV Strategy Backtester v1.0"
    )
    parser.add_argument("--csv",      type=str, default=None,
                        help="Path to CSV file (use real data instead of simulated)")
    parser.add_argument("--strategy", type=str, default=DEFAULT_STRATEGY_PATH,
                        help="Path to strategy JSON config")
    parser.add_argument("--seed",     type=int, default=42,
                        help="Random seed for simulated data")
    parser.add_argument("--mode",     type=str, default="bull",
                        choices=["random", "bull", "bear", "choppy", "diverge"],
                        help="Simulated market mode")
    parser.add_argument("--bars",     type=int, default=500,
                        help="Number of bars to simulate")
    parser.add_argument("--output",   type=str, default=None,
                        help="Save full backtest result to this JSON file")
    parser.add_argument("--no-validation", action="store_true",
                        help="Skip Monte Carlo, Monkey Test, and Walk-Forward")
    parser.add_argument("--mc-sims",  type=int, default=5000,
                        help="Number of Monte Carlo simulations")
    parser.add_argument("--mt-sims",  type=int, default=10000,
                        help="Number of Monkey Test simulations")
    parser.add_argument("--mc-seed",  type=int, default=0,
                        help="Seed for Monte Carlo / Monkey Test (0 = no seed)")
    parser.add_argument("--compare",   action="store_true",
                        help="Compare 4 built-in strategies side by side")
    parser.add_argument("--chart",     action="store_true",
                        help="Also generate a chart PNG after backtest (requires --output)")
    parser.add_argument("--to-image", type=str, default=None, metavar="RESULTS_JSON",
                        help="Convert a results JSON file to a chart PNG image")
    parser.add_argument("--image-out", type=str, default=None, metavar="OUTPUT_PNG",
                        help="Output path for chart image (default: same name as JSON, .png)")
    return parser.parse_args()


def run_compare(args):
    """Compare 4 built-in strategies across market modes."""
    from run_compare import (
        strategy_breakout, strategy_ma_crossover,
        strategy_rsi, strategy_momentum,
    )

    STRATEGIES = [
        ("Trend Breakout",  strategy_breakout),
        ("MA Crossover",    strategy_ma_crossover),
        ("RSI Rebound",     strategy_rsi),
        ("Momentum",        strategy_momentum),
    ]
    modes = [args.mode] if args.mode != "bull" else ["bull", "bear", "choppy", "random"]

    header = f"{'Strategy':<22} {'Mode':<8} {'#':<4} {'WR%':<7} {'Ret%':<9} {'DD%':<9} {'PF':<7} {'Sharpe':<7}"
    sep    = "-" * len(header)
    print("\n" + sep)
    print(header)
    print(sep)

    def fmt(val, suffix=""):
        return f"{val:.1f}{suffix}" if isinstance(val, float) else "—"

    for strat_name, strat_fn in STRATEGIES:
        for mode in modes:
            ohlcv          = generate(n=args.bars, mode=mode, seed=args.seed)
            config, custom = strat_fn()
            result         = run_backtest(ohlcv, config, custom_conditions=custom or None)
            result["summary"] = compute_summary(result["trades"])
            s              = result["summary"]
            pf             = fmt(s["profit_factor"]) if isinstance(s["profit_factor"], float) else str(s["profit_factor"])
            print(
                f"{strat_name:<22} {mode:<8} "
                f"{s['total_trades']:<4} "
                f"{fmt(s['win_rate'], '%'):<7} "
                f"{fmt(s['total_return_pct'], '%'):<9} "
                f"{fmt(s['max_drawdown_pct'], '%'):<9} "
                f"{pf:<7} "
                f"{fmt(s['sharpe_ratio']):<7}"
            )
        print(sep)

    ALL_CONDITION_TYPES.discard("rsi_entry")
    ALL_CONDITION_TYPES.discard("rsi_exit")


def main():
    args = parse_args()

    if args.compare:
        run_compare(args)
        return

    if args.to_image:
        from output.chart import chart_from_json
        out = chart_from_json(args.to_image, args.image_out)
        print(f"Chart saved to: {out}")
        return

    # ------------------------------------------------------------------
    # 1. Load data
    # ------------------------------------------------------------------
    if args.csv:
        print(f"[1/4] Loading data from CSV: {args.csv}")
        ohlcv = load_from_csv(args.csv)
        data_source = f"csv:{args.csv}"
    else:
        print(f"[1/4] Generating simulated data "
              f"(mode={args.mode}, bars={args.bars}, seed={args.seed})")
        ohlcv = generate(n=args.bars, mode=args.mode, seed=args.seed)
        data_source = f"simulated:{args.mode}"

    print(f"      Loaded {len(ohlcv)} bars "
          f"({ohlcv[0]['date']} → {ohlcv[-1]['date']})")

    # ------------------------------------------------------------------
    # 2. Load strategy
    # ------------------------------------------------------------------
    print(f"[2/4] Loading strategy from: {args.strategy}")
    config = load_strategy(args.strategy)
    print(f"      Strategy: {config['name']}")

    # ------------------------------------------------------------------
    # 3. Run backtest
    # ------------------------------------------------------------------
    print("[3/4] Running backtest...")
    result = run_backtest(ohlcv, config)
    result["metadata"]["data_source"] = data_source
    result["summary"] = compute_summary(result["trades"])

    summary = result["summary"]
    trades  = result["trades"]

    print(f"      Trades:        {summary['total_trades']}")
    print(f"      Win rate:      {summary['win_rate']:.1f}%")
    print(f"      Total return:  {summary['total_return_pct']:.2f}%")
    print(f"      Max drawdown:  {summary['max_drawdown_pct']:.2f}%")
    print(f"      Profit factor: {summary['profit_factor']}")
    print(f"      Sharpe ratio:  {summary['sharpe_ratio']:.2f}")

    # ------------------------------------------------------------------
    # 4. Statistical validation
    # ------------------------------------------------------------------
    mc_result = None
    mt_result = None
    wf_result = None

    if not args.no_validation and trades:
        print("[4/4] Running statistical validation...")

        mc_seed = args.mc_seed if args.mc_seed != 0 else None

        mc_result = run_monte_carlo(
            trades, simulations=args.mc_sims, seed=mc_seed
        )
        print(f"      Monte Carlo p50 return: "
              f"{mc_result['percentiles']['p50']['total_return']:.2f}%  "
              f"ruin prob: {mc_result['ruin_probability']:.1f}%")

        mt_result = run_monkey_test(
            ohlcv, strategy_return=summary["total_return_pct"],
            simulations=args.mt_sims, seed=mc_seed
        )
        print(f"      Monkey Test rank: {mt_result['percentile_rank']:.1f}th percentile  "
              f"p-value: {mt_result['p_value']:.3f}  "
              f"significant: {mt_result['significant']}")

        wf_result = run_walk_forward(ohlcv, config)
        print(f"      Walk-Forward folds: {len(wf_result['folds'])}  "
              f"degradation: {wf_result['degradation_ratio']}  "
              f"overfit warning: {wf_result['overfit_warning']}")
    elif not trades:
        print("[4/4] Skipping validation — no trades generated.")
    else:
        print("[4/4] Validation skipped (--no-validation).")

    # ------------------------------------------------------------------
    # 5. AI Diagnostic Slices
    # ------------------------------------------------------------------
    if trades:
        ind    = compute_indicators(ohlcv, config)
        slices = build_slices(
            trades, ohlcv, result["scan_log"], ind,
            top_n=3, criteria="worst_pnl", context_bars=15
        )
        result["ai_diagnostic_slices"] = slices

    # ------------------------------------------------------------------
    # 6. Attach validation results and output
    # ------------------------------------------------------------------
    result["validation"] = {
        "monte_carlo":      mc_result,
        "monkey_test":      mt_result,
        "walk_forward":     wf_result,
    }

    if args.output:
        save_json(result, args.output)
        print(f"\nFull results saved to: {args.output}")
        if args.chart:
            from output.chart import generate_chart
            img_path = os.path.splitext(args.output)[0] + ".png"
            generate_chart(result, img_path)
            print(f"Chart saved to:        {img_path}")
    else:
        print("\n--- JSON Output (truncated scan_log) ---")
        # Print without the full scan_log to keep output manageable
        display = {k: v for k, v in result.items() if k != "scan_log"}
        display["scan_log"] = f"[{len(result['scan_log'])} entries — omitted for display]"
        print(to_json(display))

    return result


if __name__ == "__main__":
    main()
