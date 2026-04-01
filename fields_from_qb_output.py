#!/usr/bin/env python3
"""
Extract a generic set of fields from a QB-style extracted workbook (by_target).

This is a service-friendly layer: it produces FieldValue[] with provenance.
"""

from __future__ import annotations

from field_service import FieldValue
from qb_posting_rules import (
    extract_account_id_field,
    extract_accounts_ids_field,
    extract_cash_closing_balance_field,
    extract_change_in_accrued_dividend_field,
    extract_change_in_accrued_interest_field,
    extract_holdings_totals_fields,
    extract_plsummary_numeric_fields,
    extract_plsummary_source_map_field,
    extract_purchases_sales_accrued_interest_field,
    extract_statement_period_end_field,
    extract_statement_period_start_field,
    extract_unrealized_change_field,
    infer_account_id_from_by_target,
)


def extract_fields(by_target: dict) -> list[FieldValue]:
    fields: list[FieldValue] = []

    for fn in (
        extract_cash_closing_balance_field,
        extract_purchases_sales_accrued_interest_field,
    ):
        try:
            f = fn(by_target)
        except Exception:
            f = None
        if f is not None:
            fields.append(f)

    try:
        ps = extract_statement_period_start_field(by_target)
    except Exception:
        ps = None
    if ps is not None:
        fields.append(ps)

    try:
        pe = extract_statement_period_end_field(by_target)
    except Exception:
        pe = None
    if pe is not None:
        fields.append(pe)

    try:
        fields.append(extract_account_id_field(by_target))
    except Exception:
        pass

    try:
        fields.extend(extract_holdings_totals_fields(by_target))
    except Exception:
        pass

    try:
        aids = extract_accounts_ids_field(by_target)
    except Exception:
        aids = None
    if aids is not None:
        fields.append(aids)

    try:
        sm = extract_plsummary_source_map_field(by_target)
    except Exception:
        sm = None
    if sm is not None:
        fields.append(sm)

    try:
        fields.extend(extract_plsummary_numeric_fields(by_target))
    except Exception:
        pass

    acct = infer_account_id_from_by_target(by_target) or "366-3"
    for fn in (
        lambda bt: extract_unrealized_change_field(bt, acct),
        lambda bt: extract_change_in_accrued_interest_field(bt, acct),
        lambda bt: extract_change_in_accrued_dividend_field(bt, acct),
    ):
        try:
            f = fn(by_target)
        except Exception:
            f = None
        if f is not None:
            fields.append(f)

    return fields
