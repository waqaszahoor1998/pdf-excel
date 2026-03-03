"""Unit tests for tables_to_excel merge and clean logic. No PDF I/O."""

import pytest

from tables_to_excel import _merge_fragmented_row, _clean_table_rows, _cell_value


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
        # "1,421,910." + "03 1,494,773.17" -> "1,421,910.03" and 1494773.17 (float)
        out = _merge_fragmented_row(["Equity", "1,421,910.", "03 1,494,773.17", "72,863.14"])
        assert out[0] == "Equity"
        assert out[1] == "1,421,910.03"
        assert out[2] == 1494773.17
        assert out[3] == "72,863.14"

    def test_empty_and_single_cell(self):
        assert _merge_fragmented_row([]) == []
        assert _merge_fragmented_row(["Only"]) == ["Only"]


class TestCellValue:
    """Tests for _cell_value() numeric normalization."""

    def test_parenthetical_negative(self):
        assert _cell_value("(308.60)") == -308.6
        assert _cell_value("($37,303.03)") == -37303.03

    def test_dollar_amount_after_digits(self):
        assert _cell_value("09 $24,157,595.24") == 24157595.24
        assert _cell_value("24 $24,284,278.98") == 24284278.98


class TestCleanTableRows:
    """Tests for _clean_table_rows()."""

    def test_merge_then_drop_empty(self):
        rows = [["Beginni", "n", "g"], [], ["Ending"], [None, None]]
        out = _clean_table_rows(rows)
        assert out == [["Beginning"], ["Ending"]]
