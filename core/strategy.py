"""
core/strategy.py — Strategy definition, validation, and condition dispatch.

Supports declarative JSON-based strategy configs with built-in conditions
and a CustomCondition interface for user extensions.
"""
import json

from core.indicators import sma, atr, volume_ma, highest_high, lowest_low

# ---------------------------------------------------------------------------
# Supported condition types
# ---------------------------------------------------------------------------
ENTRY_CONDITION_TYPES = {
    "breakout", "volume_above_ma", "ma_alignment", "price_above_ma", "pattern",
}
EXIT_CONDITION_TYPES = {
    "atr_stop", "ma_stop", "trailing_stop", "fixed_stop", "time_stop",
}
ALL_CONDITION_TYPES = ENTRY_CONDITION_TYPES | EXIT_CONDITION_TYPES

REQUIRED_STRATEGY_KEYS = {"name", "entry", "exit"}
REQUIRED_ENTRY_KEYS    = {"mode", "conditions"}
REQUIRED_EXIT_KEYS     = {"mode", "conditions"}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate_strategy(config: dict) -> None:
    """
    Validate a strategy config dict.

    Raises:
        ValueError: with a descriptive message if validation fails.
    """
    missing_top = REQUIRED_STRATEGY_KEYS - set(config.keys())
    if missing_top:
        raise ValueError(f"Strategy config missing required keys: {sorted(missing_top)}")

    for section in ("entry", "exit"):
        section_keys = REQUIRED_ENTRY_KEYS if section == "entry" else REQUIRED_EXIT_KEYS
        missing = section_keys - set(config[section].keys())
        if missing:
            raise ValueError(
                f"Strategy config['{section}'] missing required keys: {sorted(missing)}"
            )
        for i, cond in enumerate(config[section]["conditions"]):
            if "type" not in cond:
                raise ValueError(
                    f"Strategy config['{section}']['conditions'][{i}] missing 'type'"
                )
            ctype = cond["type"]
            if ctype not in ALL_CONDITION_TYPES:
                raise ValueError(
                    f"Unsupported condition type '{ctype}' in '{section}'. "
                    f"Supported types: {sorted(ALL_CONDITION_TYPES)}"
                )


def load_strategy(path: str) -> dict:
    """Load and validate a strategy config from a JSON file."""
    with open(path, encoding="utf-8") as f:
        config = json.load(f)
    validate_strategy(config)
    return config


# ---------------------------------------------------------------------------
# Indicator pre-computation helper
# ---------------------------------------------------------------------------
def compute_indicators(ohlcv: list, config: dict) -> dict:
    """
    Pre-compute all indicators needed by the strategy.

    Returns a dict of named indicator arrays, each the same length as ohlcv.
    """
    closes  = [b["close"]  for b in ohlcv]
    highs   = [b["high"]   for b in ohlcv]
    lows    = [b["low"]    for b in ohlcv]
    volumes = [b["volume"] for b in ohlcv]

    ind = {}

    # Collect all unique periods needed
    sma_periods    = set()
    atr_periods    = set()
    volma_periods  = set()
    hh_periods     = set()

    all_conditions = (
        config["entry"]["conditions"] + config["exit"]["conditions"]
    )

    for cond in all_conditions:
        p = cond.get("params", {})
        t = cond["type"]
        if t in ("ma_alignment", "ma_stop"):
            sma_periods.add(p.get("fast", 20))
            sma_periods.add(p.get("slow", 50))
        if t == "price_above_ma":
            sma_periods.add(p.get("period", 20))
        if t == "atr_stop":
            atr_periods.add(p.get("period", 14))
        if t == "volume_above_ma":
            volma_periods.add(p.get("period", 20))
            sma_periods.add(p.get("period", 20))  # also need SMA for entry condition display
        if t == "breakout":
            hh_periods.add(p.get("period", 20))

    for period in sma_periods:
        ind[f"sma_{period}"] = sma(closes, period)

    for period in atr_periods:
        ind[f"atr_{period}"] = atr(ohlcv, period)

    for period in volma_periods:
        ind[f"volume_ma_{period}"] = volume_ma(volumes, period)

    for period in hh_periods:
        ind[f"highest_high_{period}"] = highest_high(highs, period)

    return ind


