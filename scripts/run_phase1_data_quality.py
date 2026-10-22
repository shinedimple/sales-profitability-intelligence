"""
Phase 1 runner: RAW -> AUDIT -> CLEANING -> VALIDATION -> PROCESSED.

Usage (from the project root):
    python scripts/run_phase1_data_quality.py
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from spis import config  # noqa: E402
from spis.audit import run_audit  # noqa: E402
from spis.cleaning import run_cleaning  # noqa: E402
from spis.io_utils import file_sha256, load_raw_workbook, read_orders_clean, write_csv  # noqa: E402
from spis.reporting import build_report  # noqa: E402
from spis.validation import assert_valid, validate, validate_round_trip  # noqa: E402


def main(run_date: date | None = None) -> None:
    run_date = run_date or date.today()
    config.REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. RAW ------------------------------------------------------------
    hash_before = file_sha256(config.RAW_FILE)
    raw = load_raw_workbook()
    print(f"[raw]        loaded {', '.join(f'{k}={v.shape}' for k, v in raw.items())}")

    # 2. AUDIT ----------------------------------------------------------
    audit = run_audit(raw, today=run_date)
    checks, issue_log = audit.checks_frame(), audit.issue_log()
    print(f"[audit]      {len(checks)} checks: {checks['status'].value_counts().to_dict()}")

    # 3. CLEANING -------------------------------------------------------
    clean, log = run_cleaning(raw)
    print(f"[cleaning]   orders {len(raw['orders']):,} -> {len(clean['orders']):,} rows")

    # 4. VALIDATION -----------------------------------------------------
    hash_after = file_sha256(config.RAW_FILE)
    validation = validate(raw, clean, log, hash_before, hash_after, issue_log)
    assert_valid(validation)  # stop here if anything is wrong

    # 5. PROCESSED ------------------------------------------------------
    write_csv(clean["orders"], config.OUT_ORDERS)
    write_csv(clean["returns"], config.OUT_RETURNS)
    write_csv(clean["people"], config.OUT_PEOPLE)
    round_trip = validate_round_trip(clean["orders"], read_orders_clean())
    assert_valid(round_trip)
    validation = pd.concat([validation, round_trip], ignore_index=True)
    print(f"[validation] {(validation['status'] == 'PASS').sum()}/{len(validation)} checks passed")

    # Audit trail
    checks.to_csv(config.REPORT_DIR / "audit_checks.csv", index=False)
    issue_log.to_csv(config.REPORT_DIR / "dq_issue_log.csv", index=False)
    log.frame().to_csv(config.REPORT_DIR / "cleaning_log.csv", index=False)
    log.removed_rows.to_csv(config.REPORT_DIR / "removed_rows.csv", index=False)
    validation.to_csv(config.REPORT_DIR / "validation_results.csv", index=False)
    report = build_report(audit.profile, checks, issue_log, log.frame(), validation,
                          clean["orders"], hash_before, run_date)
    (config.REPORT_DIR / "data_quality_report.md").write_text(report, encoding="utf-8")
    print(f"[done]       processed data -> {config.OUT_ORDERS.relative_to(config.PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
