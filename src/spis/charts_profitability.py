"""Phase 5 charts: each answers one profitability question (the chart title)."""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
import seaborn as sns

from .charts import ACCENT, MUTED, NEG, NEUTRAL, POS, _finish, _money, _pct

QCOLORS = {"Q1": POS, "Q2": NEG, "Q3": "#4C8BD6", "Q4": ACCENT, "NA": MUTED}
QSHORT = {"Q1": "Q1 Core earners", "Q2": "Q2 Margin leaks", "Q3": "Q3 Niche earners",
          "Q4": "Q4 Review candidates", "NA": "Insufficient evidence"}


def product_quadrants(p: pd.DataFrame, company_margin: float, sales_cut: float, path: Path) -> Path:
    """Q: Where does each product sit on revenue vs margin?"""
    fig, ax = plt.subplots(figsize=(10, 6.5))
    for q in ["NA", "Q3", "Q4", "Q1", "Q2"]:
        d = p[p["quadrant"] == q]
        ax.scatter(d["sales"], d["profit_margin"].clip(-1.5, 0.6), s=14, alpha=0.55,
                   color=QCOLORS[q], label=f"{QSHORT[q]} (n={len(d)})", edgecolor="none")
    ax.set_xscale("log")
    ax.axvline(sales_cut, color=NEUTRAL, ls="--", lw=1)
    ax.axhline(company_margin, color=NEUTRAL, ls="--", lw=1)
    ax.text(sales_cut * 1.1, -1.45, f"median revenue of eligible products ({sales_cut:,.0f})", fontsize=8, color=NEUTRAL)
    ax.text(1.2, company_margin + 0.03, f"company margin {company_margin:.1%}", fontsize=8, color=NEUTRAL,
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.85, pad=1))
    ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    _pct(ax)
    ax.set_xlabel("Product revenue over four years (log scale)")
    ax.set_ylabel("Product profit margin (capped at -150%)")
    ax.legend(frameon=False, fontsize=8.5, loc="lower left")
    ax.set_title("Where does each product sit? Revenue vs margin, classified into four quadrants")
    return _finish(fig, path, "Products with fewer than 3 order lines are shown grey and not classified.")


def quadrant_shares(qs: pd.DataFrame, path: Path) -> Path:
    """Q: How are products, revenue and profit distributed across the quadrants?"""
    q = qs.loc[["Q1", "Q2", "Q3", "Q4", "NA"]]
    metrics = [("share_of_products", "Products"), ("share_of_sales", "Revenue"), ("share_of_profit", "Profit")]
    fig, ax = plt.subplots(figsize=(10, 4.8))
    x = np.arange(len(q))
    for i, (col, lab) in enumerate(metrics):
        bars = ax.bar(x + (i - 1) * 0.26, q[col], width=0.26, label=lab,
                      color=[MUTED, NEUTRAL, POS][i])
        for b, v in zip(bars, q[col]):
            ax.text(b.get_x() + b.get_width() / 2, v + (0.012 if v >= 0 else -0.012),
                    f"{v:.0%}" if abs(v) >= 0.01 else f"{v:.1%}",
                    ha="center", va="bottom" if v >= 0 else "top", fontsize=7.5)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks(x, [QSHORT[i].replace(" ", "\n", 1) for i in q.index], fontsize=9)
    _pct(ax)
    ax.legend(frameon=False, ncol=3, loc="upper right")
    ax.set_title("How are products, revenue and profit distributed across the quadrants?")
    return _finish(fig, path)


def quadrant_waterfall(qs: pd.DataFrame, total_profit: float, path: Path) -> Path:
    """Q: How does each quadrant add to or subtract from total profit?"""
    order = ["Q1", "Q3", "NA", "Q4", "Q2"]
    vals = qs.loc[order, "profit"].values
    starts = np.concatenate([[0], np.cumsum(vals)[:-1]])
    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    for i, (s, v, q) in enumerate(zip(starts, vals, order)):
        ax.bar(i, v, bottom=s, color=POS if v >= 0 else NEG, width=0.6)
        ax.text(i, s + v + (4000 if v >= 0 else -4000), f"{v/1000:+,.1f}k", ha="center",
                va="bottom" if v >= 0 else "top", fontsize=9)
    ax.bar(len(order), total_profit, color=NEUTRAL, width=0.6)
    ax.text(len(order), total_profit + 4000, f"{total_profit/1000:,.1f}k", ha="center", fontsize=9, fontweight="bold")
    ax.set_xticks(range(len(order) + 1), [QSHORT[q].replace(" ", "\n", 1) for q in order] + ["Total\nprofit"], fontsize=9)
    ax.set_ylim(0, (starts + np.maximum(vals, 0)).max() * 1.12)
    _money(ax)
    ax.set_title("How does each quadrant add to or subtract from total profit?")
    return _finish(fig, path)


def loss_pareto(neg: pd.DataFrame, path: Path) -> Path:
    """Q: How concentrated are product-level losses?"""
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    x = neg["loss_rank"]
    ax.plot(x, neg["cumulative_share"], color=NEG, lw=2)
    for t in (0.5, 0.8):
        k = int((neg["cumulative_share"] < t).sum() + 1)
        ax.axhline(t, color=MUTED, ls=":", lw=1)
        ax.annotate(f"{k} products = {t:.0%} of losses", (k, t), textcoords="offset points",
                    xytext=(10, -14), fontsize=8.5, arrowprops=dict(arrowstyle="-", color=MUTED))
        ax.scatter([k], [t], color=NEG, zorder=3)
    _pct(ax)
    ax.set_xlabel("Loss-making products, ranked by loss amount (largest first)")
    ax.set_ylabel("Cumulative share of product losses")
    ax.set_title(f"How concentrated are product losses? ({len(neg)} loss-making products)")
    return _finish(fig, path)


