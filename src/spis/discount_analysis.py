"""
Phase 6: Discount and profitability analysis.

Business question: is discounting helping the business generate profitable
growth, or is it eroding profitability?

The module separates four kinds of evidence, and every function says which
kind it produces:
  DESCRIPTIVE  - what the numbers are (totals, shares, margins by group)
  CORRELATION  - how strongly two variables move together (rank correlation)
  EXPLANATION  - a mechanism the data can verify (e.g. price arithmetic)
  CAUSAL       - what would happen if discount changed; requires variation the
                 data must actually contain (tested in rule_stability)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .eda import summarise

DEEP = 0.30

BAND_SCHEMES = {
    "A. Proposed: 0 | 1-10 | 10-20 | 20-30 | 30+": ([-0.01, 0, 0.10, 0.20, 0.30, 1.0],
                                                    ["0%", "1-10%", "10-20%", "20-30%", "30%+"]),
    "B. Model bands: 0 | 1-20 | 21-40 | 41-60 | 61-80": ([-0.01, 0, 0.20, 0.40, 0.60, 0.80],
                                                         ["0%", "1-20%", "21-40%", "41-60%", "61-80%"]),
    "C. Alternative: 0 | 1-20 | 21-40 | 41-50 | 51-80": ([-0.01, 0, 0.20, 0.40, 0.50, 0.80],
                                                         ["0%", "1-20%", "21-40%", "41-50%", "51-80%"]),
}
RECOMMENDED_SCHEME = "B. Model bands: 0 | 1-20 | 21-40 | 41-60 | 61-80"


# --------------------------------------------------------------------------
# Unit economics (EXPLANATION layer)
# --------------------------------------------------------------------------
def add_unit_economics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Line margin m, discount d. If cost per unit is fixed and the discount only
    lowers the price, then:  m = 1 - (1 - m0) / (1 - d)
    where m0 = the product's margin at list price. Rearranged, every line
    implies a list margin:   m0 = 1 - (1 - m)(1 - d).
    The break-even discount of a product equals its list margin m0.
    """
    d = df.copy()
    d["line_margin"] = d["profit"] / d["sales"]
    d["implied_list_margin"] = 1 - (1 - d["line_margin"]) * (1 - d["discount_rate"])
    d["headroom"] = d["implied_list_margin"] - d["discount_rate"]       # > 0: discount below break-even
    d["beyond_break_even"] = d["discount_rate"] > d["implied_list_margin"] + 1e-9
    d["headroom_band"] = np.select(
        [d["discount_rate"] == 0, d["headroom"] > 0.10, d["headroom"] >= -1e-9],
        ["Full price", "Discounted, >10 pp below break-even", "Discounted, within 10 pp of break-even"],
        default="Discounted beyond break-even")
    return d


def identity_check(d: pd.DataFrame) -> dict[str, float]:
    """
    Verify the price-arithmetic mechanism two ways:
      1. Implied list margin must be constant within each product.
      2. For products also sold at full price, the margin predicted from the
         full-price margin must equal the actual discounted margin.
    """
    spread = d.groupby("product_key")["implied_list_margin"].agg(lambda s: s.max() - s.min())
    fp = d[d["discount_rate"] == 0].groupby("product_key").apply(
        lambda g: g["profit"].sum() / g["sales"].sum(), include_groups=False).rename("fp_margin")
    disc = d[d["discount_rate"] > 0].join(fp, on="product_key").dropna(subset=["fp_margin"])
    pred = 1 - (1 - disc["fp_margin"]) / (1 - disc["discount_rate"])
    err = (disc["line_margin"] - pred).abs()
    return {"products": int(d["product_key"].nunique()),
            "max_spread_implied_list_margin": float(spread.max()),
            "discounted_lines_tested": int(len(disc)),
            "max_abs_prediction_error": float(err.max()),
            "loss_lines_equal_beyond_break_even": float(((d["profit"] < 0) == d["beyond_break_even"]).mean())}


def list_margin_distribution(d: pd.DataFrame) -> pd.Series:
    return d.groupby("product_key")["implied_list_margin"].first().describe(percentiles=[.1, .25, .5, .75, .9])


def headroom_summary(d: pd.DataFrame) -> pd.DataFrame:
    """DESCRIPTIVE: revenue and profit by distance from each product's own break-even discount."""
    order = ["Full price", "Discounted, >10 pp below break-even", "Discounted, within 10 pp of break-even",
             "Discounted beyond break-even"]
    g = summarise(d, "headroom_band")[["lines", "sales", "profit", "profit_margin", "effective_discount",
                                       "share_of_sales", "share_of_profit", "loss_line_share"]]
    return g.reindex(order)


