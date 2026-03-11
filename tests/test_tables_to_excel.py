"""Unit tests for tables_to_excel merge, clean, and validation logic. No PDF I/O."""

import pytest
from decimal import Decimal

from tables_to_excel import (
    _merge_fragmented_row,
    _clean_table_rows,
    _cell_value,
    validate_extraction_json,
)


class TestMergeFragmentedRow:
    """Tests for _merge_fragmented_row()."""

    def test_decimal_part_merge(self):
        # "15,088,442." + "61" -> one value
        out = _merge_fragmented_row(["15,088,442.", "61"])
        assert out == ["15,088,442.61"]

    def test_word_fragment_beginning_ending(self):
        # "Beginni" + "n" + "g" -> "Beginning"; "Endi" + "ng" -> "Ending" (1-2 letter only)
        out = _merge_fragmented_row(["Beginni", "n", "g"])
        assert out == ["Beginning"]
        out2 = _merge_fragmented_row(["Beginning", "Endi", "ng"])
        assert out2 == ["Beginning", "Ending"]

    def test_no_overmerge_separate_words(self):
        # "Ending" (6 letters) must not merge with "Beginning"
        out = _merge_fragmented_row([None, "Beginni", "n", "g", "Endi", "ng", None, "Change"])
        assert out[1] == "Beginning"
        assert out[2] == "Ending"
        assert out[4] == "Change"

    def test_num_dot_then_digits_space_next_num(self):
        # "1,421,910." + "03 1,494,773.17" -> "1,421,910.03" and 1494773.17 (Decimal)
        out = _merge_fragmented_row(["Equity", "1,421,910.", "03 1,494,773.17", "72,863.14"])
        assert out[0] == "Equity"
        assert out[1] == "1,421,910.03"
        assert out[2] == Decimal("1494773.17")
        assert out[3] == "72,863.14"

    def test_empty_and_single_cell(self):
        assert _merge_fragmented_row([]) == []
        assert _merge_fragmented_row(["Only"]) == ["Only"]

    def test_split_parenthetical_negative(self):
        # "(37,30" + "3.03)" -> -37303.03 (Decimal)
        out = _merge_fragmented_row(["Net Contributions/Withdrawals", None, None, "(37,30", "3.03)", None])
        assert out[3] == Decimal("-37303.03")

    def test_year_to_date_merge(self):
        out = _merge_fragmented_row(["Current", "Year-to-", "Date", ""])
        assert out[1] == "Year-to-Date"


class TestCellValue:
    """Tests for _cell_value() numeric normalization (returns Decimal for amounts)."""

    def test_parenthetical_negative(self):
        assert _cell_value("(308.60)") == Decimal("-308.60")
        assert _cell_value("($37,303.03)") == Decimal("-37303.03")

    def test_dollar_amount_after_digits(self):
        assert _cell_value("09 $24,157,595.24") == Decimal("24157595.24")
        assert _cell_value("24 $24,284,278.98") == Decimal("24284278.98")

    def test_footnote_stripped_from_string(self):
        assert _cell_value("E79271004¹") == "E79271004"
        assert _cell_value("G41269004²") == "G41269004"


class TestCleanTableRows:
    """Tests for _clean_table_rows()."""

    def test_merge_then_drop_empty(self):
        rows = [["Beginni", "n", "g"], [], ["Ending"], [None, None]]
        out = _clean_table_rows(rows)
        assert out == [["Beginning"], ["Ending"]]


class TestValidateExtractionJson:
    """Tests for validate_extraction_json()."""

    def test_valid_payload_passes(self):
        payload = {
            "sections": [
                {"name": "Summary", "headings": ["H1"], "rows": [["A", "B"], [1, 2]]}
            ]
        }
        validate_extraction_json(payload)

    def test_missing_sections_fails(self):
        with pytest.raises(ValueError, match="validation failed|required"):
            validate_extraction_json({})

    def test_section_missing_name_fails(self):
        payload = {"sections": [{"headings": [], "rows": []}]}
        with pytest.raises(ValueError, match="Extraction JSON validation|required"):
            validate_extraction_json(payload)
