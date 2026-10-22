"""
Phase 5 runner: deep profitability analysis.

    python scripts/run_phase5_profitability.py      (after Phases 1-4)

Outputs (reports/phase5/): profitability_report.md, figures/*.png, tables/*.csv,
validation_results.csv
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

from spis import charts, config, eda, modeling  # noqa: E402
from spis import charts_profitability as cp  # noqa: E402
from spis import profitability as pr  # noqa: E402
from spis.profitability_report import build_report  # noqa: E402

OUT = config.PROJECT_ROOT / "reports" / "phase5"
TABLES, FIGURES = OUT / "tables", OUT / "figures"


def evidence(lines: int) -> str:
    return "High" if lines >= 100 else "Medium" if lines >= 30 else "Low"


def priorities(cells: pd.DataFrame, products: pd.DataFrame) -> pd.DataFrame:
    """Disjoint groups of loss-making rules, ranked by profit destroyed, plus one cross-cutting item."""
    loss = cells[cells["profit_destroying"]]
    groups = [
        ("Discount rules above 40% (all loss-making)", loss[loss["discount_rule"] > 0.40]),
        ("Loss-making rules at 21-40% discount", loss[(loss["discount_rule"] > 0.20) & (loss["discount_rule"] <= 0.40)]),
        ("Loss-making rules at 1-20% discount", loss[(loss["discount_rule"] > 0) & (loss["discount_rule"] <= 0.20)]),
    ]
    rows = []
    for name, g in groups:
        rows.append({"focus": name, "units": f"{len(g)} rules", "revenue": g["sales"].sum(),
                     "loss_at_stake": g["profit"].sum(), "order_lines": int(g["lines"].sum()),
                     "evidence": evidence(int(g["lines"].sum())),
                     "main_sub_categories": ", ".join(g.groupby("sub_category")["profit"].sum().nsmallest(3).index)})
    rows.sort(key=lambda d: d["loss_at_stake"])
    m = products[(products["sub_category"] == "Machines") & (products["profit"] < 0)]
    rows.append({"focus": "Cross-cutting: loss-making Machines products (overlaps the rules above)",
                 "units": f"{len(m)} products", "revenue": m["sales"].sum(), "loss_at_stake": m["profit"].sum(),
                 "order_lines": int(m["lines"].sum()), "evidence": evidence(int(m["lines"].sum())),
                 "main_sub_categories": "Machines (few, high-value transactions)"})
    out = pd.DataFrame(rows)
    out.insert(0, "priority", range(1, len(out) + 1))
    return out


def compute(df: pd.DataFrame) -> dict:
    r: dict = {}
    r["overall"] = eda.overall(df)
    cm = r["company_margin"] = r["overall"]["profit_margin"]
    r["line_losses"] = df.loc[df["profit"] < 0, "profit"].sum()
    p = pr.product_metrics(df)
    p["quadrant"] = pr.assign_quadrants(p, cm)
    r["products"] = p
    r["sales_cut"] = p.loc[p["eligible"], "sales"].median()
    r["quadrants"] = pr.quadrant_summary(p)
    r["composition"] = pr.quadrant_composition(p)
    r["examples"] = {q: pr.quadrant_examples(p, q) for q in ["Q1", "Q2", "Q3", "Q4"]}
    r["sensitivity"] = pr.quadrant_sensitivity(p, cm)
    r["negative"] = pr.negative_products(p)
    r["pareto"] = pr.loss_pareto_points(r["negative"])
    r["loss_diagnosis"] = pr.loss_product_diagnosis(p)
    r["high_discount"] = pr.high_discount_products(p)
    r["within_product"] = pr.discount_diagnosis(p)
    r["driver"] = pr.driver_matrix(df)
    r["dim_category"] = pr.dimension_view(df, "category")
    r["dim_sub_category"] = pr.dimension_view(df, "sub_category")
    r["dim_segment"] = pr.dimension_view(df, "segment")
    r["dim_region"] = pr.dimension_view(df, "region")
    r["dim_state"] = pr.dimension_view(df, "state_province")
    r["dim_quantity"] = pr.quantity_view(df)
    r["cells"] = pr.policy_cells(df)
    r["rule_bands"] = pr.policy_cell_summary(r["cells"])
    r["priorities"] = priorities(r["cells"], p)
    return r


def validate(r: dict) -> pd.DataFrame:
    o = r["overall"]
    q01 = pd.read_csv(config.PROJECT_ROOT / "reports" / "phase3" / "q01_headline_kpis.csv").iloc[0]

    def chk(name, a, b, tol):
        return {"check": name, "expected": float(b), "actual": float(a),
                "status": "PASS" if abs(a - b) <= tol else "FAIL"}

    qs, cells, p = r["quadrants"], r["cells"], r["products"]
    dm = r["driver"]["eta_squared"]
    return pd.DataFrame([
        chk("Total revenue = SQL Q01", o["sales"], q01.total_sales, 0.01),
        chk("Total profit = SQL Q01", o["profit"], q01.total_profit, 0.01),
        chk("Quadrant revenue sums to total", qs["sales"].sum(), o["sales"], 0.01),
        chk("Quadrant profit sums to total", qs["profit"].sum(), o["profit"], 0.01),
        chk("Quadrant products = all products", qs["products"].sum(), len(p), 0),
        chk("Policy-cell profit sums to total", cells["profit"].sum(), o["profit"], 0.01),
        chk("Rule-band revenue sums to total", r["rule_bands"]["sales"].sum(), o["sales"], 0.01),
        chk("Full-price + discounted revenue = product revenue",
            (p["full_price_sales"] + p["discounted_sales"]).sum(), p["sales"].sum(), 0.01),
        chk("Loss diagnosis covers all loss products", r["loss_diagnosis"]["products"].sum(), r["pareto"]["loss_products"], 0),
        chk("Every policy cell has one discount rule", cells["discount_rule"].notna().sum(), len(cells), 0),
        chk("Eta-squared within [0, 1]", float(((dm >= 0) & (dm <= 1 + 1e-9)).all()), 1, 0),
        chk("No loss-making full-price lines (premise of diagnosis)",
            float((p.loc[p["full_price_lines"] > 0, "full_price_profit"] < 0).sum()), 0, 0),
    ])


def draw(r: dict) -> dict[str, str]:
    FIGURES.mkdir(parents=True, exist_ok=True)
    charts.setup_style()
    p, cm = r["products"], r["company_margin"]
    figs = {
        "P1": cp.product_quadrants(p, cm, r["sales_cut"], FIGURES / "p1_product_quadrants.png"),
        "P2": cp.quadrant_shares(r["quadrants"], FIGURES / "p2_quadrant_shares.png"),
        "P3": cp.quadrant_waterfall(r["quadrants"], r["overall"]["profit"], FIGURES / "p3_quadrant_profit_waterfall.png"),
        "P4": cp.loss_pareto(r["negative"], FIGURES / "p4_product_loss_pareto.png"),
        "P5": cp.within_product_dumbbell(r["within_product"], FIGURES / "p5_full_price_vs_discounted_margin.png"),
        "P6": cp.driver_matrix(r["driver"], FIGURES / "p6_profitability_driver_matrix.png"),
        "P7": cp.policy_cell_heatmap(r["cells"], FIGURES / "p7_policy_cell_heatmap.png"),
        "P8": cp.rule_band_profit(r["rule_bands"], FIGURES / "p8_profit_by_discount_rule.png"),
    }
    return {k: f"figures/{v.name}" for k, v in figs.items()}


def save_tables(r: dict) -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    for name, obj in r.items():
        if isinstance(obj, pd.DataFrame):
            obj.to_csv(TABLES / f"{name}.csv", index=not isinstance(obj.index, pd.RangeIndex))
    for q, ex in r["examples"].items():
        ex.to_csv(TABLES / f"examples_{q}.csv", index=False)


def main() -> None:
    conn = modeling.connect()
    df = eda.load_core_lines(conn)
    conn.close()
    r = compute(df)
    validation = validate(r)
    print(f"[validation] {(validation.status == 'PASS').sum()}/{len(validation)} checks passed")
    if (validation.status != "PASS").any():
        print(validation[validation.status != "PASS"].to_string(index=False))
        raise SystemExit("Validation failed - outputs not written.")
    OUT.mkdir(parents=True, exist_ok=True)
    validation.to_csv(OUT / "validation_results.csv", index=False)
    save_tables(r)
    figs = draw(r)
    (OUT / "profitability_report.md").write_text(build_report(r, figs, validation), encoding="utf-8")
    print(f"[done]       {len(figs)} figures, report -> reports/phase5/profitability_report.md")


if __name__ == "__main__":
    main()