def within_product_dumbbell(d: pd.DataFrame, path: Path, n: int = 15) -> Path:
    """Q: Are the biggest loss products unprofitable at full price, or only when discounted?"""
    top = d[d["profit"] < 0].nsmallest(n, "profit").iloc[::-1]
    fig, ax = plt.subplots(figsize=(10, 6.5))
    y = np.arange(len(top))
    ax.hlines(y, top["discounted_margin"].clip(-2), top["full_price_margin"], color=MUTED, lw=2)
    ax.scatter(top["full_price_margin"], y, color=POS, s=45, label="Margin on full-price lines", zorder=3)
    ax.scatter(top["discounted_margin"].clip(-2), y, color=NEG, s=45, label="Margin on discounted lines", zorder=3)
    labels = [f"{l[:48]}{'…' if len(l) > 48 else ''}  ({money_k(p)})" for l, p in zip(top["product_name"], top["profit"])]
    ax.set_yticks(y, labels, fontsize=8)
    ax.axvline(0, color="black", lw=0.8)
    _pct(ax, "x")
    ax.legend(frameon=False, fontsize=9, loc="lower left")
    ax.set_xlabel("Profit margin (discounted margin capped at -200%)")
    ax.set_title("Same product, different price: full-price vs discounted margin (largest losses)")
    return _finish(fig, path, "Products sold both at full price and discounted. Label shows total product profit.")


def money_k(v: float) -> str:
    return f"{v/1000:+.1f}k"


def driver_matrix(dm: pd.DataFrame, path: Path) -> Path:
    """Q: Which dimensions separate profitable from unprofitable sales?"""
    d = dm.sort_values("eta_squared")
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.barh(d["dimension"], d["eta_squared"], color=[NEG if "Discount" in x or "policy" in x else NEUTRAL for x in d["dimension"]])
    for i, (v, g) in enumerate(zip(d["eta_squared"], d["groups"])):
        ax.text(v + 0.01, i, f"{v:.0%}  ({g:,} groups)", va="center", fontsize=8.5)
    ax.set_xlim(0, 1.15)
    _pct(ax, "x")
    ax.set_xlabel("Share of line-margin variation lying between groups (sales-weighted eta-squared)")
    ax.set_title("Which dimensions separate profitable from unprofitable sales?")
    return _finish(fig, path, "Descriptive measure. More groups mechanically raise the score; compare with the group count.")


def policy_cell_heatmap(cells: pd.DataFrame, path: Path, top_states: int = 18) -> Path:
    """Q: Exactly which state x sub-category rules destroy profit?"""
    sales_by_state = cells.groupby("state_province")["sales"].sum()
    loss_states = cells.loc[cells["profit"] < -1000, "state_province"].unique()
    states = list(dict.fromkeys(list(sales_by_state.nlargest(top_states).index) + list(loss_states)))
    c = cells[cells["state_province"].isin(states)]
    profit = c.pivot(index="state_province", columns="sub_category", values="profit")
    rule = c.pivot(index="state_province", columns="sub_category", values="discount_rule")
    order_rows = profit.sum(axis=1).sort_values().index
    order_cols = profit.sum(axis=0).sort_values().index
    profit, rule = profit.loc[order_rows, order_cols], rule.loc[order_rows, order_cols]
    annot = rule.map(lambda v: "" if pd.isna(v) else f"{v:.0%}")
    fig, ax = plt.subplots(figsize=(13, 9))
    sns.heatmap(profit.clip(-6000, 6000), cmap="RdYlGn", center=0, annot=annot, fmt="", linewidths=0.4,
                annot_kws={"fontsize": 7}, cbar_kws={"label": "Profit (capped at ±6k)",
                                                     "format": mtick.FuncFormatter(lambda v, _: f"{v/1000:,.0f}k")}, ax=ax)
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.set_title("Which state x sub-category rules destroy profit? Colour = profit, label = discount rule")
    return _finish(fig, path, f"Top {top_states} states by revenue plus every state with a cell losing >1k. Blank = no sales.")


def rule_band_profit(summary: pd.DataFrame, path: Path) -> Path:
    """Q: How does profit change across discount rules, and how many rules lose money?"""
    s = summary.reset_index()
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    ax.bar(s["rule_band"].astype(str), s["profit"], color=np.where(s["profit"] >= 0, POS, NEG), width=0.6)
    for i, r in s.iterrows():
        ax.text(i, r["profit"] + (6000 if r["profit"] >= 0 else -6000),
                f"{int(r['loss_cells'])} of {int(r['cells'])} rules\nloss-making", ha="center",
                va="bottom" if r["profit"] >= 0 else "top", fontsize=8.5)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_ylim(s["profit"].min() - 40000, s["profit"].max() + 50000)
    _money(ax)
    ax.set_xlabel("Discount rule of the state x sub-category cell")
    ax.set_ylabel("Profit (four years)")
    ax.set_title("How does profit change across discount rules?")
    return _finish(fig, path, "A 'rule' = one state x sub-category combination, which always carries one discount level.")
