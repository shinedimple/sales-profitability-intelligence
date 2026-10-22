"""
Phase 7 runner: customer profitability analysis.

    python scripts/run_phase7_customers.py      (after Phases 1-6)

Outputs (reports/phase7/): customer_report.md, figures/*.png, tables/*.csv,
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
from spis import charts_customers as cc  # noqa: E402
from spis import customer_analysis as ca  # noqa: E402
from spis.customer_report import build_report  # noqa: E402

OUT = config.PROJECT_ROOT / "reports" / "phase7"
TABLES, FIGURES = OUT / "tables", OUT / "figures"


def compute(df: pd.DataFrame) -> dict:
    v = ca.valid_lines(df)
    cm = v["profit"].sum() / v["sales"].sum()
    c = ca.customer_metrics(v)
    c["cust_segment"] = ca.assign_segments(c, cm)
    top = c.nlargest(int(np.ceil(len(c) * 0.10)), "profit")
    return {"lines": v, "company_margin": cm, "customers": c,
            "revenue_cut": c.loc[c["eligible"], "revenue"].median(),
            "headline": ca.headline_metrics(c), "coverage": ca.history_coverage(c, v),
            "segments": ca.segment_summary(c),
            "examples": {s: ca.segment_examples(c, s) for s in ["C1", "C2", "C3", "C4"]},
            "sensitivity": ca.segment_sensitivity(c, cm), "by_type": ca.segment_by_customer_type(c),
            "seg_comparison": ca.segmentation_comparison(c), "persistence": ca.persistence(v, cm),
            "unprofitable": ca.unprofitable_diagnosis(c), "investigation": ca.investigation_groups(c, cm),
            "top10_profit_share": top["profit"].sum() / c["profit"].sum()}


def validate(r: dict) -> pd.DataFrame:
    c, s, v = r["customers"], r["segments"], r["lines"]
    q01 = pd.read_csv(config.PROJECT_ROOT / "reports" / "phase3" / "q01_headline_kpis.csv").iloc[0]
    q18 = pd.read_csv(config.PROJECT_ROOT / "reports" / "phase3" / "q18_customer_profitability_table.csv")

    def chk(name, a, b, tol):
        return {"check": name, "expected": float(b), "actual": float(a), "status": "PASS" if abs(a - b) <= tol else "FAIL"}

    return pd.DataFrame([
        chk("Customers = SQL valid customers", len(c), q01.valid_customers, 0),
        chk("Customer profit = SQL Q18 total", c["profit"].sum(), q18["profit"].sum(), 0.005 * len(c)),
        chk("Customer revenue = valid-line revenue", c["revenue"].sum(), v["sales"].sum(), 0.01),
        chk("Segment revenue sums to total", s["revenue"].sum(), c["revenue"].sum(), 0.01),
        chk("Segment profit sums to total", s["profit"].sum(), c["profit"].sum(), 0.01),
        chk("Segment customers sum to total", s["customers"].sum(), len(c), 0),
        chk("Within-BE + beyond-BE profit = profit", (c["profit_within_be"] + c["beyond_be_profit"]).sum(), c["profit"].sum(), 0.01),
        chk("Orders sum = distinct valid orders", c["orders"].sum(), v["order_id"].nunique(), 0),
        chk("Persistence matrix covers customers in both periods", r["persistence"]["matrix"].values.sum(),
            r["persistence"]["customers_in_both"], 0),
    ])


def draw(r: dict) -> dict[str, str]:
    FIGURES.mkdir(parents=True, exist_ok=True)
    charts.setup_style()
    figs = {
        "K1": cc.customer_matrix(r["customers"], r["company_margin"], r["revenue_cut"], FIGURES / "k1_customer_matrix.png"),
        "K2": cc.segment_shares(r["segments"], FIGURES / "k2_segment_shares.png"),
        "K3": cc.profit_decomposition(r["segments"], FIGURES / "k3_profit_decomposition.png"),
        "K4": cc.segmentation_comparison(r["seg_comparison"], FIGURES / "k4_segmentation_comparison.png"),
        "K5": cc.persistence_heatmap(r["persistence"], FIGURES / "k5_segment_persistence.png"),
        "K6": cc.order_history(r["customers"], FIGURES / "k6_order_history.png"),
    }
    return {k: f"figures/{v.name}" for k, v in figs.items()}


def save_tables(r: dict) -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    for name, obj in r.items():
        if name == "lines":
            continue
        if isinstance(obj, pd.DataFrame):
            obj.to_csv(TABLES / f"{name}.csv", index=not isinstance(obj.index, pd.RangeIndex))
    r["persistence"]["matrix"].to_csv(TABLES / "persistence_matrix.csv")
    pd.Series({k: v for k, v in r["persistence"].items() if k != "matrix"}).to_csv(TABLES / "persistence_summary.csv")
    for s, ex in r["examples"].items():
        ex.to_csv(TABLES / f"examples_{s}.csv", index=False)


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
    (OUT / "customer_report.md").write_text(build_report(r, figs, validation), encoding="utf-8")
    print(f"[done]       {len(figs)} figures, report -> reports/phase7/customer_report.md")


if __name__ == "__main__":
    main()
