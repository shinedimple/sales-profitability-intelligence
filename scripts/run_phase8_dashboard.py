"""
Phase 8 runner: Power BI dashboard specification assets.

    python scripts/run_phase8_dashboard.py      (after Phases 1-7)

Produces
  data/model/ref_product_portfolio.csv, ref_customer_profitability.csv   (classification tables)
  powerbi/spis_theme.json                                                (report theme)
  powerbi/wireframes/p1..p5_*.png                                        (page layouts)
  reports/phase8/acceptance_values.csv, validation_results.csv           (build checks)
  docs/powerbi_dashboard_spec.md                                         (the specification)
"""
from __future__ import annotations

import json
import re
import sys
import textwrap
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
warnings.filterwarnings("ignore")

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.patches as mpatches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from spis import config, customer_analysis as ca, dashboard_spec as ds, eda, modeling, profitability as pr  # noqa: E402
from spis.reporting import md_table  # noqa: E402

ROOT = config.PROJECT_ROOT
PBI = ROOT / "powerbi"
WIRE = PBI / "wireframes"
OUT = ROOT / "reports" / "phase8"
SPEC = ROOT / "docs" / "powerbi_dashboard_spec.md"
DAX = PBI / "dax_measures.dax"

MERGED_COLUMNS = {"dim_product": ["portfolio_quadrant", "portfolio_label", "revenue_tier", "margin_tier"],
                  "dim_customer": ["profitability_segment", "profitability_label"]}


