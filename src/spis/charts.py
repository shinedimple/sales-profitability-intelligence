"""
Phase 4 charts. Each function draws ONE chart that answers ONE business
question; the question is the chart title. Charts take prepared DataFrames from
eda.py and never compute business logic themselves.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mtick  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402

POS, NEG, NEUTRAL, ACCENT, MUTED = "#1D7874", "#C0392B", "#5F6B7A", "#E39B2D", "#B8C0CA"
SOURCE = "Source: Superstore dataset (synthetic years), core scope: US, suspected copies excluded."


def setup_style() -> None:
    sns.set_theme(style="whitegrid", context="notebook")
    plt.rcParams.update({"figure.dpi": 110, "savefig.dpi": 150, "axes.titleweight": "bold",
                         "axes.titlesize": 12, "axes.titlelocation": "left",
                         "axes.spines.top": False, "axes.spines.right": False,
                         "font.family": "DejaVu Sans"})


def _finish(fig, path: Path, note: str = "") -> Path:
    fig.text(0.01, 0.005, f"{SOURCE} {note}".strip(), fontsize=7.5, color=NEUTRAL)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def _money(ax, axis="y"):
    fmt = mtick.FuncFormatter(lambda v, _: f"{v/1000:,.0f}k")
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


def _pct(ax, axis="y", decimals=0):
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(mtick.PercentFormatter(1, decimals=decimals))


# --------------------------------------------------------------------------
def monthly_trend(monthly: pd.DataFrame, path: Path) -> Path:
    """Q: Is revenue growing, and does profit follow revenue month by month?"""
    fig, axes = plt.subplots(2, 1, figsize=(11, 6.5), sharex=True)
    x = monthly.index
    axes[0].bar(x, monthly["sales"], width=20, color=MUTED, label="Monthly revenue")
    axes[0].plot(x, monthly["sales_rolling_12m"] / 12, color=POS, lw=2, label="12-month average")
    axes[0].set_title("Is revenue growing? Monthly revenue with 12-month average")
    axes[0].legend(loc="upper left", frameon=False)
    _money(axes[0])
    colors = np.where(monthly["profit"] >= 0, POS, NEG)
    axes[1].bar(x, monthly["profit"], width=20, color=colors)
    ax2 = axes[1].twinx()
    ax2.plot(x, monthly["margin_rolling_12m"], color=ACCENT, lw=2, label="Rolling 12-month margin")
    ax2.set_ylim(0, 0.2)
    _pct(ax2)
    ax2.grid(False)
    ax2.legend(loc="upper left", frameon=False)
    axes[1].set_title("Does profit follow? Monthly profit and rolling 12-month margin")
    _money(axes[1])
    return _finish(fig, path)


def growth_decomposition(yearly: pd.DataFrame, path: Path) -> Path:
    """Q: Is growth coming from more orders or from bigger orders?"""
    y = yearly.dropna(subset=["growth_from_orders"])
    fig, ax = plt.subplots(figsize=(8, 4.5))
    idx = np.arange(len(y))
    ax.bar(idx - 0.18, y["growth_from_orders"], width=0.36, color=POS, label="From number of orders")
    ax.bar(idx + 0.18, y["growth_from_aov"], width=0.36, color=ACCENT, label="From average order value")
    ax.scatter(idx, np.log1p(y["sales_yoy"]), color="black", zorder=3, label="Total revenue growth")
    top = max(y["growth_from_orders"].max(), y["growth_from_aov"].max(), np.log1p(y["sales_yoy"]).max())
    for i, v in enumerate(y["sales_yoy"]):
        ax.text(i, top + 0.03, f"Revenue {v:+.1%}", ha="center", fontsize=9, fontweight="bold")
    ax.set_ylim(top=top + 0.07)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks(idx, [str(i) for i in y.index])
    ax.set_title("Where does revenue growth come from? Orders vs order value")
    ax.set_ylabel("Log growth contribution")
    ax.legend(frameon=False, fontsize=9, loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=3)
    return _finish(fig, path, "Log growth: orders + AOV contributions add up exactly to revenue growth.")


def subcategory_profit(sub: pd.DataFrame, path: Path) -> Path:
    """Q: Which sub-categories create profit and which destroy it?"""
    s = sub.reset_index().sort_values("profit")
    fig, ax = plt.subplots(figsize=(9, 6.5))
    ax.barh(s["sub_category"], s["profit"], color=np.where(s["profit"] >= 0, POS, NEG))
    for i, (p, m) in enumerate(zip(s["profit"], s["profit_margin"])):
        ax.text(p + (800 if p >= 0 else -800), i, f"{m:.0%}", va="center",
                ha="left" if p >= 0 else "right", fontsize=8.5, color=NEUTRAL)
    ax.axvline(0, color="black", lw=0.8)
    _money(ax, "x")
    ax.set_title("Where is profit created and destroyed? Profit by sub-category (label = margin)")
    return _finish(fig, path)


def subcategory_portfolio(quad: pd.DataFrame, company_margin: float, path: Path) -> Path:
    """Q: Which sub-categories are high-sales/low-margin vs low-sales/high-margin?"""
    q = quad.reset_index()
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.scatter(q["sales"], q["profit_margin"], s=60, color=np.where(q["profit_margin"] >= company_margin, POS, NEG))
    for _, r in q.iterrows():
        ax.annotate(r["sub_category"], (r["sales"], r["profit_margin"]), textcoords="offset points",
                    xytext=(5, 4), fontsize=8.5)
    ax.axhline(company_margin, color=NEUTRAL, ls="--", lw=1)
    ax.axvline(q["sales"].median(), color=NEUTRAL, ls="--", lw=1)
    ax.text(q["sales"].min(), company_margin - 0.025, "company margin", ha="left", fontsize=8, color=NEUTRAL)
    _money(ax, "x")
    _pct(ax)
    ax.set_xlabel("Revenue (4 years)")
    ax.set_ylabel("Profit margin")
    ax.set_title("Portfolio: revenue vs margin by sub-category (lines = median revenue, company margin)")
    return _finish(fig, path)


def discount_margin(levels: pd.DataFrame, path: Path) -> Path:
    """Q: At what discount level do order lines stop being profitable?"""
    d = levels.reset_index()
    labels = [f"{r:.0%}" for r in d["discount_rate"]]
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.bar(labels, d["profit_margin"], color=np.where(d["profit_margin"] >= 0, POS, NEG))
    for i, (m, n) in enumerate(zip(d["profit_margin"], d["lines"])):
        ax.text(i, m + (0.04 if m >= 0 else -0.04), f"n={n:,}", ha="center",
                va="bottom" if m >= 0 else "top", fontsize=8, color=NEUTRAL)
    ax.axhline(0, color="black", lw=0.8)
    _pct(ax)
    ax.set_ylim(min(d["profit_margin"]) - 0.25, max(d["profit_margin"]) + 0.15)
    ax.set_xlabel("Discount level")
    ax.set_ylabel("Profit margin (ratio of sums)")
    ax.set_title("At what discount does profitability break? Margin by discount level (n = order lines)")
    return _finish(fig, path)


def discount_heatmap(margin: pd.DataFrame, lines: pd.DataFrame, path: Path) -> Path:
    """Q: Which sub-categories lose money even at low discount levels?"""
    order = margin["No discount"].sort_values().index
    m, n = margin.loc[order], lines.loc[order]
    annot = m.map(lambda v: "" if pd.isna(v) else f"{v:.0%}") + n.map(lambda v: "" if pd.isna(v) else f"\n(n={int(v)})")
    fig, ax = plt.subplots(figsize=(9, 8))
    sns.heatmap(m.clip(-1, 0.5), annot=annot, fmt="", cmap="RdYlGn", center=0, vmin=-1, vmax=0.5,
                linewidths=0.5, cbar_kws={"format": mtick.PercentFormatter(1)}, ax=ax,
                annot_kws={"fontsize": 7.5})
    ax.set_xlabel("Discount band")
    ax.set_ylabel("")
    ax.set_title("Which sub-categories lose money even at low discounts? Margin by band")
    return _finish(fig, path, "Blank = combination never occurs. Colour scale capped at -100%.")


def region_mix_adjusted(adj: pd.DataFrame, company_margin: float, path: Path) -> Path:
    """Q: Is a region's margin explained by its discount mix?"""
    a = adj.reset_index().sort_values("profit_margin")
    idx = np.arange(len(a))
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(idx - 0.18, a["profit_margin"], width=0.36, color=MUTED, label="Actual margin")
    ax.bar(idx + 0.18, a["mix_adjusted_margin"], width=0.36, color=POS,
           label="Margin at company-average discount mix")
    ax.axhline(company_margin, color=NEUTRAL, ls="--", lw=1, label="Company margin")
    ax.set_xticks(idx, [f"{r}\n(discount {d:.0%})" for r, d in zip(a[a.columns[0]], a["effective_discount"])])
    _pct(ax)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    ax.set_title("Is regional margin explained by discount mix? Actual vs mix-adjusted margin")
    return _finish(fig, path, "Mix-adjusted = region's own margin in each discount band, weighted by company band mix.")


