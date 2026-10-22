"""
Data-quality AUDIT.

Rule: the audit only observes. It never changes the input data. Every check
returns a structured CheckResult, and row-level findings are written to an
issue log (row_id -> issue_code). Cleaning decisions are taken later.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from . import config

PASS, WARN, FAIL, INFO = "PASS", "WARN", "FAIL", "INFO"


@dataclass
class CheckResult:
    section: str          # which audit area (maps to the Phase 1 brief)
    check: str            # what was tested
    status: str           # PASS / WARN / FAIL / INFO
    n_affected: int = 0   # rows (or entities) affected
    detail: str = ""      # human-readable evidence
    issue_code: str = ""  # link to ISSUE_CATALOG, if an issue was found


@dataclass
class AuditResult:
    checks: list[CheckResult] = field(default_factory=list)
    issue_rows: list[pd.DataFrame] = field(default_factory=list)
    profile: dict = field(default_factory=dict)

    def add(self, result: CheckResult, rows: pd.Series | None = None) -> None:
        """Store a check and, optionally, the row_ids it affects."""
        self.checks.append(result)
        if rows is not None and len(rows) and result.issue_code:
            self.issue_rows.append(
                pd.DataFrame({"row_id": rows.values, "issue_code": result.issue_code})
            )

    def checks_frame(self) -> pd.DataFrame:
        return pd.DataFrame([c.__dict__ for c in self.checks])

    def issue_log(self) -> pd.DataFrame:
        if not self.issue_rows:
            return pd.DataFrame(columns=["row_id", "issue_code"])
        return (pd.concat(self.issue_rows, ignore_index=True)
                .drop_duplicates()
                .sort_values(["issue_code", "row_id"], ignore_index=True))


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _status(condition_ok: bool, fail_status: str = WARN) -> str:
    return PASS if condition_ok else fail_status


def _rename_for_audit(orders: pd.DataFrame) -> pd.DataFrame:
    """Rename columns only (values untouched) so checks can use stable names."""
    return orders.rename(columns=config.ORDERS_COLUMN_MAP).copy()


def implied_list_price(df: pd.DataFrame) -> pd.Series:
    """Unit price before discount = sales / (quantity * (1 - discount))."""
    return df["sales"] / (df["quantity"] * (1 - df["discount"]))


def clone_copy_mask(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """
    Find order lines copied across orders.

    A clone group = lines in DIFFERENT orders sharing the order sequence number
    (last 6 digits of order_id), customer, product and sales value.
    Returns (in_clone_group, is_copy): copies are the non-primary-market rows.
    """
    key = [df["order_id"].str[-6:], df["customer_id"].str.upper(),
           df["product_id"], df["sales"].round(3)]
    in_group = (df.groupby(key)["order_id"].transform("nunique") > 1).astype(bool)
    is_copy = (in_group & df["country"].ne(config.PRIMARY_MARKET)).astype(bool)
    return in_group, is_copy


def iqr_bounds(series: pd.Series, k: float) -> tuple[float, float]:
    q1, q3 = series.quantile([0.25, 0.75])
    iqr = q3 - q1
    return q1 - k * iqr, q3 + k * iqr


# --------------------------------------------------------------------------
# 1-4. Structure: load, dimensions, columns, data types
# --------------------------------------------------------------------------
def audit_structure(raw: dict[str, pd.DataFrame], res: AuditResult) -> None:
    orders = raw["orders"]
    res.profile["dimensions"] = {name: df.shape for name, df in raw.items()}
    res.profile["columns"] = list(orders.columns)
    res.profile["dtypes"] = orders.dtypes.astype(str).to_dict()

    missing_cols = set(config.EXPECTED_ORDER_COLUMNS) - set(orders.columns)
    extra_cols = set(orders.columns) - set(config.EXPECTED_ORDER_COLUMNS)
    res.add(CheckResult(
        "Structure", "All expected Orders columns present, no unexpected columns",
        _status(not missing_cols and not extra_cols, FAIL),
        len(missing_cols) + len(extra_cols),
        f"missing={sorted(missing_cols)}, unexpected={sorted(extra_cols)}"))

    # Postal code: mixed Python types inside one column is a type problem
    type_mix = orders["Postal Code"].map(lambda v: type(v).__name__).value_counts().to_dict()
    res.profile["postal_code_types"] = type_mix
    df = _rename_for_audit(orders)
    is_us = df["country"].eq("United States")
    lost_zero = is_us & df["postal_code"].map(lambda v: isinstance(v, (int, np.integer)) and v < 10000)
    res.add(CheckResult(
        "Data types", "Postal code stored as a consistent text type",
        _status(len(type_mix) == 1), int(lost_zero.sum()),
        f"python types in column: {type_mix}; US codes that lost a leading zero: {int(lost_zero.sum())}",
        "DQ02"), df.loc[lost_zero, "row_id"])

    for col in ["Order Date", "Ship Date"]:
        ok = pd.api.types.is_datetime64_any_dtype(orders[col])
        res.add(CheckResult("Data types", f"{col} parsed as datetime", _status(ok, FAIL),
                            0 if ok else len(orders), str(orders[col].dtype)))
    for col in ["Sales", "Quantity", "Discount", "Profit"]:
        ok = pd.api.types.is_numeric_dtype(orders[col])
        res.add(CheckResult("Data types", f"{col} is numeric", _status(ok, FAIL),
                            0 if ok else len(orders), str(orders[col].dtype)))


# --------------------------------------------------------------------------
# 5. Missing values  |  6. Duplicates
# --------------------------------------------------------------------------
def audit_missing_and_duplicates(raw: dict[str, pd.DataFrame], res: AuditResult) -> None:
    missing = {name: int(df.isna().sum().sum()) for name, df in raw.items()}
    res.profile["missing_by_table"] = missing
    res.profile["missing_by_column"] = raw["orders"].isna().sum().to_dict()
    # Blank strings are "hidden" missing values that isna() does not catch
    orders = raw["orders"]
    blanks = int(sum(orders[c].astype(str).str.strip().eq("").sum()
                     for c in orders.select_dtypes(include=["object", "string"]).columns))
    res.add(CheckResult("Missing values", "No null values in any table",
                        _status(sum(missing.values()) == 0, FAIL), sum(missing.values()),
                        f"nulls per table: {missing}"))
    res.add(CheckResult("Missing values", "No blank / whitespace-only text values",
                        _status(blanks == 0), blanks))

    df = _rename_for_audit(orders)
    exact = int(df.duplicated().sum())
    res.add(CheckResult("Duplicates", "No fully identical rows", _status(exact == 0, FAIL), exact))
    res.add(CheckResult("Duplicates", "row_id is unique (primary key)",
                        _status(df["row_id"].is_unique, FAIL),
                        int(df["row_id"].duplicated().sum())))

    business_cols = [c for c in df.columns if c != "row_id"]
    near_dup = df.duplicated(subset=business_cols, keep="first")
    res.add(CheckResult(
        "Duplicates", "No rows identical in every business column (ignoring row_id)",
        _status(near_dup.sum() == 0), int(near_dup.sum()),
        "copies: " + ", ".join(f"row {r} ({o})" for r, o in
                               df.loc[near_dup, ["row_id", "order_id"]].itertuples(index=False)),
        "DQ01"), df.loc[near_dup, "row_id"])

    same_line = df.duplicated(subset=["order_id", "product_id"], keep=False) & ~df.duplicated(
        subset=business_cols, keep=False)
    lp = implied_list_price(df.loc[same_line])
    spread = lp.groupby([df.loc[same_line, "order_id"], df.loc[same_line, "product_id"]]).agg(
        lambda s: s.max() / s.min())
    consistent = int((spread < 1.01).sum())
    res.add(CheckResult(
        "Duplicates", "Same product on several lines of one order (not exact copies)",
        INFO, int(same_line.sum()),
        f"{len(spread)} order-product pairs; {consistent} with identical unit price "
        f"(split lines); inconsistent in orders "
        f"{sorted(spread[spread >= 1.01].index.get_level_values(0).unique())}", "DQ16"),
        df.loc[same_line, "row_id"])

    returns = raw["returns"]
    res.add(CheckResult("Duplicates", "Returns: Order ID unique",
                        _status(returns["Order ID"].is_unique, FAIL),
                        int(returns["Order ID"].duplicated().sum())))


# --------------------------------------------------------------------------
# 7. Dates
# --------------------------------------------------------------------------
def audit_dates(df: pd.DataFrame, res: AuditResult, today: date) -> None:
    res.profile["date_range"] = {
        "order_date": (df["order_date"].min().date(), df["order_date"].max().date()),
        "ship_date": (df["ship_date"].min().date(), df["ship_date"].max().date()),
    }
    days = (df["ship_date"] - df["order_date"]).dt.days
    res.profile["ship_days_by_mode"] = (df.assign(days=days).groupby("ship_mode")["days"]
                                        .agg(["min", "mean", "max"]).round(2))
    res.profile["rows_per_year"] = df["order_date"].dt.year.value_counts().sort_index().to_dict()

    neg = days < 0
    res.add(CheckResult("Dates", "Ship date never before order date",
                        _status(not neg.any(), FAIL), int(neg.sum())))
    slow = days > config.MAX_PLAUSIBLE_SHIP_DAYS
    res.add(CheckResult("Dates", f"Shipping time <= {config.MAX_PLAUSIBLE_SHIP_DAYS} days",
                        _status(not slow.any()), int(slow.sum()), f"max days = {days.max()}"))

    future = df["order_date"].dt.date > today
    res.add(CheckResult(
        "Dates", f"Order dates not later than today ({today})",
        _status(not future.any()), int(future.sum()),
        f"latest order date {df['order_date'].max().date()}: dataset years are synthetic",
        "DQ13"))  # dataset-level issue: no row log needed

    id_year = pd.to_numeric(df["order_id"].str[3:7], errors="coerce")
    mismatch = id_year != df["order_date"].dt.year
    res.add(CheckResult("Dates", "Year embedded in Order ID matches order date year",
                        _status(not mismatch.any()), int(mismatch.sum())))

    # Order-level attributes must be identical on every line of an order
    per_order = df.groupby("order_id")[["order_date", "ship_date", "ship_mode"]].nunique()
    bad = int((per_order > 1).any(axis=1).sum())
    res.add(CheckResult("Dates", "Order date, ship date and ship mode consistent within each order",
                        _status(bad == 0), bad))


# --------------------------------------------------------------------------
# 8, 9, 11. Numeric columns: ranges, impossible and unusual values
# --------------------------------------------------------------------------
def audit_numeric(df: pd.DataFrame, res: AuditResult) -> None:
    desc = df[config.NUMERIC_COLUMNS].describe(percentiles=[.01, .05, .25, .5, .75, .95, .99]).T
    desc["skew"] = df[config.NUMERIC_COLUMNS].skew()
    res.profile["numeric_summary"] = desc.round(3)
    res.profile["discount_levels"] = df["discount"].value_counts().sort_index().to_dict()

    rules = [
        ("sales > 0", df["sales"] <= 0, FAIL),
        ("quantity >= 1", df["quantity"] < 1, FAIL),
        ("quantity is a whole number", df["quantity"] % 1 != 0, FAIL),
        ("0 <= discount < 1", ~df["discount"].between(config.VALID_DISCOUNT_RANGE[0],
                                                      config.VALID_DISCOUNT_RANGE[1],
                                                      inclusive="left"), FAIL),
        ("profit <= sales (margin cannot exceed 100%)", df["profit"] > df["sales"], FAIL),
    ]
    for label, mask, fail in rules:
        res.add(CheckResult("Impossible values", label, _status(not mask.any(), fail),
                            int(mask.sum())), df.loc[mask, "row_id"])

    margin = df["profit"] / df["sales"]
    zero_profit = df["profit"].eq(0)
    res.add(CheckResult("Unusual values", "Lines with profit exactly 0", INFO,
                        int(zero_profit.sum()),
                        f"{zero_profit.mean():.1%} of lines; discounts on these lines: "
                        f"{sorted(float(x) for x in df.loc[zero_profit, 'discount'].unique())}", "DQ15"),
            df.loc[zero_profit, "row_id"])

    deep_loss = margin < -1
    res.add(CheckResult(
        "Unusual values", "Lines where loss exceeds the line's sales (margin < -100%)", INFO,
        int(deep_loss.sum()),
        f"min margin {margin.min():.0%}; minimum discount on these lines "
        f"{df.loc[deep_loss, 'discount'].min():.0%}", "DQ17"), df.loc[deep_loss, "row_id"])

    zero_disc_loss = (df["discount"] == 0) & (df["profit"] < 0)
    res.add(CheckResult("Unusual values", "Loss-making lines with zero discount (plausibility)",
                        INFO, int(zero_disc_loss.sum()),
                        "noted for Phase 3; not interpreted here"))

    # Implied list price stability per product (ID + name, to avoid ID-reuse effects)
    lp = implied_list_price(df)
    med = lp.groupby([df["product_id"], df["product_name"]]).transform("median")
    deviation = (lp / med - 1).abs()
    anomaly = deviation > config.PRICE_DEVIATION_THRESHOLD
    res.add(CheckResult(
        "Unusual values",
        f"Implied list price within {config.PRICE_DEVIATION_THRESHOLD:.0%} of product median",
        _status(not anomaly.any()), int(anomaly.sum()),
        f"{df.loc[anomaly, 'product_id'].nunique()} products affected; "
        f"max ratio to median {(lp / med).max():.0f}x", "DQ09"), df.loc[anomaly, "row_id"])


# --------------------------------------------------------------------------
# 12. Outliers
# --------------------------------------------------------------------------
def audit_outliers(df: pd.DataFrame, res: AuditResult) -> None:
    """
    IQR (Tukey) method: robust because it is based on quartiles, which are not
    pulled by extreme values. Z-scores assume a roughly normal distribution,
    which these heavily skewed columns are not.
    """
    summary = {}
    for col in ["sales", "profit", "quantity"]:
        lo_m, hi_m = iqr_bounds(df[col], config.IQR_MULTIPLIER_MILD)
        lo_x, hi_x = iqr_bounds(df[col], config.IQR_MULTIPLIER_EXTREME)
        mild = ~df[col].between(lo_m, hi_m)
        extreme = ~df[col].between(lo_x, hi_x)
        summary[col] = {"fence_1.5_low": lo_m, "fence_1.5_high": hi_m, "n_1.5": int(mild.sum()),
                        "fence_3_low": lo_x, "fence_3_high": hi_x, "n_3": int(extreme.sum()),
                        "share_of_total_3": float(df.loc[extreme, col].sum() / df[col].sum())}
        if col in ("sales", "profit"):
            res.add(CheckResult(
                "Outliers", f"{col}: values beyond 3 x IQR fences", INFO, int(extreme.sum()),
                f"fences [{lo_x:,.2f}, {hi_x:,.2f}]; these rows hold "
                f"{summary[col]['share_of_total_3']:.1%} of total {col}", "DQ10"),
                df.loc[extreme, "row_id"])
    res.profile["outliers"] = pd.DataFrame(summary).T.round(3)


# --------------------------------------------------------------------------
# 10. Categorical consistency
# --------------------------------------------------------------------------
def audit_categoricals(df: pd.DataFrame, people: pd.DataFrame, res: AuditResult) -> None:
    res.profile["categorical_counts"] = {
        c: df[c].value_counts().to_dict() for c in config.EXPECTED_DOMAINS}
    res.profile["category_tree"] = (df.groupby("category")["sub_category"]
                                    .apply(lambda s: sorted(s.unique())).to_dict())

    for col, allowed in config.EXPECTED_DOMAINS.items():
        bad = ~df[col].isin(allowed)
        res.add(CheckResult("Categorical consistency", f"{col} values within expected domain",
                            _status(not bad.any(), FAIL), int(bad.sum()),
                            f"unexpected: {sorted(df.loc[bad, col].unique())}"))

    text_cols = df.select_dtypes(include=["object", "string"]).columns
    ws = sum(int((df[c].astype(str) != df[c].astype(str).str.strip()).sum()) for c in text_cols)
    res.add(CheckResult("Categorical consistency", "No leading/trailing whitespace", _status(ws == 0), ws))

    for col in ["city", "state_province", "product_name", "sub_category"]:
        uniq = pd.Series(df[col].unique())
        collisions = int(uniq.str.lower().duplicated().sum())
        res.add(CheckResult("Categorical consistency", f"No case-variant spellings in {col}",
                            _status(collisions == 0), collisions))

    hierarchies = [("sub_category", "category"), ("state_province", "region"),
                   ("state_province", "country"), ("customer_id", "segment")]
    for child, parent in hierarchies:
        n = int((df.groupby(child)[parent].nunique() > 1).sum())
        res.add(CheckResult("Categorical consistency", f"Each {child} maps to one {parent}",
                            _status(n == 0, FAIL), n))

    lower_name = df["customer_name"].str.split().map(lambda ws: any(w[:1].islower() for w in ws))
    res.add(CheckResult("Categorical consistency", "Customer names consistently capitalised",
                        _status(not lower_name.any()), int(lower_name.sum()),
                        f"examples: {sorted(df.loc[lower_name, 'customer_name'].unique())}", "DQ04"),
            df.loc[lower_name, "row_id"])

    city_multi_state = int((df.groupby("city")["state_province"].nunique() > 1).sum())
    res.add(CheckResult("Categorical consistency", "City names that exist in several states",
                        INFO, city_multi_state, "real geography; use city + state", "DQ12"))

    pc = df["postal_code"].astype(str)
    multi_city = df.assign(pc=pc).groupby("pc")["city"].nunique()
    bad_pc = multi_city[multi_city > 1].index
    mask = pc.isin(bad_pc)
    res.add(CheckResult("Categorical consistency", "Each postal code maps to one city",
                        _status(len(bad_pc) == 0), len(bad_pc),
                        f"postal codes: {list(bad_pc)}", "DQ11"), df.loc[mask, "row_id"])

    missing_mgr = set(df["region"]) - set(people["Region"])
    res.add(CheckResult("Referential integrity", "Every region has a regional manager",
                        _status(not missing_mgr, FAIL), len(missing_mgr)))


# --------------------------------------------------------------------------
# 13. Identifiers: Order, Product, Customer
# --------------------------------------------------------------------------
def audit_identifiers(df: pd.DataFrame, returns: pd.DataFrame, res: AuditResult) -> None:
    res.profile["unique_counts"] = {
        "order_id": df["order_id"].nunique(), "customer_id": df["customer_id"].nunique(),
        "customer_name": df["customer_name"].nunique(), "product_id": df["product_id"].nunique(),
        "product_name": df["product_name"].nunique(), "city": df["city"].nunique(),
        "state_province": df["state_province"].nunique(),
        "postal_code": df["postal_code"].astype(str).nunique(),
    }

    # Format checks
    for col, pattern, code in [("order_id", config.ORDER_ID_PATTERN, ""),
                               ("product_id", config.PRODUCT_ID_PATTERN, ""),
                               ("customer_id", config.CUSTOMER_ID_PATTERN, "DQ03")]:
        bad = ~df[col].astype(str).str.match(pattern)
        res.add(CheckResult("Identifiers", f"{col} matches expected format",
                            _status(not bad.any()), int(bad.sum()),
                            f"examples: {sorted(df.loc[bad, col].unique())[:5]}",
                            code if bad.any() else ""), df.loc[bad, "row_id"])

    # Upper-casing customer IDs must not merge two different customers
    upper = df["customer_id"].str.upper()
    collide = int((df.groupby(upper)["customer_id"].nunique() > 1).sum())
    res.add(CheckResult("Identifiers", "Upper-casing customer_id creates no collisions",
                        _status(collide == 0, FAIL), collide))

    # Prefix agreement
    pref_cat = df["product_id"].str[:3].map(config.PRODUCT_PREFIX_TO_CATEGORY) != df["category"]
    res.add(CheckResult("Identifiers", "Product ID prefix agrees with category",
                        _status(not pref_cat.any(), FAIL), int(pref_cat.sum())))
    pref_cty = df["order_id"].str[:2].map(config.ORDER_PREFIX_TO_COUNTRY) != df["country"]
    res.add(CheckResult("Identifiers", "Order ID prefix agrees with country",
                        _status(not pref_cty.any(), FAIL), int(pref_cty.sum())))

    # Product: one product ID -> one hierarchy; ID <-> name one-to-one?
    hier = int((df.groupby("product_id")[["category", "sub_category"]].nunique() > 1).any(axis=1).sum())
    res.add(CheckResult("Identifiers", "Each product_id belongs to one category/sub-category",
                        _status(hier == 0, FAIL), hier))
    id_multi_name = df.groupby("product_id")["product_name"].nunique()
    name_multi_id = df.groupby("product_name")["product_id"].nunique()
    affected = df["product_id"].isin(id_multi_name[id_multi_name > 1].index) | \
        df["product_name"].isin(name_multi_id[name_multi_id > 1].index)
    res.add(CheckResult(
        "Identifiers", "product_id and product_name are one-to-one",
        _status(not affected.any()), int(affected.sum()),
        f"{int((id_multi_name > 1).sum())} IDs with 2+ names; "
        f"{int((name_multi_id > 1).sum())} names with 2+ IDs", "DQ07"), df.loc[affected, "row_id"])

    # Customer: one ID -> one name; one name -> one ID; one order -> one customer
    id_multi_cname = int((df.groupby("customer_id")["customer_name"].nunique() > 1).sum())
    res.add(CheckResult("Identifiers", "Each customer_id has one name",
                        _status(id_multi_cname == 0), id_multi_cname))

    name_ids = df.groupby("customer_name")["customer_id"].nunique()
    multi_id_names = name_ids[name_ids > 1].index
    order_cust = df.groupby("order_id")["customer_id"].nunique()
    multi_cust_orders = order_cust[order_cust > 1].index
    anomaly = df["customer_name"].isin(multi_id_names) | df["order_id"].isin(multi_cust_orders)
    res.add(CheckResult(
        "Identifiers", "Each customer name has one ID and each order has one customer",
        _status(not anomaly.any()), int(anomaly.sum()),
        f"names with several IDs: {list(multi_id_names)}; orders with several customers: "
        f"{list(multi_cust_orders)}", "DQ05"), df.loc[anomaly, "row_id"])

    placeholder = df["customer_name"].str.contains(config.PLACEHOLDER_NAME_PATTERN,
                                                   case=False, regex=True)
    res.add(CheckResult(
        "Identifiers", "No placeholder / test customer names",
        _status(not placeholder.any()), int(placeholder.sum()),
        f"names: {sorted(df.loc[placeholder, 'customer_name'].unique())}; "
        f"sales {df.loc[placeholder, 'sales'].sum():,.2f}", "DQ06"), df.loc[placeholder, "row_id"])

    # Copy-paste suspicion: different products, identical financials, same order
    fin = ["order_id", "sales", "quantity", "discount", "profit"]
    grp = df.groupby(fin)["product_id"].transform("nunique")
    copied = grp > 1
    res.add(CheckResult(
        "Identifiers", "Different products in one order do not share identical financial values",
        _status(not copied.any()), int(copied.sum()),
        f"orders: {sorted(df.loc[copied, 'order_id'].unique())}", "DQ08"), df.loc[copied, "row_id"])

    # Order-level geography should be single-valued
    multi = (df.groupby("order_id")[["city", "state_province", "region"]].nunique() > 1).any(axis=1)
    multi_orders = multi[multi].index
    res.add(CheckResult("Identifiers", "Each order ships to one location",
                        _status(len(multi_orders) == 0), len(multi_orders),
                        f"orders: {list(multi_orders)}", "DQ19"),
            df.loc[df["order_id"].isin(multi_orders), "row_id"])

    in_group, is_copy = clone_copy_mask(df)
    us_twins = int((in_group & ~is_copy).sum())
    res.add(CheckResult(
        "Identifiers", "No order lines copied across different orders",
        _status(not in_group.any()), int(is_copy.sum()),
        f"{int(in_group.sum())} lines in clone groups; {int(is_copy.sum())} non-US copies "
        f"(sales {df.loc[is_copy, 'sales'].sum():,.2f} = "
        f"{df.loc[is_copy, 'sales'].sum() / df.loc[df['country'].eq('Canada'), 'sales'].sum():.0%} "
        f"of Canadian sales); {us_twins} US lines are the matching originals", "DQ18"),
        df.loc[is_copy, "row_id"])

    # Returns referential integrity
    orphan = ~returns["Order ID"].isin(df["order_id"])
    res.add(CheckResult("Referential integrity", "Every returned Order ID exists in Orders",
                        _status(not orphan.any(), FAIL), int(orphan.sum())))
    res.add(CheckResult("Referential integrity", "Returns are recorded per order, not per line",
                        INFO, int(returns["Order ID"].nunique()),
                        f"{int(df['order_id'].isin(returns['Order ID']).sum())} order lines belong "
                        "to returned orders", "DQ14"))


# --------------------------------------------------------------------------
# Orchestrator
# --------------------------------------------------------------------------
def run_audit(raw: dict[str, pd.DataFrame], today: date | None = None) -> AuditResult:
    """Run every audit check on the raw tables. Input data is never modified."""
    today = today or date.today()
    snapshot = {k: v.copy() for k, v in raw.items()}  # guard against accidental mutation
    res = AuditResult()
    df = _rename_for_audit(raw["orders"])

    audit_structure(raw, res)
    audit_missing_and_duplicates(raw, res)
    audit_dates(df, res, today)
    audit_numeric(df, res)
    audit_outliers(df, res)
    audit_categoricals(df, raw["people"], res)
    audit_identifiers(df, raw["returns"], res)

    for name in raw:
        pd.testing.assert_frame_equal(raw[name], snapshot[name])  # audit must not mutate input
    return res
