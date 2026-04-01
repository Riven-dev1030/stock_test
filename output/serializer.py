"""
output/serializer.py — Serialize backtest results to JSON.
"""
import json


def to_json(result: dict, indent: int = 2) -> str:
    """
    Serialize a backtest result dict to a JSON string.

    Args:
        result: The dict returned by engine.run_backtest() (with summary attached).
        indent: JSON indentation level.

    Returns:
        A valid JSON string.
    """
    return json.dumps(result, ensure_ascii=False, indent=indent)


def save_json(result: dict, path: str, indent: int = 2) -> None:
    """Write a backtest result dict to a JSON file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=indent)


def load_json(path: str) -> dict:
    """Load a backtest result dict from a JSON file."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)