def state_discount_vs_margin(states: pd.DataFrame, path: Path) -> Path:
    """Q: Do loss-making states share a common pattern of heavy discounting?"""
    s = states[states["volume_flag"] == "OK"]
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.scatter(s["effective_discount"], s["profit_margin"], s=s["sales"] / 1500,
               color=np.where(s["profit"] >= 0, POS, NEG), alpha=0.7, edgecolor="white")
    offsets = [(10, 10), (10, -14), (-75, 10), (-75, -14)]
    loss = s[s["profit"] < -10000].sort_values("profit")
    big = s[(s["sales"] > 100000) & ~s.index.isin(loss.index)].sort_values("sales", ascending=False)
    for group in (loss, big):
        for k, (_, r) in enumerate(group.iterrows()):
            ax.annotate(r["state_province"], (r["effective_discount"], r["profit_margin"]),
                        textcoords="offset points", xytext=offsets[k % 4], fontsize=8.5,
                        arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.6))
    ax.axhline(0, color="black", lw=0.8)
    _pct(ax)
    _pct(ax, "x")
    ax.set_xlabel("Effective discount rate (discount given / list value)")
    ax.set_ylabel("Profit margin")
    ax.set_title("Do loss-making states share heavy discounting? (bubble = revenue, states with 30+ orders)")
    return _finish(fig, path)


