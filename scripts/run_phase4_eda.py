"""
Phase 4 runner: Exploratory Data Analysis.

    python scripts/run_phase4_eda.py        (after Phases 1-3)

Outputs (reports/phase4/):
    tables/*.csv          every analysis table
    figures/*.png         one chart per business question
    eda_findings.md       findings report (finding, calculation, interpretation,
                          limitations, next step)
    findings_register.csv one row per finding
    validation_results.csv reconciliation with the Phase 3 SQL results
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from spis import charts, config, eda, findings, modeling  # noqa: E402

OUT = config.PROJECT_ROOT / "reports" / "phase4"
TABLES, FIGURES = OUT / "tables", OUT / "figures"
SQL_RESULTS = config.PROJECT_ROOT / "reports" / "phase3"


def compute(df: pd.DataFrame) -> dict:
    r: dict = {}
    r["overall"] = eda.overall(df)
    cm = r["overall"]["profit_margin"]
    # A. Sales performance
    r["yearly"] = eda.yearly_performance(df)
    r["monthly"] = eda.monthly_performance(df)
    r["seasonality"] = eda.seasonality(df)
    r["order_value_distribution"] = eda.order_value_distribution(df)
    # B. Profitability
    r["category"] = eda.profitability_by(df, "category")
    r["sub_category"] = eda.profitability_by(df, "sub_category")
    r["loss_concentration"] = eda.loss_concentration(df)
    r["mix_adjusted_category"] = eda.mix_adjusted_margin(df, "category")
    r["mix_adjusted_region"] = eda.mix_adjusted_margin(df, "region")
    r["mix_adjusted_segment"] = eda.mix_adjusted_margin(df, "segment")
    # C. Products
    r["products"] = eda.product_table(df)
    r["product_portfolio"] = eda.product_portfolio(r["products"], cm)
    # D. Customers
    r["customers"] = eda.customer_table(df)
    r["customer_concentration"] = eda.customer_concentration(r["customers"])
    r["customer_discount_groups"] = eda.customer_discount_profit(r["customers"])
    freq = eda.order_frequency(df, r["customers"])
    r["order_gap_summary"], r["frequency_bands"], r["retention"] = (
        freq["gap_summary"], freq["frequency_bands"], freq["retention"])
    r["segment"] = eda.segment_performance(df)
    # Worst single line per customer: is unprofitability customer- or transaction-driven?
    valid = df[df["is_excluded_from_customer_analysis"] == 0]
    worst = valid.groupby("customer_id")["profit"].min()
    c = r["customers"].set_index("customer_id")
    unprof = c[c["profit"] < 0]
    r["unprofitable_without_worst_line"] = int(((unprof["profit"] - worst.reindex(unprof.index)) > 0).sum())
    # E. Geography
    r["region"] = eda.geography(df, "region")
    r["state"] = eda.geography(df, "state_province")
    r["city"] = eda.geography(df, "city_state")
    r["state_discount_correlation"] = eda.geo_discount_relationship(r["state"])
    # F. Discounts
    r["discount_levels"] = eda.discount_levels(df)
    r["discount_quantity"] = eda.discount_quantity_check(df)
    r["discount_heat_margin"], r["discount_heat_lines"] = eda.discount_by_subcategory(df)
    r["discount_correlations"] = eda.discount_line_correlation(df)
    r["discount_policy"] = eda.discount_policy_structure(df)
    return r


def validate(r: dict) -> pd.DataFrame:
    """Reconcile pandas EDA results with the independently computed Phase 3 SQL results."""
    def chk(name, a, b, tol):
        return {"check": name, "pandas": round(float(a), 4), "sql": round(float(b), 4),
                "status": "PASS" if abs(a - b) <= tol else "FAIL"}

    q01 = pd.read_csv(SQL_RESULTS / "q01_headline_kpis.csv").iloc[0]
    q02 = pd.read_csv(SQL_RESULTS / "q02_sales_and_profit_by_year.csv").set_index("order_year")
    q07 = pd.read_csv(SQL_RESULTS / "q07_sales_and_profit_by_region.csv").set_index("region")
    q15 = pd.read_csv(SQL_RESULTS / "q15_profitability_by_discount_band.csv")
    rows = [chk("Total sales", r["overall"]["sales"], q01.total_sales, 0.01),
            chk("Total profit", r["overall"]["profit"], q01.total_profit, 0.01),
            chk("Orders", r["overall"]["orders"], q01.orders, 0),
            chk("Valid customers", len(r["customers"]), q01.valid_customers, 0)]
    for y in q02.index:
        rows.append(chk(f"Sales {y}", r["yearly"].loc[y, "sales"], q02.loc[y, "sales"], 0.01))
        rows.append(chk(f"Margin {y}", r["yearly"].loc[y, "profit_margin"], q02.loc[y, "profit_margin"], 1e-4))
    reg = r["region"].set_index("region")
    for g in q07.index:
        rows.append(chk(f"Profit {g}", reg.loc[g, "profit"], q07.loc[g, "profit"], 0.01))
    rows.append(chk("Discount band lines", r["discount_levels"]["lines"].sum(), q15["lines"].sum(), 0))
    return pd.DataFrame(rows)


def save_tables(r: dict) -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    for name, obj in r.items():
        if isinstance(obj, pd.DataFrame):
            obj.to_csv(TABLES / f"{name}.csv", index=not isinstance(obj.index, pd.RangeIndex))
        elif isinstance(obj, pd.Series):
            obj.to_frame("value").to_csv(TABLES / f"{name}.csv")
        elif isinstance(obj, dict):
            pd.Series(obj, name="value").to_csv(TABLES / f"{name}.csv")


def draw(r: dict) -> dict[str, str]:
    FIGURES.mkdir(parents=True, exist_ok=True)
    charts.setup_style()
    cm = r["overall"]["profit_margin"]
    quad = r["sub_category"][["sales", "profit_margin"]]
    figs = {
        "F01": charts.monthly_trend(r["monthly"], FIGURES / "f01_monthly_revenue_profit.png"),
        "F02": charts.growth_decomposition(r["yearly"], FIGURES / "f02_growth_decomposition.png"),
        "F03": charts.subcategory_profit(r["sub_category"], FIGURES / "f03_subcategory_profit.png"),
        "F04": charts.subcategory_portfolio(quad, cm, FIGURES / "f04_subcategory_portfolio.png"),
        "F05": charts.discount_margin(r["discount_levels"], FIGURES / "f05_margin_by_discount_level.png"),
        "F06": charts.discount_heatmap(r["discount_heat_margin"], r["discount_heat_lines"],
                                       FIGURES / "f06_subcategory_discount_heatmap.png"),
        "F07": charts.region_mix_adjusted(r["mix_adjusted_region"], cm, FIGURES / "f07_region_mix_adjusted.png"),
        "F08": charts.state_discount_vs_margin(r["state"], FIGURES / "f08_state_discount_vs_margin.png"),
        "F09": charts.customer_lorenz(eda.lorenz_points(r["customers"]["sales"]),
                                      eda.lorenz_points(r["customers"]["profit"]),
                                      FIGURES / "f09_customer_concentration.png"),
        "F10": charts.customer_discount_vs_margin(r["customers"], FIGURES / "f10_customer_discount_vs_margin.png"),
    }
    return {k: f"figures/{v.name}" for k, v in figs.items()}


def main() -> None:
    conn = modeling.connect()
    df = eda.load_core_lines(conn)
    conn.close()
    r = compute(df)
    validation = validate(r)
    print(f"[validation] {(validation.status == 'PASS').sum()}/{len(validation)} reconciliation checks passed")
    if (validation.status != "PASS").any():
        print(validation[validation.status != "PASS"].to_string(index=False))
        raise SystemExit("EDA does not reconcile with SQL results - outputs not written.")
    OUT.mkdir(parents=True, exist_ok=True)
    validation.to_csv(OUT / "validation_results.csv", index=False)
    save_tables(r)
    figs = draw(r)
    register = findings.build_findings(r)
    pd.DataFrame(register)[["id", "area", "title", "finding", "confidence"]].to_csv(
        OUT / "findings_register.csv", index=False)
    (OUT / "eda_findings.md").write_text(findings.build_report(r, register, figs, validation), encoding="utf-8")
    print(f"[done]       {len(register)} findings, {len(figs)} figures, tables -> reports/phase4/")


if __name__ == "__main__":
    main()
