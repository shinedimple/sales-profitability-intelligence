"""
Phase 7: Customer profitability analysis.

Population: valid customers (placeholder and identity-anomaly customers
excluded), core scope.

Segmentation: customer revenue (vs median) x customer margin (vs company
margin), with an evidence rule (>= MIN_ORDERS orders). RFM is evaluated, not
assumed: see segmentation_comparison().
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .discount_analysis import add_unit_economics

MIN_ORDERS = 3

SEGMENTS = {
    "C1": "High revenue, high margin (core accounts)",
    "C2": "High revenue, low margin (margin-dilutive accounts)",
    "C3": "Low revenue, high margin (efficient small accounts)",
    "C4": "Low revenue, low margin (low-value accounts)",
    "NA": f"Limited history (< {MIN_ORDERS} orders)",
}
SHORT = {"C1": "C1 Core", "C2": "C2 Margin-dilutive", "C3": "C3 Efficient small",
         "C4": "C4 Low-value", "NA": "Limited history"}


def valid_lines(df: pd.DataFrame) -> pd.DataFrame:
    d = add_unit_economics(df)
    return d[d["is_excluded_from_customer_analysis"] == 0].copy()


# --------------------------------------------------------------------------
# Customer table
# --------------------------------------------------------------------------
def customer_metrics(v: pd.DataFrame) -> pd.DataFrame:
    end = v["order_date"].max()
    c = v.groupby(["customer_id", "customer_name", "segment"]).agg(
        revenue=("sales", "sum"), profit=("profit", "sum"), gross_sales=("gross_sales", "sum"),
        discount_amount=("discount_amount", "sum"), orders=("order_id", "nunique"), lines=("sales_line_id", "size"),
        units=("quantity", "sum"), first_order=("order_date", "min"), last_order=("order_date", "max"),
        active_years=("order_year", "nunique"), ship_to_states=("state_province", "nunique"),
        worst_line_profit=("profit", "min")).reset_index()
    bb = v[v["beyond_break_even"]].groupby("customer_id").agg(beyond_be_revenue=("sales", "sum"),
                                                             beyond_be_profit=("profit", "sum"))
    c = c.join(bb, on="customer_id").fillna({"beyond_be_revenue": 0, "beyond_be_profit": 0})
    c["profit_margin"] = c["profit"] / c["revenue"]
    c["avg_order_value"] = c["revenue"] / c["orders"]
    c["profit_per_order"] = c["profit"] / c["orders"]
    c["effective_discount"] = c["discount_amount"] / c["gross_sales"]
    c["observed_tenure_days"] = (c["last_order"] - c["first_order"]).dt.days
    c["days_since_last_order"] = (end - c["last_order"]).dt.days
    c["orders_per_active_year"] = c["orders"] / c["active_years"]
    c["beyond_be_share"] = c["beyond_be_revenue"] / c["revenue"]
    c["profit_within_be"] = c["profit"] - c["beyond_be_profit"]
    c["profit_excl_worst_line"] = c["profit"] - c["worst_line_profit"]
    gaps = (v.groupby(["customer_id", "order_id"])["order_date"].min().reset_index()
            .sort_values(["customer_id", "order_date"]))
    gaps["gap"] = gaps.groupby("customer_id")["order_date"].diff().dt.days
    c = c.join(gaps.groupby("customer_id")["gap"].median().rename("median_days_between_orders"), on="customer_id")
    c["eligible"] = c["orders"] >= MIN_ORDERS
    return c


def headline_metrics(c: pd.DataFrame) -> pd.DataFrame:
    """Customer-level distributions: medians are reported because all measures are skewed."""
    cols = {"revenue": "Revenue per customer", "profit": "Profit per customer", "orders": "Orders per customer",
            "avg_order_value": "Average order value", "profit_margin": "Profit margin",
            "observed_tenure_days": "Observed tenure (days, first to last order)",
            "median_days_between_orders": "Median days between orders",
            "days_since_last_order": "Days since last order (to data end)",
            "active_years": "Active years (of 4)", "ship_to_states": "Ship-to states per customer"}
    t = c[list(cols)].describe(percentiles=[.1, .25, .5, .75, .9]).T
    t.index = [cols[i] for i in t.index]
    return t[["mean", "10%", "25%", "50%", "75%", "90%"]]


def history_coverage(c: pd.DataFrame, v: pd.DataFrame) -> dict[str, float]:
    first_year, last_year = v["order_year"].min(), v["order_year"].max()
    return {"customers": len(c),
            "share_first_seen_in_first_year": float((c["first_order"].dt.year == first_year).mean()),
            "share_active_in_last_year": float((c["last_order"].dt.year == last_year).mean()),
            "share_with_fewer_than_3_orders": float((c["orders"] < MIN_ORDERS).mean())}


# --------------------------------------------------------------------------
# Segmentation
# --------------------------------------------------------------------------
def assign_segments(c: pd.DataFrame, company_margin: float, revenue_quantile: float = 0.5,
                    margin_hurdle: float | None = None) -> pd.Series:
    hurdle = company_margin if margin_hurdle is None else margin_hurdle
    cut = c.loc[c["eligible"], "revenue"].quantile(revenue_quantile)
    hi_r, hi_m = c["revenue"] >= cut, c["profit_margin"] >= hurdle
    return pd.Series(np.select([~c["eligible"], hi_r & hi_m, hi_r & ~hi_m, ~hi_r & hi_m],
                               ["NA", "C1", "C2", "C3"], default="C4"), index=c.index)


def segment_summary(c: pd.DataFrame) -> pd.DataFrame:
    g = c.groupby("cust_segment").agg(
        customers=("customer_id", "size"), revenue=("revenue", "sum"), profit=("profit", "sum"),
        gross_sales=("gross_sales", "sum"), discount_amount=("discount_amount", "sum"),
        orders=("orders", "sum"), beyond_be_revenue=("beyond_be_revenue", "sum"),
        beyond_be_profit=("beyond_be_profit", "sum"), unprofitable=("profit", lambda s: (s < 0).sum()),
        median_revenue=("revenue", "median"), median_profit=("profit", "median"),
        median_orders=("orders", "median"), median_aov=("avg_order_value", "median"))
    g["profit_margin"] = g["profit"] / g["revenue"]
    g["effective_discount"] = g["discount_amount"] / g["gross_sales"]
    g["beyond_be_share"] = g["beyond_be_revenue"] / g["revenue"]
    g["profit_within_be"] = g["profit"] - g["beyond_be_profit"]
    g["revenue_per_customer"] = g["revenue"] / g["customers"]
    g["profit_per_customer"] = g["profit"] / g["customers"]
    g["orders_per_customer"] = g["orders"] / g["customers"]
    g["share_of_customers"] = g["customers"] / g["customers"].sum()
    g["share_of_revenue"] = g["revenue"] / g["revenue"].sum()
    g["share_of_profit"] = g["profit"] / g["profit"].sum()
    g.insert(0, "definition", g.index.map(SEGMENTS))
    return g.reindex(["C1", "C2", "C3", "C4", "NA"])


def segment_examples(c: pd.DataFrame, seg: str, n: int = 5) -> pd.DataFrame:
    """Examples ranked by a stated metric: largest absolute profit impact |profit|."""
    s = c[c["cust_segment"] == seg].assign(abs_profit=lambda x: x["profit"].abs())
    return s.nlargest(n, "abs_profit")[["customer_id", "customer_name", "segment", "revenue", "profit",
                                         "profit_margin", "orders", "effective_discount", "beyond_be_share"]]


def segment_sensitivity(c: pd.DataFrame, company_margin: float) -> pd.DataFrame:
    base = c["cust_segment"]
    rows = [{"scenario": "Base: median revenue, company margin", "reclassified": 0, "share_reclassified": 0.0,
             "c2_customers": int((base == "C2").sum()), "c2_profit": c.loc[base == "C2", "profit"].sum()}]
    for name, kw in {"Revenue cut at 60th percentile": dict(revenue_quantile=0.6),
                     "Revenue cut at 40th percentile": dict(revenue_quantile=0.4),
                     "Margin hurdle 10%": dict(margin_hurdle=0.10), "Margin hurdle 15%": dict(margin_hurdle=0.15)}.items():
        alt = assign_segments(c, company_margin, **kw)
        moved = (alt != base) & c["eligible"]
        rows.append({"scenario": name, "reclassified": int(moved.sum()), "share_reclassified": moved.sum() / c["eligible"].sum(),
                     "c2_customers": int((alt == "C2").sum()), "c2_profit": c.loc[alt == "C2", "profit"].sum()})
    return pd.DataFrame(rows)


def segment_by_customer_type(c: pd.DataFrame) -> pd.DataFrame:
    """Share of each business segment's customers in each profitability segment."""
    t = pd.crosstab(c["segment"], c["cust_segment"], normalize="index")
    return t.reindex(columns=["C1", "C2", "C3", "C4", "NA"], fill_value=0)


