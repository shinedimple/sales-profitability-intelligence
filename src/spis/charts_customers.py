"""Phase 7 charts: customer profitability. Title = the business question answered."""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
import seaborn as sns

from .charts import ACCENT, MUTED, NEG, NEUTRAL, POS, _finish, _money, _pct
from .customer_analysis import SHORT

SCOLORS = {"C1": POS, "C2": NEG, "C3": "#4C8BD6", "C4": ACCENT, "NA": MUTED}
ORDER = ["C1", "C2", "C3", "C4", "NA"]


def customer_matrix(c: pd.DataFrame, company_margin: float, revenue_cut: float, path: Path) -> Path:
    """Q: Where does each customer sit on revenue vs margin?"""
    fig, ax = plt.subplots(figsize=(10, 6.5))
    for s in ["NA", "C3", "C4", "C1", "C2"]:
        d = c[c["cust_segment"] == s]
        ax.scatter(d["revenue"], d["profit_margin"].clip(-1.25, 0.55), s=22, alpha=0.6, color=SCOLORS[s],
                   edgecolor="white", linewidth=0.3, label=f"{SHORT[s]} (n={len(d)})")
    ax.set_xscale("log")
    ax.axvline(revenue_cut, color=NEUTRAL, ls="--", lw=1)
    ax.axhline(company_margin, color=NEUTRAL, ls="--", lw=1)
    ax.text(revenue_cut * 1.08, -1.2, f"median revenue ({revenue_cut:,.0f})", fontsize=8, color=NEUTRAL)
    ax.text(c["revenue"].min() * 1.1, company_margin + 0.03, f"company margin {company_margin:.1%}", fontsize=8,
            color=NEUTRAL, bbox=dict(facecolor="white", edgecolor="none", alpha=0.85, pad=1))
    ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    _pct(ax)
    ax.set_xlabel("Customer revenue over four years (log scale)")
    ax.set_ylabel("Customer profit margin (capped at -125%)")
    ax.legend(frameon=False, fontsize=8.5, loc="lower left")
    ax.set_title("Where does each customer sit? Revenue vs margin, four segments")
    return _finish(fig, path, "Customers with fewer than 3 orders are grey (limited history) and not classified.")


def segment_shares(s: pd.DataFrame, path: Path) -> Path:
    """Q: How are customers, revenue and profit distributed across segments?"""
    q = s.loc[ORDER]
    fig, ax = plt.subplots(figsize=(10, 4.8))
    x = np.arange(len(q))
    for i, (col, lab, color) in enumerate([("share_of_customers", "Customers", MUTED), ("share_of_revenue", "Revenue", NEUTRAL),
                                           ("share_of_profit", "Profit", POS)]):
        bars = ax.bar(x + (i - 1) * 0.26, q[col], 0.26, label=lab, color=color)
        for b, v in zip(bars, q[col]):
            ax.text(b.get_x() + b.get_width() / 2, v + (0.012 if v >= 0 else -0.012),
                    f"{v:.0%}" if abs(v) >= 0.01 else f"{v:.1%}", ha="center",
                    va="bottom" if v >= 0 else "top", fontsize=7.5)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks(x, [SHORT[i].replace(" ", "\n", 1) for i in q.index], fontsize=9)
    _pct(ax)
    ax.legend(frameon=False, ncol=3)
    ax.set_title("How are customers, revenue and profit distributed across the segments?")
    return _finish(fig, path)


def profit_decomposition(s: pd.DataFrame, path: Path) -> Path:
    """Q: Is a segment's weak profit caused by lines sold beyond break-even?"""
    q = s.loc[ORDER]
    x = np.arange(len(q))
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.bar(x, q["profit_within_be"], 0.55, color=POS, label="Profit on lines within break-even")
    ax.bar(x, q["beyond_be_profit"], 0.55, color=NEG, label="Profit on lines beyond break-even")
    ax.scatter(x, q["profit"], color="black", zorder=3, label="Net profit")
    for xi, p in zip(x, q["profit"]):
        ax.annotate(f"net {p/1000:+.1f}k", (xi, p), textcoords="offset points", xytext=(18, -3), fontsize=8.5)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks(x, [SHORT[i].replace(" ", "\n", 1) for i in q.index], fontsize=9)
    _money(ax)
    ax.legend(frameon=False, fontsize=9, loc="upper right")
    ax.set_title("Is weak customer profit explained by lines sold beyond break-even?")
    return _finish(fig, path, "Break-even = discount equal to the product's list margin (Phase 6). Decomposition, not a forecast.")


