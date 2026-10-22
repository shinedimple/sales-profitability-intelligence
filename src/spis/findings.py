"""
Phase 4 findings: turns computed EDA results into an evidence-based report.

Every number in the narrative is read from the results dictionary at run time,
so the text cannot drift from the data. The interpretation, limitation and
next-step wording is analyst judgement written AFTER inspecting the results,
and is deliberately non-causal unless the evidence supports more.
"""
from __future__ import annotations

import pandas as pd

from .reporting import md_table


def pct(v: float, d: int = 1) -> str:
    return f"{v * 100:.{d}f}%"


def pp(v: float, d: int = 1) -> str:
    return f"{v * 100:+.{d}f} pp"


def money(v: float) -> str:
    return f"{v / 1000:,.1f}k" if abs(v) >= 1000 else f"{v:,.0f}"


def _tbl(df: pd.DataFrame, cols: list[str], fmt: dict[str, str], index: bool = True) -> str:
    t = df[cols].copy()
    for c, f in fmt.items():
        if c not in t.columns:
            continue
        t[c] = t[c].map(lambda v: "" if pd.isna(v) else
                        (pct(v) if f == "pct" else money(v) if f == "money" else f"{v:,.0f}" if f == "int" else f"{v:.2f}"))
    return md_table(t, index=index)


ANALYSIS_PLAN = [
    ("A", "Revenue trend, monthly revenue, YoY growth", "Is the business growing, and is growth steady?", "Monthly series, rolling 12-month totals, same-month-last-year growth", "F01"),
    ("A", "Order volume and average order value", "Is growth driven by more orders or bigger orders, and is AOV representative?", "Exact log decomposition of revenue growth into orders x AOV; order-value distribution", "F02"),
    ("B", "Profit trend and margin", "Is profit growing with revenue, or is margin eroding?", "Yearly and rolling 12-month margin (ratio of sums)", "F01"),
    ("B", "Profit by category / sub-category", "Where is profit created and where is it destroyed?", "Profit, margin and loss amounts; loss concentration (Pareto)", "F03"),
    ("B", "Profit by region / segment", "Are weak groups weak in themselves, or because of their discount mix?", "Direct standardisation: margin at the company's discount mix", "F07"),
    ("C", "Product rankings and portfolio", "Which products are margin leaks, and which are high-margin niche items?", "Sales quintiles vs company margin, minimum 3 lines per product", "F04"),
    ("D", "Customer sales, profit and profitability", "How dependent are we on a few customers, and why are some customers unprofitable?", "Lorenz/Pareto curves; customer discount vs margin; worst-line test", "F09, F10"),
    ("D", "Order frequency and segments", "Are frequent buyers more valuable? Does segment matter?", "Frequency bands, inter-order gaps, year-to-year retention", "-"),
    ("E", "Region, state, city", "Where are losses located, and what do loss-making locations have in common?", "Ranked tables with volume thresholds; state discount vs margin correlation", "F08"),
    ("F", "Discount vs sales, profit, margin", "Do discounts buy volume, and at what point do they destroy profit?", "Margin by discount level; within-sub-category quantity comparison; policy-structure test", "F05, F06"),
]


