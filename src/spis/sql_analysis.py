"""
Phase 3: run the SQL analytical layer.

Each .sql file in sql/analysis/ contains one or more queries, each introduced by
a metadata header:

    -- query: Q05 | Sales and profit by category
    -- covers: 12 Sales by category, 13 Profit by category
    -- question: ...
    -- logic: ...          (may repeat)
    -- use: ...
    SELECT ...;

The SQL files are the single source of truth: this module executes them, saves
results, checks that they reconcile, and generates the documentation from the
same headers, so documentation and code cannot drift apart.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from . import config
from .reporting import md_table

ANALYSIS_DIR = config.SQL_DIR / "analysis"
PHASE3_REPORT_DIR = config.PROJECT_ROOT / "reports" / "phase3"
GUIDE_PATH = config.PROJECT_ROOT / "docs" / "sql_analysis_guide.md"

_META = re.compile(r"^--\s*(question|logic|use|covers):\s*(.*)$")


@dataclass
class AnalysisQuery:
    query_id: str
    title: str
    source_file: str
    sql: str
    covers: str = ""
    question: str = ""
    logic: list[str] = field(default_factory=list)
    use: str = ""


def parse_analysis_file(path: Path) -> list[AnalysisQuery]:
    text = path.read_text(encoding="utf-8")
    blocks = re.split(r"^-- query:\s*", text, flags=re.MULTILINE)[1:]
    queries = []
    for block in blocks:
        header, _, rest = block.partition("\n")
        query_id, title = [part.strip() for part in header.split("|", 1)]
        q = AnalysisQuery(query_id, title, path.name, sql="")
        sql_lines = []
        for line in rest.splitlines():
            match = _META.match(line)
            if match and not sql_lines:
                key, value = match.groups()
                if key == "logic":
                    q.logic.append(value.strip())
                else:
                    setattr(q, key, value.strip())
            else:
                sql_lines.append(line)
        q.sql = "\n".join(sql_lines).strip().rstrip(";").strip()
        queries.append(q)
    return queries


def load_all_queries(directory: Path = ANALYSIS_DIR) -> list[AnalysisQuery]:
    queries = []
    for path in sorted(directory.glob("*.sql")):
        queries.extend(parse_analysis_file(path))
    ids = [q.query_id for q in queries]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Duplicate query ids: {ids}")
    return queries


def run_queries(conn: sqlite3.Connection, queries: list[AnalysisQuery]) -> dict[str, pd.DataFrame]:
    return {q.query_id: pd.read_sql_query(q.sql, conn) for q in queries}


# --------------------------------------------------------------------------
# Validation: every breakdown must add back to the headline totals
# --------------------------------------------------------------------------
def _check(name: str, expected: float, actual: float, tol: float) -> dict:
    ok = abs(expected - actual) <= tol
    return {"check": name, "expected": round(float(expected), 4),
            "actual": round(float(actual), 4), "tolerance": tol,
            "status": "PASS" if ok else "FAIL"}


def validate_results(conn: sqlite3.Connection, results: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Reconciliation tests. Totals are re-queried directly from fct_sales (not from
    Q01) so each breakdown is compared with an independent reference.
    """
    ref = pd.read_sql_query("""
        SELECT SUM(f.sales) AS sales, SUM(f.profit) AS profit,
               COUNT(DISTINCT f.order_id) AS orders,
               SUM(CASE WHEN c.is_excluded_from_customer_analysis = 0 THEN f.profit END) AS valid_profit,
               COUNT(DISTINCT CASE WHEN c.is_excluded_from_customer_analysis = 0
                                   THEN f.customer_key END) AS valid_customers
        FROM fct_sales f JOIN dim_customer c ON c.customer_key = f.customer_key
        WHERE f.is_core_scope = 1""", conn).iloc[0]

    rows = [
        _check("Q01 total sales = fact table", ref.sales, results["Q01"].total_sales[0], 0.01),
        _check("Q01 total profit = fact table", ref.profit, results["Q01"].total_profit[0], 0.01),
        _check("Q01 orders = fact table", ref.orders, results["Q01"].orders[0], 0),
    ]
    # Every additive breakdown must sum back to the total (tolerance = rounding of each row)
    for qid in ["Q02", "Q03", "Q05", "Q06", "Q07", "Q08", "Q09", "Q15", "Q16", "Q17"]:
        df = results[qid]
        tol = 0.005 * len(df) + 0.01
        rows.append(_check(f"{qid} sales sum to total", ref.sales, df["sales"].sum(), tol))
        rows.append(_check(f"{qid} profit sums to total", ref.profit, df["profit"].sum(), tol))
    for qid in ["Q05", "Q06", "Q07", "Q09"]:
        rows.append(_check(f"{qid} sales shares sum to 1", 1, results[qid]["share_of_sales"].sum(),
                           0.0001 * len(results[qid]) + 0.001))
    rows.append(_check("Q02 orders sum to total orders (orders belong to one year)",
                       ref.orders, results["Q02"]["orders"].sum(), 0))
    # Customer queries reconcile to the valid-customer population
    n = ref.valid_customers
    rows.append(_check("Q18 one row per valid customer", n, len(results["Q18"]), 0))
    rows.append(_check("Q18 profit = valid-customer profit", ref.valid_profit,
                       results["Q18"]["profit"].sum(), 0.005 * n))
    rows.append(_check("Q18 cumulative share ends at 1",
                       1, results["Q18"]["cumulative_share_of_profit"].iloc[-1], 0.0001))
    for qid in ["Q19", "Q20", "Q21"]:
        rows.append(_check(f"{qid} customers sum to valid customers", n, results[qid]["customers"].sum(), 0))
    rows.append(_check("Q14 one row per sub-category (17)", 17, len(results["Q14"]), 0))
    return pd.DataFrame(rows)