def customer_lorenz(sales_pts: pd.DataFrame, profit_pts: pd.DataFrame, path: Path) -> Path:
    """Q: How dependent is the business on its best customers?"""
    fig, ax = plt.subplots(figsize=(7.5, 5))
    ax.plot(sales_pts["customer_share"], sales_pts["cumulative_share"], color=NEUTRAL, lw=2, label="Revenue")
    ax.plot(profit_pts["customer_share"], profit_pts["cumulative_share"], color=POS, lw=2, label="Profit")
    ax.plot([0, 1], [0, 1], color=MUTED, ls=":", label="Equal contribution")
    ax.axhline(1, color="black", lw=0.6)
    _pct(ax)
    _pct(ax, "x")
    ax.set_xlabel("Customers, ranked from most to least valuable")
    ax.set_ylabel("Cumulative share of total")
    ax.legend(frameon=False)
    ax.set_title("How concentrated are revenue and profit across customers?")
    return _finish(fig, path, "Profit curve exceeds 100% because the least valuable customers lose money.")


def customer_discount_vs_margin(customers: pd.DataFrame, path: Path) -> Path:
    """Q: Are unprofitable customers the ones who receive deep discounts?"""
    c = customers
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.scatter(c["effective_discount"], c["profit_margin"].clip(-1.5, 0.6), s=c["sales"] / 250,
               color=np.where(c["profit"] >= 0, POS, NEG), alpha=0.5, edgecolor="white")
    ax.axhline(0, color="black", lw=0.8)
    _pct(ax)
    _pct(ax, "x")
    ax.set_xlabel("Customer's effective discount rate (4 years)")
    ax.set_ylabel("Customer profit margin (capped at -150%)")
    ax.set_title("Are unprofitable customers the deep-discount customers? (bubble = revenue)")
    return _finish(fig, path)
