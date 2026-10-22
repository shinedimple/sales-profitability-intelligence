"""
Phase 9 runner: the DAX layer.

    python scripts/run_phase9_dax_layer.py      (after Phase 8)

Produces
  docs/dax_guide.md                     every measure: code, plain explanation, where used, mistakes, validation
  powerbi/validation_queries.dax        DAX queries to run in Power BI's DAX query view
  reports/phase9/dax_expected_values.csv expected results for those queries (from the SQL warehouse)
  reports/phase9/checks.csv             consistency checks (library vs docs vs dashboard)
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from spis import config, dashboard_spec as ds, dax_docs as dd  # noqa: E402
from spis.reporting import md_table  # noqa: E402

ROOT = config.PROJECT_ROOT
DAX = ROOT / "powerbi" / "dax_measures.dax"
GUIDE = ROOT / "docs" / "dax_guide.md"
QUERIES = ROOT / "powerbi" / "validation_queries.dax"
OUT = ROOT / "reports" / "phase9"

VALIDATED = ["Revenue", "Profit", "Profit Margin %", "Orders", "Customers", "Valid Customers", "Units Sold",
             "Average Order Value", "Effective Discount %", "Average Line Discount %", "Profit per Order",
             "Profit per Customer", "Revenue PY", "Revenue Growth %", "Profit Growth %", "Margin Change pp"]


# --------------------------------------------------------------------------
def parse_library() -> dict[str, dict]:
    lines = DAX.read_text(encoding="utf-8").splitlines()
    out, folder, i = {}, "", 0
    while i < len(lines):
        f = re.match(r"^// -+ Folder: (.+?) -+", lines[i])
        if f:
            folder = f.group(1)
        m = re.match(r"^([A-Za-z0-9%][A-Za-z0-9 %\-]*?) =\s*$", lines[i])
        if m:
            name, code, j = m.group(1).strip(), [lines[i]], i + 1
            while j < len(lines) and not lines[j].startswith("//") and lines[j].strip() != "":
                code.append(lines[j])
                j += 1
            note = lines[j][3:] if j < len(lines) and lines[j].startswith("//") else ""
            fmt, desc = (note.split("|", 1) + [""])[:2]
            out[name] = {"folder": folder, "code": "\n".join(code),
                         "format": fmt.replace("Format:", "").replace("Use:", "").strip(), "desc": desc.strip() or fmt.replace("Use:", "").strip()}
            i = j
        i += 1
    return out


def where_used() -> dict[str, list[str]]:
    used: dict[str, list[str]] = {}
    for p in ds.PAGES:
        for v in p["visuals"]:
            for m in v["measures"]:
                used.setdefault(m, []).append(f"{p['id']} {v['title']}")
    return used


def references(lib: dict) -> dict[str, list[str]]:
    """Which measures each measure depends on (for the dependency column)."""
    return {n: [m for m in lib if m != n and f"[{m}]" in lib[n]["code"]] for n in lib}


# --------------------------------------------------------------------------
def expected_values() -> pd.DataFrame:
    conn = sqlite3.connect(config.WAREHOUSE_DB)
    d = pd.read_sql("""SELECT f.*, d.year, c.is_excluded_from_customer_analysis AS excl FROM fct_sales f
                       JOIN dim_date d ON d.date_key = f.order_date_key
                       JOIN dim_customer c ON c.customer_key = f.customer_key WHERE f.is_core_scope = 1""", conn)
    conn.close()

    def base(x: pd.DataFrame) -> dict:
        v = x[x["excl"] == 0]
        return {"Revenue": x["sales"].sum(), "Profit": x["profit"].sum(), "Profit Margin %": x["profit"].sum() / x["sales"].sum(),
                "Orders": x["order_id"].nunique(), "Customers": x["customer_key"].nunique(), "Valid Customers": v["customer_key"].nunique(),
                "Units Sold": x["quantity"].sum(), "Average Order Value": x["sales"].sum() / x["order_id"].nunique(),
                "Effective Discount %": x["discount_amount"].sum() / x["gross_sales"].sum(),
                "Average Line Discount %": x["discount_rate"].mean(), "Profit per Order": x["profit"].sum() / x["order_id"].nunique(),
                "Profit per Customer": v["profit"].sum() / v["customer_key"].nunique()}

    rows = {"All years": {**base(d), "Revenue PY": np.nan, "Revenue Growth %": np.nan, "Profit Growth %": np.nan, "Margin Change pp": np.nan}}
    years = sorted(d["year"].unique())
    for y in years:
        cur = base(d[d["year"] == y])
        if y - 1 in years:
            py = base(d[d["year"] == y - 1])
            cur |= {"Revenue PY": py["Revenue"], "Revenue Growth %": cur["Revenue"] / py["Revenue"] - 1,
                    "Profit Growth %": cur["Profit"] / py["Profit"] - 1 if py["Profit"] > 0 else np.nan,
                    "Margin Change pp": cur["Profit Margin %"] - py["Profit Margin %"]}
        else:
            cur |= {"Revenue PY": np.nan, "Revenue Growth %": np.nan, "Profit Growth %": np.nan, "Margin Change pp": np.nan}
        rows[str(y)] = cur
    return pd.DataFrame(rows).T[VALIDATED]


def fmt(measure: str, v) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "(blank)"
    if measure.endswith("pp"):
        return f"{v * 100:+.2f} pp"
    if measure.endswith("%"):
        return f"{v:.2%}"
    if measure in ("Average Order Value", "Profit per Order", "Profit per Customer"):
        return f"{v:,.2f}"
    return f"{v:,.0f}"


# --------------------------------------------------------------------------
def validation_queries(exp: pd.DataFrame) -> str:
    cols = ",\n".join(f'    "{m}", [{m}]' for m in VALIDATED)
    lines = [
        "// ==========================================================================",
        "// Validation queries - run in Power BI Desktop: DAX query view (or DAX Studio).",
        "// Report-level filters do NOT apply in the DAX query view, so every query adds",
        "// the core-scope filter explicitly. Compare results with",
        "// reports/phase9/dax_expected_values.csv (generated from the SQL warehouse).",
        "// ==========================================================================",
        "",
        "// Query 1: all years (growth measures must be BLANK here)",
        "EVALUATE",
        "CALCULATETABLE (",
        "    ROW (",
        ",\n".join(f'        "{m}", [{m}]' for m in VALIDATED),
        "    ),",
        "    fct_sales[is_core_scope] = 1",
        ")",
        "",
        "// Query 2: by year (growth BLANK for 2023, the first year)",
        "EVALUATE",
        "SUMMARIZECOLUMNS (",
        "    dim_date[year],",
        "    TREATAS ( { 1 }, fct_sales[is_core_scope] ),",
        cols,
        ")",
        "ORDER BY dim_date[year]",
        "",
        "// Query 3: filter context check - category totals must add up to Revenue and Profit,",
        "// but Orders and Customers must NOT (one order/customer spans several categories).",
        "EVALUATE",
        "SUMMARIZECOLUMNS (",
        "    dim_product[category],",
        "    TREATAS ( { 1 }, fct_sales[is_core_scope] ),",
        '    "Revenue", [Revenue], "Profit", [Profit], "Orders", [Orders], "Customers", [Customers],',
        '    "Profit Margin %", [Profit Margin %]',
        ")",
        "",
        "// Expected values (from SQL):",
    ]
    for period, row in exp.iterrows():
        lines.append(f"//   {period}: " + "; ".join(f"{m} = {fmt(m, row[m])}" for m in ["Revenue", "Profit", "Profit Margin %", "Orders",
                                                                                         "Revenue Growth %", "Profit Growth %"]))
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
def build_guide(lib: dict, used: dict, deps: dict, exp: pd.DataFrame, checks: pd.DataFrame) -> str:
    L: list[str] = []
    add = L.append
    add("# DAX Layer — Measures, Explanations and Validation")
    add("_Generated by `scripts/run_phase9_dax_layer.py`. The code shown is read from `powerbi/dax_measures.dax`, so this guide always matches the library._\n")
    add(f"**Library:** {len(lib)} measures in `powerbi/dax_measures.dax`, every one used by the dashboard or by another measure. "
        f"**Consistency checks:** {(checks.status == 'PASS').sum()}/{len(checks)} passed.\n")

    add("## 1. Requested measures and where to find them")
    add("| Requested | Measure in the library | Note |")
    add("|---|---|---|")
    for req, name, note in dd.REQUESTED:
        add(f"| {req} | `{name}` | {note} |")
    add("")

    add("## 2. DAX concepts used in this layer (read first)")
    for title, text in dd.PRIMER:
        add(f"**{title}.** {text}\n")
    add("**Model rules these measures rely on:** star schema with single-direction relationships; `dim_date` marked as the date table; "
        "report-level filter `fct_sales[is_core_scope] = 1`; all `*_key` columns hidden so users build visuals from measures and dimension attributes only.\n")

    add("## 3. Core measures in detail")
    add("Expected values are computed independently from the SQL warehouse (core scope). Section 6 explains how to compare.\n")
    order = ["Revenue", "Profit", "Profit Margin %", "Orders", "Customers", "Valid Customers", "Units Sold", "Average Order Value",
             "Effective Discount %", "Average Line Discount %", "Last Sales Date Key", "PY Comparison Valid", "Revenue PY", "Revenue Growth %",
             "Profit PY", "Profit Growth %", "Margin Change pp", "Profit per Order", "Profit per Customer"]
    for i, name in enumerate(order, 1):
        doc, m = dd.CORE[name], lib[name]
        add(f"### 3.{i} {name}")
        add("```dax\n" + m["code"] + "\n```")
        add(f"*Format:* `{m['format']}`" + (f"  ·  *Depends on:* " + ", ".join(f"`{x}`" for x in deps[name]) if deps[name] else ""))
        add(f"\n**1. What it does.** {doc['plain']}\n")
        add(f"**2. Where to use it.** {doc['use']}" + (f" (In the spec: {'; '.join(used[name][:4])}{'…' if len(used.get(name, [])) > 4 else ''}.)" if name in used else "") + "\n")
        add("**3. Common mistakes.**")
        for mistake in doc["mistakes"]:
            add(f"- {mistake}")
        add("\n**4. How to validate it.**")
        add(f"```sql\n{doc['sql']}\n```")
        if name in exp.columns:
            vals = ", ".join(f"{p}: **{fmt(name, exp.loc[p, name])}**" for p in exp.index)
            add(f"Expected: {vals}.")
        add("")

    add("## 4. Supporting measures")
    add("Used by specific dashboard visuals. Each row gives the plain meaning, where it is used, the typical mistake and how to check it.\n")
    rows = []
    for name, m in lib.items():
        if name in dd.CORE:
            continue
        mistake, check = dd.FOLDER_DEFAULTS.get(m["folder"], ("", ""))
        rows.append({"measure": f"`{name}`", "folder": m["folder"], "what it does": m["desc"],
                     "used in": "; ".join(used.get(name, [])[:2]) or "inside: " + ", ".join(
                         n for n, d in deps.items() if name in d)[:60],
                     "typical mistake": mistake, "validate": check})
    add(md_table(pd.DataFrame(rows)))
    add("\nThree supporting measures deserve a closer look because they iterate:\n")
    for name, text in [
        ("Loss-making Products", "FILTER walks the list of products in context (VALUES), evaluates [Profit] for each one through context "
                                 "transition, and keeps those below zero. Iterating over fct_sales rows instead would test each line, not each product."),
        ("Top 10% Customer Profit Share", "Builds the list of valid customers in context, takes the top 10% by profit with TOPN, and divides their "
                                          "profit by all valid customers' profit. It recalculates for any slicer, so it answers 'top 10% of which customers?' correctly."),
        ("Loss-making Rules", "SUMMARIZE creates every state x sub-category combination present in the fact table (one discount rule each); FILTER keeps "
                              "the combinations with negative profit.")]:
        add(f"**{name}**\n```dax\n{lib[name]['code']}\n```\n{text}\n")

    add("## 5. Considered but not created")
    for title, why, code in dd.NOT_CREATED:
        add(f"**{title}.** {why}")
        if code:
            add(f"```dax\n{code}\n```")
        add("")

    add("## 6. How to validate the DAX layer")
    add("1. **DAX query view.** Open `powerbi/validation_queries.dax` in Power BI Desktop (DAX query view) and run the three queries. "
        "Query 1 and 2 must match the table below; growth must be blank for 'All years' and for 2023.")
    add("2. **Filter-context check (query 3).** Category Revenue and Profit add up to the total; Orders and Customers do not, because one order "
        "or customer can span several categories. If they *do* add up exactly, the measure is counting rows, not distinct values.")
    add("3. **Independent SQL.** Each core measure above lists the SQL that reproduces it from `data/warehouse/spis.sqlite`.")
    add("4. **Visual spot-checks.** Select 2026 in the Year slicer: the Revenue card label must read ▲ 20.4% vs prior year; with no year selected it must "
        "ask for a year instead of showing a number.")
    add("5. **Report filter check.** Temporarily remove the report-level scope filter: Revenue rises to 2,326k (Canadian rows included). Restore it.\n")
    show = exp.copy()
    for c in show.columns:
        show[c] = [fmt(c, v) for v in show[c]]
    add("**Expected values (core scope)**\n")
    add(md_table(show.T.reset_index().rename(columns={"index": "measure"})))
    add("\n## 7. Library consistency checks")
    add(md_table(checks))
    return "\n".join(L)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    lib = parse_library()
    used, deps = where_used(), references(lib)
    dashboard = {m for p in ds.PAGES for v in p["visuals"] for m in v["measures"]}
    referenced = {m for d in deps.values() for m in d}
    checks = pd.DataFrame([
        {"check": "Every requested measure exists", "status": "PASS" if all(n in lib for _, n, _ in dd.REQUESTED) else "FAIL",
         "detail": ", ".join(n for _, n, _ in dd.REQUESTED if n not in lib)},
        {"check": "Every dashboard measure exists in the library", "status": "PASS" if dashboard <= set(lib) else "FAIL",
         "detail": ", ".join(sorted(dashboard - set(lib)))},
        {"check": "No unused measures (each is on the dashboard or used by another measure)",
         "status": "PASS" if set(lib) <= dashboard | referenced else "FAIL", "detail": ", ".join(sorted(set(lib) - dashboard - referenced))},
        {"check": "Every core write-up refers to a library measure", "status": "PASS" if set(dd.CORE) <= set(lib) else "FAIL",
         "detail": ", ".join(sorted(set(dd.CORE) - set(lib)))},
        {"check": "Every measure has a format/usage note", "status": "PASS" if all(m["format"] for m in lib.values()) else "FAIL",
         "detail": ", ".join(n for n, m in lib.items() if not m["format"])},
    ])
    checks.to_csv(OUT / "checks.csv", index=False)
    print(f"[checks]     {(checks.status == 'PASS').sum()}/{len(checks)} passed")
    if (checks.status != "PASS").any():
        print(checks[checks.status != "PASS"].to_string(index=False))
        raise SystemExit("DAX layer checks failed.")
    exp = expected_values()
    exp.to_csv(OUT / "dax_expected_values.csv")
    QUERIES.write_text(validation_queries(exp), encoding="utf-8")
    GUIDE.write_text(build_guide(lib, used, deps, exp, checks), encoding="utf-8")
    print(f"[done]       {len(lib)} measures documented -> {GUIDE.relative_to(ROOT)}; queries -> {QUERIES.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
