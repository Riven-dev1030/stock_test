"""
validation/overfit_detect.py — Overfitting Detection via Walk-Forward Analysis.

Splits the OHLCV data into rolling in-sample / out-of-sample windows
to detect whether strategy performance degrades significantly out-of-sample.
"""

from core.engine import run_backtest
from output.summary import compute_summary


def run_walk_forward(ohlcv: list, config: dict,
                     window_size: int = 100, step_size: int = 30,
                     overfit_threshold: float = 0.3) -> dict:
    """
    Walk-Forward Analysis.

    Args:
        ohlcv:              Full OHLCV list.
        config:             Strategy config dict.
        window_size:        Number of bars in the in-sample window.
        step_size:          Number of bars to advance between folds.
        overfit_threshold:  degradation_ratio below this value triggers overfit_warning.

    Returns:
        Walk-forward result dict as specified in SDD §5.3.
    """
    n     = len(ohlcv)
    folds = []
    fold_num = 1

    start = 0
    while start + window_size + step_size <= n:
        in_end   = start + window_size          # exclusive
        out_end  = min(in_end + step_size, n)   # exclusive

        in_sample_bars  = ohlcv[start:in_end]
        out_sample_bars = ohlcv[in_end:out_end]

        # Run backtest on each window with the same strategy config
        in_result  = run_backtest(in_sample_bars,  config)
        out_result = run_backtest(out_sample_bars, config)

        in_summary  = compute_summary(in_result["trades"])
        out_summary = compute_summary(out_result["trades"])

        folds.append({
            "fold": fold_num,
            "in_sample": {
                "start":       start,
                "end":         in_end - 1,
                "best_params": config.get("params", {}),
                "return":      round(in_summary["total_return_pct"], 4),
            },
            "out_of_sample": {
                "start":  in_end,
                "end":    out_end - 1,
                "return": round(out_summary["total_return_pct"], 4),
            },
        })

        start    += step_size
        fold_num += 1

    if not folds:
        return _empty_result(window_size, step_size)

    in_returns  = [f["in_sample"]["return"]      for f in folds]
    out_returns = [f["out_of_sample"]["return"]  for f in folds]

    in_avg  = sum(in_returns)  / len(in_returns)
    out_avg = sum(out_returns) / len(out_returns)

    degradation_ratio = out_avg / in_avg if in_avg != 0 else float("nan")
    overfit_warning   = (
        not isinstance(degradation_ratio, float) or
        degradation_ratio < overfit_threshold or
        (out_avg < 0 and in_avg > 0)
    )

    return {
        "method":                  "walk_forward",
        "window_size":             window_size,
        "step_size":               step_size,
        "folds":                   folds,
        "in_sample_avg_return":    round(in_avg,  4),
        "out_of_sample_avg_return": round(out_avg, 4),
        "degradation_ratio":       round(degradation_ratio, 4)
                                   if isinstance(degradation_ratio, float) else None,
        "overfit_warning":         overfit_warning,
    }


def _empty_result(window_size: int, step_size: int) -> dict:
    return {
        "method":                   "walk_forward",
        "window_size":              window_size,
        "step_size":                step_size,
        "folds":                    [],
        "in_sample_avg_return":     0.0,
        "out_of_sample_avg_return": 0.0,
        "degradation_ratio":        None,
        "overfit_warning":          False,
    }