# --------------------------------------------------------------------------
# 1. Classification tables (full-period, from Phases 5 and 7)
# --------------------------------------------------------------------------
def build_reference_tables(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    cm = df["profit"].sum() / df["sales"].sum()
    p = pr.product_metrics(df)
    p["portfolio_quadrant"] = pr.assign_quadrants(p, cm)
    cut = p.loc[p["eligible"], "sales"].median()
    labels = {"Q1": "Q1 Core earners", "Q2": "Q2 Margin leaks", "Q3": "Q3 Niche earners",
              "Q4": "Q4 Review candidates", "NA": "Insufficient evidence"}
    prod = pd.DataFrame({
        "product_key": p["product_key"], "portfolio_quadrant": p["portfolio_quadrant"],
        "portfolio_label": p["portfolio_quadrant"].map(labels),
        "revenue_tier": np.where(~p["eligible"], "Insufficient evidence", np.where(p["sales"] >= cut, "High revenue", "Low revenue")),
        "margin_tier": np.where(~p["eligible"], "Insufficient evidence",
                                np.where(p["profit_margin"] >= cm, "Above margin hurdle", "Below margin hurdle"))})

    v = ca.valid_lines(df)
    cmv = v["profit"].sum() / v["sales"].sum()
    c = ca.customer_metrics(v)
    c["seg"] = ca.assign_segments(c, cmv)
    keys = pd.read_csv(config.MODEL_EXPORT_DIR / "dim_customer.csv")[["customer_key", "customer_id"]]
    cust = keys.merge(c[["customer_id", "seg"]], on="customer_id", how="left")
    cust["profitability_segment"] = cust["seg"].fillna("EX")
    cust["profitability_label"] = cust["profitability_segment"].map(
        {**ca.SHORT, "EX": "Excluded or no core-scope sales"})
    cust = cust[["customer_key", "profitability_segment", "profitability_label"]]
    return {"ref_product_portfolio": prod, "ref_customer_profitability": cust,
            "_meta": pd.Series({"product_revenue_cut": cut, "company_margin": cm})}


# --------------------------------------------------------------------------
# 2. Inventories for validation
# --------------------------------------------------------------------------
def dax_measures() -> dict[str, dict]:
    text = DAX.read_text(encoding="utf-8")
    measures, lines = {}, text.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^([A-Za-z0-9%][A-Za-z0-9 %\-]*?) =\s*$", line)
        if m and not line.startswith("//"):
            name, fmt, note = m.group(1).strip(), "", ""
            for nxt in lines[i + 1:i + 14]:
                if re.match(r"^[A-Za-z0-9%].* =\s*$", nxt):
                    break
                if nxt.startswith("// Format:") or nxt.startswith("// Use:"):
                    parts = nxt[3:].split("|", 1)
                    fmt = parts[0].replace("Format:", "").replace("Use:", "").strip()
                    note = parts[1].strip() if len(parts) > 1 else ""
                    break
            folder = ""
            for back in range(i, -1, -1):
                f = re.match(r"^// -+ Folder: (.+?) -+", lines[back])
                if f:
                    folder = f.group(1)
                    break
            measures[name] = {"format": fmt, "note": note, "folder": folder}
    return measures


def model_fields() -> set[str]:
    fields = set()
    for csv in config.MODEL_EXPORT_DIR.glob("dim_*.csv"):
        fields |= {f"{csv.stem}[{c}]" for c in pd.read_csv(csv, nrows=1).columns}
    fields |= {f"fct_sales[{c}]" for c in pd.read_csv(config.MODEL_EXPORT_DIR / "fct_sales.csv", nrows=1).columns}
    for table, cols in MERGED_COLUMNS.items():
        fields |= {f"{table}[{c}]" for c in cols}
    return fields


def validate(measures: dict, fields: set[str]) -> pd.DataFrame:
    rows = []
    for page in ds.PAGES:
        vis = page["visuals"]
        for v in vis:
            inside = v["x"] >= 0 and v["y"] >= 0 and v["x"] + v["w"] <= ds.CANVAS_W and v["y"] + v["h"] <= ds.CANVAS_H
            on_grid = all(n % ds.GRID == 0 for n in (v["x"], v["y"], v["w"], v["h"]))
            missing_m = [m for m in v["measures"] if m not in measures]
            refs = re.findall(r"(\w+\[\w+\])", " ".join(v["fields"] + v["filters"]))
            missing_f = [f for f in refs if f not in fields]
            rows += [{"page": page["id"], "check": f"{v['id']}: inside canvas", "status": "PASS" if inside else "FAIL", "detail": ""},
                     {"page": page["id"], "check": f"{v['id']}: on 8 px grid", "status": "PASS" if on_grid else "FAIL", "detail": ""},
                     {"page": page["id"], "check": f"{v['id']}: measures exist in DAX library",
                      "status": "PASS" if not missing_m else "FAIL", "detail": ", ".join(missing_m)},
                     {"page": page["id"], "check": f"{v['id']}: fields exist in model",
                      "status": "PASS" if not missing_f else "FAIL", "detail": ", ".join(missing_f)}]
        overlaps = []
        for i, a in enumerate(vis):
            for b in vis[i + 1:]:
                if a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"] and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]:
                    overlaps.append(f"{a['id']}/{b['id']}")
        rows.append({"page": page["id"], "check": "no overlapping visuals", "status": "PASS" if not overlaps else "FAIL",
                     "detail": ", ".join(overlaps)})
        n_data = sum(v["kind"] == "data" for v in vis)
        rows.append({"page": page["id"], "check": f"data visuals <= {ds.MAX_DATA_VISUALS} (declutter rule)",
                     "status": "PASS" if n_data <= ds.MAX_DATA_VISUALS else "FAIL", "detail": f"{n_data} data visuals"})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# 3. Acceptance values: what each KPI card must show after the build
# --------------------------------------------------------------------------
def acceptance_values(df: pd.DataFrame) -> pd.DataFrame:
    def kpis(d: pd.DataFrame) -> dict:
        valid = d[d["is_excluded_from_customer_analysis"] == 0]
        cust_profit = valid.groupby("customer_id")["profit"].sum().sort_values(ascending=False)
        n10 = int(np.ceil(len(cust_profit) * 0.10))
        prod_profit = d.groupby("product_key")["profit"].sum()
        cells = d.groupby(["state_province", "sub_category"])["profit"].sum()
        return {
            "Revenue": d["sales"].sum(), "Profit": d["profit"].sum(), "Profit Margin %": d["profit"].sum() / d["sales"].sum(),
            "Orders": d["order_id"].nunique(), "Customers": d["customer_id"].nunique(), "Units Sold": d["quantity"].sum(),
            "Average Order Value": d["sales"].sum() / d["order_id"].nunique(),
            "Valid Customers": valid["customer_id"].nunique(),
            "Profit per Customer": valid["profit"].sum() / valid["customer_id"].nunique(),
            "Unprofitable Customers": int((cust_profit < 0).sum()),
            "Top 10% Customer Profit Share": cust_profit.head(n10).sum() / cust_profit.sum(),
            "Loss Amount": d.loc[d["profit"] < 0, "profit"].sum(),
            "Loss-making Products": int((prod_profit < 0).sum()),
            "Loss-making Rules": int((cells < 0).sum()), "Loss from Loss-making Rules": cells[cells < 0].sum(),
            "Effective Discount %": d["discount_amount"].sum() / d["gross_sales"].sum(),
            "Discounted Line Share %": (d["discount_rate"] > 0).mean(),
            "Beyond Break-even Revenue %": d.loc[d["is_beyond_break_even"] == 1, "sales"].sum() / d["sales"].sum(),
            "Profit Beyond Break-even": d.loc[d["is_beyond_break_even"] == 1, "profit"].sum(),
        }
    full = kpis(df)
    last, prev = df["order_year"].max(), df["order_year"].max() - 1
    cur, py = kpis(df[df["order_year"] == last]), kpis(df[df["order_year"] == prev])
    rows = [{"measure": k, "filter": "All years", "expected": v} for k, v in full.items()]
    rows += [{"measure": k, "filter": f"Year = {last}", "expected": cur[k]} for k in
             ["Revenue", "Profit", "Profit Margin %", "Orders", "Average Order Value"]]
    growth = {"Revenue Growth %": cur["Revenue"] / py["Revenue"] - 1, "Profit Growth %": cur["Profit"] / py["Profit"] - 1,
              "Margin Change pp": cur["Profit Margin %"] - py["Profit Margin %"],
              "Orders Growth %": cur["Orders"] / py["Orders"] - 1,
              "AOV Growth %": cur["Average Order Value"] / py["Average Order Value"] - 1}
    rows += [{"measure": k, "filter": f"Year = {last}", "expected": v} for k, v in growth.items()]
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# 4. Theme
# --------------------------------------------------------------------------
def theme() -> dict:
    c = ds.COLORS
    return {
        "name": "SPIS Executive",
        "dataColors": [c["profit"], c["neutral"], c["accent"], "#4C8BD6", c["loss"], "#7FB7A4", c["muted"], "#8E6C8A"],
        "background": c["card"], "foreground": c["text"], "tableAccent": c["profit"],
        "good": c["profit"], "neutral": c["accent"], "bad": c["loss"],
        "maximum": c["profit"], "center": "#F2F2F2", "minimum": c["loss"],
        "textClasses": {
            "callout": {"fontSize": 26, "fontFace": "Segoe UI Semibold", "color": c["text"]},
            "title": {"fontSize": 11, "fontFace": "Segoe UI Semibold", "color": c["text"]},
            "header": {"fontSize": 10, "fontFace": "Segoe UI Semibold", "color": c["text"]},
            "label": {"fontSize": 9, "fontFace": "Segoe UI", "color": c["subtle"]},
        },
        "visualStyles": {
            "*": {"*": {
                "background": [{"show": True, "color": {"solid": {"color": c["card"]}}, "transparency": 0}],
                "border": [{"show": False}],
                "dropShadow": [{"show": False}],
                "title": [{"show": True, "fontSize": 11, "fontColor": {"solid": {"color": c["text"]}}, "alignment": "left"}],
                "padding": [{"top": 8, "bottom": 8, "left": 12, "right": 12}],
            }},
            "page": {"*": {"background": [{"color": {"solid": {"color": c["page"]}}, "transparency": 0}]}},
        },
    }


# --------------------------------------------------------------------------
# 5. Wireframes
# --------------------------------------------------------------------------
KIND_STYLE = {"kpi": ("#E7F1F0", ds.COLORS["profit"]), "data": ("#FFFFFF", ds.COLORS["neutral"]),
              "slicer": ("#EEF0F3", ds.COLORS["muted"]), "chrome": ("#F4F6F8", ds.COLORS["muted"]),
              "text": ("#FFF6E8", ds.COLORS["accent"])}


def wireframe(page: dict, path: Path) -> Path:
    fig = plt.figure(figsize=(12.8, 7.2), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, ds.CANVAS_W)
    ax.set_ylim(ds.CANVAS_H, 0)
    ax.axis("off")
    ax.add_patch(mpatches.Rectangle((0, 0), ds.CANVAS_W, ds.CANVAS_H, color=ds.COLORS["page"]))
    for v in page["visuals"]:
        face, edge = KIND_STYLE[v["kind"]]
        ax.add_patch(mpatches.FancyBboxPatch((v["x"], v["y"]), v["w"], v["h"], boxstyle="round,pad=0,rounding_size=4",
                                             facecolor=face, edgecolor=edge, linewidth=1.2))
        if v["kind"] in ("data", "text"):
            ax.text(v["x"] + 10, v["y"] + 18, v["title"], fontsize=9.5, fontweight="bold", color=ds.COLORS["text"], va="center")
            ax.text(v["x"] + 10, v["y"] + 36, v["type"], fontsize=8.5, color=ds.COLORS["subtle"], va="center", style="italic")
            body = ", ".join(v["measures"][:3]) if v["measures"] else ""
            if body:
                ax.text(v["x"] + 10, v["y"] + 54, textwrap.shorten(body, width=int(v["w"] / 6.2)), fontsize=7.5,
                        color=ds.COLORS["subtle"], va="center")
        elif v["kind"] == "kpi":
            ax.text(v["x"] + 10, v["y"] + 20, v["title"], fontsize=8.5, color=ds.COLORS["subtle"], va="center")
            ax.text(v["x"] + 10, v["y"] + 50, f"[{v['measures'][0]}]", fontsize=10, fontweight="bold", color=ds.COLORS["text"], va="center")
            if len(v["measures"]) > 1:
                ax.text(v["x"] + 10, v["y"] + 72, textwrap.shorten(f"vs: {v['measures'][1]}", width=int(v["w"] / 6)),
                        fontsize=7.5, color=ds.COLORS["profit"], va="center")
        else:
            label = page["name"] if v["id"] == "hdr_title" else v["title"]
            weight, size = ("bold", 14) if v["id"] == "hdr_title" else ("normal", 8.5)
            ax.text(v["x"] + 8, v["y"] + v["h"] / 2, label, fontsize=size, fontweight=weight, color=ds.COLORS["text"], va="center")
    ax.text(ds.CANVAS_W - 24, ds.CANVAS_H - 2, f"{page['id']} wireframe | 1280 x 720 | 8 px grid", fontsize=7, ha="right",
            va="bottom", color=ds.COLORS["subtle"])
    fig.savefig(path, dpi=100)
    plt.close(fig)
    return path


# --------------------------------------------------------------------------
# 6. Specification document
# --------------------------------------------------------------------------
def fmt_value(measure: str, v: float, measures: dict) -> str:
    f = measures.get(measure, {}).get("format", "")
    if "%" in f or measure.endswith("%") or measure.endswith("pp"):
        return f"{v * 100:+.1f} pp" if measure.endswith("pp") else f"{v:.1%}"
    if "0.00" in f:
        return f"{v:,.2f}"
    return f"{v:,.0f}"


def build_spec(measures: dict, validation: pd.DataFrame, accept: pd.DataFrame, refs: dict, figs: dict) -> str:
    L: list[str] = []
    add = L.append
    add("# Power BI Dashboard Specification — Sales & Profitability Intelligence System")
    add("_Generated by `scripts/run_phase8_dashboard.py` from `src/spis/dashboard_spec.py` (single source of truth). "
        "Edit the spec module, not this document._\n")
    add(f"**Layout and reference checks:** {(validation.status == 'PASS').sum()}/{len(validation)} passed "
        "(visuals inside the canvas, on the 8 px grid, no overlaps, every measure in the DAX library, every field in the model).\n")

    add("## 1. Design principles")
    add("1. **One question per page.** The page title states it; every visual must help answer it.")
    add("2. **Decision before decoration.** No pie, donut, gauge, 3-D or map visuals; no dual axes; no visual without a stated purpose.")
    add(f"3. **Uncluttered.** At most {ds.MAX_DATA_VISUALS} data visuals per page (the busiest page has 6), plus KPI cards.")
    add("4. **Every KPI has a comparison.** Cards show the value and the change versus the prior year.")
    add("5. **Colour has meaning.** Teal = profit or above hurdle; red = loss or below hurdle; slate = neutral; amber = highlight. Colour is never decorative.")
    add("6. **Rankings state their metric.** Every top/bottom list says what it is ranked by (absolute profit, loss amount, margin).")
    add("7. **No causal language.** Dynamic findings describe; management questions ask. The scope note is visible on every page.\n")

    add("## 2. Data model setup")
    add("**Source:** the star-schema CSVs in `data/model/` (or the SQLite warehouse via ODBC). Import mode.\n")
    add("| Step | Action |")
    add("|---|---|")
    add("| 1 | Load `fct_sales`, `dim_date`, `dim_customer`, `dim_product`, `dim_location`, `dim_ship_mode`, `dim_discount`, `ref_product_portfolio`, `ref_customer_profitability` |")
    add("| 2 | Power Query: merge `ref_product_portfolio` into `dim_product` and `ref_customer_profitability` into `dim_customer` (left outer join on the key); expand the new columns; disable load of the two `ref_` queries |")
    add("| 3 | Relationships: one-to-many, single direction, dimension -> fact, as in `docs/data_model.md`. `dim_date[date_key]` -> `fct_sales[order_date_key]` active; -> `ship_date_key` inactive |")
    add("| 4 | Mark `dim_date` as the date table (`dim_date[date]`) |")
    add("| 5 | Sort by column: `month_name`/`month_short` by `month`; `discount_label` by `discount_key`; `discount_band` by `discount_band_sort`; `portfolio_label` by `portfolio_quadrant`; `profitability_label` by `profitability_segment` |")
    add("| 6 | Hide every `*_key` column, all `dq_*` flags and raw measures columns (users work only with measures and dimension attributes) |")
    add("| 7 | Create a blank `_Measures` table and paste the measures from `powerbi/dax_measures.dax`, using its display folders |")
    add("| 8 | Create the field parameter `Sales Breakdown` (definition at the end of the DAX file) |")
    add(f"| 9 | Report-level filter: {ds.REPORT_FILTERS[0]} |")
    add("| 10 | Apply the theme `powerbi/spis_theme.json` (View > Themes > Browse) |")
    add("\nPower Query merge (M) for the product classification:\n")
    add("```m\nlet\n    Source = dim_product,\n    Merged = Table.NestedJoin(Source, {\"product_key\"}, ref_product_portfolio, {\"product_key\"}, \"ref\", JoinKind.LeftOuter),\n"
        "    Expanded = Table.ExpandTableColumn(Merged, \"ref\", {\"portfolio_quadrant\", \"portfolio_label\", \"revenue_tier\", \"margin_tier\"})\n"
        "in\n    Expanded\n```")
    meta = refs["_meta"]
    add(f"\nThe classification columns are a **2023-2026 classification** (product revenue cut {meta['product_revenue_cut']:,.0f}, "
        f"margin hurdle {meta['company_margin']:.1%}; Phases 5 and 7). They do not change with the year slicer; visuals that use them say so in their subtitle.\n")

    add("## 3. Design system")
    add("| Element | Specification |")
    add("|---|---|")
    add(f"| Canvas | {ds.CANVAS_W} x {ds.CANVAS_H} (16:9), page background {ds.COLORS['page']} |")
    add(f"| Grid | {ds.GRID} px; outer margin {ds.MARGIN} px; 16 px between visuals |")
    add(f"| Bands | Header y={ds.HEADER_Y} (40 px) - filter bar y={ds.FILTER_Y} (40 px) - KPI row y={ds.KPI_Y} (88 px) - row A y={ds.ROW_A_Y} - row B y={ds.ROW_B_Y} (each {ds.ROW_H} px) - footer y={ds.FOOTER_Y} |")
    add("| Typography | Segoe UI; titles Semibold 11 pt; KPI callouts Semibold 24-28 pt; labels 9 pt #6B7785 |")
    add("| Colours | " + ", ".join(f"{k} `{v}`" for k, v in ds.COLORS.items()) + " |")
    add("| Visual containers | White, no border, no shadow, 8/12 px padding, left-aligned titles |")
    add("| Slicers | Year, Region, Category, Segment in the filter bar of every page, synced across all five pages (View > Sync slicers) |")
    add("| Interactions | Cross-filter (not cross-highlight) between charts; KPI cards and the context card are not filtered by other visuals' selections, only by slicers |")
    add("| Accessibility | Alt text on every visual (its purpose), tab order top-left to bottom-right, colour never the only signal (labels and signs accompany red/teal) |\n")

    for page in ds.PAGES:
        vis = page["visuals"]
        add(f"## Page {page['id'][1:]} — {page['name']}")
        add(f"**Question:** {page['question']}  ")
        add(f"**Business purpose:** {page['purpose']}\n")
        add(f"![{page['id']} wireframe]({figs[page['id']]})\n")
        add("**Layout** (pixels, top-left origin)\n")
        lay = pd.DataFrame([{"id": v["id"], "visual": v["title"], "type": v["type"], "x": v["x"], "y": v["y"], "w": v["w"], "h": v["h"]}
                            for v in vis if v["kind"] in ("kpi", "data", "text") or v["id"] in ("v2_breakdown_sel", "v4_toggle")])
        add(md_table(lay))
        add("\n**KPI cards**\n")
        add("| Card | Callout measure | Comparison (reference label) |")
        add("|---|---|---|")
        for v in vis:
            if v["kind"] == "kpi":
                add(f"| {v['title']} | `{v['measures'][0]}` | " + (f"`{v['measures'][1]}`" if len(v["measures"]) > 1 else "-") + " |")
        add("\n**Visuals**\n")
        for v in vis:
            if v["kind"] not in ("data", "text") and v["id"] != "v2_breakdown_sel":
                continue
            add(f"**{v['id']} — {v['title']}**")
            add(f"- *Visual type:* {v['type']}")
            if v["fields"]:
                add(f"- *Fields:* " + "; ".join(f"`{f}`" for f in v["fields"]))
            if v["measures"]:
                add(f"- *Measures:* " + ", ".join(f"`{m}`" for m in v["measures"]))
            add(f"- *Filters:* " + ("; ".join(v["filters"]) if v["filters"] else "page slicers + report scope filter"))
            if v["formatting"]:
                add(f"- *Formatting:* {v['formatting']}")
            if v["purpose"]:
                add(f"- *Business purpose:* {v['purpose']}")
            if v["id"] == "v5_questions":
                add("- *Content:*")
                for q in ds.MANAGEMENT_QUESTIONS:
                    add(f"  - {q}")
            add("")
        add("**Filters on this page:** synced slicers (Year, Region, Category, Segment); report scope filter; visual-level filters as listed above.\n")
        used = []
        for v in vis:
            for m in v["measures"]:
                if m not in used:
                    used.append(m)
        add("**DAX measures required on this page:** " + ", ".join(f"`{m}`" for m in used) + "\n")

    add("## 9. Measure catalogue")
    add("All measures are defined in `powerbi/dax_measures.dax`. Measures used by the dashboard:\n")
    used_all = sorted({m for p in ds.PAGES for v in p["visuals"] for m in v["measures"]})
    cat = pd.DataFrame([{"measure": m, "folder": measures[m]["folder"], "format": measures[m]["format"],
                         "note": measures[m]["note"]} for m in used_all]).sort_values(["folder", "measure"])
    add(md_table(cat))
    add("\nKey DAX patterns (full definitions in the library):\n")
    add("```dax\nProfit Margin % = DIVIDE ( [Profit], [Revenue] )                      -- ratio of sums, never an average of ratios\n"
        "Revenue Growth % = IF ( NOT ISBLANK ( [Revenue] ) && [Revenue PY] > 0, DIVIDE ( [Revenue] - [Revenue PY], [Revenue PY] ) )\n"
        "Profit Growth %  = blank when prior-year profit <= 0 (a % change from a negative base is misleading)\n"
        "Beyond Break-even Revenue % = DIVIDE ( CALCULATE ( [Revenue], fct_sales[is_beyond_break_even] = 1 ), [Revenue] )\n"
        "Loss-making Rules = COUNTROWS ( FILTER ( SUMMARIZE ( fct_sales, dim_location[state_province], dim_product[sub_category] ), [Profit] < 0 ) )\n```\n")

    add("## 10. Bookmarks and navigation")
    add(md_table(pd.DataFrame(ds.BOOKMARKS, columns=["bookmark", "page", "behaviour"])))
    add("\nNavigation uses the page navigator in the header; the native page tabs are hidden in the published app.\n")

    add("## 11. Acceptance tests")
    add("After building, each KPI card must show the value below (core scope). These come from the Python/SQL pipeline, so a match proves the DAX "
        "is correct. Compare at the stated filter.\n")
    acc = accept.assign(expected=[fmt_value(m, v, measures) for m, v in zip(accept["measure"], accept["expected"])])
    add(md_table(acc))
    add("")

    add("## 12. Deliberately not shown")
    add(md_table(pd.DataFrame(ds.NOT_SHOWN, columns=["element", "reason"])))
    add("\n## 13. Build checklist")
    for item in ["Model loads with 0 relationship warnings; all keys hidden",
                 "Date table marked; time-intelligence measures return blank for the first year",
                 "All acceptance values in section 11 match (tolerance: rounding)",
                 "Each page: title states the question; no visual without a purpose; scope note visible",
                 "Slicers synced on all pages; Reset bookmark restores 'All'",
                 "Performance Analyzer: every visual < 1 s on refresh",
                 "Alt text and tab order set; report reviewed in the colour-blind simulator"]:
        add(f"- [ ] {item}")
    add("\n## 14. Validation details")
    add(md_table(validation[validation["status"] != "PASS"] if (validation["status"] != "PASS").any()
                 else pd.DataFrame([{"result": f"All {len(validation)} checks passed"}])))
    return "\n".join(L)


def main() -> None:
    for d in (WIRE, OUT):
        d.mkdir(parents=True, exist_ok=True)
    conn = modeling.connect()
    df = eda.load_core_lines(conn)
    conn.close()

    refs = build_reference_tables(df)
    for name in ("ref_product_portfolio", "ref_customer_profitability"):
        refs[name].to_csv(config.MODEL_EXPORT_DIR / f"{name}.csv", index=False)

    measures, fields = dax_measures(), model_fields()
    validation = validate(measures, fields)
    validation.to_csv(OUT / "validation_results.csv", index=False)
    print(f"[validation] {(validation.status == 'PASS').sum()}/{len(validation)} spec checks passed")
    if (validation.status != "PASS").any():
        print(validation[validation.status != "PASS"].to_string(index=False))
        raise SystemExit("Specification failed validation.")

    accept = acceptance_values(df)
    accept.to_csv(OUT / "acceptance_values.csv", index=False)
    (PBI / "spis_theme.json").write_text(json.dumps(theme(), indent=2), encoding="utf-8")
    figs = {}
    for page in ds.PAGES:
        slug = re.sub(r"[^a-z0-9]+", "_", page["name"].lower()).strip("_")
        path = wireframe(page, WIRE / f"{page['id'].lower()}_{slug}.png")
        figs[page["id"]] = f"../powerbi/wireframes/{path.name}"
    SPEC.write_text(build_spec(measures, validation, accept, refs, figs), encoding="utf-8")
    print(f"[done]       spec -> {SPEC.relative_to(ROOT)}, wireframes -> {WIRE.relative_to(ROOT)}, theme -> powerbi/spis_theme.json")


if __name__ == "__main__":
    main()