# ---------------------------------------------------------------------------
# Built-in condition checkers
# ---------------------------------------------------------------------------
def check_breakout(ohlcv: list, index: int, ind: dict, params: dict) -> dict:
    period = params.get("period", 20)
    field  = params.get("field", "high")
    hh_key = f"highest_high_{period}"

    hh_val = ind.get(hh_key, [None] * len(ohlcv))
    if index < period or hh_val[index - 1] is None:
        return {"result": False, "detail": "insufficient_data"}

    # Breakout: current close > previous N-period highest high
    prev_hh = hh_val[index - 1]
    current = ohlcv[index]["close"]
    result  = current > prev_hh
    return {
        "result": result,
        "detail": f"close {current} {'>' if result else '<='} highest_{field}_{period}[prev] {prev_hh}",
    }


def check_volume_above_ma(ohlcv: list, index: int, ind: dict, params: dict) -> dict:
    multiplier = params.get("multiplier", 1.5)
    period     = params.get("period", 20)
    vma_key    = f"volume_ma_{period}"

    vma_arr = ind.get(vma_key, [None] * len(ohlcv))
    vma_val = vma_arr[index] if index < len(vma_arr) else None

    if vma_val is None:
        return {"result": False, "detail": "insufficient_data"}

    vol     = ohlcv[index]["volume"]
    thresh  = vma_val * multiplier
    result  = vol >= thresh
    return {
        "result": result,
        "detail": f"vol {vol} {'>=' if result else '<'} {vma_val:.0f}x{multiplier}={thresh:.0f}",
    }


def check_ma_alignment(ohlcv: list, index: int, ind: dict, params: dict) -> dict:
    fast      = params.get("fast", 20)
    slow      = params.get("slow", 50)
    direction = params.get("direction", "bullish")

    fast_arr = ind.get(f"sma_{fast}", [None] * len(ohlcv))
    slow_arr = ind.get(f"sma_{slow}", [None] * len(ohlcv))

    fv = fast_arr[index] if index < len(fast_arr) else None
    sv = slow_arr[index] if index < len(slow_arr) else None

    if fv is None or sv is None:
        return {"result": False, "detail": "insufficient_data"}

    if direction == "bullish":
        result = fv > sv
    else:
        result = fv < sv

    return {
        "result": result,
        "detail": f"sma_{fast} {fv:.4f} {'>' if direction=='bullish' else '<'} sma_{slow} {sv:.4f}",
    }


def check_price_above_ma(ohlcv: list, index: int, ind: dict, params: dict) -> dict:
    period    = params.get("period", 20)
    direction = params.get("direction", "above")
    sma_key   = f"sma_{period}"

    sma_arr = ind.get(sma_key, [None] * len(ohlcv))
    sv      = sma_arr[index] if index < len(sma_arr) else None

    if sv is None:
        return {"result": False, "detail": "insufficient_data"}

    price  = ohlcv[index]["close"]
    result = price > sv if direction != "below" else price < sv
    return {
        "result": result,
        "detail": f"close {price} {'>' if direction!='below' else '<'} sma_{period} {sv:.4f}",
    }


def check_atr_stop(ohlcv: list, index: int, ind: dict, params: dict,
                   position: dict) -> dict:
    multiplier = params.get("multiplier", 3)
    period     = params.get("period", 14)
    atr_key    = f"atr_{period}"

    atr_arr  = ind.get(atr_key, [None] * len(ohlcv))
    atr_val  = atr_arr[index] if index < len(atr_arr) else None

    if atr_val is None or position is None:
        return {"triggered": False, "detail": "insufficient_data",
                "stop_price": None, "distance_pct": None}

    entry_price = position["entry_price"]
    stop_price  = entry_price - multiplier * atr_val
    current     = ohlcv[index]["close"]
    triggered   = current <= stop_price
    distance_pct = (current - stop_price) / current * 100 if current > 0 else 0

    return {
        "triggered":    triggered,
        "stop_price":   round(stop_price, 4),
        "distance_pct": round(distance_pct, 4),
        "detail":       f"close {current} {'<=' if triggered else '>'} stop {stop_price:.4f}",
    }