# --------------------------------------------------------------------------
# DESCRIPTIVE layer
# --------------------------------------------------------------------------
def discount_averages(d: pd.DataFrame) -> pd.DataFrame:
    """'Average discount' has several defensible definitions; they give different answers."""
    rows = [
        ("Simple average of line discount rates", d["discount_rate"].mean(),
         "Every line counts equally, a 2-dollar line as much as a 2,000-dollar line."),
        ("Average weighted by net revenue", np.average(d["discount_rate"], weights=d["sales"]),
         "Weights by revenue after discount, which under-weights deeply discounted lines."),
        ("Effective discount rate (recommended)", d["discount_amount"].sum() / d["gross_sales"].sum(),
         "Discount given away / list value. Answers: what share of list value did we give up?"),
        ("Share of lines discounted", (d["discount_rate"] > 0).mean(), "How common discounting is."),
        ("Share of lines at 30%+ discount", (d["discount_rate"] >= DEEP).mean(), "How common deep discounting is."),
    ]
    return pd.DataFrame(rows, columns=["measure", "value", "meaning"])


def distribution(d: pd.DataFrame) -> pd.DataFrame:
    g = d.groupby("discount_rate").agg(lines=("sales_line_id", "size"), sales=("sales", "sum"),
                                       gross_sales=("gross_sales", "sum"), discount_amount=("discount_amount", "sum"),
                                       profit=("profit", "sum"), units=("quantity", "sum"))
    g["share_of_lines"] = g["lines"] / g["lines"].sum()
    g["share_of_sales"] = g["sales"] / g["sales"].sum()
    g["share_of_discount_given"] = g["discount_amount"] / g["discount_amount"].sum()
    g["cumulative_share_of_lines"] = g["share_of_lines"].cumsum()
    return g


def by_dimension(d: pd.DataFrame, col: str | list[str]) -> pd.DataFrame:
    s = summarise(d, col)
    extra = d.groupby(col).agg(
        avg_line_discount=("discount_rate", "mean"),
        share_lines_discounted=("discount_rate", lambda x: (x > 0).mean()),
        share_lines_deep=("discount_rate", lambda x: (x >= DEEP).mean()))
    beyond = d.groupby(col).apply(lambda g: g.loc[g["beyond_break_even"], "sales"].sum() / g["sales"].sum(),
                                  include_groups=False).rename("share_sales_beyond_break_even")
    lm = d.groupby(col).apply(lambda g: np.average(g["implied_list_margin"], weights=g["gross_sales"]),
                              include_groups=False).rename("list_margin")
    out = s[["sales", "profit", "profit_margin", "effective_discount", "discount_amount"]].join(extra).join(beyond).join(lm)
    return out.sort_values("effective_discount", ascending=False)


def level_relationship(d: pd.DataFrame) -> pd.DataFrame:
    """DESCRIPTIVE: sales, profit, margin and volume at each observed discount level."""
    g = d.groupby("discount_rate").agg(
        lines=("sales_line_id", "size"), sales=("sales", "sum"), profit=("profit", "sum"),
        units=("quantity", "sum"), median_line_sales=("sales", "median"),
        median_line_list_value=("gross_sales", "median"), loss_line_share=("is_loss_line", "mean"))
    g["profit_margin"] = g["profit"] / g["sales"]
    g["units_per_line"] = g["units"] / g["lines"]
    g["profit_per_line"] = g["profit"] / g["lines"]
    return g


