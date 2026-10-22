"""Phase 6 charts: discount and profitability. Title = the business question answered."""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .charts import ACCENT, MUTED, NEG, NEUTRAL, POS, _finish, _money, _pct

BAND_COLORS = ["#1D7874", "#7FB7A4", "#E39B2D", "#D9653B", "#C0392B"]


def distribution(dist: pd.DataFrame, path: Path) -> Path:
    """Q: How common is discounting, and where does the discount money go?"""
    x = [f"{v:.0%}" for v in dist.index]
    fig, ax = plt.subplots(figsize=(10, 4.6))
    i = np.arange(len(x))
    ax.bar(i - 0.27, dist["share_of_lines"], 0.27, color=MUTED, label="Share of order lines")
    ax.bar(i, dist["share_of_sales"], 0.27, color=NEUTRAL, label="Share of revenue")
    ax.bar(i + 0.27, dist["share_of_discount_given"], 0.27, color=ACCENT, label="Share of discount given away")
    ax.set_xticks(i, x)
    _pct(ax)
    ax.set_xlabel("Discount level")
    ax.legend(frameon=False, fontsize=9)
    ax.set_title("How common is discounting, and where does the discount money go?")
    return _finish(fig, path, "Discount given away = implied list value minus revenue.")


def level_panels(lv: pd.DataFrame, path: Path) -> Path:
    """Q: How do revenue, profit and margin change across discount levels?"""
    x = [f"{v:.0%}" for v in lv.index]
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.4))
    axes[0].bar(x, lv["sales"], color=NEUTRAL)
    axes[0].set_title("Revenue")
    _money(axes[0])
    axes[1].bar(x, lv["profit"], color=np.where(lv["profit"] >= 0, POS, NEG))
    axes[1].set_title("Profit")
    _money(axes[1])
    axes[2].bar(x, lv["profit_margin"], color=np.where(lv["profit_margin"] >= 0, POS, NEG))
    axes[2].set_title("Profit margin")
    _pct(axes[2])
    for ax in axes:
        ax.axhline(0, color="black", lw=0.8)
        ax.tick_params(axis="x", rotation=60, labelsize=8)
        ax.set_xlabel("Discount level")
    fig.suptitle("How do revenue, profit and margin change across discount levels?", x=0.01, ha="left",
                 fontweight="bold", fontsize=12)
    return _finish(fig, path, "Descriptive: totals per observed discount level, four dataset years.")


def subcategory_break_even(sub: pd.DataFrame, path: Path) -> Path:
    """Q: Which sub-categories are discounted beyond what their list margin can absorb?"""
    s = sub.sort_values("list_margin")
    y = np.arange(len(s))
    fig, ax = plt.subplots(figsize=(10, 6.5))
    ax.hlines(y, 0, s["list_margin"], color=MUTED, lw=6, alpha=0.6, label="List margin = break-even discount")
    ax.scatter(s["effective_discount"], y, color=np.where(s["effective_discount"] > s["list_margin"], NEG, POS),
               s=60, zorder=3, label="Effective discount actually given")
    for yi, sh in zip(y, s["share_sales_beyond_break_even"]):
        if sh > 0:
            ax.text(0.62, yi, f"{sh:.0%} of revenue beyond break-even", va="center", fontsize=8, color=NEG)
    ax.set_yticks(y, s.index)
    ax.set_xlim(0, 0.95)
    _pct(ax, "x")
    ax.legend(frameon=False, fontsize=9, loc="upper center", bbox_to_anchor=(0.45, -0.08), ncol=2)
    ax.set_title("Which sub-categories are discounted beyond what their list margin can absorb?")
    return _finish(fig, path, "Break-even discount of a product = its margin at list price (verified price arithmetic).")


