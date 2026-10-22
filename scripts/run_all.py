"""
Run the complete pipeline from the raw file to the management report.

    python scripts/run_all.py

Each phase validates its own outputs and stops the run if a check fails, so a
successful run means every reconciliation in the project passed.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PHASES = [
    ("Phase 1  Data quality audit and cleaning", "run_phase1_data_quality.py"),
    ("Phase 2  Star-schema model (SQLite)", "run_phase2_build_model.py"),
    ("Phase 3  SQL analytical layer", "run_phase3_sql_analysis.py"),
    ("Phase 4  Exploratory data analysis", "run_phase4_eda.py"),
    ("Phase 5  Profitability analysis", "run_phase5_profitability.py"),
    ("Phase 6  Discount analysis", "run_phase6_discount.py"),
    ("Phase 7  Customer profitability", "run_phase7_customers.py"),
    ("Phase 8  Power BI dashboard specification", "run_phase8_dashboard.py"),
    ("Phase 9  DAX layer documentation", "run_phase9_dax_layer.py"),
    ("Phase 10 Management insight report", "run_phase10_management_report.py"),
]


def main() -> None:
    start = time.time()
    for label, script in PHASES:
        t0 = time.time()
        print(f"\n=== {label} ===", flush=True)
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / script)], cwd=ROOT)
        if result.returncode != 0:
            raise SystemExit(f"Stopped: {label} failed (exit code {result.returncode}).")
        print(f"--- done in {time.time() - t0:.1f}s", flush=True)
    print(f"\nAll {len(PHASES)} phases completed in {time.time() - start:.1f}s.")


if __name__ == "__main__":
    main()
