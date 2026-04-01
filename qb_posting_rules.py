#!/usr/bin/env python3
"""
Rule-based extraction helpers to populate QB-style sheets.

This module implements the accounting mapping rules learned from:
- Purchases & Sales -> Interest Paid on Purchases / Interest Income (sign logic)
- Cash Activity -> Cash - Due from Broker (closing balance rule)
- Unrealized / Change in Interest -> PLSummary deltas

Inputs:
- `by_target`: dict[str, list[tuple[source_sheet_name, rows]]]
  where `rows` is a list[list] of extracted cell values.
  This is the same `by_target` structure passed to `plsummary_builder.build_plsummary_jpm_sheet()`.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any

from field_service import FieldValue, Provenance

_ACCOUNT_ID_RE = re.compile(r"\b(\d{3}-\d)\b")

def _num(v: Any) -> float | None:
    """Parse numbers robustly from extracted values."""
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float, Decimal)):
        return float(v)
    s = str(v).strip()
    if not s:
        return None
    s = s.replace(",", "").replace("$", "").replace("€", "").replace("£", "").strip()
    # Parentheses indicate negative numbers: (123.45)
    if s.startswith("(") and s.endswith(")"):
        inner = s[1:-1].strip()
        try:
            return -float(inner)
        except Exception:
            return None
    try:
        # allow trailing % (as fraction) only if it clearly exists
        if s.endswith("%"):
            return float(s[:-1]) / 100.0
        return float(s)
    except Exception:
        return None


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


def _find_header_col(rows: list[list], header_contains: str) -> int | None:
    """
    Find a column index where header cell contains the given phrase.
    We scan all rows; first header-like match wins.
    """
    target = _norm(header_contains)
    for r in rows or []:
        if not isinstance(r, (list, tuple)):
            continue
        cells = [c for c in r if c is not None]
        if not cells:
            continue
        for j, c in enumerate(r):
            if c is None:
                continue
            if isinstance(c, str) and target in _norm(c):
                return j
    return None


def _find_first_row_value(rows: list[list], row_contains: str, col_idx: int | None) -> float | None:
    """Find first row where any cell contains row_contains, then return numeric from col_idx (or last numeric)."""
    needle = _norm(row_contains)
    for r in rows or []:
        if not isinstance(r, (list, tuple)):
            continue
        row_text = " ".join(_norm(str(c)) for c in r if c is not None)
        if needle in row_text:
            if col_idx is not None and col_idx < len(r):
                return _num(r[col_idx])
            # fallback: last numeric in the row
            last = None
            for c in r:
                n = _num(c)
                if n is not None:
                    last = n
            return last
    return None


def _get_first_sheet_rows(by_target: dict[str, list[tuple[str, list[list]]]], sheet_key: str) -> list[list]:
    blocks = by_target.get(sheet_key) or []
    if not blocks:
        return []
    _source_name, rows = blocks[0]
    return rows or []


def _extract_latest_value_in_row_with_account_block(
    rows: list[list],
    account_id: str,
    row_label_contains: str,
) -> float | None:
    """
    In a time-series sheet (Unrealized / Change in Interest / Change in Dividend):
    - Find the block starting at a row containing `account_id`
    - Within that block, locate a row containing `row_label_contains`
    - Return the last numeric value in that row (assumes latest month column is rightmost populated).
    """
    if not rows:
        return None
    acct = _norm(account_id)
    label = _norm(row_label_contains)

    # Find start indices for the account block.
    starts: list[int] = []
    for i, r in enumerate(rows):
        if not isinstance(r, (list, tuple)):
            continue
        row_text = _norm(" ".join(str(c) for c in r if c is not None))
        if acct and acct in row_text:
            starts.append(i)
    if not starts:
        # fall back to global search if account blocks aren't clearly separated
        for r in rows:
            if not isinstance(r, (list, tuple)):
                continue
            row_text = _norm(" ".join(str(c) for c in r if c is not None))
            if label in row_text:
                last = None
                for c in r:
                    n = _num(c)
                    if n is not None:
                        last = n
                return last
        return None

    # For each block, try to find the desired row; prefer the last block.
    for idx in range(len(starts) - 1, -1, -1):
        start = starts[idx]
        end = starts[idx + 1] if idx + 1 < len(starts) else len(rows)
        block = rows[start:end]
        for r in block:
            if not isinstance(r, (list, tuple)):
                continue
            row_text = _norm(" ".join(str(c) for c in r if c is not None))
            if label in row_text:
                last = None
                for c in r:
                    n = _num(c)
                    if n is not None:
                        last = n
                return last

    return None


def extract_cash_closing_balance(by_target: dict[str, list[tuple[str, list[list]]]]) -> float | None:
    """
    Extract cash closing balance from Cash Activity (Continued).
    Preferred: Transactions affecting cash -> Closing balance as of period end.
    """
    rows = _get_first_sheet_rows(by_target, "Cash Activity")
    if not rows:
        # Some PDFs may output a different normalized sheet key.
        for k in ("Cash Activity", "Cash & Fixed Income", "Cash & Fixed Income "):
            if k in by_target:
                rows = _get_first_sheet_rows(by_target, k)
                break
    if not rows:
        return None

    # Exact header label varies ("End of Day Money Balance", etc.), so:
    # - Find every row that contains "CLOSING BALANCE AS OF"
    # - Prefer the latest date mentioned in that label (if parseable)
    # - Return the last numeric value in that row
    best_val = None
    best_key = None  # sortable date key
    date_re = re.compile(r"\b([A-Z]{3})\s+(\d{1,2})\s+(\d{2})\b", re.I)  # e.g. DEC 31 25
    month_map = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }

    for r in rows or []:
        if not isinstance(r, (list, tuple)) or not r:
            continue
        row_text = " ".join(str(c) for c in r if c is not None)
        if "closing balance as of" not in _norm(row_text):
            continue

        # parse date from the label (best effort)
        key = None
        m = date_re.search(row_text)
        if m:
            mon = month_map.get(m.group(1).lower())
            day = int(m.group(2))
            yy = int(m.group(3))
            if mon:
                # 2-digit year -> 2000+
                key = (2000 + yy, mon, day)

        # last numeric in row
        last = None
        for c in r:
            n = _num(c)
            if n is not None:
                last = n
        if last is None:
            continue

        if best_key is None and key is None and best_val is None:
            best_val = last
        elif best_key is None and key is not None:
            best_key = key
            best_val = last
        elif best_key is not None and key is not None and key > best_key:
            best_key = key
            best_val = last
        elif best_key is None and key is None:
            # fallback: keep latest encountered
            best_val = last

    return best_val


def extract_cash_closing_balance_field(by_target: dict[str, list[tuple[str, list[list]]]]) -> FieldValue | None:
    val = extract_cash_closing_balance(by_target)
    if val is None:
        return None
    return FieldValue(
        key="cash.closing_balance",
        value=float(val),
        confidence="high",
        provenance=Provenance(
            source="qb_extracted_sections",
            sheet="Cash Activity",
            row_label="CLOSING BALANCE AS OF ...",
            note="Preferred source: Cash Activity (Transactions affecting cash) closing balance",
        ),
        method="rule.cash_closing_balance",
    )


def extract_purchases_sales_accrued_interest(by_target: dict[str, list[tuple[str, list[list]]]]) -> float | None:
    """
    Extract TOTAL PURCHASES & SALES accrued interest total from Purchases & Sales section.
    """
    rows = _get_first_sheet_rows(by_target, "Purchases and Sales")
    if not rows:
        # In TOC/grouped workbooks, Purchases & Sales often lives inside Investment Activity.
        for k in ("Investment Activity", "Investment Activity "):
            if k in by_target:
                rows = _get_first_sheet_rows(by_target, k)
                break
    if not rows:
        # fallback: sometimes normalized spelling differs
        for k in by_target.keys():
            nk = _norm(k)
            if ("purchase" in nk and "sale" in nk) or "investment activity" in nk:
                rows = _get_first_sheet_rows(by_target, k)
                break
    if not rows:
        return None

    # Column headers can be messy; just find the TOTAL row and take the last numeric in it.
    for r in rows or []:
        if not isinstance(r, (list, tuple)) or not r:
            continue
        if "total purchases & sales" in _norm(" ".join(str(c) for c in r if c is not None)):
            last = None
            for c in r:
                n = _num(c)
                if n is not None:
                    last = n
            return last
    return None


def extract_purchases_sales_accrued_interest_field(by_target: dict[str, list[tuple[str, list[list]]]]) -> FieldValue | None:
    val = extract_purchases_sales_accrued_interest(by_target)
    if val is None:
        return None
    return FieldValue(
        key="purchases_sales.total_accrued_interest",
        value=float(val),
        confidence="high",
        provenance=Provenance(
            source="qb_extracted_sections",
            sheet="Investment Activity",
            row_label="TOTAL PURCHASES & SALES",
            note="Used last numeric in TOTAL PURCHASES & SALES row",
        ),
        method="rule.purchases_sales_total_accrued_interest",
    )


def map_interest_from_purchases_sales(total_accrued_interest: float | None) -> tuple[float, float]:
    """
    Apply sign logic:
    - negative -> Interest Paid on Purchases = abs(value)
    - positive -> Interest Income = value
    """
    if total_accrued_interest is None:
        return (0.0, 0.0)
    if total_accrued_interest < 0:
        return (abs(total_accrued_interest), 0.0)
    return (0.0, total_accrued_interest)


def extract_unrealized_change_for_account(
    by_target: dict[str, list[tuple[str, list[list]]]],
    account_id: str,
) -> float | None:
    rows = _get_first_sheet_rows(by_target, "Unrealized")
    if not rows:
        return None
    return _extract_latest_value_in_row_with_account_block(rows, account_id, "Change in Unrealized")


def extract_change_in_accrued_interest_for_account(
    by_target: dict[str, list[tuple[str, list[list]]]],
    account_id: str,
) -> float | None:
    rows = _get_first_sheet_rows(by_target, "Change in Interest")
    if not rows:
        return None
    return _extract_latest_value_in_row_with_account_block(rows, account_id, "Change in Accrued Interest")


def extract_change_in_accrued_dividend_for_account(
    by_target: dict[str, list[tuple[str, list[list]]]],
    account_id: str,
) -> float | None:
    rows = _get_first_sheet_rows(by_target, "Change in Dividend")
    if not rows:
        return None
    return _extract_latest_value_in_row_with_account_block(rows, account_id, "Change in Accrued Dividend")


def infer_account_id_from_by_target(by_target: dict[str, list[tuple[str, list[list]]]]) -> str | None:
    """Match template layout: e.g. 366-3 from PLSummary A4 or any sheet cell."""
    rows = _get_first_sheet_rows(by_target, "PLSummary")
    if rows and len(rows) >= 4:
        r4 = rows[3]
        if isinstance(r4, (list, tuple)) and r4:
            cell = r4[0]
            if isinstance(cell, str):
                m = _ACCOUNT_ID_RE.search(cell)
                if m:
                    return m.group(1)
    for _blocks in by_target.values():
        for _src, rows in _blocks or []:
            for r in rows or []:
                if not isinstance(r, (list, tuple)):
                    continue
                for c in r:
                    if isinstance(c, str):
                        m = _ACCOUNT_ID_RE.search(c)
                        if m:
                            return m.group(1)
    return None


def infer_period_end_from_by_target(by_target: dict[str, list[tuple[str, list[list]]]]) -> date | None:
    month_map = {
        "jan": 1, "january": 1,
        "feb": 2, "february": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12,
    }
    pat_long = re.compile(r"period ended\s+([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", re.I)
    pat_short = re.compile(r"(?:as of|ended)\s+([A-Za-z]{3,9})\s+(\d{1,2})\s+(\d{2,4})", re.I)

    for _blocks in by_target.values():
        for _src, rows in _blocks or []:
            for r in rows or []:
                if not isinstance(r, (list, tuple)):
                    continue
                for c in r:
                    if not isinstance(c, str):
                        continue
                    s = c.strip()
                    m = pat_long.search(s)
                    if m:
                        mon = month_map.get(m.group(1).lower())
                        if mon:
                            return date(int(m.group(3)), mon, int(m.group(2)))
                    m2 = pat_short.search(s)
                    if m2:
                        mon = month_map.get(m2.group(1).lower())
                        if mon:
                            y = int(m2.group(3))
                            if y < 100:
                                y += 2000
                            return date(y, mon, int(m2.group(2)))
    return None


def infer_period_start_from_by_target(by_target: dict[str, list[tuple[str, list[list]]]]) -> date | None:
    """
    Best-effort parse for "For the Period MM/DD/YY to MM/DD/YY" style strings.
    We search all extracted cells and return the first parsed start date found.
    """
    # Examples: "For the Period 12/1/25 to 12/31/25"
    pat = re.compile(
        r"\bfor the period\s+(\d{1,2})/(\d{1,2})/(\d{2,4})\s+to\s+(\d{1,2})/(\d{1,2})/(\d{2,4})\b",
        re.I,
    )
    for _blocks in by_target.values():
        for _src, rows in _blocks or []:
            for r in rows or []:
                if not isinstance(r, (list, tuple)):
                    continue
                for c in r:
                    if not isinstance(c, str):
                        continue
                    s = c.strip()
                    m = pat.search(s)
                    if not m:
                        continue
                    mm, dd, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    if yy < 100:
                        yy += 2000
                    try:
                        return date(yy, mm, dd)
                    except Exception:
                        continue
    return None


def extract_statement_period_start_field(
    by_target: dict[str, list[tuple[str, list[list]]]],
) -> FieldValue | None:
    d = infer_period_start_from_by_target(by_target)
    if d is None:
        return None
    return FieldValue(
        key="statement.period_start",
        value=d,
        confidence="medium",
        provenance=Provenance(
            source="qb_extracted_sections",
            sheet="*",
            note="Parsed from 'For the Period ... to ...' text in extracted sections",
        ),
        method="rule.statement_period_start",
    )


def extract_holdings_totals_from_by_target(
    by_target: dict[str, list[tuple[str, list[list]]]],
) -> tuple[float | None, float | None, float | None, float | None]:
    """
    Parse Holdings TOTAL GS row if present.
    Returns (market_value, original_cost, unrealized_gain_loss, accrued_income).
    """
    rows = _get_first_sheet_rows(by_target, "Holdings")
    if not rows:
        return (None, None, None, None)
    max_r = len(rows)
    max_c = 20
    for r_i in range(max_r):
        r = rows[r_i]
        if not isinstance(r, (list, tuple)) or not r:
            continue
        label = r[0]
        if not isinstance(label, str) or "total gs" not in label.lower():
            continue
        nums: list[float] = []
        for c in range(1, min(len(r), max_c + 1)):
            n = _num(r[c])
            if n is not None:
                nums.append(n)
        accrued_income = None
        if r_i + 1 < max_r:
            r2 = rows[r_i + 1]
            if isinstance(r2, (list, tuple)):
                nums_next = []
                for c in range(1, min(len(r2), max_c + 1)):
                    n = _num(r2[c] if c < len(r2) else None)
                    if n is not None:
                        nums_next.append(n)
                if len(nums_next) == 1:
                    accrued_income = nums_next[0]
        if len(nums) >= 3:
            return (nums[0], nums[1], nums[2], accrued_income)
    return (None, None, None, None)


def extract_plsummary_source_map_from_by_target(
    by_target: dict[str, list[tuple[str, list[list]]]],
) -> dict[str, list[Any]]:
    """Label in col A -> [B..F] for the PLSummary sheet, if present."""
    rows = _get_first_sheet_rows(by_target, "PLSummary")
    if not rows:
        return {}
    out: dict[str, list[Any]] = {}
    for r in rows:
        if not isinstance(r, (list, tuple)) or not r:
            continue
        label = r[0]
        if not isinstance(label, str) or not label.strip():
            continue
        vals = [r[i] if i < len(r) else None for i in range(1, 6)]
        out[label.strip()] = vals
    return out


def extract_account_id_field(by_target: dict[str, list[tuple[str, list[list]]]]) -> FieldValue:
    inferred = infer_account_id_from_by_target(by_target)
    acct = inferred or "366-3"
    return FieldValue(
        key="account.id",
        value=acct,
        confidence="high" if inferred else "medium",
        provenance=Provenance(
            source="qb_extracted_sections",
            sheet="PLSummary",
            row_label="A4 (account id)",
            note="Pattern XXX-X from PLSummary or workbook scan",
        ),
        method="rule.account_id",
    )


def extract_statement_period_end_field(
    by_target: dict[str, list[tuple[str, list[list]]]],
) -> FieldValue | None:
    d = infer_period_end_from_by_target(by_target)
    if d is None:
        return None
    return FieldValue(
        key="statement.period_end",
        value=d,
        confidence="medium",
        provenance=Provenance(
            source="qb_extracted_sections",
            sheet="*",
            note="Parsed from period ended / as of text in extracted sections",
        ),
        method="rule.statement_period_end",
    )


def _slugify_label(label: str) -> str:
    s = _norm(label)
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    s = re.sub(r"_+", "_", s)
    return s or "unknown"


def _find_row_index_by_label(rows: list[list], label: str) -> int | None:
    target = (label or "").strip()
    if not target:
        return None
    for i, r in enumerate(rows or [], start=1):
        if not isinstance(r, (list, tuple)) or not r:
            continue
        v = r[0]
        if isinstance(v, str) and v.strip() == target:
            return i
    return None


def extract_plsummary_numeric_fields(
    by_target: dict[str, list[tuple[str, list[list]]]],
) -> list[FieldValue]:
    """
    Convert PLSummary label-map into typed numeric fields. These are "useful" downstream facts
    (cash, investments, contributions, withdrawals, etc.) with provenance.
    """
    rows = _get_first_sheet_rows(by_target, "PLSummary")
    if not rows:
        return []
    src_map = extract_plsummary_source_map_from_by_target(by_target)
    out: list[FieldValue] = []
    # Labels that are headers/identifiers rather than numeric facts.
    skip_labels = {
        "account name",
        "mtd pnl per trading account summary",
    }
    for label, vals in (src_map or {}).items():
        if not isinstance(label, str) or not label.strip():
            continue
        if _norm(label) in skip_labels:
            continue
        # Find first numeric among B..F
        n = None
        col_idx = None
        for j, v in enumerate(vals or [], start=2):  # B=2
            nn = _num(v)
            if nn is not None:
                n = float(nn)
                col_idx = j
                break
        if n is None:
            continue
        r_idx = _find_row_index_by_label(rows, label)
        out.append(
            FieldValue(
                key=f"plsummary.{_slugify_label(label)}",
                value=n,
                confidence="high",
                provenance=Provenance(
                    source="qb_extracted_sections",
                    sheet="PLSummary",
                    row_label=label.strip(),
                    row_index=r_idx,
                    column_label="first_numeric(B..F)",
                    column_index=col_idx,
                ),
                method="rule.plsummary_numeric_map",
            )
        )
    return out


def extract_accounts_ids_field(by_target: dict[str, list[tuple[str, list[list]]]]) -> FieldValue | None:
    """
    Extract all detected account identifiers from sheet names and PLSummary labels.
    Returns a list of IDs (strings).
    """
    ids: list[str] = []
    # From sheet keys like "Account E79271004"
    for k in by_target.keys():
        m = re.match(r"^Account\s+([A-Z0-9]+)$", (k or "").strip(), re.I)
        if m:
            cand = m.group(1).strip()
            # Avoid accidental captures like "Account Summary"
            if cand.lower() not in ("summary",):
                ids.append(cand)
    # From PLSummary label column
    rows = _get_first_sheet_rows(by_target, "PLSummary")
    if rows:
        for r in rows:
            if not isinstance(r, (list, tuple)) or not r:
                continue
            v = r[0]
            if isinstance(v, str):
                vv = v.strip()
                if re.match(r"^[A-Z]?\d{6,}$", vv, re.I):
                    ids.append(vv)
    # Dedup, stable order
    seen = set()
    uniq = []
    for x in ids:
        if x and x not in seen:
            seen.add(x)
            uniq.append(x)
    if not uniq:
        return None
    return FieldValue(
        key="accounts.ids",
        value=uniq,
        confidence="medium",
        provenance=Provenance(
            source="qb_extracted_sections",
            sheet="*",
            note="From sheet names (Account <id>) and PLSummary label column",
        ),
        method="rule.accounts_ids",
    )


def extract_holdings_totals_fields(
    by_target: dict[str, list[tuple[str, list[list]]]],
) -> list[FieldValue]:
    mv, oc, ur, ai = extract_holdings_totals_from_by_target(by_target)
    out: list[FieldValue] = []
    if mv is not None:
        out.append(
            FieldValue(
                key="holdings.market_value",
                value=float(mv),
                confidence="high",
                provenance=Provenance(
                    source="qb_extracted_sections",
                    sheet="Holdings",
                    row_label="TOTAL GS",
                    note="First numeric in TOTAL GS row",
                ),
                method="rule.holdings_total_gs",
            )
        )
    if oc is not None:
        out.append(
            FieldValue(
                key="holdings.original_cost",
                value=float(oc),
                confidence="high",
                provenance=Provenance(
                    source="qb_extracted_sections",
                    sheet="Holdings",
                    row_label="TOTAL GS",
                    note="Second numeric in TOTAL GS row",
                ),
                method="rule.holdings_total_gs",
            )
        )
    if ur is not None:
        out.append(
            FieldValue(
                key="holdings.unrealized_gain_loss",
                value=float(ur),
                confidence="high",
                provenance=Provenance(
                    source="qb_extracted_sections",
                    sheet="Holdings",
                    row_label="TOTAL GS",
                    note="Third numeric in TOTAL GS row",
                ),
                method="rule.holdings_total_gs",
            )
        )
    if ai is not None:
        out.append(
            FieldValue(
                key="holdings.accrued_income",
                value=float(ai),
                confidence="medium",
                provenance=Provenance(
                    source="qb_extracted_sections",
                    sheet="Holdings",
                    row_label="TOTAL GS (+1)",
                    note="Optional single numeric on row below TOTAL GS",
                ),
                method="rule.holdings_total_gs",
            )
        )
    return out


def extract_plsummary_source_map_field(
    by_target: dict[str, list[tuple[str, list[list]]]],
) -> FieldValue | None:
    d = extract_plsummary_source_map_from_by_target(by_target)
    if not d:
        return None
    return FieldValue(
        key="plsummary.source_map",
        value=d,
        confidence="high",
        provenance=Provenance(
            source="qb_extracted_sections",
            sheet="PLSummary",
            note="Col A label -> [B..F] values for template Admin GS mapping",
        ),
        method="rule.plsummary_source_map",
    )


def extract_unrealized_change_field(
    by_target: dict[str, list[tuple[str, list[list]]]],
    account_id: str,
) -> FieldValue | None:
    val = extract_unrealized_change_for_account(by_target, account_id)
    if val is None:
        return None
    return FieldValue(
        key="delta.change_in_unrealized_gain_loss",
        value=float(val),
        confidence="medium",
        provenance=Provenance(
            source="qb_extracted_sections",
            sheet="Unrealized",
            row_label=f"account {account_id} / Change in Unrealized",
        ),
        method="rule.unrealized_change_latest",
    )


def extract_change_in_accrued_interest_field(
    by_target: dict[str, list[tuple[str, list[list]]]],
    account_id: str,
) -> FieldValue | None:
    val = extract_change_in_accrued_interest_for_account(by_target, account_id)
    if val is None:
        return None
    return FieldValue(
        key="delta.change_in_accrued_interest",
        value=float(val),
        confidence="medium",
        provenance=Provenance(
            source="qb_extracted_sections",
            sheet="Change in Interest",
            row_label=f"account {account_id} / Change in Accrued Interest",
        ),
        method="rule.change_in_accrued_interest_latest",
    )


def extract_change_in_accrued_dividend_field(
    by_target: dict[str, list[tuple[str, list[list]]]],
    account_id: str,
) -> FieldValue | None:
    val = extract_change_in_accrued_dividend_for_account(by_target, account_id)
    if val is None:
        return None
    return FieldValue(
        key="delta.change_in_accrued_dividend",
        value=float(val),
        confidence="medium",
        provenance=Provenance(
            source="qb_extracted_sections",
            sheet="Change in Dividend",
            row_label=f"account {account_id} / Change in Accrued Dividend",
        ),
        method="rule.change_in_accrued_dividend_latest",
    )

