"""
VALIDATION: proves that cleaning did exactly what was intended and nothing else.

Two kinds of checks:
  1. Reconciliation: totals in = totals out +/- logged removals.
  2. Rule checks: every corrected issue is now resolved; flags are well formed.

If any check fails, the pipeline stops and no processed file is trusted.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .cleaning import CleaningLog

TOLERANCE = 1e-6


class ValidationError(Exception):
    pass


def _row(check: str, expected, actual, ok: bool) -> dict:
    return {"check": check, "expected": expected, "actual": actual,
            "status": "PASS" if ok else "FAIL"}


def validate(raw: dict[str, pd.DataFrame], clean: dict[str, pd.DataFrame],
             log: CleaningLog, raw_hash_before: str, raw_hash_after: str,
             audit_issue_log: pd.DataFrame) -> pd.DataFrame:
    r = raw["orders"].rename(columns=config.ORDERS_COLUMN_MAP)
    c = clean["orders"]
    removed = log.removed_rows
    rows: list[dict] = []

    # ---- Raw data protection -------------------------------------------
    rows.append(_row("Raw file unchanged (SHA-256 before = after)", raw_hash_before[:12],
                     raw_hash_after[:12], raw_hash_before == raw_hash_after))

    # ---- Reconciliation --------------------------------------------------
    rows.append(_row("Rows: clean = raw - removed", len(r) - len(removed), len(c),
                     len(c) == len(r) - len(removed)))
    for col in ["sales", "profit", "quantity"]:
        expected = r[col].sum() - (removed[col].sum() if len(removed) else 0)
        actual = c[col].sum()
        rows.append(_row(f"Total {col}: clean = raw - removed", round(expected, 4),
                         round(actual, 4), abs(expected - actual) < TOLERANCE))
    rows.append(_row("Distinct orders unchanged (no order lost entirely)",
                     r["order_id"].nunique(), c["order_id"].nunique(),
                     r["order_id"].nunique() == c["order_id"].nunique()))
    rows.append(_row("Every remaining row_id existed in raw", True,
                     bool(c["row_id"].isin(r["row_id"]).all()), c["row_id"].isin(r["row_id"]).all()))

    # Untouched business values: compare numeric columns row-by-row on row_id
    merged = c[["row_id", *config.NUMERIC_COLUMNS]].merge(
        r[["row_id", *config.NUMERIC_COLUMNS]], on="row_id", suffixes=("", "_raw"))
    unchanged = all(np.allclose(merged[col], merged[f"{col}_raw"]) for col in config.NUMERIC_COLUMNS)
    rows.append(_row("Sales/quantity/discount/profit values unchanged per row", True,
                     unchanged, unchanged))

    # ---- Integrity -------------------------------------------------------
    rows.append(_row("row_id unique", 0, int(c["row_id"].duplicated().sum()), c["row_id"].is_unique))
    nulls = int(c.isna().sum().sum())
    rows.append(_row("No nulls in processed orders", 0, nulls, nulls == 0))
    business = [col for col in config.ORDERS_COLUMN_MAP.values() if col != "row_id"]
    near_dup = int(c.duplicated(subset=business).sum())
    rows.append(_row("No near-duplicate lines remain", 0, near_dup, near_dup == 0))

    # ---- Corrected issues are resolved ----------------------------------
    is_us = c["country"].eq("United States")
    us_ok = c.loc[is_us, "postal_code"].str.match(config.US_POSTAL_PATTERN).all()
    ca_ok = c.loc[~is_us, "postal_code"].str.match(config.CA_POSTAL_PATTERN).all()
    rows.append(_row("US postal codes are 5-digit text", True, bool(us_ok), bool(us_ok)))
    rows.append(_row("Canadian postal codes are 3-char FSA text", True, bool(ca_ok), bool(ca_ok)))
    bad_cid = int((~c["customer_id"].str.match(config.CUSTOMER_ID_PATTERN)).sum())
    rows.append(_row("All customer_id values match format", 0, bad_cid, bad_cid == 0))
    lower = int(c["customer_name"].str.split().map(
        lambda ws: any(w[:1].islower() for w in ws)).sum())
    rows.append(_row("No customer-name words start lower-case", 0, lower, lower == 0))
    same_cust_count = r["customer_id"].str.upper().nunique() == c["customer_id"].nunique()
    rows.append(_row("Customer count unchanged by ID case fix", r["customer_id"].str.upper().nunique(),
                     c["customer_id"].nunique(), same_cust_count))

    # ---- Domains and types ----------------------------------------------
    for col, allowed in config.EXPECTED_DOMAINS.items():
        ok = bool(c[col].isin(allowed).all())
        rows.append(_row(f"{col} within expected domain", True, ok, ok))
    ok_types = (pd.api.types.is_datetime64_any_dtype(c["order_date"])
                and pd.api.types.is_string_dtype(c["postal_code"])
                and pd.api.types.is_integer_dtype(c["quantity"])
                and pd.api.types.is_float_dtype(c["sales"]))
    rows.append(_row("Final data types as specified", True, ok_types, ok_types))

    # ---- Flags agree with the audit ------------------------------------
    removed_ids = set(removed["row_id"]) if len(removed) else set()
    for code, col in [("DQ05", "dq_is_identity_anomaly"), ("DQ06", "dq_is_placeholder_customer"),
                      ("DQ08", "dq_is_value_copy_suspect"), ("DQ09", "dq_is_price_anomaly"),
                      ("DQ18", "dq_is_clone_copy")]:
        audit_ids = set(audit_issue_log.loc[audit_issue_log["issue_code"] == code, "row_id"]) - removed_ids
        flag_ids = set(c.loc[c[col], "row_id"])
        rows.append(_row(f"{col} matches audit rows ({code})", len(audit_ids), len(flag_ids),
                         audit_ids == flag_ids))
    flag_cols = [col for col in c.columns if col.startswith("dq_") or col.startswith("exclude_")]
    bool_ok = all(c[col].dtype == bool for col in flag_cols)
    rows.append(_row("All flag columns are boolean with no nulls", True, bool_ok, bool_ok))

    # ---- Related tables ---------------------------------------------------
    ret = clean["returns"]
    orphan = int((~ret["order_id"].isin(c["order_id"])).sum())
    rows.append(_row("Every returned order exists in clean orders", 0, orphan, orphan == 0))
    mgr_ok = set(c["region"]) <= set(clean["people"]["region"])
    rows.append(_row("Every region has a regional manager", True, mgr_ok, mgr_ok))

    result = pd.DataFrame(rows)
    result["expected"] = result["expected"].astype(str)
    result["actual"] = result["actual"].astype(str)
    return result


def assert_valid(result: pd.DataFrame) -> None:
    failed = result[result["status"] == "FAIL"]
    if not failed.empty:
        raise ValidationError("Validation failed:\n" + failed.to_string(index=False))


def validate_round_trip(clean_orders: pd.DataFrame, reloaded: pd.DataFrame) -> pd.DataFrame:
    """Re-read the written CSV and prove nothing was lost in the file (e.g. leading zeros)."""
    rows = [
        _row("CSV round-trip: same row count", len(clean_orders), len(reloaded),
             len(clean_orders) == len(reloaded)),
        _row("CSV round-trip: postal codes identical (leading zeros kept)", True,
             bool((clean_orders["postal_code"].values == reloaded["postal_code"].values).all()),
             bool((clean_orders["postal_code"].values == reloaded["postal_code"].values).all())),
        _row("CSV round-trip: sales total identical", round(clean_orders["sales"].sum(), 4),
             round(reloaded["sales"].sum(), 4),
             abs(clean_orders["sales"].sum() - reloaded["sales"].sum()) < TOLERANCE),
    ]
    out = pd.DataFrame(rows)
    out["expected"] = out["expected"].astype(str)
    out["actual"] = out["actual"].astype(str)
    return out