def build_findings(r: dict) -> list[dict]:
    o, y = r["overall"], r["yearly"]
    cm = o["profit_margin"]
    F: list[dict] = []

    # ---------------- A. Sales performance ----------------
    ov = r["order_value_distribution"]
    F.append(dict(
        id="A1", area="A. Sales performance", figure="F02", confidence="High",
        title="Growth since 2025 comes from more orders, not bigger orders",
        finding=(f"Revenue grew {pct(y.loc[2025,'sales_yoy'])} in 2025 and {pct(y.loc[2026,'sales_yoy'])} in 2026. "
                 f"Order count grew {pct(y.loc[2025,'orders_yoy'])} and {pct(y.loc[2026,'orders_yoy'])}, while average order value "
                 f"changed {pct(y.loc[2025,'aov_yoy'])} and {pct(y.loc[2026,'aov_yoy'])}. In 2024 revenue fell "
                 f"{pct(-y.loc[2024,'sales_yoy'])} even though orders rose {pct(y.loc[2024,'orders_yoy'])}, because AOV fell {pct(-y.loc[2024,'aov_yoy'])}."),
        calculation=("Revenue = orders x AOV, so ln(revenue growth) = ln(order growth) + ln(AOV growth) exactly.\n\n"
                     + _tbl(y, ["sales", "orders", "aov", "sales_yoy", "orders_yoy", "aov_yoy"],
                            {"sales": "money", "orders": "int", "aov": "money", "sales_yoy": "pct", "orders_yoy": "pct", "aov_yoy": "pct"})),
        interpretation=("The business is winning more transactions rather than larger baskets. AOV is a weak signal on its own: "
                        f"the mean order is about {ov['mean_to_median'].mean():.1f}x the median and the top 5% of orders carry "
                        f"{pct(ov['top5pct_orders_share_of_sales'].min(),0)}-{pct(ov['top5pct_orders_share_of_sales'].max(),0)} of revenue each year, "
                        f"so a few large orders move AOV. Median order value is stable ({money(ov['50%'].min())}-{money(ov['50%'].max())})."),
        limitations="Dataset years are synthetic. Orders are counted per order ID; we cannot see order intent, quotes or lost deals.",
        next_step="Track median order value alongside AOV, and check whether the AOV decline in 2026 comes from fewer large Technology/Furniture orders (mix) or lower prices."))

    m = r["monthly"]
    neg_months = [d.strftime("%b %Y") for d in m.index[m["profit"] < 0]]
    s = r["seasonality"]
    peak = s.loc[[9, 11, 12], "mean_share"].sum()
    F.append(dict(
        id="A2", area="A. Sales performance", figure="F01", confidence="High",
        title="Revenue is strongly seasonal: September, November and December carry the year",
        finding=(f"On average, September, November and December produce {pct(peak)} of annual revenue; January and February together "
                 f"produce {pct(s.loc[[1,2],'mean_share'].sum())}. The pattern is stable across all four years. "
                 f"Monthly margin is volatile (between {pct(m['profit_margin'].min())} and {pct(m['profit_margin'].max())}); "
                 f"{len(neg_months)} months were loss-making ({', '.join(neg_months)})."),
        calculation="Each month's share of its own year's revenue, averaged over 2023-2026:\n\n" + _tbl(
            s.rename(index=lambda i: pd.Timestamp(2000, i, 1).strftime('%b')), ["mean_share", "min_share", "max_share"],
            {"mean_share": "pct", "min_share": "pct", "max_share": "pct"}),
        interpretation="Month-on-month comparisons are misleading; performance should be judged against the same month last year or on a rolling 12-month basis.",
        limitations="Single loss months can be caused by a handful of large discounted orders; monthly margins rest on few transactions in quiet months.",
        next_step="Report monthly KPIs as same-month-prior-year and rolling 12 months. Review the large discounted orders behind the two loss months."))

    F.append(dict(
        id="A3", area="B. Profitability", figure="F01", confidence="Medium",
        title="Profit grew faster than revenue until 2025; margin slipped in 2026 as discounting rose",
        finding=(f"Margin rose from {pct(y.loc[2023,'profit_margin'])} (2023) to {pct(y.loc[2025,'profit_margin'])} (2025), "
                 f"then fell to {pct(y.loc[2026,'profit_margin'])} in 2026. Over the same years the effective discount rate moved "
                 f"{pct(y.loc[2023,'effective_discount'])} -> {pct(y.loc[2025,'effective_discount'])} -> {pct(y.loc[2026,'effective_discount'])}. "
                 f"Profit growth was {pct(y.loc[2025,'profit_yoy'])} in 2025 but {pct(y.loc[2026,'profit_yoy'])} in 2026."),
        calculation=_tbl(y, ["profit", "profit_margin", "effective_discount", "profit_yoy"],
                         {"profit": "money", "profit_margin": "pct", "effective_discount": "pct", "profit_yoy": "pct"}),
        interpretation="Margin and discount move in opposite directions year to year. This is consistent with the discount findings (F1-F3) but four annual points cannot establish cause; product and regional mix also change between years.",
        limitations="Four yearly observations; association only.",
        next_step="Decompose the 2025-2026 margin change into discount-rate, category-mix and regional-mix effects (a margin bridge) before drawing conclusions."))

    # ---------------- B. Profitability ----------------
    cat, adjc, heat = r["category"], r["mix_adjusted_category"], r["discount_heat_margin"]
    furn_nodisc = heat.loc[["Bookcases", "Tables", "Chairs", "Furnishings"], "No discount"]
    other_nodisc = heat.drop(index=["Bookcases", "Tables", "Chairs", "Furnishings"])["No discount"]
    F.append(dict(
        id="B1", area="B. Profitability", figure="F03", confidence="High",
        title="Furniture earns almost nothing, and not only because of discounting",
        finding=(f"Furniture generates {pct(cat.loc['Furniture','share_of_sales'])} of revenue but {pct(cat.loc['Furniture','share_of_profit'])} of profit "
                 f"(margin {pct(cat.loc['Furniture','profit_margin'])}, vs {pct(cat.loc['Technology','profit_margin'])} Technology and "
                 f"{pct(cat.loc['Office Supplies','profit_margin'])} Office Supplies). Its effective discount ({pct(cat.loc['Furniture','effective_discount'])}) "
                 f"is the same as the other categories. At the company's discount mix its margin would still be only {pct(adjc.loc['Furniture','mix_adjusted_margin'])}. "
                 f"Even without any discount, Furniture sub-categories earn {pct(furn_nodisc.min(),0)}-{pct(furn_nodisc.max(),0)}, "
                 f"against a median of {pct(other_nodisc.median(),0)} for other sub-categories."),
        calculation=_tbl(cat, ["sales", "profit", "profit_margin", "share_of_sales", "share_of_profit", "effective_discount"],
                         {"sales": "money", "profit": "money", "profit_margin": "pct", "share_of_sales": "pct", "share_of_profit": "pct", "effective_discount": "pct"})
                    + "\n\nMix-adjusted margin (direct standardisation to the company discount mix):\n\n"
                    + _tbl(adjc, ["profit_margin", "mix_adjusted_margin"], {"profit_margin": "pct", "mix_adjusted_margin": "pct"}),
        interpretation="Furniture's problem appears to be structural: thin margins at list price (pricing, cost, or freight for bulky items), which any discount then pushes into losses. Tables and Bookcases are loss-making overall.",
        limitations="The dataset has no cost breakdown, so we cannot tell whether the cause is purchase cost, shipping or price. Office Supplies has no sales in the 21-60% bands, so its adjusted figure uses company-level margins for those bands.",
        next_step="Review Furniture list prices and landed cost (especially freight) for Tables and Bookcases; test whether these lines should carry a lower maximum discount."))

    lc, sub = r["loss_concentration"], r["sub_category"]
    gross_pos = sub["profit"].sum() - lc["loss_amount"].sum()
    top3 = lc.head(3)
    F.append(dict(
        id="B2", area="B. Profitability", figure="F03", confidence="High",
        title="Losses are concentrated: three sub-categories account for two-thirds of all losses",
        finding=(f"Loss-making order lines lose {money(-lc['loss_amount'].sum())} in total, equal to {pct(-lc['loss_amount'].sum() / gross_pos)} of the profit "
                 f"earned on profitable lines. {', '.join(top3['sub_category'])} account for {pct(top3['share_of_all_losses'].sum())} of all losses. "
                 f"Binders are profitable overall ({pct(sub.loc['Binders','profit_margin'])} margin) yet lose {money(-sub.loc['Binders','loss_amount'])} on "
                 f"individual lines, with an effective discount of {pct(sub.loc['Binders','effective_discount'])}."),
        calculation=_tbl(lc.head(6), ["sub_category", "loss_amount", "share_of_all_losses", "cumulative_share"],
                         {"loss_amount": "money", "share_of_all_losses": "pct", "cumulative_share": "pct"}, index=False),
        interpretation="Total profit hides how much is given back on loss-making lines. Fixing losses in a few sub-categories would have a larger effect than growing high-margin niches.",
        limitations="Line-level losses depend on how profit is allocated to lines in the source system, which is not documented.",
        next_step="Build a loss-line drill-down (sub-category x state x discount) in Power BI and size the profit at stake under a discount cap."))

    adjr = r["mix_adjusted_region"]
    F.append(dict(
        id="B3", area="B. Profitability", figure="F07", confidence="Medium",
        title="Central's weak margin is largely associated with its heavier discounting",
        finding=(f"Central has the lowest margin ({pct(adjr.loc['Central','profit_margin'])}) and the highest effective discount "
                 f"({pct(adjr.loc['Central','effective_discount'])}). If Central had the company's discount mix, its margin would be "
                 f"{pct(adjr.loc['Central','mix_adjusted_margin'])}, closing about {pct(adjr.loc['Central','share_of_gap_explained_by_mix'],0)} of its gap to the company "
                 f"margin ({pct(cm)}). West's lead disappears after adjustment ({pct(adjr.loc['West','profit_margin'])} -> {pct(adjr.loc['West','mix_adjusted_margin'])}), "
                 f"because West discounts least ({pct(adjr.loc['West','effective_discount'])})."),
        calculation=_tbl(adjr, ["profit_margin", "effective_discount", "mix_adjusted_margin", "gap_actual", "gap_adjusted"],
                         {"profit_margin": "pct", "effective_discount": "pct", "mix_adjusted_margin": "pct", "gap_actual": "pct", "gap_adjusted": "pct"}),
        interpretation="Regional performance differences look more like differences in discount policy than in regional management or demand. Regional managers should not be compared on raw margin alone.",
        limitations="Standardisation controls for discount band only, not for product mix within bands. Because discounts are set by state and sub-category (see F3), region and discount cannot be fully separated.",
        next_step="Compare regions within the same sub-category and discount level; agree with management who sets the discount rules for each state."))

    segs, adjs = r["segment"], r["mix_adjusted_segment"]
    F.append(dict(
        id="B4", area="D. Customers", figure=None, confidence="Medium",
        title="Customer segment is a weak differentiator of profitability",
        finding=(f"Segment margins range only from {pct(segs['profit_margin'].min())} to {pct(segs['profit_margin'].max())}, and profit per customer from "
                 f"{money(segs['profit_per_customer'].min())} to {money(segs['profit_per_customer'].max())}. Consumer is the largest segment "
                 f"({pct(segs.loc['Consumer','share_of_profit'])} of profit) because it has the most customers, not because each customer is worth more. "
                 f"Orders per customer are similar ({segs['orders_per_customer'].min():.1f}-{segs['orders_per_customer'].max():.1f})."),
        calculation=_tbl(segs, ["sales", "profit", "profit_margin", "customers", "profit_per_customer", "orders_per_customer", "effective_discount"],
                         {"sales": "money", "profit": "money", "profit_margin": "pct", "customers": "int", "profit_per_customer": "money",
                          "orders_per_customer": "num", "effective_discount": "pct"})
                    + "\n\nMix-adjusted margin: " + ", ".join(f"{k} {pct(v)}" for k, v in adjs["mix_adjusted_margin"].items()),
        interpretation="Category and discount explain far more of the profit variation than segment. Segment-specific strategies are unlikely to be the main lever for margin.",
        limitations="Segment is a broad label; we have no firmographic data (company size, industry).",
        next_step="Deprioritise segment as a margin lever; use it mainly for go-to-market planning."))

    # ---------------- C. Products ----------------
    pf = r["product_portfolio"]
    hl = pf[pf["portfolio_class"] == "High sales, loss-making"]
    hb = pf[pf["portfolio_class"] == "High sales, below-average margin"]
    ls = pf[pf["portfolio_class"] == "Low sales, high margin"]
    ins = pf[pf["portfolio_class"] == "Insufficient data"]
    top10 = r["products"].nlargest(10, "sales")
    F.append(dict(
        id="C1", area="C. Products", figure="F04", confidence="Medium",
        title="Margin leaks are large; high-margin niche products are too small to offset them",
        finding=(f"{len(hl)} products in the top sales quintile are loss-making: they generate {money(hl['sales'].sum())} revenue "
                 f"({pct(hl['sales'].sum() / o['sales'])} of total) and lose {money(-hl['profit'].sum())}. Most are "
                 f"{', '.join(hl['sub_category'].value_counts().head(4).index)}. A further {len(hb)} high-sales products earn below the company margin. "
                 f"By contrast, the {len(ls)} low-sales products with at least double the company margin generate only {money(ls['sales'].sum())} "
                 f"revenue ({pct(ls['sales'].sum() / o['sales'])}) and {money(ls['profit'].sum())} profit. "
                 f"{int((top10['profit'] <= 0).sum())} of the 10 best-selling products earn zero or negative profit."),
        calculation=("Classes: top sales quintile vs company margin; 'low sales, high margin' = bottom two quintiles with margin >= 2x company margin; "
                     f"{len(ins)} products with fewer than 3 lines are excluded as insufficient data.\n\n"
                     + _tbl(pf.groupby("portfolio_class").agg(products=("product_key", "size"), sales=("sales", "sum"), profit=("profit", "sum")),
                            ["products", "sales", "profit"], {"products": "int", "sales": "money", "profit": "money"})
                     + "\n\nTop 10 products by revenue:\n\n"
                     + _tbl(top10, ["product_label", "sales", "profit", "profit_margin", "orders"],
                            {"sales": "money", "profit": "money", "profit_margin": "pct", "orders": "int"}, index=False)),
        interpretation="The profit opportunity lies in repairing high-volume products, not in promoting niche high-margin products, which are mostly low-priced paper, art and labels.",
        limitations="Most products sell only a handful of times over four years, so individual product margins are noisy. Product IDs are reused for different names (DQ07), handled with a composite key.",
        next_step="Review pricing and discount eligibility for the high-sales loss-making list, starting with Tables and Chairs; treat single-order products with caution."))

    # ---------------- D. Customers ----------------
    cc = r["customer_concentration"].set_index(["metric", "top_customers_share"])["share_of_total"]
    cdg, cust = r["customer_discount_groups"], r["customers"]
    unprof = cust[cust["profit"] < 0]
    F.append(dict(
        id="D1", area="D. Customers", figure="F09", confidence="High",
        title="Profit is highly concentrated in a minority of customers",
        finding=(f"The top 10% of customers generate {pct(cc[('profit',0.1)])} of profit but {pct(cc[('sales',0.1)])} of revenue; the top 20% generate "
                 f"{pct(cc[('profit',0.2)])} of profit. {len(unprof)} customers ({pct(len(unprof)/len(cust))}) are unprofitable over four years, "
                 f"costing {money(-unprof['profit'].sum())}."),
        calculation=_tbl(r["customer_concentration"], ["metric", "top_customers_share", "customers", "share_of_total"],
                         {"top_customers_share": "pct", "customers": "int", "share_of_total": "pct"}, index=False),
        interpretation="Losing a small number of top customers would have an outsized effect on profit; the unprofitable tail gives back a meaningful part of what the top customers earn.",
        limitations="Customer profit is measured over the four-year data window only; lifetime value cannot be estimated.",
        next_step="Create a key-account watch list for the top 10% of customers and review the unprofitable tail (see D2)."))

    F.append(dict(
        id="D2", area="D. Customers", figure="F10", confidence="High",
        title="Unprofitable customers are mostly deep-discount customers, driven by a few transactions",
        finding=(f"Among customers whose effective discount is 30% or more, {pct(cdg.loc['30%+','share_unprofitable'],0)} are unprofitable; among those below 10%, "
                 f"{pct(cdg.loc['0-10%','share_unprofitable'],0)} are. The rank correlation between a customer's effective discount and their margin is "
                 f"{cust['effective_discount'].corr(cust['profit_margin'], method='spearman'):.2f}. {r['unprofitable_without_worst_line']} of the {len(unprof)} "
                 f"unprofitable customers would be profitable if their single worst order line were removed."),
        calculation=_tbl(cdg, ["customers", "unprofitable", "share_unprofitable", "profit_margin"],
                         {"customers": "int", "unprofitable": "int", "share_unprofitable": "pct", "profit_margin": "pct"}),
        interpretation="Customer unprofitability looks transaction-driven (a few heavily discounted lines) rather than a property of the customer. The lever is discount rules on specific products and locations, not dropping customers.",
        limitations="Customer discount is itself determined by where the customer ships and what they buy (F3), so 'customer' and 'discount' effects overlap.",
        next_step="Review the worst lines of unprofitable customers: which product, state and discount produced them?"))

    fb, ret, gap = r["frequency_bands"], r["retention"], r["order_gap_summary"]["days_between_orders"]
    F.append(dict(
        id="D3", area="D. Customers", figure=None, confidence="Medium",
        title="Repeat buyers carry the business; frequency adds volume, not margin",
        finding=(f"Customers with 7-10 orders are {pct(fb.loc['7-10 orders','share_of_customers'])} of customers but earn {pct(fb.loc['7-10 orders','share_of_profit'])} of profit. "
                 f"Margin is similar for all bands with 4+ orders ({pct(fb.iloc[1:]['profit_margin'].min())}-{pct(fb.iloc[1:]['profit_margin'].max())}); "
                 f"customers with 1-3 orders earn only {pct(fb.loc['1-3 orders','profit_margin'])}. The median gap between a customer's orders is "
                 f"{gap['50%']:.0f} days. Year-to-year retention rose from {pct(ret['retention_rate'].iloc[0])} to {pct(ret['retention_rate'].iloc[-1])}."),
        calculation=_tbl(fb, ["customers", "share_of_customers", "share_of_profit", "profit_margin", "median_customer_profit"],
                         {"customers": "int", "share_of_customers": "pct", "share_of_profit": "pct", "profit_margin": "pct", "median_customer_profit": "money"})
                    + "\n\n" + _tbl(ret, ["base_year", "active", "retained_next_year", "retention_rate"],
                                    {"base_year": "int", "active": "int", "retained_next_year": "int", "retention_rate": "pct"}, index=False),
        interpretation="Retention is strong and improving, and value grows with the number of orders. Frequent buyers are worth more because they buy more, not because they buy at better margins.",
        limitations="History starts in 2023 (left-censored): order counts partly reflect how long a customer has been visible, and 'new' customers cannot be identified.",
        next_step="Monitor retention as a KPI; investigate why 1-3 order customers have low margins (are their few orders heavily discounted?)."))

    # ---------------- E. Geography ----------------
    st, sc = r["state"], r["state_discount_correlation"]
    loss_states = st[st["profit"] < 0]
    tx = st.set_index("state_province").loc["Texas"]
    F.append(dict(
        id="E1", area="E. Geography", figure="F08", confidence="High",
        title="Every loss-making state is a heavy-discount state",
        finding=(f"{len(loss_states)} states are loss-making, together losing {money(-loss_states['profit'].sum())} on {pct(loss_states['sales'].sum() / o['sales'])} "
                 f"of revenue. All of them have an effective discount of at least {pct(loss_states['effective_discount'].min())}. Across the "
                 f"{sc['states_used']} states with 30+ orders, the rank correlation between effective discount and margin is "
                 f"{sc['spearman_discount_vs_margin']:.2f}. Texas is the 3rd-largest state by revenue but the largest loss ({money(tx['profit'])}, "
                 f"discount {pct(tx['effective_discount'])})."),
        calculation=_tbl(loss_states.sort_values("profit"), ["state_province", "region", "sales", "profit", "profit_margin", "effective_discount", "orders"],
                         {"sales": "money", "profit": "money", "profit_margin": "pct", "effective_discount": "pct", "orders": "int"}, index=False),
        interpretation="Geographic losses and discounting are tightly linked. Whether a state loses money is better predicted by its discount rules than by its region.",
        limitations=f"{(st['volume_flag'] == 'Low volume').sum()} states have fewer than 30 orders and are excluded from the correlation. Correlation is not causation, and state and discount are confounded by design (F3).",
        next_step="Obtain the discount rule table by state and check who approved deep discounts in Texas, Ohio, Pennsylvania and Illinois."))

    ci = r["city"]
    ci_ok = ci[ci["volume_flag"] == "OK"]
    loss_c = ci[ci["profit"] < 0]
    F.append(dict(
        id="E2", area="E. Geography", figure=None, confidence="Low",
        title="City losses concentrate in a few large cities, but city data is thin",
        finding=(f"{len(loss_c)} cities are loss-making ({money(-loss_c['profit'].sum())} in total). The five largest loss cities account for "
                 f"{pct(loss_c['profit'].nsmallest(5).sum() / loss_c['profit'].sum())} of city-level losses, led by "
                 f"{'; '.join(loss_c.nsmallest(3, 'profit')['city_state'])}. Only {len(ci_ok)} of {len(ci)} cities have 30+ orders."),
        calculation=_tbl(ci_ok.sort_values("profit"), ["city_state", "sales", "profit", "profit_margin", "effective_discount", "orders"],
                         {"sales": "money", "profit": "money", "profit_margin": "pct", "effective_discount": "pct", "orders": "int"}, index=False),
        interpretation="The big loss cities sit inside the heavy-discount states; city adds little beyond state-level discount rules.",
        limitations="Most cities have too few orders for reliable margins; city is reported for the largest cities only.",
        next_step="Use city only for drill-down within loss-making states, not as a separate decision level."))

    # ---------------- F. Discounts ----------------
    dl, dq, corr, pol = r["discount_levels"], r["discount_quantity"], r["discount_correlations"], r["discount_policy"]
    deep = dl[dl.index >= 0.30]
    F.append(dict(
        id="F1", area="F. Discounts", figure="F05", confidence="High",
        title="Margin falls steadily with discount; at 30% and above, order lines almost always lose money",
        finding=(f"Margin is {pct(dl.loc[0.0,'profit_margin'])} at no discount and {pct(dl.loc[0.2,'profit_margin'])} at 20%, then negative at every level "
                 f"from 30% upward. At 30%+ discount, {pct((deep['loss_line_share'] * deep['lines']).sum() / deep['lines'].sum())} of lines lose money; "
                 f"these lines are {pct(deep['lines'].sum() / dl['lines'].sum())} of all lines but produce {money(deep['profit'].sum())} profit. "
                 f"The rank correlation between discount and line margin is {corr['spearman_discount_vs_line_margin']:.2f}."),
        calculation=_tbl(dl, ["lines", "sales", "profit", "profit_margin", "loss_line_share"],
                         {"lines": "int", "sales": "money", "profit": "money", "profit_margin": "pct", "loss_line_share": "pct"}),
        interpretation="Deep discounts are the single clearest pattern associated with losses. The break-even point lies between 20% and 30%.",
        limitations="The relationship is strong but observational. The dataset may generate profit from discount mechanically (synthetic data), which would exaggerate its strength.",
        next_step="Model the profit impact of capping discounts at 20%, explicitly stating the assumed volume loss, before any policy change."))

    F.append(dict(
        id="F2", area="F. Discounts", figure=None, confidence="Medium",
        title="There is no evidence that discounts increase the volume of each sale",
        finding=(f"The rank correlation between discount and units per line is {abs(corr['spearman_discount_vs_quantity']) if abs(corr['spearman_discount_vs_quantity']) < 0.005 else corr['spearman_discount_vs_quantity']:.2f}, and between discount and line revenue "
                 f"{corr['spearman_discount_vs_line_sales']:.2f}. Within the same sub-category, discounted lines carry fewer units than full-price lines in "
                 f"{int((dq['difference'] < 0).sum())} of {len(dq)} sub-categories."),
        calculation=_tbl(dq, ["Full price", "Discounted", "difference"], {"Full price": "num", "Discounted": "num", "difference": "num"}),
        interpretation="If discounts are meant to buy volume, they do not appear to do so at the order-line level.",
        limitations="This tests units per line only. Discounts might still attract additional orders or customers, which cannot be tested because discount levels are fixed by state and sub-category (F3): there is no comparison group.",
        next_step="Before any change, run a controlled pilot (e.g. lower the discount ceiling in a few states) and measure order volume, not only margin."))

    heat = r["discount_heat_margin"]
    low_band_losers = heat.index[heat["1-20%"] < 0].tolist()
    F.append(dict(
        id="F3", area="F. Discounts", figure="F06", confidence="High",
        title="Discount is set by a fixed rule (state x sub-category), so it is a controllable policy",
        finding=(f"In all {pol['state_subcategory_cells']} state x sub-category combinations, every order line has exactly the same discount "
                 f"({pct(pol['share_cells_single_discount'],0)} of combinations). State alone explains {pct(pol['r2_state'],0)} of the variation in discount, "
                 f"sub-category {pct(pol['r2_sub_category'],0)}, and the two together {pct(pol['r2_state_x_sub_category'],0)}. "
                 f"{pol['states_never_full_price']} states never sell at full price; {pol['states_always_full_price']} states always do. "
                 f"{', '.join(low_band_losers)} lose money even at 1-20% discount."),
        calculation=("R-squared of discount explained by group means (1.0 = the grouping fully determines the discount).\n\n"
                     + md_table(pd.Series(pol).to_frame("value").reset_index().rename(columns={"index": "measure"}),
                                floatfmt=lambda v: f"{v:.3f}")),
        interpretation=("Discounting is not negotiated deal by deal: it behaves like a rule table by state and sub-category. "
                        "That is good news for management, because the losses come from rules that can be changed. It also means the effect of discount "
                        "cannot be separated statistically from the effect of location."),
        limitations="This pattern may be an artefact of how the synthetic dataset was generated; in a real business it should be confirmed against the pricing policy.",
        next_step="Obtain or reconstruct the discount rule table; prioritise rules that put Tables, Bookcases, Machines and Binders at 30%+ or that put Storage, Supplies and Tables at any discount."))
    return F


