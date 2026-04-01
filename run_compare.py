"""
run_compare.py — Strategy Comparison across 4 modes

Strategies:
  1. Trend Following Breakout  (breakout + volume + MA alignment)
  2. Double MA Crossover       (SMA20 > SMA50 + price above SMA20)
  3. RSI Oversold Rebound      (RSI-14 < 30 entry, RSI > 50 exit)
  4. Momentum                  (N-day high breakout, trailing stop)
"""
import json, math
from core.data_gen   import generate
from core.engine     import run_backtest
from core.strategy   import ALL_CONDITION_TYPES
from core.indicators import sma
from output.summary  import compute_summary


# ---------------------------------------------------------------------------
# Custom RSI condition
# ---------------------------------------------------------------------------
def _calc_rsi(ohlcv, period=14):
    closes = [b["close"] for b in ohlcv]
    rsi    = [None] * len(closes)
    if len(closes) < period + 1:
        return rsi

    gains  = [max(closes[i] - closes[i-1], 0) for i in range(1, len(closes))]
    losses = [max(closes[i-1] - closes[i], 0) for i in range(1, len(closes))]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(closes)):
        if avg_loss == 0:
            rsi[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100 - (100 / (1 + rs))
        if i < len(closes) - 1:
            g = gains[i]
            l = losses[i]
            avg_gain = (avg_gain * (period - 1) + g) / period
            avg_loss = (avg_loss * (period - 1) + l) / period

    return rsi


class RSIEntry:
    """Enter when RSI-14 drops below threshold."""
    def __init__(self, params):
        self.period    = params.get("period", 14)
        self.threshold = params.get("threshold", 30)
        self._rsi_cache = {}

    def check(self, ohlcv, index, position=None):
        key = id(ohlcv)
        if key not in self._rsi_cache:
            self._rsi_cache[key] = _calc_rsi(ohlcv, self.period)
        rsi = self._rsi_cache[key]
        val = rsi[index] if index < len(rsi) else None
        return val is not None and val < self.threshold


class RSIExit:
    """Exit when RSI-14 rises above threshold."""
    def __init__(self, params):
        self.period    = params.get("period", 14)
        self.threshold = params.get("threshold", 50)
        self._rsi_cache = {}

    def check(self, ohlcv, index, position=None):
        key = id(ohlcv)
        if key not in self._rsi_cache:
            self._rsi_cache[key] = _calc_rsi(ohlcv, self.period)
        rsi = self._rsi_cache[key]
        val = rsi[index] if index < len(rsi) else None
        return val is not None and val > self.threshold


# ---------------------------------------------------------------------------
# Strategy definitions
# ---------------------------------------------------------------------------
def strategy_breakout():
    with open("config/strategy_config.json") as f:
        config = json.load(f)
    return config, {}


def strategy_ma_crossover():
    config = {
        "name": "Double MA Crossover",
        "entry": {"mode": "ALL", "conditions": [
            {"type": "ma_alignment",   "params": {"fast": 20, "slow": 50, "direction": "bullish"}},
            {"type": "price_above_ma", "params": {"period": 20}},
        ]},
        "exit": {"mode": "ANY", "conditions": [
            {"type": "ma_stop",    "params": {"fast": 20, "slow": 50}},
            {"type": "atr_stop",   "params": {"multiplier": 3, "period": 14}},
        ]},
    }
    return config, {}


def strategy_rsi():
    ALL_CONDITION_TYPES.add("rsi_entry")
    ALL_CONDITION_TYPES.add("rsi_exit")
    config = {
        "name": "RSI Oversold Rebound",
        "entry": {"mode": "ALL", "conditions": [
            {"type": "rsi_entry", "params": {"period": 14, "threshold": 30}},
        ]},
        "exit": {"mode": "ANY", "conditions": [
            {"type": "rsi_exit",  "params": {"period": 14, "threshold": 50}},
            {"type": "atr_stop",  "params": {"multiplier": 2, "period": 14}},
            {"type": "time_stop", "params": {"max_days": 30}},
        ]},
    }
    custom = {
        "rsi_entry": RSIEntry({"period": 14, "threshold": 30}),
        "rsi_exit":  RSIExit({"period": 14, "threshold": 50}),
    }
    return config, custom


def strategy_momentum():
    config = {
        "name": "Momentum (N-day High)",
        "entry": {"mode": "ALL", "conditions": [
            {"type": "breakout",       "params": {"period": 20, "field": "high"}},
            {"type": "price_above_ma", "params": {"period": 50}},
        ]},
        "exit": {"mode": "ANY", "conditions": [
            {"type": "trailing_stop", "params": {"activation_pct": 8, "trail_pct": 96}},
            {"type": "atr_stop",      "params": {"multiplier": 2, "period": 14}},
        ]},
    }
    return config, {}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
STRATEGIES = [
    ("Trend Breakout",    strategy_breakout),
    ("MA Crossover",      strategy_ma_crossover),
    ("RSI Rebound",       strategy_rsi),
    ("Momentum",          strategy_momentum),
]
MODES = ["bull", "bear", "choppy", "random"]


def run_one(config, custom, ohlcv):
    result = run_backtest(ohlcv, config, custom_conditions=custom or None)
    result["summary"] = compute_summary(result["trades"])
    return result["summary"]


def fmt(val, suffix="", none_str="—"):
    if val is None:
        return none_str
    return f"{val:.1f}{suffix}"


def main():
    header = f"{'Strategy':<22} {'Mode':<8} {'#':<4} {'WR%':<7} {'Ret%':<9} {'DD%':<9} {'PF':<7} {'Sharpe':<8}"
    sep    = "-" * len(header)

    print("\n" + sep)
    print(header)
    print(sep)

    for strat_name, strat_fn in STRATEGIES:
        for mode in MODES:
            ohlcv         = generate(n=500, mode=mode, seed=42)
            config, custom = strat_fn()
            s             = run_one(config, custom, ohlcv)

            pf = fmt(s["profit_factor"]) if isinstance(s["profit_factor"], float) else str(s["profit_factor"])

            print(
                f"{strat_name:<22} {mode:<8} "
                f"{s['total_trades']:<4} "
                f"{fmt(s['win_rate'], '%'):<7} "
                f"{fmt(s['total_return_pct'], '%'):<9} "
                f"{fmt(s['max_drawdown_pct'], '%'):<9} "
                f"{pf:<7} "
                f"{fmt(s['sharpe_ratio']):<8}"
            )
        print(sep)

    ALL_CONDITION_TYPES.discard("rsi_entry")
    ALL_CONDITION_TYPES.discard("rsi_exit")


if __name__ == "__main__":
    main()
