"""
Phase 2 runner: PROCESSED CSV -> STAGING -> STAR SCHEMA -> TESTS -> EXPORT.

Usage (from the project root, after Phase 1):
    python scripts/run_phase2_build_model.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from spis import config, modeling  # noqa: E402
from spis.io_utils import read_orders_clean  # noqa: E402


def independent_kpi_check(conn) -> pd.DataFrame:
    """
    Recompute core KPIs with pandas directly from the Phase 1 file (no SQL model)
    and compare with vw_kpi_by_year. Two independent methods agreeing is the
    strongest evidence that the model and the KPI logic are correct.
    """
    df = read_orders_clean()
    core = df[df["country"].isin(config.CORE_SCOPE_COUNTRIES) & ~df["dq_is_clone_copy"]]
    g = core.groupby(core["order_date"].dt.year)
    pandas_kpi = pd.DataFrame({
        "revenue": g["sales"].sum(), "profit": g["profit"].sum(),
        "orders": g["order_id"].nunique(), "customers": g["customer_id"].nunique(),
        "units_sold": g["quantity"].sum(),
    })
    pandas_kpi["profit_margin"] = pandas_kpi["profit"] / pandas_kpi["revenue"]
    pandas_kpi["avg_order_value"] = pandas_kpi["revenue"] / pandas_kpi["orders"]

    sql_kpi = pd.read_sql_query(
        "SELECT * FROM vw_kpi_by_year WHERE scope = 'Core scope'", conn).set_index("year")
    rows = []
    for year in pandas_kpi.index:
        for col in pandas_kpi.columns:
            a, b = pandas_kpi.loc[year, col], sql_kpi.loc[year, col]
            tol = 0.01 if col not in ("profit_margin",) else 1e-4  # SQL view rounds
            rows.append({"year": year, "kpi": col, "pandas": round(float(a), 4),
                         "sql": float(b), "status": "PASS" if np.isclose(a, b, atol=tol) else "FAIL"})
    return pd.DataFrame(rows)


def main() -> None:
    config.PHASE2_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    if config.WAREHOUSE_DB.exists():
        config.WAREHOUSE_DB.unlink()          # full rebuild: no leftovers from earlier runs
    conn = modeling.connect()

    staged = modeling.load_staging(conn)
    print(f"[staging]   {staged}")

    for step in config.SQL_BUILD_STEPS:
        modeling.run_sql_file(conn, step)
        print(f"[build]     {step.relative_to(config.PROJECT_ROOT)}")

    fk_violations = modeling.check_foreign_keys(conn)
    tests = modeling.run_tests(conn)
    kpi_check = independent_kpi_check(conn)
    print(f"[tests]     SQL tests {(tests.status == 'PASS').sum()}/{len(tests)} passed; "
          f"FK violations: {fk_violations}; independent KPI checks "
          f"{(kpi_check.status == 'PASS').sum()}/{len(kpi_check)} passed")
    if fk_violations or (tests.status == "FAIL").any() or (kpi_check.status == "FAIL").any():
        print(tests[tests.status == "FAIL"].to_string(index=False))
        print(kpi_check[kpi_check.status == "FAIL"].to_string(index=False))
        raise SystemExit("Model build failed validation - outputs not exported.")

    exported = modeling.export_model(conn)
    print(f"[export]    {exported}")

    tests.to_csv(config.PHASE2_REPORT_DIR / "model_tests.csv", index=False)
    kpi_check.to_csv(config.PHASE2_REPORT_DIR / "kpi_independent_check.csv", index=False)
    modeling.table_profile(conn).to_csv(config.PHASE2_REPORT_DIR / "table_profile.csv", index=False)
    pd.read_sql_query("SELECT * FROM vw_kpi_by_year ORDER BY scope DESC, year", conn).to_csv(
        config.PHASE2_REPORT_DIR / "kpi_by_year_reference.csv", index=False)
    conn.close()
    print(f"[done]      warehouse -> {config.WAREHOUSE_DB.relative_to(config.PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