def identity_scatter(d: pd.DataFrame, path: Path) -> Path:
    """Q: Does discount lower margin exactly as price arithmetic predicts?"""
    fp = d[d["discount_rate"] == 0].groupby("product_key").apply(
        lambda g: g["profit"].sum() / g["sales"].sum(), include_groups=False).rename("fp")
    x = d[d["discount_rate"] > 0].join(fp, on="product_key").dropna(subset=["fp"])
    pred = 1 - (1 - x["fp"]) / (1 - x["discount_rate"])
    fig, ax = plt.subplots(figsize=(6.5, 6))
    ax.scatter(pred.clip(-2, 0.6), x["line_margin"].clip(-2, 0.6), s=8, alpha=0.3, color=NEUTRAL)
    ax.plot([-2, 0.6], [-2, 0.6], color=NEG, lw=1, ls="--", label="Perfect agreement")
    _pct(ax)
    _pct(ax, "x")
    ax.set_xlabel("Predicted margin = 1 - (1 - full-price margin) / (1 - discount)")
    ax.set_ylabel("Actual margin of the discounted line")
    ax.legend(frameon=False)
    ax.set_title("Does discount lower margin exactly as price arithmetic predicts?")
    return _finish(fig, path, f"{len(x):,} discounted lines of products also sold at full price. Capped at -200%.")


def dimension_mix(region_mix: pd.DataFrame, segment_mix: pd.DataFrame, path: Path) -> Path:
    """Q: Do regions and segments differ in how deeply they are discounted?"""
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.4), gridspec_kw={"width_ratios": [4, 3]})
    for ax, mix, title in [(axes[0], region_mix, "Region"), (axes[1], segment_mix, "Customer segment")]:
        left = np.zeros(len(mix))
        for col, color in zip(mix.columns, BAND_COLORS):
            ax.barh(mix.index.astype(str), mix[col], left=left, color=color, label=str(col))
            left += mix[col].values
        _pct(ax, "x")
        ax.set_title(title)
        ax.set_xlim(0, 1)
    axes[1].legend(frameon=False, fontsize=8.5, bbox_to_anchor=(1.0, 1.0), loc="upper left", title="Discount band")
    fig.suptitle("Do regions and segments differ in how deeply they are discounted? (share of revenue by band)",
                 x=0.01, ha="left", fontweight="bold", fontsize=12)
    return _finish(fig, path)


def growth_index(growth: dict[str, pd.DataFrame], path: Path) -> Path:
    """Q: Did the deeply discounted part of the business grow faster?"""
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4), sharey=True)
    for ax, metric in zip(axes, ["orders", "units"]):
        t = growth[metric]
        idx = t / t.iloc[0]
        for col, color in zip(idx.columns, BAND_COLORS):
            ax.plot(idx.index, idx[col], marker="o", color=color, lw=2, label=str(col))
        ax.set_title(f"{metric.capitalize()} (index, first year = 1.0)")
        ax.set_xticks(idx.index)
        ax.axhline(1, color=MUTED, lw=0.8)
    axes[1].legend(frameon=False, fontsize=8.5, title="Discount band")
    fig.suptitle("Did the deeply discounted part of the business grow faster?", x=0.01, ha="left",
                 fontweight="bold", fontsize=12)
    return _finish(fig, path, "Bands follow the state x sub-category rule, which never changed over the four years.")


def break_even_volume(path: Path, list_margins=(0.20, 0.33, 0.45)) -> Path:
    """Q: How much extra volume would a discount need to pay for itself? (arithmetic)"""
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    for m0, color in zip(list_margins, [NEG, ACCENT, POS]):
        d = np.linspace(0, m0 - 0.01, 200)
        ax.plot(d, m0 / (m0 - d), color=color, lw=2, label=f"List margin {m0:.0%}")
        ax.axvline(m0, color=color, ls=":", lw=1)
    ax.set_ylim(1, 6)
    ax.set_xlim(0, 0.5)
    _pct(ax, "x")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}x"))
    ax.set_xlabel("Discount")
    ax.set_ylabel("Units needed vs selling at list price")
    ax.legend(frameon=False)
    ax.set_title("How much extra volume would a discount need to pay for itself?")
    return _finish(fig, path, "Arithmetic, not observed data: same profit requires m0 / (m0 - d) times the units. Dotted line = break-even.")
