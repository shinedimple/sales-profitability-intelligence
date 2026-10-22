"""
CLEANING: implements the decisions documented in issue_catalog.py.

Principles:
  * Work on a copy. The raw DataFrames passed in are never modified.
  * Each step is a small, pure function: DataFrame in -> DataFrame out.
  * Every change is recorded in a cleaning log (what, why, rows affected).
  * Uncertain records are FLAGGED, not deleted or rewritten.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from . import config
from .audit import clone_copy_mask, iqr_bounds, implied_list_price


@dataclass
class CleaningLog:
    entries: list[dict] = field(default_factory=list)
    removed_rows: pd.DataFrame = field(default_factory=pd.DataFrame)

    def record(self, step: str, issue_code: str, rows_affected: int, note: str = "") -> None:
        self.entries.append({"step": step, "issue_code": issue_code,
                             "rows_affected": int(rows_affected), "note": note})

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.entries)


# --------------------------------------------------------------------------
# Standardisation steps
# --------------------------------------------------------------------------
def standardize_column_names(df: pd.DataFrame, mapping: dict, log: CleaningLog) -> pd.DataFrame:
    log.record("Rename columns to snake_case", "-", 0, f"{len(mapping)} columns renamed")
    return df.rename(columns=mapping)


def strip_text(df: pd.DataFrame, columns: list[str], log: CleaningLog) -> pd.DataFrame:
    """Defensive trim of whitespace (audit found none, but the step keeps the pipeline robust)."""
    out = df.copy()
    changed = 0
    for col in columns:
        as_text = out[col].astype("string")
        trimmed = as_text.str.strip()
        changed += int((trimmed != as_text).sum())
        out[col] = trimmed
    log.record("Trim whitespace in text columns", "-", changed)
    return out


def fix_postal_codes(df: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    """DQ02: postal codes are identifiers -> text; restore US leading zeros."""
    out = df.copy()
    as_text = out["postal_code"].astype("string").str.strip().str.upper()
    is_us = out["country"].eq("United States")
    padded = as_text.where(~is_us, as_text.str.zfill(5))
    log.record("Postal code to text; zero-pad US codes to 5 digits", "DQ02",
               int((padded != as_text).sum()))
    out["postal_code"] = padded
    return out


def fix_customer_id_case(df: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    """DQ03: upper-case IDs (audit confirmed this creates no collisions)."""
    out = df.copy()
    upper = out["customer_id"].str.upper()
    log.record("Upper-case customer_id", "DQ03", int((upper != out["customer_id"]).sum()))
    out["customer_id"] = upper
    return out


def _capitalise_word_starts(name: str) -> str:
    return " ".join(w[:1].upper() + w[1:] if w[:1].islower() else w for w in name.split())


def fix_customer_name_case(df: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    """DQ04: capitalise lower-case word starts only; never restructure names."""
    out = df.copy()
    fixed = out["customer_name"].map(_capitalise_word_starts)
    log.record("Capitalise lower-case starts of customer name words", "DQ04",
               int((fixed != out["customer_name"]).sum()))
    out["customer_name"] = fixed
    return out


def remove_near_duplicates(df: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    """DQ01: drop rows identical in every business column; keep the lowest row_id."""
    business_cols = [c for c in df.columns if c != "row_id"]
    ordered = df.sort_values("row_id")
    dup_mask = ordered.duplicated(subset=business_cols, keep="first")
    removed = ordered.loc[dup_mask]
    log.removed_rows = pd.concat([log.removed_rows, removed.assign(removal_reason="DQ01")])
    log.record("Remove near-duplicate order lines", "DQ01", len(removed),
               f"removed row_ids {removed['row_id'].tolist()}; "
               f"sales {removed['sales'].sum():,.4f}, profit {removed['profit'].sum():,.4f}")
    return ordered.loc[~dup_mask].reset_index(drop=True)


# --------------------------------------------------------------------------
# Flagging steps (rows kept, evidence attached)
# --------------------------------------------------------------------------
def add_quality_flags(df: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    """Add boolean dq_* columns so later phases can include/exclude rows explicitly."""
    out = df.copy()

    # DQ05 identity anomaly: a name with several IDs, or an order with several customers
    name_ids = out.groupby("customer_name")["customer_id"].nunique()
    order_cust = out.groupby("order_id")["customer_id"].nunique()
    out["dq_is_identity_anomaly"] = (
        out["customer_name"].isin(name_ids[name_ids > 1].index)
        | out["order_id"].isin(order_cust[order_cust > 1].index))

    # DQ06 placeholder customer
    out["dq_is_placeholder_customer"] = out["customer_name"].str.contains(
        config.PLACEHOLDER_NAME_PATTERN, case=False, regex=True)

    # DQ08 copied values across different products in one order
    fin = ["order_id", "sales", "quantity", "discount", "profit"]
    out["dq_is_value_copy_suspect"] = out.groupby(fin)["product_id"].transform("nunique") > 1

    # DQ09 implied list price far from the product's median
    lp = implied_list_price(out)
    med = lp.groupby([out["product_id"], out["product_name"]]).transform("median")
    out["dq_is_price_anomaly"] = (lp / med - 1).abs() > config.PRICE_DEVIATION_THRESHOLD

    # DQ18 lines copied across orders (copy side only, see assumption A6)
    out["dq_is_clone_copy"] = clone_copy_mask(out)[1]

    # DQ10 statistical outliers (3 x IQR), kept in the data
    for col in ["sales", "profit"]:
        lo, hi = iqr_bounds(out[col], config.IQR_MULTIPLIER_EXTREME)
        out[f"dq_is_{col}_outlier"] = ~out[col].between(lo, hi)

    # Convenience column for customer-level analysis in later phases
    out["exclude_from_customer_analysis"] = (out["dq_is_identity_anomaly"]
                                             | out["dq_is_placeholder_customer"])

    for code, col in [("DQ05", "dq_is_identity_anomaly"), ("DQ06", "dq_is_placeholder_customer"),
                      ("DQ08", "dq_is_value_copy_suspect"), ("DQ09", "dq_is_price_anomaly"),
                      ("DQ18", "dq_is_clone_copy"), ("DQ10", "dq_is_sales_outlier"), ("DQ10", "dq_is_profit_outlier"),
                      ("DQ05+DQ06", "exclude_from_customer_analysis")]:
        log.record(f"Flag: {col}", code, int(out[col].sum()))
    return out


def enforce_types(df: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    out = df.copy()
    for col in config.TEXT_COLUMNS:
        out[col] = out[col].astype("string")
    out["row_id"] = out["row_id"].astype("int64")
    out["quantity"] = out["quantity"].astype("int64")
    for col in ["sales", "discount", "profit"]:
        out[col] = out[col].astype("float64")
    for col in config.DATE_COLUMNS:
        out[col] = pd.to_datetime(out[col])
    log.record("Enforce final data types", "-", 0)
    return out


# --------------------------------------------------------------------------
# Orchestrators
# --------------------------------------------------------------------------
def clean_orders(raw_orders: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    df = raw_orders.copy()  # never touch the raw frame
    df = standardize_column_names(df, config.ORDERS_COLUMN_MAP, log)
    df = strip_text(df, [c for c in config.TEXT_COLUMNS if c != "postal_code"], log)
    df = fix_postal_codes(df, log)
    df = fix_customer_id_case(df, log)
    df = fix_customer_name_case(df, log)
    df = remove_near_duplicates(df, log)
    df = add_quality_flags(df, log)
    df = enforce_types(df, log)
    return df


def clean_returns(raw_returns: pd.DataFrame) -> pd.DataFrame:
    out = raw_returns.rename(columns=config.RETURNS_COLUMN_MAP).copy()
    out["order_id"] = out["order_id"].astype("string").str.strip()
    out["is_returned"] = out["returned"].str.strip().str.lower().eq("yes")
    return out[["order_id", "is_returned"]].drop_duplicates()


def clean_people(raw_people: pd.DataFrame) -> pd.DataFrame:
    out = raw_people.rename(columns=config.PEOPLE_COLUMN_MAP).copy()
    for col in out.columns:
        out[col] = out[col].astype("string").str.strip()
    return out[["region", "regional_manager"]]


def run_cleaning(raw: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], CleaningLog]:
    log = CleaningLog()
    clean = {
        "orders": clean_orders(raw["orders"], log),
        "returns": clean_returns(raw["returns"]),
        "people": clean_people(raw["people"]),
    }
    return clean, log
