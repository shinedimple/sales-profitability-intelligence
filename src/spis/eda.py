"""
Phase 4: Exploratory Data Analysis (analysis functions).

Design rules
  * Every function answers one business question and returns a DataFrame.
  * No plotting here (see charts.py) and no narrative here (see findings.py):
    calculation, visualisation and interpretation are kept separate so each can
    be reviewed on its own.
  * Ratios are ratio-of-sums; orders and customers are distinct counts.
  * Data comes from the star schema (vw_sales_line), core scope only.
"""
from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

from . import config

MIN_ORDERS_GEO = 30        # minimum orders before a state/city margin is interpreted
MIN_LINES_PRODUCT = 3      # minimum order lines before a product margin is interpreted


# --------------------------------------------------------------------------
# Data access and helpers
# --------------------------------------------------------------------------
def load_core_lines(conn: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_sql_query("SELECT * FROM vw_sales_line WHERE is_core_scope = 1", conn,
                           parse_dates=["order_date", "ship_date"])
    df["order_month_start"] = df["order_date"].dt.to_period("M").dt.to_timestamp()
    return df


def summarise(df: pd.DataFrame, by: list[str] | str) -> pd.DataFrame:
    """Standard KPI block for any grouping (ratio-of-sums, distinct counts)."""
    agg = dict(sales=("sales", "sum"), profit=("profit", "sum"), units=("quantity", "sum"),
               orders=("order_id", "nunique"), customers=("customer_id", "nunique"),
               lines=("sales_line_id", "size"), gross_sales=("gross_sales", "sum"),
               discount_amount=("discount_amount", "sum"), loss_lines=("is_loss_line", "sum"),
               loss_amount=("profit", lambda s: s[s < 0].sum()))
    out = df.groupby(by, observed=True).agg(**agg)
    out["profit_margin"] = out["profit"] / out["sales"]
    out["aov"] = out["sales"] / out["orders"]
    out["effective_discount"] = out["discount_amount"] / out["gross_sales"]
    out["loss_line_share"] = out["loss_lines"] / out["lines"]
    out["share_of_sales"] = out["sales"] / out["sales"].sum()
    out["share_of_profit"] = out["profit"] / out["profit"].sum()
    return out


def overall(df: pd.DataFrame) -> pd.Series:
    """Headline KPIs as a Series (single group)."""
    tmp = df.assign(_all="All")
    return summarise(tmp, "_all").iloc[0]


# --------------------------------------------------------------------------
# A. Sales performance
# --------------------------------------------------------------------------
def yearly_performance(df: pd.DataFrame) -> pd.DataFrame:
    """Q: Is the business growing, and is growth coming from more orders or bigger orders?"""
    y = summarise(df, "order_year")[["sales", "profit", "profit_margin", "orders", "aov",
                                     "customers", "effective_discount"]]
    y["sales_yoy"] = y["sales"].pct_change()
    y["orders_yoy"] = y["orders"].pct_change()
    y["aov_yoy"] = y["aov"].pct_change()
    y["profit_yoy"] = np.where(y["profit"].shift() > 0, y["profit"] / y["profit"].shift() - 1, np.nan)
    # Growth decomposition: sales = orders x AOV, so ln-growth splits exactly
    y["growth_from_orders"] = np.log(y["orders"] / y["orders"].shift())
    y["growth_from_aov"] = np.log(y["aov"] / y["aov"].shift())
    return y


def monthly_performance(df: pd.DataFrame) -> pd.DataFrame:
    """Q: How do revenue and profit move month to month, and how volatile is monthly margin?"""
    m = summarise(df, "order_month_start")[["sales", "profit", "profit_margin", "orders", "aov"]]
    m["sales_same_month_py"] = m["sales"].shift(12)
    m["sales_yoy"] = m["sales"] / m["sales_same_month_py"] - 1
    m["sales_rolling_12m"] = m["sales"].rolling(12).sum()
    m["profit_rolling_12m"] = m["profit"].rolling(12).sum()
    m["margin_rolling_12m"] = m["profit_rolling_12m"] / m["sales_rolling_12m"]
    return m


def seasonality(df: pd.DataFrame) -> pd.DataFrame:
    """Q: Which months carry the year (share of annual sales), and is it stable?"""
    m = df.groupby(["order_year", "order_month"])["sales"].sum().rename("sales").reset_index()
    m["share"] = m["sales"] / m.groupby("order_year")["sales"].transform("sum")
    s = m.pivot(index="order_month", columns="order_year", values="share")
    s["mean_share"] = s.mean(axis=1)
    s["min_share"] = s.drop(columns="mean_share").min(axis=1)
    s["max_share"] = s.drop(columns=["mean_share", "min_share"]).max(axis=1)
    return s


def order_value_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Q: Is average order value representative, or driven by a few large orders?"""
    orders = df.groupby(["order_year", "order_id"])["sales"].sum().reset_index()
    out = orders.groupby("order_year")["sales"].describe(percentiles=[.25, .5, .75, .9])
    out["mean_to_median"] = out["mean"] / out["50%"]
    top5 = orders.groupby("order_year")["sales"].apply(
        lambda s: s.nlargest(max(1, int(len(s) * 0.05))).sum() / s.sum())
    out["top5pct_orders_share_of_sales"] = top5
    return out


# --------------------------------------------------------------------------
# B. Profitability
# --------------------------------------------------------------------------
def profitability_by(df: pd.DataFrame, by: str | list[str]) -> pd.DataFrame:
    cols = ["sales", "profit", "profit_margin", "share_of_sales", "share_of_profit",
            "effective_discount", "loss_amount", "loss_line_share", "orders", "lines"]
    return summarise(df, by)[cols].sort_values("profit", ascending=False)


def loss_concentration(df: pd.DataFrame) -> pd.DataFrame:
    """Q: How much profit is lost on loss-making lines, and where is it concentrated?"""
    losses = df[df["profit"] < 0]
    t = (losses.groupby(["category", "sub_category"])["profit"].sum().rename("loss_amount")
         .sort_values().reset_index())
    t["share_of_all_losses"] = t["loss_amount"] / losses["profit"].sum()
    t["cumulative_share"] = t["share_of_all_losses"].cumsum()
    return t


def mix_adjusted_margin(df: pd.DataFrame, group_col: str, mix_col: str = "discount_band") -> pd.DataFrame:
    """
    Q: Is a group's margin low because of WHAT it is, or because of its MIX of discounts?

    Method: direct standardisation. For each group we keep its own margin inside
    each discount band, but weight the bands by the COMPANY's sales mix:
        adjusted margin = sum_b ( company_sales_share_b x group_margin_b )
    If the gap to the company margin shrinks after adjustment, the group's
    discount mix explains that part of the gap. This is a descriptive control,
    not proof of causation.
    """
    company_mix = df.groupby(mix_col)["sales"].sum() / df["sales"].sum()
    cell = df.groupby([group_col, mix_col]).agg(sales=("sales", "sum"), profit=("profit", "sum"))
    cell["margin"] = cell["profit"] / cell["sales"]
    margin_by_band = cell["margin"].unstack(mix_col)
    # A group with no sales in a band falls back to the company margin in that band
    company_band_margin = df.groupby(mix_col).apply(lambda g: g["profit"].sum() / g["sales"].sum())
    margin_by_band = margin_by_band.fillna(company_band_margin)
    adjusted = (margin_by_band * company_mix).sum(axis=1)

    actual = summarise(df, group_col)[["sales", "profit_margin", "effective_discount"]]
    company_margin = df["profit"].sum() / df["sales"].sum()
    out = actual.join(adjusted.rename("mix_adjusted_margin"))
    out["gap_actual"] = out["profit_margin"] - company_margin
    out["gap_adjusted"] = out["mix_adjusted_margin"] - company_margin
    out["share_of_gap_explained_by_mix"] = np.where(
        out["gap_actual"].abs() > 0.005, 1 - out["gap_adjusted"] / out["gap_actual"], np.nan)
    return out.sort_values("profit_margin")


# --------------------------------------------------------------------------
# C. Products
# --------------------------------------------------------------------------
def product_table(df: pd.DataFrame) -> pd.DataFrame:
    p = summarise(df, ["product_key", "product_label", "category", "sub_category"])
    return p.reset_index()[["product_key", "product_label", "category", "sub_category", "sales",
                            "profit", "profit_margin", "units", "orders", "lines",
                            "effective_discount", "loss_lines"]]


def product_portfolio(products: pd.DataFrame, company_margin: float) -> pd.DataFrame:
    """
    Q: Which products are high-sales/low-profit and which are low-sales/high-margin?
    Thresholds are relative to this data: top/bottom sales quintile and company margin.
    Products with fewer than MIN_LINES_PRODUCT lines are labelled 'Insufficient data'.
    """
    p = products.copy()
    p["sales_quintile"] = pd.qcut(p["sales"].rank(method="first", ascending=False), 5,
                                  labels=[1, 2, 3, 4, 5]).astype(int)
    enough = p["lines"] >= MIN_LINES_PRODUCT
    p["portfolio_class"] = np.select(
        [~enough,
         (p["sales_quintile"] == 1) & (p["profit"] < 0),
         (p["sales_quintile"] == 1) & (p["profit_margin"] < company_margin),
         (p["sales_quintile"] >= 4) & (p["profit_margin"] >= 2 * company_margin)],
        ["Insufficient data", "High sales, loss-making", "High sales, below-average margin",
         "Low sales, high margin"],
        default="Other")
    return p


# --------------------------------------------------------------------------
# D. Customers
# --------------------------------------------------------------------------
def customer_table(df: pd.DataFrame) -> pd.DataFrame:
    valid = df[df["is_excluded_from_customer_analysis"] == 0]
    c = summarise(valid, ["customer_id", "customer_name", "segment"]).reset_index()
    first_last = valid.groupby("customer_id")["order_date"].agg(["min", "max"])
    c = c.join(first_last, on="customer_id")
    c["active_years"] = valid.groupby("customer_id")["order_year"].nunique().reindex(c["customer_id"]).values
    return c[["customer_id", "customer_name", "segment", "sales", "profit", "profit_margin",
              "orders", "aov", "effective_discount", "loss_amount", "active_years", "min", "max"]]


def customer_concentration(customers: pd.DataFrame) -> pd.DataFrame:
    """Q: How concentrated are sales and profit among customers (Pareto points)?"""
    rows = []
    for metric in ["sales", "profit"]:
        s = customers[metric].sort_values(ascending=False).reset_index(drop=True)
        cum = s.cumsum() / s.sum()
        for top in [0.05, 0.10, 0.20, 0.50]:
            k = int(np.ceil(len(s) * top))
            rows.append({"metric": metric, "top_customers_share": top, "customers": k,
                         "share_of_total": cum.iloc[k - 1]})
    return pd.DataFrame(rows)


def lorenz_points(values: pd.Series) -> pd.DataFrame:
    s = values.sort_values(ascending=False).reset_index(drop=True)
    return pd.DataFrame({"customer_share": (np.arange(1, len(s) + 1)) / len(s),
                         "cumulative_share": s.cumsum() / s.sum()})


def customer_discount_profit(customers: pd.DataFrame) -> pd.DataFrame:
    """Q: Are unprofitable customers simply the ones who receive deep discounts?"""
    c = customers.copy()
    c["discount_group"] = pd.cut(c["effective_discount"], [-0.001, 0.10, 0.20, 0.30, 1.0],
                                 labels=["0-10%", "10-20%", "20-30%", "30%+"])
    g = c.groupby("discount_group", observed=True).agg(
        customers=("customer_id", "size"), sales=("sales", "sum"), profit=("profit", "sum"),
        unprofitable=("profit", lambda s: (s < 0).sum()))
    g["profit_margin"] = g["profit"] / g["sales"]
    g["share_unprofitable"] = g["unprofitable"] / g["customers"]
    return g


def order_frequency(df: pd.DataFrame, customers: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Q: How often do customers reorder, and are frequent buyers more valuable?"""
    valid = df[df["is_excluded_from_customer_analysis"] == 0]
    orders = valid.groupby(["customer_id", "order_id"])["order_date"].min().reset_index()
    orders = orders.sort_values(["customer_id", "order_date"])
    orders["gap_days"] = orders.groupby("customer_id")["order_date"].diff().dt.days
    gaps = orders["gap_days"].dropna()
    gap_summary = gaps.describe(percentiles=[.25, .5, .75]).to_frame("days_between_orders")

    c = customers.copy()
    c["frequency_band"] = pd.cut(c["orders"], [0, 3, 6, 10, 100],
                                 labels=["1-3 orders", "4-6 orders", "7-10 orders", "11+ orders"])
    band = c.groupby("frequency_band", observed=True).agg(
        customers=("customer_id", "size"), sales=("sales", "sum"), profit=("profit", "sum"),
        median_customer_profit=("profit", "median"))
    band["profit_margin"] = band["profit"] / band["sales"]
    band["share_of_customers"] = band["customers"] / band["customers"].sum()
    band["share_of_profit"] = band["profit"] / band["profit"].sum()

    retention = []
    years = sorted(valid["order_year"].unique())
    active = {y: set(valid.loc[valid["order_year"] == y, "customer_id"]) for y in years}
    for y in years[:-1]:
        retention.append({"base_year": y, "active": len(active[y]),
                          "retained_next_year": len(active[y] & active[y + 1]),
                          "retention_rate": len(active[y] & active[y + 1]) / len(active[y])})
    return {"gap_summary": gap_summary, "frequency_bands": band,
            "retention": pd.DataFrame(retention)}


def segment_performance(df: pd.DataFrame) -> pd.DataFrame:
    valid = df[df["is_excluded_from_customer_analysis"] == 0]
    s = summarise(valid, "segment")[["sales", "profit", "profit_margin", "customers", "orders",
                                     "aov", "effective_discount", "share_of_sales", "share_of_profit"]]
    s["profit_per_customer"] = s["profit"] / s["customers"]
    s["orders_per_customer"] = s["orders"] / s["customers"]
    return s


# --------------------------------------------------------------------------
# E. Geography
# --------------------------------------------------------------------------
def geography(df: pd.DataFrame, level: str) -> pd.DataFrame:
    """level: 'region', 'state_province' or 'city_state'."""
    keys = {"region": ["region", "regional_manager"], "state_province": ["state_province", "region"],
            "city_state": ["city_state", "state_province", "region"]}[level]
    g = summarise(df, keys)[["sales", "profit", "profit_margin", "effective_discount", "orders",
                             "loss_amount", "share_of_sales", "share_of_profit"]].reset_index()
    if level != "region":
        g["volume_flag"] = np.where(g["orders"] >= MIN_ORDERS_GEO, "OK", "Low volume")
    return g.sort_values("profit")


def geo_discount_relationship(geo: pd.DataFrame) -> dict[str, float]:
    """Q: Across states, does a higher effective discount go with a lower margin?"""
    ok = geo[geo["volume_flag"] == "OK"]
    return {"states_used": len(ok),
            "spearman_discount_vs_margin": ok["effective_discount"].corr(ok["profit_margin"], method="spearman"),
            "pearson_discount_vs_margin": ok["effective_discount"].corr(ok["profit_margin"])}


# --------------------------------------------------------------------------
# F. Discounts
# --------------------------------------------------------------------------
def discount_levels(df: pd.DataFrame) -> pd.DataFrame:
    """Q: How do sales, volume and profit per line change with the discount level?"""
    g = df.groupby("discount_rate").agg(
        lines=("sales_line_id", "size"), sales=("sales", "sum"), profit=("profit", "sum"),
        gross_sales=("gross_sales", "sum"), units=("quantity", "sum"),
        median_line_sales=("sales", "median"), mean_quantity=("quantity", "mean"),
        loss_line_share=("is_loss_line", "mean"))
    g["profit_margin"] = g["profit"] / g["sales"]
    g["profit_per_line"] = g["profit"] / g["lines"]
    g["share_of_lines"] = g["lines"] / g["lines"].sum()
    return g


def discount_quantity_check(df: pd.DataFrame) -> pd.DataFrame:
    """
    Q: Do discounted lines sell more units? Compared WITHIN sub-category to avoid
    comparing cheap paper with expensive copiers.
    """
    d = df.assign(discounted=np.where(df["discount_rate"] > 0, "Discounted", "Full price"))
    t = d.pivot_table(index="sub_category", columns="discounted", values="quantity", aggfunc="mean")
    t["difference"] = t["Discounted"] - t["Full price"]
    return t.sort_values("difference")


def discount_by_subcategory(df: pd.DataFrame) -> pd.DataFrame:
    """Q: Which sub-categories lose money even at low discounts? (margin heat map)"""
    cell = df.groupby(["sub_category", "discount_band", "discount_band_sort"]).agg(
        sales=("sales", "sum"), profit=("profit", "sum"), lines=("sales_line_id", "size")).reset_index()
    cell["margin"] = cell["profit"] / cell["sales"]
    order = cell.sort_values("discount_band_sort")["discount_band"].unique()
    margin = cell.pivot(index="sub_category", columns="discount_band", values="margin")[order]
    lines = cell.pivot(index="sub_category", columns="discount_band", values="lines")[order]
    return margin, lines


def discount_line_correlation(df: pd.DataFrame) -> dict[str, float]:
    """Rank correlation between discount and line margin across all lines."""
    margin = df["profit"] / df["sales"]
    return {"spearman_discount_vs_line_margin": df["discount_rate"].corr(margin, method="spearman"),
            "spearman_discount_vs_line_sales": df["discount_rate"].corr(df["sales"], method="spearman"),
            "spearman_discount_vs_quantity": df["discount_rate"].corr(df["quantity"], method="spearman")}


def _r2(y: pd.Series, groups: list[pd.Series]) -> float:
    fitted = y.groupby(groups).transform("mean")
    return float(1 - ((y - fitted) ** 2).sum() / ((y - y.mean()) ** 2).sum())


def discount_policy_structure(df: pd.DataFrame) -> dict[str, float]:
    """
    Q: Is discount negotiated per order, or set by a fixed rule?
    R-squared of discount explained by group averages: 1.0 means the grouping
    fully determines the discount (no variation left inside a group).
    """
    cells = df.groupby(["state_province", "sub_category"])["discount_rate"].nunique()
    zero_share = df.groupby("state_province")["discount_rate"].apply(lambda s: (s == 0).mean())
    d = df["discount_rate"]
    return {
        "state_subcategory_cells": int(len(cells)),
        "share_cells_single_discount": float((cells == 1).mean()),
        "r2_state": _r2(d, [df["state_province"]]),
        "r2_sub_category": _r2(d, [df["sub_category"]]),
        "r2_state_x_sub_category": _r2(d, [df["state_province"], df["sub_category"]]),
        "states": int(df["state_province"].nunique()),
        "states_never_full_price": int((zero_share == 0).sum()),
        "states_always_full_price": int((zero_share == 1).sum()),
    }