def independent_checks(results: dict[str, pd.DataFrame], orders: pd.DataFrame) -> pd.DataFrame:
    """Recompute selected answers in pandas, from the Phase 1 file, without any SQL."""
    core = orders[orders["country"].isin(config.CORE_SCOPE_COUNTRIES) & ~orders["dq_is_clone_copy"]]
    rows = []

    cat = core.groupby("category")["profit"].sum()
    for _, r in results["Q05"].iterrows():
        rows.append(_check(f"pandas: {r.category} profit", cat[r.category], r.profit, 0.01))

    prod = core.groupby(["product_id", "product_name"])["sales"].sum().sort_values(ascending=False)
    top_label = f"{prod.index[0][1]} [{prod.index[0][0]}]"
    q10_top = results["Q10"].iloc[0]
    rows.append({"check": "pandas: top product by sales", "expected": top_label,
                 "actual": q10_top.product_label, "tolerance": "",
                 "status": "PASS" if top_label == q10_top.product_label else "FAIL"})

    valid = core[~core["exclude_from_customer_analysis"]]
    per_year = valid.groupby(valid["order_date"].dt.year)["customer_id"].apply(set)
    for _, r in results["Q22"].iterrows():
        base, nxt = per_year[r.base_year], per_year[r.base_year + 1]
        rows.append(_check(f"pandas: retention {r.base_year}", len(base & nxt) / len(base),
                           r.retention_rate, 0.0001))
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Outputs
# --------------------------------------------------------------------------
def save_results(results: dict[str, pd.DataFrame], queries: list[AnalysisQuery],
                 out_dir: Path = PHASE3_REPORT_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    titles = {q.query_id: q.title for q in queries}
    for qid, df in results.items():
        slug = re.sub(r"[^a-z0-9]+", "_", titles[qid].lower()).strip("_")[:50]
        df.to_csv(out_dir / f"{qid.lower()}_{slug}.csv", index=False)


def build_guide(queries: list[AnalysisQuery]) -> str:
    lines = ["# SQL Analytical Layer — Query Guide",
             "_Generated from the headers in `sql/analysis/*.sql` by "
             "`scripts/run_phase3_sql_analysis.py`. Edit the SQL files, not this document._\n",
             "**Scope of every query:** core scope (US order lines, suspected clone copies excluded). "
             "Customer queries additionally exclude placeholder and identity-anomaly customers.\n",
             "| ID | Query | Covers | File |", "|---|---|---|---|"]
    lines += [f"| {q.query_id} | {q.title} | {q.covers} | `{q.source_file}` |" for q in queries]
    for q in queries:
        lines += [f"\n## {q.query_id} — {q.title}",
                  f"**Business question:** {q.question}\n",
                  "**SQL logic:**", *[f"- {item}" for item in q.logic],
                  f"\n**How the result is used:** {q.use}\n",
                  "```sql", q.sql + ";", "```"]
    return "\n".join(lines)


def build_snapshot(results: dict[str, pd.DataFrame], queries: list[AnalysisQuery],
                   validation: pd.DataFrame, max_rows: int = 12) -> str:
    lines = ["# Phase 3 — SQL Results Snapshot",
             "_Raw query outputs (first rows). Facts only: interpretation follows in later phases._\n",
             f"Validation: {(validation.status == 'PASS').sum()} / {len(validation)} checks passed.\n"]
    for q in queries:
        df = results[q.query_id]
        shown = df.head(max_rows)
        lines += [f"## {q.query_id} — {q.title}",
                  f"_{len(df)} rows" + (f", first {max_rows} shown_" if len(df) > max_rows else "_"),
                  md_table(shown, floatfmt=lambda v: f"{v:,.2f}" if abs(v) >= 100 else f"{v:.4f}"), ""]
    return "\n".join(lines)
