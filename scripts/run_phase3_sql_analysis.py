"""
Phase 3 runner: execute the SQL analytical layer against the star schema,
validate every result, and write outputs + documentation.

Usage (from the project root, after Phase 2):
    python scripts/run_phase3_sql_analysis.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from spis import config, modeling, sql_analysis as sa  # noqa: E402
from spis.io_utils import read_orders_clean  # noqa: E402


def main() -> None:
    if not config.WAREHOUSE_DB.exists():
        raise SystemExit("Warehouse not found - run scripts/run_phase2_build_model.py first.")
    conn = modeling.connect()

    queries = sa.load_all_queries()
    results = sa.run_queries(conn, queries)
    print(f"[run]        {len(queries)} queries executed from {sa.ANALYSIS_DIR.relative_to(config.PROJECT_ROOT)}")

    validation = pd.concat([sa.validate_results(conn, results),
                            sa.independent_checks(results, read_orders_clean())], ignore_index=True)
    passed = (validation.status == "PASS").sum()
    print(f"[validation] {passed}/{len(validation)} checks passed")
    if passed != len(validation):
        print(validation[validation.status != "PASS"].to_string(index=False))
        raise SystemExit("SQL analysis failed validation - outputs not written.")

    sa.save_results(results, queries)
    validation.to_csv(sa.PHASE3_REPORT_DIR / "validation_results.csv", index=False)
    (sa.PHASE3_REPORT_DIR / "results_snapshot.md").write_text(
        sa.build_snapshot(results, queries, validation), encoding="utf-8")
    sa.GUIDE_PATH.write_text(sa.build_guide(queries), encoding="utf-8")
    conn.close()
    print(f"[done]       results -> {sa.PHASE3_REPORT_DIR.relative_to(config.PROJECT_ROOT)}, "
          f"guide -> {sa.GUIDE_PATH.relative_to(config.PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
