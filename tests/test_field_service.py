from fields_from_qb_output import extract_fields


def test_extract_fields_smoke():
    by_target = {
        "Cash Activity": [
            ("Cash Activity", [
                ["End of Day Balance"],
                ["CLOSING BALANCE AS OF DEC 31 25", "155,206.79"],
            ])
        ],
        "Investment Activity": [
            ("Investment Activity", [
                ["TOTAL PURCHASES & SALES", "(8,278.06)"],
            ])
        ],
    }
    fields = extract_fields(by_target)
    keys = {f.key for f in fields}
    assert "cash.closing_balance" in keys
    assert "purchases_sales.total_accrued_interest" in keys

