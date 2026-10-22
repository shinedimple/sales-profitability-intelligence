"""
Phase 2: build the analytical star schema in SQLite.

Division of labour:
  * SQL files (sql/) contain ALL transformation logic, so it is reviewable,
    portable to another warehouse, and demonstrates SQL modelling skills.
  * This module only orchestrates: load staging -> run SQL -> test -> export.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pandas as pd

from . import config
from .io_utils import read_orders_clean

BOOL_COLUMNS_PREFIXES = ("dq_", "exclude_", "is_")


def connect(db_path: Path = config.WAREHOUSE_DB) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _to_staging_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Dates -> ISO text, booleans -> 0/1 integers (SQLite storage conventions)."""
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d")
        elif out[col].dtype == bool or col.startswith(BOOL_COLUMNS_PREFIXES):
            out[col] = out[col].astype(bool).astype(int)
    return out


def load_staging(conn: sqlite3.Connection) -> dict[str, int]:
    """Load Phase 1 processed files into stg_* tables (replaced on every run)."""
    orders = _to_staging_frame(read_orders_clean())
    returns = pd.read_csv(config.OUT_RETURNS)
    returns["is_returned"] = returns["is_returned"].astype(bool).astype(int)
    managers = pd.read_csv(config.OUT_PEOPLE)
    params = pd.DataFrame({"name": "core_scope_country", "value": config.CORE_SCOPE_COUNTRIES})

    tables = {"stg_orders": orders, "stg_returns": returns,
              "stg_regional_managers": managers, "stg_parameters": params}
    for name, frame in tables.items():
        frame.to_sql(name, conn, if_exists="replace", index=False)
    return {name: len(frame) for name, frame in tables.items()}


def run_sql_file(conn: sqlite3.Connection, path: Path) -> None:
    conn.executescript(path.read_text(encoding="utf-8"))
    conn.commit()


def parse_tests(path: Path) -> list[tuple[str, str]]:
    """Split the test file into (name, sql) pairs using '-- test:' markers."""
    text = path.read_text(encoding="utf-8")
    parts = re.split(r"^-- test:\s*(.+)$", text, flags=re.MULTILINE)
    return [(parts[i].strip(), parts[i + 1].strip().rstrip(";"))
            for i in range(1, len(parts), 2)]


def run_tests(conn: sqlite3.Connection, path: Path = config.SQL_TEST_FILE) -> pd.DataFrame:
    rows = []
    for name, sql in parse_tests(path):
        failures = conn.execute(sql).fetchone()[0]
        rows.append({"test": name, "failures": failures,
                     "status": "PASS" if failures == 0 else "FAIL"})
    return pd.DataFrame(rows)


def check_foreign_keys(conn: sqlite3.Connection) -> int:
    """SQLite's own referential-integrity check (should return no rows)."""
    return len(conn.execute("PRAGMA foreign_key_check;").fetchall())


def export_model(conn: sqlite3.Connection, out_dir: Path = config.MODEL_EXPORT_DIR) -> dict[str, int]:
    """Export model tables to CSV for Power BI and Excel (keys stay as integers)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    for table in config.MODEL_TABLES:
        frame = pd.read_sql_query(f"SELECT * FROM {table}", conn)
        frame.to_csv(out_dir / f"{table}.csv", index=False)
        counts[table] = len(frame)
    return counts


def table_profile(conn: sqlite3.Connection) -> pd.DataFrame:
    rows = []
    for table in config.MODEL_TABLES:
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        cols = len(conn.execute(f"PRAGMA table_info({table})").fetchall())
        rows.append({"table": table, "rows": n, "columns": cols})
    return pd.DataFrame(rows)
