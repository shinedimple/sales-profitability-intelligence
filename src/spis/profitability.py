"""
Phase 5: Profitability analysis framework.

Central question: where is the company making money, and where is it destroying
profitability?

Framework (all thresholds are stated, relative to this data, and tested for
sensitivity):
  * Unit of analysis: product (product_key), with sub-category and the
    "policy cell" (state x sub-category, where discount is fixed) as
    higher-level views.
  * Evidence rule: a product needs >= MIN_LINES order lines to be classified;
    otherwise it is 'Insufficient evidence' (kept in totals, not classified).
  * Sales axis: product revenue vs the MEDIAN revenue of eligible products.
  * Profit axis: product margin vs the COMPANY margin (the hurdle every
    product must clear to avoid diluting overall profitability).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .eda import summarise

MIN_LINES = 3
DEEP_DISCOUNT = 0.30         # from Phase 4: >=30% is where lines almost always lose money
RELATIVE_DISCOUNT_PCTL = 0.90

QUADRANTS = {
    "Q1": "High sales, high margin (core earners)",
    "Q2": "High sales, low margin (margin leaks)",
    "Q3": "Low sales, high margin (niche earners)",
    "Q4": "Low sales, low margin (review candidates)",
    "NA": "Insufficient evidence (< 3 order lines)",
}


# --------------------------------------------------------------------------
# Product-level base table
# --------------------------------------------------------------------------
def product_metrics(df: pd.DataFrame) -> pd.DataFrame:
    keys = ["product_key", "product_label", "product_name", "category", "sub_category"]
    p = summarise(df, keys).reset_index()
    full = df[df["discount_rate"] == 0].groupby("product_key").agg(
        full_price_sales=("sales", "sum"), full_price_profit=("profit", "sum"),
        full_price_lines=("sales_line_id", "size"))
    disc = df[df["discount_rate"] > 0].groupby("product_key").agg(
        discounted_sales=("sales", "sum"), discounted_profit=("profit", "sum"),
        discounted_lines=("sales_line_id", "size"))
    deep = df[df["discount_rate"] >= DEEP_DISCOUNT].groupby("product_key").agg(
        deep_sales=("sales", "sum"), deep_profit=("profit", "sum"), deep_lines=("sales_line_id", "size"))
    p = p.join(full, on="product_key").join(disc, on="product_key").join(deep, on="product_key")
    fill = [c for c in p.columns if c.startswith(("full_price", "discounted_", "deep_"))]
    p[fill] = p[fill].fillna(0)
    p["full_price_margin"] = np.where(p["full_price_sales"] > 0, p["full_price_profit"] / p["full_price_sales"], np.nan)
    p["discounted_margin"] = np.where(p["discounted_sales"] > 0, p["discounted_profit"] / p["discounted_sales"], np.nan)
    p["avg_quantity_per_line"] = p["units"] / p["lines"]
    p["profit_per_unit"] = p["profit"] / p["units"]
    p["eligible"] = p["lines"] >= MIN_LINES
    return p


# --------------------------------------------------------------------------
# 1-4. Quadrants
# --------------------------------------------------------------------------
def assign_quadrants(p: pd.DataFrame, company_margin: float, sales_quantile: float = 0.5,
                     margin_hurdle: float | None = None) -> pd.Series:
    hurdle = company_margin if margin_hurdle is None else margin_hurdle
    elig = p["eligible"]
    sales_cut = p.loc[elig, "sales"].quantile(sales_quantile)
    high_sales = p["sales"] >= sales_cut
    high_margin = p["profit_margin"] >= hurdle
    q = np.select([~elig, high_sales & high_margin, high_sales & ~high_margin,
                   ~high_sales & high_margin], ["NA", "Q1", "Q2", "Q3"], default="Q4")
    return pd.Series(q, index=p.index)


def quadrant_summary(p: pd.DataFrame) -> pd.DataFrame:
    g = p.groupby("quadrant").agg(
        products=("product_key", "size"), sales=("sales", "sum"), profit=("profit", "sum"),
        gross_sales=("gross_sales", "sum"), discount_amount=("discount_amount", "sum"),
        units=("units", "sum"), lines=("lines", "sum"),
        loss_products=("profit", lambda s: (s < 0).sum()),
        median_product_sales=("sales", "median"), median_product_margin=("profit_margin", "median"))
    g["profit_margin"] = g["profit"] / g["sales"]
    g["effective_discount"] = g["discount_amount"] / g["gross_sales"]
    g["share_of_products"] = g["products"] / g["products"].sum()
    g["share_of_sales"] = g["sales"] / g["sales"].sum()
    g["share_of_profit"] = g["profit"] / g["profit"].sum()
    g["avg_quantity_per_line"] = g["units"] / g["lines"]
    g.insert(0, "definition", g.index.map(QUADRANTS))
    return g.reindex(["Q1", "Q2", "Q3", "Q4", "NA"])


def quadrant_composition(p: pd.DataFrame) -> pd.DataFrame:
    """Which sub-categories make up each quadrant (by revenue)?"""
    t = p.pivot_table(index="sub_category", columns="quadrant", values="sales", aggfunc="sum", fill_value=0)
    return t.div(t.sum(axis=0), axis=1)


def quadrant_examples(p: pd.DataFrame, quadrant: str, n: int = 5) -> pd.DataFrame:
    """Examples chosen by a stated metric: the products with the largest absolute profit impact."""
    q = p[p["quadrant"] == quadrant].copy()
    q["abs_profit"] = q["profit"].abs()
    return q.nlargest(n, "abs_profit")[["product_label", "sub_category", "sales", "profit", "profit_margin",
                                        "effective_discount", "lines", "full_price_margin", "discounted_margin"]]


def quadrant_sensitivity(p: pd.DataFrame, company_margin: float) -> pd.DataFrame:
    """
    How stable are the quadrants when the thresholds move? Each alternative is
    compared with the base case (median sales, company-margin hurdle).
    """
    base = p["quadrant"]
    scenarios = {
        "Sales cut at 60th percentile": dict(sales_quantile=0.6),
        "Sales cut at 40th percentile": dict(sales_quantile=0.4),
        "Margin hurdle 10%": dict(margin_hurdle=0.10),
        "Margin hurdle 15%": dict(margin_hurdle=0.15),
    }
    rows = []
    for name, kw in scenarios.items():
        alt = assign_quadrants(p, company_margin, **kw)
        elig = p["eligible"]
        moved = (alt != base) & elig
        q2 = alt == "Q2"
        rows.append({"scenario": name, "products_reclassified": int(moved.sum()),
                     "share_reclassified": moved.sum() / elig.sum(),
                     "q2_products": int(q2.sum()), "q2_profit": p.loc[q2, "profit"].sum(),
                     "q2_sales": p.loc[q2, "sales"].sum()})
    rows.insert(0, {"scenario": "Base: median sales, company margin", "products_reclassified": 0,
                    "share_reclassified": 0.0, "q2_products": int((base == "Q2").sum()),
                    "q2_profit": p.loc[base == "Q2", "profit"].sum(),
                    "q2_sales": p.loc[base == "Q2", "sales"].sum()})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# 5. Negative-profit products
# --------------------------------------------------------------------------
def negative_products(p: pd.DataFrame) -> pd.DataFrame:
    n = p[p["profit"] < 0].sort_values("profit").copy()
    n["share_of_product_losses"] = n["profit"] / n["profit"].sum()
    n["cumulative_share"] = n["share_of_product_losses"].cumsum()
    n["loss_rank"] = np.arange(1, len(n) + 1)
    return n


def loss_pareto_points(neg: pd.DataFrame) -> dict[str, float]:
    total = len(neg)
    return {f"products_for_{int(t*100)}pct_of_losses": int((neg["cumulative_share"] < t).sum() + 1)
            for t in (0.5, 0.8)} | {"loss_products": total}


# --------------------------------------------------------------------------
# 6. Unusually high discount
# --------------------------------------------------------------------------
def high_discount_products(p: pd.DataFrame) -> pd.DataFrame:
    """
    Two lenses, both stated:
      absolute: effective discount >= 30% (the level at which lines almost always lose money)
      relative: effective discount above the 90th percentile of products in the same sub-category
    Only eligible products are flagged.
    """
    q = p.copy()
    p90 = q[q["eligible"]].groupby("sub_category")["effective_discount"].quantile(RELATIVE_DISCOUNT_PCTL)
    q["sub_category_p90_discount"] = q["sub_category"].map(p90)
    q["flag_absolute"] = q["eligible"] & (q["effective_discount"] >= DEEP_DISCOUNT)
    q["flag_relative"] = q["eligible"] & (q["effective_discount"] > q["sub_category_p90_discount"])
    q["high_discount_lens"] = np.select(
        [q["flag_absolute"] & q["flag_relative"], q["flag_absolute"], q["flag_relative"]],
        ["Both", "Absolute (>=30%)", "Relative (> sub-category P90)"], default="")
    return q[q["high_discount_lens"] != ""].sort_values("effective_discount", ascending=False)


# --------------------------------------------------------------------------
# 7. Discount associated with weak profitability (within-product comparison)
# --------------------------------------------------------------------------
def discount_diagnosis(p: pd.DataFrame) -> pd.DataFrame:
    """
    Compare each product with ITSELF: margin on full-price lines vs discounted lines.
    This holds the product constant, which cross-product comparisons cannot.
    Requires >= 1 full-price line and >= 1 discounted line.

    Diagnosis (for loss-making products):
      'Loss even at full price'    : full-price margin < 0   -> price/cost problem
      'Profitable at full price, loss when discounted' : full-price margin >= 0,
                                      discounted margin < 0  -> discount-associated loss
    """
    d = p[(p["full_price_lines"] > 0) & (p["discounted_lines"] > 0)].copy()
    d["margin_gap_pp"] = d["discounted_margin"] - d["full_price_margin"]
    d["diagnosis"] = np.select(
        [d["full_price_margin"] < 0,
         (d["full_price_margin"] >= 0) & (d["discounted_margin"] < 0),
         d["discounted_margin"] < d["full_price_margin"]],
        ["Loss even at full price", "Profitable at full price, loss when discounted",
         "Profitable in both, lower margin when discounted"],
        default="Discounted margin not lower")
    return d


def loss_product_diagnosis(p: pd.DataFrame) -> pd.DataFrame:
    """Classify every loss-making product by what its own sales history can tell us."""
    n = p[p["profit"] < 0].copy()
    n["diagnosis"] = np.select(
        [(n["full_price_lines"] > 0) & (n["full_price_margin"] < 0),
         (n["full_price_lines"] > 0) & (n["discounted_lines"] > 0),
         n["full_price_lines"] == 0],
        ["Loss even at full price", "Profitable at full price, loss when discounted",
         "Only ever sold discounted (cannot test)"],
        default="Other")
    g = n.groupby("diagnosis").agg(products=("product_key", "size"), loss=("profit", "sum"),
                                   sales=("sales", "sum"), median_discount=("effective_discount", "median"))
    g["share_of_loss"] = g["loss"] / g["loss"].sum()
    return g.sort_values("loss")


# --------------------------------------------------------------------------
# Driver matrix: how strongly does each dimension separate margins?
# --------------------------------------------------------------------------
def driver_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """
    Sales-weighted eta-squared of LINE margin by each dimension:
        eta2 = between-group weighted variance / total weighted variance
    = the share of margin variation that lies BETWEEN the groups of a dimension.
    Descriptive only. Dimensions with many groups (product, state) score higher
    mechanically, so the number of groups is shown alongside.
    """
    d = df.copy()
    d["line_margin"] = d["profit"] / d["sales"]
    d["quantity_band"] = pd.cut(d["quantity"], [0, 2, 4, 7, 100], labels=["1-2", "3-4", "5-7", "8+"])
    w = d["sales"]
    total_mean = np.average(d["line_margin"], weights=w)
    total_var = np.average((d["line_margin"] - total_mean) ** 2, weights=w)
    dims = {"Discount level": "discount_rate", "Sub-category": "sub_category", "Category": "category",
            "State": "state_province", "Region": "region", "Segment": "segment",
            "Quantity band": "quantity_band", "Product": "product_key",
            "State x sub-category (policy cell)": ["state_province", "sub_category"]}
    rows = []
    for name, col in dims.items():
        grp_mean = d.groupby(col, observed=True).apply(
            lambda g: np.average(g["line_margin"], weights=g["sales"]), include_groups=False)
        fitted = d.join(grp_mean.rename("gm"), on=col)["gm"]
        between = np.average((fitted - total_mean) ** 2, weights=w)
        rows.append({"dimension": name, "groups": int(d.groupby(col, observed=True).ngroups),
                     "eta_squared": between / total_var})
    return pd.DataFrame(rows).sort_values("eta_squared", ascending=False)


def quantity_view(df: pd.DataFrame) -> pd.DataFrame:
    """Q: Do larger quantities per line earn better or worse margins?"""
    d = df.assign(quantity_band=pd.cut(df["quantity"], [0, 2, 4, 7, 100], labels=["1-2", "3-4", "5-7", "8+"]))
    g = summarise(d, "quantity_band")[["lines", "sales", "profit", "profit_margin", "effective_discount", "share_of_sales"]]
    return g


def dimension_view(df: pd.DataFrame, by: str | list[str]) -> pd.DataFrame:
    return summarise(df, by)[["sales", "profit", "profit_margin", "effective_discount", "units",
                              "lines", "loss_amount", "share_of_sales", "share_of_profit"]]


# --------------------------------------------------------------------------
# Policy cells: state x sub-category (the unit at which discount is decided)
# --------------------------------------------------------------------------
def policy_cells(df: pd.DataFrame) -> pd.DataFrame:
    c = summarise(df, ["state_province", "region", "sub_category", "category"]).reset_index()
    disc = df.groupby(["state_province", "sub_category"])["discount_rate"].first().rename("discount_rule")
    c = c.join(disc, on=["state_province", "sub_category"])
    c["profit_destroying"] = c["profit"] < 0
    return c[["state_province", "region", "category", "sub_category", "discount_rule", "sales", "profit",
              "profit_margin", "lines", "orders", "profit_destroying"]].sort_values("profit")


def policy_cell_summary(cells: pd.DataFrame) -> pd.DataFrame:
    c = cells.assign(rule_band=pd.cut(cells["discount_rule"], [-0.01, 0.0, 0.2, 0.4, 0.6, 0.8],
                                      labels=["0%", "1-20%", "21-40%", "41-60%", "61-80%"]))
    g = c.groupby("rule_band", observed=True).agg(
        cells=("sales", "size"), loss_cells=("profit_destroying", "sum"),
        sales=("sales", "sum"), profit=("profit", "sum"))
    g["profit_margin"] = g["profit"] / g["sales"]
    g["share_cells_loss_making"] = g["loss_cells"] / g["cells"]
    return g
