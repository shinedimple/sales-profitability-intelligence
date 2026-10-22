"""
Phase 6 runner: discount and profitability analysis.

    python scripts/run_phase6_discount.py      (after Phases 1-5)

Outputs (reports/phase6/): discount_report.md, figures/*.png, tables/*.csv,
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
from spis import charts_discount as cd  # noqa: E402
from spis import discount_analysis as da  # noqa: E402
from spis.discount_report import build_report  # noqa: E402

OUT = config.PROJECT_ROOT / "reports" / "phase6"
TABLES, FIGURES = OUT / "tables", OUT / "figures"


def compute(df: pd.DataFrame) -> dict:
    d = da.add_unit_economics(df)
    r: dict = {"lines": d, "overall": eda.overall(d)}
    r["averages"] = da.discount_averages(d)
    r["distribution"] = da.distribution(d)
    r["levels"] = da.level_relationship(d)
    r["identity"] = da.identity_check(d)
    r["list_margin_distribution"] = da.list_margin_distribution(d)
    r["headroom"] = da.headroom_summary(d)
    r["band_eval"], r["band_details"] = da.band_evaluation(d)
    for col in ["category", "sub_category", "region", "segment"]:
        r[f"dim_{col}"] = da.by_dimension(d, col)
    r["region_mix"] = da.dimension_band_mix(d, "region")
    r["segment_mix"] = da.dimension_band_mix(d, "segment")
    r["growth"] = da.growth_by_band(d)
    r["rule_stability"] = da.rule_stability(d)
    basket, sgrowth = da.basket_share_test(d), da.state_growth_test(d)
    customers = eda.customer_table(d)
    states = eda.geography(d, "state_province")
    states = states[states["volume_flag"] == "OK"]
    r["correlations"] = da.correlations(d, customers, states, basket, sgrowth)
    r["basket_table"], r["state_growth_table"] = basket["table"], sgrowth["table"]
    r["break_even_volume"] = da.break_even_volume()
    return r


def validate(r: dict) -> pd.DataFrame:
    o = r["overall"]
    q01 = pd.read_csv(config.PROJECT_ROOT / "reports" / "phase3" / "q01_headline_kpis.csv").iloc[0]
    q15 = pd.read_csv(config.PROJECT_ROOT / "reports" / "phase3" / "q15_profitability_by_discount_band.csv")

    def chk(name, a, b, tol):
        return {"check": name, "expected": float(b), "actual": float(a), "status": "PASS" if abs(a - b) <= tol else "FAIL"}

    rows = [chk("Revenue = SQL Q01", o["sales"], q01.total_sales, 0.01),
            chk("Profit = SQL Q01", o["profit"], q01.total_profit, 0.01),
            chk("Distribution revenue sums to total", r["distribution"]["sales"].sum(), o["sales"], 0.01),
            chk("Headroom bands profit sums to total", r["headroom"]["profit"].sum(), o["profit"], 0.01),
            chk("Beyond-break-even profit = all line losses", r["headroom"].loc["Discounted beyond break-even", "profit"],
                r["lines"].loc[r["lines"]["profit"] < 0, "profit"].sum(), 0.01),
            chk("Price-arithmetic identity: max error", r["identity"]["max_abs_prediction_error"], 0, 1e-9),
            chk("Model-band profit = SQL Q15", r["band_details"][da.RECOMMENDED_SCHEME]["profit"].sum(), q15["profit"].sum(), 0.05),
            chk("Rules that changed over time (expected 0, Phase 4)", r["rule_stability"]["multi_year_cells_where_rule_changed"], 0, 0)]
    for name, t in r["band_details"].items():
        rows.append(chk(f"Band scheme sums to revenue: {name[:2]}", t["sales"].sum(), o["sales"], 0.01))
    for col in ["category", "region", "segment"]:
        rows.append(chk(f"{col} profit sums to total", r[f"dim_{col}"]["profit"].sum(), o["profit"], 0.01))
    return pd.DataFrame(rows)


def draw(r: dict) -> dict[str, str]:
    FIGURES.mkdir(parents=True, exist_ok=True)
    charts.setup_style()
    figs = {
        "D1": cd.distribution(r["distribution"], FIGURES / "d1_discount_distribution.png"),
        "D2": cd.level_panels(r["levels"], FIGURES / "d2_revenue_profit_margin_by_discount.png"),
        "D3": cd.subcategory_break_even(r["dim_sub_category"], FIGURES / "d3_subcategory_discount_vs_break_even.png"),
        "D4": cd.identity_scatter(r["lines"], FIGURES / "d4_price_arithmetic_check.png"),
        "D5": cd.dimension_mix(r["region_mix"], r["segment_mix"], FIGURES / "d5_region_segment_discount_mix.png"),
        "D6": cd.growth_index(r["growth"], FIGURES / "d6_growth_by_discount_band.png"),
        "D7": cd.break_even_volume(FIGURES / "d7_volume_needed_to_offset_discount.png"),
    }
    return {k: f"figures/{v.name}" for k, v in figs.items()}


def save_tables(r: dict) -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    for name, obj in r.items():
        if name == "lines":
            continue
        if isinstance(obj, pd.DataFrame):
            obj.to_csv(TABLES / f"{name}.csv", index=not isinstance(obj.index, pd.RangeIndex))
        elif isinstance(obj, (pd.Series, dict)) and name not in ("band_details", "growth"):
            pd.Series(obj).to_csv(TABLES / f"{name}.csv")
    for k, t in r["band_details"].items():
        t.to_csv(TABLES / f"band_scheme_{k[:1]}.csv")
    for k, t in r["growth"].items():
        t.to_csv(TABLES / f"growth_{k}.csv")


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
    (OUT / "discount_report.md").write_text(build_report(r, figs, validation), encoding="utf-8")
    print(f"[done]       {len(figs)} figures, report -> reports/phase6/discount_report.md")


if __name__ == "__main__":
    main()