def check_ma_stop(ohlcv: list, index: int, ind: dict, params: dict,
                  position: dict) -> dict:
    fast = params.get("fast", 20)
    slow = params.get("slow", 50)

    fast_arr = ind.get(f"sma_{fast}", [None] * len(ohlcv))
    slow_arr = ind.get(f"sma_{slow}", [None] * len(ohlcv))

    if index < 1:
        return {"triggered": False, "detail": "insufficient_data"}

    fv_curr = fast_arr[index]     if index < len(fast_arr) else None
    sv_curr = slow_arr[index]     if index < len(slow_arr) else None
    fv_prev = fast_arr[index - 1] if index - 1 < len(fast_arr) else None
    sv_prev = slow_arr[index - 1] if index - 1 < len(slow_arr) else None

    if any(v is None for v in (fv_curr, sv_curr, fv_prev, sv_prev)):
        return {"triggered": False, "detail": "insufficient_data"}

    # Triggered when fast MA crosses below slow MA AND price < fast MA
    cross_down = fv_prev >= sv_prev and fv_curr < sv_curr
    price      = ohlcv[index]["close"]
    below_fast = price < fv_curr
    triggered  = cross_down and below_fast

    return {
        "triggered": triggered,
        "detail":    (
            f"sma_{fast}[prev]={fv_prev:.4f} sma_{slow}[prev]={sv_prev:.4f} → "
            f"sma_{fast}[curr]={fv_curr:.4f} sma_{slow}[curr]={sv_curr:.4f}, "
            f"cross_down={cross_down}, price_below_fast={below_fast}"
        ),
    }


def check_trailing_stop(ohlcv: list, index: int, ind: dict, params: dict,
                        position: dict) -> dict:
    activation_pct = params.get("activation_pct", 15)   # % gain to activate
    trail_pct      = params.get("trail_pct", 97)         # trail price = peak * trail_pct/100

    if position is None:
        return {"triggered": False, "active": False, "trail_price": None,
                "distance_pct": None, "detail": "no position"}

    entry_price = position["entry_price"]
    peak_price  = position.get("peak_price", entry_price)
    current     = ohlcv[index]["close"]

    gain_from_entry = (peak_price - entry_price) / entry_price * 100
    active          = gain_from_entry >= activation_pct
    trail_price     = peak_price * (trail_pct / 100) if active else None
    triggered       = active and current <= trail_price
    distance_pct    = (
        (current - trail_price) / current * 100
        if trail_price is not None and current > 0 else None
    )

    return {
        "triggered":    triggered,
        "active":       active,
        "trail_price":  round(trail_price, 4) if trail_price is not None else None,
        "distance_pct": round(distance_pct, 4) if distance_pct is not None else None,
        "detail":       (
            f"peak={peak_price}, gain={gain_from_entry:.2f}%, "
            f"active={active}, trail={trail_price}, current={current}"
        ),
    }


def check_fixed_stop(ohlcv: list, index: int, ind: dict, params: dict,
                     position: dict) -> dict:
    stop_pct = params.get("stop_pct", 5)

    if position is None:
        return {"triggered": False, "detail": "no position"}

    entry_price = position["entry_price"]
    stop_price  = entry_price * (1 - stop_pct / 100)
    current     = ohlcv[index]["close"]
    triggered   = current <= stop_price

    return {
        "triggered":  triggered,
        "stop_price": round(stop_price, 4),
        "detail":     f"close {current} {'<=' if triggered else '>'} stop {stop_price:.4f}",
    }