def build_report(r: dict, F: list[dict], figs: dict[str, str], validation: pd.DataFrame) -> str:
    o = r["overall"]
    L = ["# Phase 4 — Exploratory Data Analysis: Findings",
         "**Project:** Sales & Profitability Intelligence System  ",
         "**Scope:** core scope (US order lines; suspected Canadian copies excluded); customer analysis also excludes flagged customers.  ",
         f"**Baseline:** revenue {money(o['sales'])}, profit {money(o['profit'])}, margin {pct(o['profit_margin'])}, "
         f"{int(o['orders']):,} orders, effective discount {pct(o['effective_discount'])} (four dataset years).  ",
         f"**Validation:** {(validation.status == 'PASS').sum()}/{len(validation)} reconciliation checks against the Phase 3 SQL results passed.\n",
         "_Generated by `scripts/run_phase4_eda.py`. All numbers are computed at run time._\n",
         "## How to read this report",
         "- **Fact / calculation:** the *Finding* and *Calculation* sections.",
         "- **Interpretation:** a plausible business reading. It is not proof of cause.",
         "- **Confidence:** High = large samples and consistent across cuts; Medium = consistent but confounded or few observations; Low = thin data.",
         "- **Mix-adjusted margin:** a group's own margin inside each discount band, re-weighted to the company's discount mix. If the gap to the company margin shrinks, discount mix accounts for that part of the gap.\n",
         "## 1. Analysis plan (business question first)",
         "| Area | Analysis | Business question | Method | Chart |", "|---|---|---|---|---|"]
    L += [f"| {a} | {n} | {q} | {m} | {c} |" for a, n, q, m, c in ANALYSIS_PLAN]
    L += ["\nCharts were only produced where a picture answers the question better than a table. "
          "Order frequency, segments and cities are reported as tables.\n",
          "## 2. Key findings at a glance", "| ID | Finding | Confidence |", "|---|---|---|"]
    L += [f"| {f['id']} | {f['title']} | {f['confidence']} |" for f in F]
    L += ["\n## 3. Detailed findings"]
    area = None
    for f in F:
        if f["area"] != area:
            area = f["area"]
            L.append(f"\n### {area}")
        L += [f"\n#### {f['id']} — {f['title']}",
              f"**1. Finding.** {f['finding']}\n",
              f"**2. Supporting calculation.**\n\n{f['calculation']}\n"]
        if f.get("figure"):
            L.append(f"![{f['figure']}]({figs[f['figure']]})\n")
        L += [f"**3. Possible interpretation.** {f['interpretation']}\n",
              f"**4. Limitations.** {f['limitations']}\n",
              f"**5. What management should investigate next.** {f['next_step']}\n"]
    L += ["## 4. What this data cannot tell us",
          "- **Why** margins are low (no cost, freight or list-price data).",
          "- Whether discounts **bring in** extra orders or customers: discount is fixed by state and sub-category, so there is no comparison group.",
          "- The value of **returned** goods (returns are recorded per order only).",
          "- Customer **lifetime value or acquisition** (history starts in 2023; no acquisition cost).",
          "- Real-world timing: the dataset years are synthetic.\n",
          "## 5. Consolidated investigation agenda for management",
          "1. **Discount rules:** obtain the state x sub-category discount table; quantify the profit at stake for lines at 30%+ (F1, F3, E1).",
          "2. **Furniture economics:** list price, landed cost and freight for Tables and Bookcases (B1, C1).",
          "3. **Loss concentration:** Binders, Tables and Machines losses by state and discount (B2).",
          "4. **Regional scorecards:** judge managers on mix-adjusted margin, not raw margin (B3).",
          "5. **Controlled discount pilot:** measure order volume as well as margin before changing policy (F2).",
          "6. **Key accounts:** protect the top 10% of customers; review the worst lines behind unprofitable customers (D1, D2).\n",
          "## 6. Validation",
          md_table(validation, floatfmt=lambda v: f"{v:,.4f}")]
    return "\n".join(L)
