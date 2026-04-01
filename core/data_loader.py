import csv
import json

REQUIRED_FIELDS = ["date", "open", "high", "low", "close", "volume"]

# Default aliases for each standard field name (case-insensitive matching)
DEFAULT_COLUMN_MAP = {
    "date":   ["date", "datetime", "time", "timestamp"],
    "open":   ["open", "o"],
    "high":   ["high", "h"],
    "low":    ["low", "l"],
    "close":  ["close", "c", "adj close", "adj_close"],
    "volume": ["volume", "vol", "v"],
}


def _build_header_mapping(headers: list, column_mapping: dict = None) -> dict:
    """
    Map each CSV header to a standard field name.

    Returns:
        dict: {csv_header -> standard_field_name}
    """
    effective_map = column_mapping or DEFAULT_COLUMN_MAP

    # Build reverse lookup: lowercase_alias -> standard_name
    reverse = {}
    for standard, aliases in effective_map.items():
        for alias in aliases:
            reverse[alias.lower()] = standard

    mapping = {}
    for header in headers:
        std = reverse.get(header.strip().lower())
        if std:
            mapping[header] = std

    return mapping


def load_from_csv(path: str, column_mapping: dict = None) -> list:
    """
    Load OHLCV data from a CSV file.

    Args:
        path:           Path to the CSV file.
        column_mapping: Optional override for column alias mapping.
                        Format: {"standard_field": ["alias1", "alias2", ...]}

    Returns:
        List of OHLCV dicts.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError:        If required columns are missing, or rows contain
                           empty / unparseable values.
    """
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        if not headers:
            raise ValueError("CSV file has no header row.")

        col_map = _build_header_mapping(list(headers), column_mapping)

        # Verify all required fields are covered
        mapped_standards = set(col_map.values())
        missing = [field for field in REQUIRED_FIELDS if field not in mapped_standards]
        if missing:
            raise ValueError(
                f"Missing required columns: {missing}. "
                f"Available columns: {list(headers)}"
            )

        # Invert: standard_name -> csv_header
        std_to_csv = {v: k for k, v in col_map.items()}

        bars = []
        problem_rows = []

        for row_num, row in enumerate(reader, start=2):  # row 1 = header
            empty_fields = []
            for field in REQUIRED_FIELDS:
                val = row.get(std_to_csv[field], "")
                if val is None or str(val).strip() == "":
                    empty_fields.append(field)

            if empty_fields:
                problem_rows.append(f"row {row_num}: missing values for {empty_fields}")
                continue

            try:
                bar = {
                    "date":   row[std_to_csv["date"]].strip(),
                    "open":   float(row[std_to_csv["open"]]),
                    "high":   float(row[std_to_csv["high"]]),
                    "low":    float(row[std_to_csv["low"]]),
                    "close":  float(row[std_to_csv["close"]]),
                    "volume": int(float(row[std_to_csv["volume"]])),
                }
                bars.append(bar)
            except (ValueError, KeyError) as exc:
                problem_rows.append(f"row {row_num}: parse error — {exc}")

        if problem_rows:
            raise ValueError(
                "CSV contains invalid data:\n" + "\n".join(problem_rows)
            )

        return bars


def load_from_json(path: str) -> list:
    """
    Load OHLCV data from a JSON file (list of objects).

    Raises:
        ValueError: If the file is not a list or items are missing required fields.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("JSON file must contain a top-level list of OHLCV objects.")

    for i, bar in enumerate(data):
        missing = [field for field in REQUIRED_FIELDS if field not in bar]
        if missing:
            raise ValueError(f"Item {i}: missing fields {missing}")

    return data


def load_from_api(endpoint: str, params: dict = None) -> list:
    """
    Load OHLCV data from an HTTP API endpoint.
    Requires the 'requests' package.
    """
    try:
        import requests
    except ImportError:
        raise ImportError(
            "'requests' package is required for API loading. "
            "Install with: pip install requests"
        )

    response = requests.get(endpoint, params=params or {})
    response.raise_for_status()
    return response.json()