# --------------------------------------------------------------------------
# Is RFM appropriate? Compare how well segmentations separate customer margin
# --------------------------------------------------------------------------
def _eta(y: pd.Series, g: pd.Series) -> float:
    gm = y.groupby(g).transform("mean")
    return float(1 - ((y - gm) ** 2).sum() / ((y - y.mean()) ** 2).sum())


def segmentation_comparison(c: pd.DataFrame) -> pd.DataFrame:
    """
    Share of the variation in customer margin and customer profit that lies
    between the groups of each candidate segmentation (eta-squared, eligible
    customers only, margin capped at +/-100% to limit single-line distortion).
    """
    e = c[c["eligible"]].copy()
    q = lambda s, asc=True: pd.qcut(s.rank(method="first", ascending=asc), 5, labels=False) + 1
    e["R"] = q(-e["days_since_last_order"])
    e["F"] = q(e["orders"])
    e["M"] = q(e["revenue"])
    e["RFM"] = e["R"].astype(str) + e["F"].astype(str) + e["M"].astype(str)
    e["revenue_band"] = q(e["revenue"])
    e["be_band"] = pd.cut(e["beyond_be_share"], [-0.01, 0, 0.10, 0.25, 1.0])
    m = e["profit_margin"].clip(-1, 1)
    rows = []
    for name, col in [("Recency quintile (R)", "R"), ("Frequency quintile (F)", "F"), ("Monetary quintile (M)", "M"),
                      ("Full RFM score", "RFM"), ("Revenue x margin matrix (this analysis)", "cust_segment"),
                      ("Share of revenue beyond break-even (4 bands)", "be_band")]:
        rows.append({"segmentation": name, "groups": int(e[col].nunique()),
                     "eta_margin": _eta(m, e[col]), "eta_profit": _eta(e["profit"], e[col])})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Is customer profitability a stable trait? (persistence test)
