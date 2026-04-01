#!/usr/bin/env python3
"""
Generic field extraction service layer.

Goal: guaranteed correctness + auditability.

This module returns a list/dict of extracted fields with:
- value (typed)
- confidence (high/medium/low)
- provenance (which sheet/section/row we used)
- method (deterministic rule / fallback)

Downstream workflows (QB template, family template, others) should consume these fields
instead of re-parsing PDFs directly.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date
from typing import Any, Literal


Confidence = Literal["high", "medium", "low"]


@dataclass(frozen=True)
class Provenance:
    source: str  # e.g. "qb_output_xlsx"
    sheet: str
    row_label: str | None = None
    row_index: int | None = None
    column_label: str | None = None
    column_index: int | None = None
    note: str | None = None


@dataclass(frozen=True)
class FieldValue:
    key: str
    value: Any
    confidence: Confidence
    provenance: Provenance
    method: str  # e.g. "rule.cash_closing_balance"

    def to_json(self) -> dict:
        d = asdict(self)
        # dataclasses convert date to string poorly in default json dumps; keep isoformat.
        if isinstance(self.value, date):
            d["value"] = self.value.isoformat()
        return d

