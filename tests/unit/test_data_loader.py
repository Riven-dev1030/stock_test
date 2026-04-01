"""
Unit tests for core/data_loader.py
Covers acceptance criteria: DAT-06, DAT-07, DAT-08
"""
import csv
import os
import sys
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from core.data_loader import load_from_csv


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _write_csv(path: str, header: list, rows: list):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# DAT-06: Standard CSV with lowercase headers loads correctly
# ---------------------------------------------------------------------------
class TestDAT06:
    def test_standard_csv_parses_correctly(self, tmp_path):
        path = tmp_path / "standard.csv"
        header = ["date", "open", "high", "low", "close", "volume"]
        rows = [
            ["2026-01-01", "100.00", "105.00", "98.00",  "103.00", "10000"],
            ["2026-01-02", "103.00", "108.00", "101.00", "106.50", "12000"],
        ]
        _write_csv(str(path), header, rows)

        bars = load_from_csv(str(path))

        assert len(bars) == 2
        assert bars[0]["date"]   == "2026-01-01"
        assert bars[0]["open"]   == 100.00
        assert bars[0]["high"]   == 105.00
        assert bars[0]["low"]    == 98.00
        assert bars[0]["close"]  == 103.00
        assert bars[0]["volume"] == 10000
        assert bars[1]["close"]  == 106.50
        assert bars[1]["volume"] == 12000

    def test_case_insensitive_standard_headers(self, tmp_path):
        """Header names should be matched case-insensitively."""
        path = tmp_path / "mixed_case.csv"
        header = ["Date", "Open", "High", "Low", "Close", "Volume"]
        rows = [["2026-01-01", "100.0", "105.0", "98.0", "103.0", "10000"]]
        _write_csv(str(path), header, rows)

        bars = load_from_csv(str(path))
        assert len(bars) == 1
        assert bars[0]["open"] == 100.0


# ---------------------------------------------------------------------------
# DAT-07: CSV with non-standard column names
# ---------------------------------------------------------------------------
class TestDAT07:
    def test_vol_alias_loads_via_default_mapping(self, tmp_path):
        """'Vol' should map to 'volume' via the built-in alias list."""
        path = tmp_path / "vol_alias.csv"
        header = ["date", "open", "high", "low", "close", "Vol"]
        rows = [["2026-01-01", "100.0", "105.0", "98.0", "103.0", "9999"]]
        _write_csv(str(path), header, rows)

        bars = load_from_csv(str(path))
        assert bars[0]["volume"] == 9999

    def test_custom_mapping_loads_unknown_column(self, tmp_path):
        """A completely non-standard column can be loaded via a custom mapping."""
        path = tmp_path / "custom.csv"
        header = ["date", "open", "high", "low", "close", "TotalVol"]
        rows = [["2026-01-01", "100.0", "105.0", "98.0", "103.0", "5000"]]
        _write_csv(str(path), header, rows)

        custom_map = {
            "date":   ["date"],
            "open":   ["open"],
            "high":   ["high"],
            "low":    ["low"],
            "close":  ["close"],
            "volume": ["totalvol"],
        }
        bars = load_from_csv(str(path), column_mapping=custom_map)
        assert bars[0]["volume"] == 5000

    def test_unknown_column_raises_clear_error(self, tmp_path):
        """Completely unrecognised volume column → ValueError naming missing field."""
        path = tmp_path / "unknown_col.csv"
        header = ["date", "open", "high", "low", "close", "XYZ_volume_unknown"]
        rows = [["2026-01-01", "100.0", "105.0", "98.0", "103.0", "10000"]]
        _write_csv(str(path), header, rows)

        with pytest.raises(ValueError, match="Missing required columns"):
            load_from_csv(str(path))


# ---------------------------------------------------------------------------
# DAT-08: CSV with missing values raises a clear error naming the bad rows
# ---------------------------------------------------------------------------
class TestDAT08:
    def test_missing_value_raises_with_row_info(self, tmp_path):
        path = tmp_path / "missing.csv"
        header = ["date", "open", "high", "low", "close", "volume"]
        rows = [
            ["2026-01-01", "100.0", "105.0", "98.0", "103.0", "10000"],  # row 2 OK
            ["2026-01-02", "",      "108.0", "101.0", "106.0", "12000"],  # row 3 missing open
            ["2026-01-03", "106.0", "110.0", "104.0", "108.0", ""],       # row 4 missing volume
        ]
        _write_csv(str(path), header, rows)

        with pytest.raises(ValueError) as exc_info:
            load_from_csv(str(path))

        error_msg = str(exc_info.value)
        # Message must mention at least one of the problematic rows
        assert "row 3" in error_msg or "row 4" in error_msg, \
            f"Error should mention row numbers, got: {error_msg}"

    def test_missing_value_does_not_silently_produce_data(self, tmp_path):
        """Rows with missing values must NOT be silently included in output."""
        path = tmp_path / "silent.csv"
        header = ["date", "open", "high", "low", "close", "volume"]
        rows = [
            ["2026-01-01", "100.0", "105.0", "98.0", "103.0", "10000"],
            ["2026-01-02", "",      "108.0", "101.0", "106.0", "12000"],
        ]
        _write_csv(str(path), header, rows)

        with pytest.raises(ValueError):
            load_from_csv(str(path))