def segmentation_comparison(t: pd.DataFrame, path: Path) -> Path:
    """Q: Which segmentation best separates profitable from unprofitable customers?"""
    d = t.sort_values("eta_margin")
    y = np.arange(len(d))
    fig, ax = plt.subplots(figsize=(9.5, 4.6))
    ax.barh(y - 0.2, d["eta_margin"], 0.4, color=POS, label="Customer margin")
    ax.barh(y + 0.2, d["eta_profit"], 0.4, color=MUTED, label="Customer profit")
    ax.set_yticks(y, [f"{s} ({g} groups)" for s, g in zip(d["segmentation"], d["groups"])], fontsize=8.5)
    _pct(ax, "x")
    ax.set_xlabel("Share of variation lying between groups (eta-squared)")
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    ax.set_title("Which segmentation best separates profitable from unprofitable customers?")
    return _finish(fig, path, "Eligible customers (3+ orders). More groups mechanically raise the score (RFM has 100+ groups).")


def persistence_heatmap(p: dict, path: Path) -> Path:
    """Q: Do customers stay in the same profitability segment over time?"""
    m = p["matrix"].reindex(index=ORDER[:4], columns=ORDER[:4], fill_value=0)
    share = m.div(m.sum(axis=1), axis=0)
    annot = m.astype(str) + "\n(" + share.map(lambda v: f"{v:.0%}") + ")"
    fig, ax = plt.subplots(figsize=(7.5, 5.8))
    sns.heatmap(share, annot=annot, fmt="", cmap="Greys", vmin=0, vmax=0.6, cbar=False, linewidths=0.5, ax=ax,
                annot_kws={"fontsize": 9})
    ax.set_xticklabels([SHORT[i] for i in m.columns], rotation=20, ha="right", fontsize=8.5)
    ax.set_yticklabels([SHORT[i] for i in m.index], rotation=0, fontsize=8.5)
    ax.set_xlabel(f"Segment in {p['period_2']}")
    ax.set_ylabel(f"Segment in {p['period_1']}")
    ax.set_title("Do customers stay in the same segment over time?")
    return _finish(fig, path, f"{p['customers_in_both']} customers active in both periods. "
                              f"Same segment: {p['same_segment_share']:.0%} (random allocation would give about 25%).")


def order_history(c: pd.DataFrame, path: Path) -> Path:
    """Q: What does a typical customer's order history look like?"""
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    axes[0].hist(c["orders"], bins=np.arange(0.5, c["orders"].max() + 1.5), color=NEUTRAL, edgecolor="white")
    axes[0].set_title("Orders per customer")
    axes[0].set_xlabel("Orders (four years)")
    axes[1].hist(c["avg_order_value"].clip(upper=2500), bins=30, color=NEUTRAL, edgecolor="white")
    axes[1].set_title("Average order value per customer")
    axes[1].set_xlabel("AOV (capped at 2,500)")
    axes[2].hist(c["median_days_between_orders"].dropna().clip(upper=800), bins=30, color=NEUTRAL, edgecolor="white")
    axes[2].set_title("Median days between a customer's orders")
    axes[2].set_xlabel("Days (capped at 800)")
    for ax, col in zip(axes, ["orders", "avg_order_value", "median_days_between_orders"]):
        med = c[col].median()
        ax.axvline(med, color=ACCENT, lw=2)
        ax.text(med, ax.get_ylim()[1] * 0.92, f" median {med:,.0f}", color=ACCENT, fontsize=8.5)
        ax.set_ylabel("Customers")
    fig.suptitle("What does a typical customer's order history look like?", x=0.01, ha="left", fontweight="bold", fontsize=12)
    return _finish(fig, path, "Observed within the 2023-2026 window only (history before 2023 is not visible).")