# --------------------------------------------------------------------------
def persistence(v: pd.DataFrame, company_margin: float) -> dict:
    years = sorted(v["order_year"].unique())
    mid = years[len(years) // 2 - 1]
    h1 = v[v["order_year"] <= mid].groupby("customer_id").agg(r1=("sales", "sum"), p1=("profit", "sum"), o1=("order_id", "nunique"))
    h2 = v[v["order_year"] > mid].groupby("customer_id").agg(r2=("sales", "sum"), p2=("profit", "sum"), o2=("order_id", "nunique"))
    j = h1.join(h2, how="inner")
    j["m1"], j["m2"] = j["p1"] / j["r1"], j["p2"] / j["r2"]
    lo1, lo2 = j["m1"] < company_margin, j["m2"] < company_margin
    hr1, hr2 = j["r1"] >= j["r1"].median(), j["r2"] >= j["r2"].median()
    j["seg1"] = np.select([hr1 & ~lo1, hr1 & lo1, ~hr1 & ~lo1], ["C1", "C2", "C3"], "C4")
    j["seg2"] = np.select([hr2 & ~lo2, hr2 & lo2, ~hr2 & ~lo2], ["C1", "C2", "C3"], "C4")
    matrix = pd.crosstab(j["seg1"], j["seg2"])
    return {"period_1": f"{years[0]}-{mid}", "period_2": f"{mid + 1}-{years[-1]}", "customers_in_both": len(j),
            "spearman_margin": j["m1"].corr(j["m2"], method="spearman"),
            "spearman_revenue": j["r1"].corr(j["r2"], method="spearman"),
            "spearman_profit": j["p1"].corr(j["p2"], method="spearman"),
            "p_low_margin_again_if_low": float((lo1 & lo2).sum() / lo1.sum()),
            "p_low_margin_if_previously_high": float((~lo1 & lo2).sum() / (~lo1).sum()),
            "same_segment_share": float((j["seg1"] == j["seg2"]).mean()),
            "matrix": matrix}


# --------------------------------------------------------------------------
# Unprofitable customers: what explains them?
# --------------------------------------------------------------------------
def unprofitable_diagnosis(c: pd.DataFrame) -> pd.DataFrame:
    u = c[c["profit"] < 0]
    rows = [("Unprofitable customers", len(u), u["profit"].sum()),
            ("... with no line beyond break-even", int((u["beyond_be_revenue"] == 0).sum()), u.loc[u["beyond_be_revenue"] == 0, "profit"].sum()),
            ("... profitable on their within-break-even lines", int((u["profit_within_be"] > 0).sum()), u.loc[u["profit_within_be"] > 0, "profit"].sum()),
            ("... profitable if their single worst line is excluded", int((u["profit_excl_worst_line"] > 0).sum()),
             u.loc[u["profit_excl_worst_line"] > 0, "profit"].sum())]
    return pd.DataFrame(rows, columns=["group", "customers", "profit"])


def investigation_groups(c: pd.DataFrame, company_margin: float) -> pd.DataFrame:
    """
    Candidate groups for commercial investigation, each with stated metrics:
      loss = sum of negative customer profit in the group
      hurdle_shortfall = revenue x (company margin - customer margin), summed over
                         customers below the hurdle: profit 'missing' vs the company average
    """
    def shortfall(g):
        below = g[g["profit_margin"] < company_margin]
        return float((below["revenue"] * (company_margin - below["profit_margin"])).sum())

    groups = {
        "C2 customers that are loss-making": c[(c["cust_segment"] == "C2") & (c["profit"] < 0)],
        "C2 customers that are profitable but below hurdle": c[(c["cust_segment"] == "C2") & (c["profit"] >= 0)],
        "C1 core accounts (concentration risk)": c[c["cust_segment"] == "C1"],
        "Top 10% of customers by profit": c.nlargest(int(np.ceil(len(c) * 0.10)), "profit"),
        "C4 low-value accounts": c[c["cust_segment"] == "C4"],
        "Limited-history customers": c[c["cust_segment"] == "NA"],
    }
    rows = []
    for name, g in groups.items():
        rows.append({"group": name, "customers": len(g), "revenue": g["revenue"].sum(), "profit": g["profit"].sum(),
                     "loss": g.loc[g["profit"] < 0, "profit"].sum(), "hurdle_shortfall": shortfall(g),
                     "beyond_be_share": g["beyond_be_revenue"].sum() / g["revenue"].sum() if len(g) else np.nan,
                     "share_of_total_profit": g["profit"].sum() / c["profit"].sum()})
    return pd.DataFrame(rows)
