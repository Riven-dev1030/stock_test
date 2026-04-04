"""
output/chart.py — Generate a summary chart image from backtest results.

Produces a single PNG with 4 panels:
  1. Equity curve (cumulative PnL %)
  2. Per-trade PnL bar chart
  3. Summary stats table
  4. Exit reason breakdown (horizontal bar)
"""

import json
import os


def generate_chart(result: dict, output_path: str) -> str:
    """
    Generate a chart PNG from a backtest result dict.

    Args:
        result:      Backtest result dict (from run_backtest + compute_summary).
        output_path: Path to save the PNG file.

    Returns:
        Absolute path to the saved PNG.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    from matplotlib.patches import FancyBboxPatch

    DARK_BG    = "#1a1a2e"
    PANEL_BG   = "#16213e"
    ACCENT     = "#e94560"
    GREEN      = "#00c853"
    TEXT       = "#e0e0e0"
    SUBTEXT    = "#888888"
    GRID_COLOR = "#0f3460"

    trades   = result.get("trades", [])
    summary  = result.get("summary") or {}
    metadata = result.get("metadata", {})

    strategy_name = metadata.get("strategy_name", "Strategy")
    date_start    = (metadata.get("data_range") or {}).get("start", "")
    date_end      = (metadata.get("data_range") or {}).get("end", "")

    # ----------------------------------------------------------------
    # Figure layout
    # ----------------------------------------------------------------
    fig = plt.figure(figsize=(14, 10), facecolor=DARK_BG)
    gs  = gridspec.GridSpec(
        3, 2,
        figure=fig,
        hspace=0.45, wspace=0.35,
        left=0.07, right=0.96, top=0.90, bottom=0.07,
    )

    ax_equity  = fig.add_subplot(gs[0, :])   # row 0, full width
    ax_trades  = fig.add_subplot(gs[1, 0])   # row 1 left
    ax_exit    = fig.add_subplot(gs[1, 1])   # row 1 right
    ax_stats   = fig.add_subplot(gs[2, :])   # row 2, full width

    for ax in (ax_equity, ax_trades, ax_exit, ax_stats):
        ax.set_facecolor(PANEL_BG)
        ax.tick_params(colors=TEXT, labelsize=9)
        for spine in ax.spines.values():
            spine.set_edgecolor(GRID_COLOR)

    # ----------------------------------------------------------------
    # Title
    # ----------------------------------------------------------------
    fig.text(
        0.5, 0.955,
        f"{strategy_name}   |   {date_start} → {date_end}",
        ha="center", va="center",
        fontsize=14, fontweight="bold", color=TEXT,
    )

    # ----------------------------------------------------------------
    # Panel 1 — Equity curve
    # ----------------------------------------------------------------
    if trades:
        cum_pnl = []
        total   = 0.0
        for t in trades:
            total += t.get("pnl_pct", 0)
            cum_pnl.append(total)

        xs = list(range(1, len(cum_pnl) + 1))
        colors_line = [GREEN if v >= 0 else ACCENT for v in cum_pnl]

        ax_equity.plot(xs, cum_pnl, color=ACCENT, linewidth=1.5, zorder=2)
        ax_equity.fill_between(
            xs, cum_pnl, 0,
            where=[v >= 0 for v in cum_pnl],
            color=GREEN, alpha=0.15, zorder=1,
        )
        ax_equity.fill_between(
            xs, cum_pnl, 0,
            where=[v < 0 for v in cum_pnl],
            color=ACCENT, alpha=0.15, zorder=1,
        )
        ax_equity.axhline(0, color=SUBTEXT, linewidth=0.8, linestyle="--")
        ax_equity.scatter(xs, cum_pnl, c=colors_line, s=30, zorder=3)
    else:
        ax_equity.text(
            0.5, 0.5, "No trades", ha="center", va="center",
            color=SUBTEXT, fontsize=12, transform=ax_equity.transAxes,
        )

    ax_equity.set_title("Equity Curve (Cumulative PnL %)", color=TEXT, fontsize=10, pad=6)
    ax_equity.set_xlabel("Trade #", color=SUBTEXT, fontsize=8)
    ax_equity.set_ylabel("Cumulative PnL %", color=SUBTEXT, fontsize=8)
    ax_equity.grid(True, color=GRID_COLOR, linewidth=0.5, alpha=0.7)

    # ----------------------------------------------------------------
    # Panel 2 — Per-trade PnL bars
    # ----------------------------------------------------------------
    if trades:
        pnls   = [t.get("pnl_pct", 0) for t in trades]
        xs2    = list(range(1, len(pnls) + 1))
        bar_colors = [GREEN if p >= 0 else ACCENT for p in pnls]
        ax_trades.bar(xs2, pnls, color=bar_colors, width=0.7, zorder=2)
        ax_trades.axhline(0, color=SUBTEXT, linewidth=0.8, linestyle="--")
    else:
        ax_trades.text(
            0.5, 0.5, "No trades", ha="center", va="center",
            color=SUBTEXT, fontsize=10, transform=ax_trades.transAxes,
        )

    ax_trades.set_title("Per-trade PnL %", color=TEXT, fontsize=10, pad=6)
    ax_trades.set_xlabel("Trade #", color=SUBTEXT, fontsize=8)
    ax_trades.set_ylabel("PnL %", color=SUBTEXT, fontsize=8)
    ax_trades.grid(True, color=GRID_COLOR, linewidth=0.5, alpha=0.7, axis="y")

    # ----------------------------------------------------------------
    # Panel 3 — Exit reason breakdown
    # ----------------------------------------------------------------
    exit_bd = summary.get("exit_reason_breakdown") or {}
    if exit_bd:
        labels = list(exit_bd.keys())
        values = list(exit_bd.values())
        total_v = sum(values) or 1
        pcts   = [v / total_v * 100 for v in values]
        ys     = list(range(len(labels)))
        bar_c  = [ACCENT, "#e9a046", "#46b4e9", "#a046e9", GREEN]
        ax_exit.barh(
            ys, pcts,
            color=[bar_c[i % len(bar_c)] for i in range(len(labels))],
            height=0.6, zorder=2,
        )
        ax_exit.set_yticks(ys)
        ax_exit.set_yticklabels(labels, color=TEXT, fontsize=8)
        for i, (p, v) in enumerate(zip(pcts, values)):
            ax_exit.text(p + 0.5, i, f"{v} ({p:.0f}%)", va="center",
                         color=TEXT, fontsize=8)
    else:
        ax_exit.text(
            0.5, 0.5, "No data", ha="center", va="center",
            color=SUBTEXT, fontsize=10, transform=ax_exit.transAxes,
        )

    ax_exit.set_title("Exit Reason Breakdown", color=TEXT, fontsize=10, pad=6)
    ax_exit.set_xlabel("% of trades", color=SUBTEXT, fontsize=8)
    ax_exit.grid(True, color=GRID_COLOR, linewidth=0.5, alpha=0.7, axis="x")

    # ----------------------------------------------------------------
    # Panel 4 — Stats table
    # ----------------------------------------------------------------
    ax_stats.axis("off")

    def _fmt(key, suffix="", none_str="—"):
        v = summary.get(key)
        if v is None:
            return none_str
        if isinstance(v, float):
            return f"{v:.2f}{suffix}"
        return f"{v}{suffix}"

    stats = [
        ("Total Trades",      str(summary.get("total_trades", 0))),
        ("Win Rate",          _fmt("win_rate", "%")),
        ("Total Return",      _fmt("total_return_pct", "%")),
        ("Max Drawdown",      _fmt("max_drawdown_pct", "%")),
        ("Profit Factor",     _fmt("profit_factor")),
        ("Sharpe Ratio",      _fmt("sharpe_ratio")),
        ("Expectancy",        _fmt("expectancy_pct", "%")),
        ("Avg Bars Held",     _fmt("avg_bars_held")),
        ("Avg Win",           _fmt("avg_win_pct", "%")),
        ("Avg Loss",          _fmt("avg_loss_pct", "%")),
        ("Max Consec. Wins",  str(summary.get("max_consecutive_wins", "—"))),
        ("Max Consec. Losses",str(summary.get("max_consecutive_losses", "—"))),
    ]

    cols  = 4
    rows  = (len(stats) + cols - 1) // cols
    cell_w = 1.0 / cols
    cell_h = 1.0 / (rows + 0.5)

    ax_stats.set_title("Summary Statistics", color=TEXT, fontsize=10, pad=6)

    for idx, (label, value) in enumerate(stats):
        col = idx % cols
        row = idx // cols
        x   = col * cell_w + cell_w * 0.05
        y   = 1.0 - (row + 1) * cell_h

        ax_stats.text(x, y + cell_h * 0.35, label,
                      color=SUBTEXT, fontsize=8, transform=ax_stats.transAxes)

        # Color value based on content
        v_color = TEXT
        if "%" in value and value not in ("—", "0.00%"):
            try:
                num = float(value.replace("%", ""))
                if label in ("Max Drawdown", "Avg Loss"):
                    v_color = ACCENT if num < 0 else GREEN
                else:
                    v_color = GREEN if num > 0 else ACCENT
            except ValueError:
                pass

        ax_stats.text(x, y, value,
                      color=v_color, fontsize=11, fontweight="bold",
                      transform=ax_stats.transAxes)

    # ----------------------------------------------------------------
    # Save
    # ----------------------------------------------------------------
    output_path = os.path.abspath(output_path)
    fig.savefig(output_path, dpi=150, facecolor=DARK_BG, bbox_inches="tight")
    plt.close(fig)
    return output_path


def chart_from_json(json_path: str, output_path: str = None) -> str:
    """Load a results JSON file and generate a chart image."""
    with open(json_path, encoding="utf-8") as f:
        result = json.load(f)

    if output_path is None:
        base        = os.path.splitext(json_path)[0]
        output_path = base + ".png"

    return generate_chart(result, output_path)