def check_time_stop(ohlcv: list, index: int, ind: dict, params: dict,
                    position: dict) -> dict:
    max_days = params.get("max_days", 20)

    if position is None:
        return {"triggered": False, "detail": "no position"}

    bars_held = position.get("bars_held", 0)
    triggered = bars_held >= max_days

    return {
        "triggered": triggered,
        "detail":    f"bars_held={bars_held}, max_days={max_days}",
    }


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------
ENTRY_CHECKERS = {
    "breakout":        check_breakout,
    "volume_above_ma": check_volume_above_ma,
    "ma_alignment":    check_ma_alignment,
    "price_above_ma":  check_price_above_ma,
}

EXIT_CHECKERS = {
    "atr_stop":      check_atr_stop,
    "ma_stop":       check_ma_stop,
    "trailing_stop": check_trailing_stop,
    "fixed_stop":    check_fixed_stop,
    "time_stop":     check_time_stop,
}


def evaluate_entry(ohlcv: list, index: int, ind: dict, config: dict,
                   custom_conditions: dict = None) -> dict:
    """
    Evaluate all entry conditions at the given index.

    Returns:
        {
          "triggered": bool,
          "conditions": {type: {result, detail}, ...}
        }
    """
    mode       = config["entry"]["mode"]  # "ALL" or "ANY"
    conditions = config["entry"]["conditions"]
    results    = {}
    custom     = custom_conditions or {}

    for cond in conditions:
        ctype  = cond["type"]
        params = cond.get("params", {})

        if ctype in custom:
            res = {"result": custom[ctype].check(ohlcv, index), "detail": "custom condition"}
        elif ctype in ENTRY_CHECKERS:
            res = ENTRY_CHECKERS[ctype](ohlcv, index, ind, params)
        elif ctype == "pattern":
            res = {"result": False, "detail": "pattern condition requires engine-level evaluation"}
        else:
            res = {"result": False, "detail": f"unknown type '{ctype}'"}

        results[ctype] = res

    values = [r["result"] for r in results.values()]
    if mode == "ALL":
        triggered = all(values)
    else:
        triggered = any(values)

    return {"triggered": triggered, "conditions": results}


def evaluate_exit(ohlcv: list, index: int, ind: dict, config: dict,
                  position: dict, custom_conditions: dict = None) -> dict:
    """
    Evaluate all exit conditions at the given index.

    Returns:
        {
          "triggered": bool,
          "exit_reason": str | None,
          "conditions": {type: {...}, ...}
        }
    """
    mode       = config["exit"]["mode"]  # "ANY" or "ALL"
    conditions = config["exit"]["conditions"]
    results    = {}
    custom     = custom_conditions or {}
    exit_reason = None

    for cond in conditions:
        ctype  = cond["type"]
        params = cond.get("params", {})

        if ctype in custom:
            triggered = custom[ctype].check(ohlcv, index, position)
            res = {"triggered": triggered, "detail": "custom condition"}
        elif ctype in EXIT_CHECKERS:
            res = EXIT_CHECKERS[ctype](ohlcv, index, ind, params, position)
        else:
            res = {"triggered": False, "detail": f"unknown type '{ctype}'"}

        results[ctype] = res

    triggered_types = [ctype for ctype, r in results.items() if r.get("triggered")]

    if mode == "ANY":
        overall = len(triggered_types) > 0
        if triggered_types:
            exit_reason = triggered_types[0]  # first-triggered wins
    else:
        overall = len(triggered_types) == len(conditions)
        if overall:
            exit_reason = triggered_types[0]

    return {
        "triggered":   overall,
        "exit_reason": exit_reason,
        "conditions":  results,
    }


# ---------------------------------------------------------------------------
# Warmup period helper
# ---------------------------------------------------------------------------
def get_warmup_period(config: dict) -> int:
    """
    Return the minimum number of bars required before trading can begin.
    Derived from the slowest indicator period in the strategy config.
    """
    max_period = 0
    all_conditions = config["entry"]["conditions"] + config["exit"]["conditions"]

    for cond in all_conditions:
        p = cond.get("params", {})
        t = cond["type"]
        for key in ("period", "slow"):
            if key in p:
                max_period = max(max_period, p[key])

    return max_period