def band_evaluation(d: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """
    Evaluate candidate band schemes against four stated criteria:
      1. Explanatory power: sales-weighted eta-squared of line margin (vs the 12 raw levels)
      2. Sample size: smallest band (lines)
      3. Homogeneity: largest margin range between discount levels inside one band
      4. Business meaning: does a boundary fall at the profit break-even (between 20% and 30%)?
    """
    w = d["sales"]
    tm = np.average(d["line_margin"], weights=w)
    tv = np.average((d["line_margin"] - tm) ** 2, weights=w)

    def eta(labels: pd.Series) -> float:
        gm = d.groupby(labels, observed=True).apply(
            lambda g: g["profit"].sum() / g["sales"].sum(), include_groups=False)
        fitted = labels.map(gm).astype(float)
        return float(np.average((fitted - tm) ** 2, weights=w) / tv)

    levels_eta = eta(d["discount_rate"].astype(str))
    level_margin = d.groupby("discount_rate").apply(lambda g: g["profit"].sum() / g["sales"].sum(), include_groups=False)
    rows, details = [], {}
    for name, (bins, labels) in BAND_SCHEMES.items():
        band = pd.cut(d["discount_rate"], bins, labels=labels)
        tab = summarise(d.assign(band=band), "band")[["lines", "sales", "profit", "profit_margin", "share_of_sales"]]
        lv = pd.DataFrame({"band": pd.cut(level_margin.index.to_series(), bins, labels=labels), "m": level_margin})
        within = lv.groupby("band", observed=True)["m"].agg(lambda s: s.max() - s.min())
        tab["levels_in_band"] = lv.groupby("band", observed=True)["m"].size()
        tab["margin_range_within_band"] = within
        details[name] = tab
        e = eta(band.astype(str))
        rows.append({"scheme": name, "bands": len(labels), "eta_squared": e,
                     "share_of_level_detail_retained": e / levels_eta,
                     "smallest_band_lines": int(tab["lines"].min()),
                     "max_margin_range_within_band": float(within.max()),
                     "boundary_at_break_even_20_30": bool(any(0.20 - 1e-9 <= b < 0.30 for b in bins[1:-1]))})
    rows.append({"scheme": "Reference: 12 raw discount levels", "bands": 12, "eta_squared": levels_eta,
                 "share_of_level_detail_retained": 1.0, "smallest_band_lines": int(d["discount_rate"].value_counts().min()),
                 "max_margin_range_within_band": 0.0, "boundary_at_break_even_20_30": True})
    return pd.DataFrame(rows), details


def dimension_band_mix(d: pd.DataFrame, col: str) -> pd.DataFrame:
    """DESCRIPTIVE: share of each group's revenue in each recommended band."""
    bins, labels = BAND_SCHEMES[RECOMMENDED_SCHEME]
    band = pd.cut(d["discount_rate"], bins, labels=labels)
    t = d.assign(band=band).pivot_table(index=col, columns="band", values="sales", aggfunc="sum", observed=False, fill_value=0)
    return t.div(t.sum(axis=1), axis=0)


# --------------------------------------------------------------------------
# CORRELATION layer
# --------------------------------------------------------------------------
def correlations(d: pd.DataFrame, customers: pd.DataFrame, states: pd.DataFrame,
                 basket: dict, state_growth: dict) -> pd.DataFrame:
    sub_corr = d.groupby("sub_category").apply(
        lambda g: g["discount_rate"].corr(g["line_margin"], method="spearman") if g["discount_rate"].nunique() > 1 else np.nan,
        include_groups=False)
    rows = [
        ("Discount vs line margin", "Order line", len(d), d["discount_rate"].corr(d["line_margin"], method="spearman")),
        ("Discount vs line margin, within sub-category (median of 17)", "Order line", len(d), sub_corr.median()),
        ("Discount vs units per line", "Order line", len(d), d["discount_rate"].corr(d["quantity"], method="spearman")),
        ("Discount vs line revenue", "Order line", len(d), d["discount_rate"].corr(d["sales"], method="spearman")),
        ("Effective discount vs margin", "Customer", len(customers),
         customers["effective_discount"].corr(customers["profit_margin"], method="spearman")),
        ("Effective discount vs margin", "State (30+ orders)", state_growth["states"],
         states["effective_discount"].corr(states["profit_margin"], method="spearman")),
        ("Effective discount vs revenue growth 2023-2026", "State (30+ orders)", state_growth["states"], state_growth["spearman"]),
        ("Relative discount vs share of the state's purchases (revenue)", "State x sub-category", basket["cells"], basket["spearman_revenue"]),
        ("Relative discount vs share of the state's purchases (units)", "State x sub-category", basket["cells"], basket["spearman_units"]),
    ]
    out = pd.DataFrame(rows, columns=["relationship", "level", "n", "spearman_rho"])
    out["strength"] = pd.cut(out["spearman_rho"].abs(), [-0.01, 0.1, 0.3, 0.5, 1.0],
                             labels=["None / negligible", "Weak", "Moderate", "Strong"])
    return out


def basket_share_test(d: pd.DataFrame, min_state_sales: float = 20000) -> dict:
    """
    If discounts attract demand, a sub-category that is discounted more heavily
    in a state than elsewhere should take a LARGER share of that state's
    purchases. Index = sub-category share of state purchases / national share.
    Discount is expressed relative to the sub-category's average rule.
    """
    cell = d.groupby(["state_province", "sub_category"]).agg(
        sales=("sales", "sum"), units=("quantity", "sum"), rule=("discount_rate", "first")).reset_index()
    tot = cell.groupby("state_province")[["sales", "units"]].transform("sum")
    nat_s = d.groupby("sub_category")["sales"].sum() / d["sales"].sum()
    nat_u = d.groupby("sub_category")["quantity"].sum() / d["quantity"].sum()
    cell["rev_index"] = np.log((cell["sales"] / tot["sales"]) / cell["sub_category"].map(nat_s))
    cell["unit_index"] = np.log((cell["units"] / tot["units"]) / cell["sub_category"].map(nat_u))
    cell["relative_rule"] = cell["rule"] - cell.groupby("sub_category")["rule"].transform("mean")
    big = cell[tot["sales"] >= min_state_sales]
    return {"cells": len(big),
            "spearman_revenue": big["relative_rule"].corr(big["rev_index"], method="spearman"),
            "spearman_units": big["relative_rule"].corr(big["unit_index"], method="spearman"),
            "table": big}


def state_growth_test(d: pd.DataFrame, min_orders: int = 30) -> dict:
    st = d.groupby("state_province").agg(orders=("order_id", "nunique"), disc=("discount_amount", "sum"),
                                         gross=("gross_sales", "sum"))
    st["effective_discount"] = st["disc"] / st["gross"]
    first, last = d["order_year"].min(), d["order_year"].max()
    s0 = d[d["order_year"] == first].groupby("state_province")["sales"].sum()
    s1 = d[d["order_year"] == last].groupby("state_province")["sales"].sum()
    st["revenue_growth"] = s1 / s0 - 1
    ok = st[st["orders"] >= min_orders].dropna()
    return {"states": len(ok), "spearman": ok["effective_discount"].corr(ok["revenue_growth"], method="spearman"), "table": ok}


# --------------------------------------------------------------------------
# Growth: did discounted business grow faster?
# --------------------------------------------------------------------------
def growth_by_band(d: pd.DataFrame) -> dict[str, pd.DataFrame]:
    bins, labels = BAND_SCHEMES[RECOMMENDED_SCHEME]
    x = d.assign(band=pd.cut(d["discount_rate"], bins, labels=labels))
    out = {}
    for metric, agg in [("revenue", ("sales", "sum")), ("units", ("quantity", "sum")), ("orders", ("order_id", "nunique")),
                        ("profit", ("profit", "sum"))]:
        t = x.groupby(["order_year", "band"], observed=True).agg(v=agg)["v"].unstack()
        out[metric] = t
    first, last = x["order_year"].min(), x["order_year"].max()
    summary = pd.DataFrame({f"{m}_index_{last}_vs_{first}": out[m].loc[last] / out[m].loc[first]
                            for m in ["revenue", "units", "orders"]})
    summary["revenue_cagr"] = summary.iloc[:, 0] ** (1 / (last - first)) - 1
    summary["profit_first_year"] = out["profit"].loc[first]
    summary["profit_last_year"] = out["profit"].loc[last]
    out["summary"] = summary
    return out


# --------------------------------------------------------------------------
# CAUSAL layer: what variation exists?
# --------------------------------------------------------------------------
def rule_stability(d: pd.DataFrame) -> dict:
    """
    A causal estimate needs discount to vary for comparable sales: within the
    same state and sub-category, or over time for the same rule. Test both.
    """
    cell = d.groupby(["state_province", "sub_category"]).agg(
        levels=("discount_rate", "nunique"), years=("order_year", "nunique"))
    multi_year = cell[cell["years"] > 1]
    return {"policy_cells": len(cell),
            "cells_with_more_than_one_discount_level": int((cell["levels"] > 1).sum()),
            "cells_observed_in_several_years": len(multi_year),
            "multi_year_cells_where_rule_changed": int((multi_year["levels"] > 1).sum())}


# --------------------------------------------------------------------------
# Arithmetic: volume needed for a discount to pay for itself
# --------------------------------------------------------------------------
def break_even_volume(list_margins=(0.20, 0.33, 0.45), discounts=(0.05, 0.10, 0.15, 0.20, 0.30, 0.40)) -> pd.DataFrame:
    """
    ARITHMETIC, not data: with unit cost fixed, profit per unit falls from m0*P
    to (m0 - d)*P, so keeping the same profit needs m0 / (m0 - d) times the units.
    Undefined (infinite) once d >= m0.
    """
    rows = []
    for m0 in list_margins:
        for disc in discounts:
            rows.append({"list_margin": m0, "discount": disc,
                         "volume_multiplier_needed": m0 / (m0 - disc) if disc < m0 else np.inf})
    t = pd.DataFrame(rows).pivot(index="discount", columns="list_margin", values="volume_multiplier_needed")
    t.columns = [f"list margin {c:.0%}" for c in t.columns]
    return t
