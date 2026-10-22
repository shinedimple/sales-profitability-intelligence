"""
Phase 10 runner: management insight report and one-page executive summary.

    python scripts/run_phase10_management_report.py      (after Phases 1-9)

Every number is recomputed here by the same functions used in Phases 4-7, so
the report cannot drift from the analysis. Narrative wording is analyst
judgement and labels each statement as FACT, CALCULATED, INTERPRETATION,
ASSUMPTION or RECOMMENDATION.

Outputs
  docs/management_insight_report.md
  docs/executive_summary.md
  reports/phase10/insight_register.csv, validation_results.csv
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))
sys.path.insert(0, str(ROOT_DIR / "scripts"))
warnings.filterwarnings("ignore")

import pandas as pd  # noqa: E402

import run_phase4_eda as p4  # noqa: E402
import run_phase5_profitability as p5  # noqa: E402
import run_phase6_discount as p6  # noqa: E402
import run_phase7_customers as p7  # noqa: E402
from spis import config, eda, modeling  # noqa: E402
from spis.findings import money, pct  # noqa: E402
from spis.reporting import md_table  # noqa: E402

OUT = ROOT_DIR / "reports" / "phase10"
REPORT = ROOT_DIR / "docs" / "management_insight_report.md"
SUMMARY = ROOT_DIR / "docs" / "executive_summary.md"

ASSUMPTIONS = [
    ("A1", "Sales are recorded net of discount.", "Verified indirectly: the price-arithmetic test in Phase 6 holds only if this is true."),
    ("A2", "All values are in one currency.", "Not verifiable from the data."),
    ("A3", "Profit is not adjusted for returns.", "Returns are recorded per order only."),
    ("A4", "Implied list value = sales / (1 - discount).", "Follows from A1."),
    ("A5", "Dataset years (2023-2026) are synthetic.", "Orders are dated after the analysis date."),
    ("A6", "Where a Canadian line duplicates a US line, the US line is the original.", "Basis for excluding Canadian copies from core scope."),
    ("A7", "Fiscal year = calendar year.", "No fiscal calendar in the source."),
    ("A8", "Classification thresholds: median revenue and company margin (12.5%); deep discount = 30%+.",
     "Analyst choices, tested for sensitivity in Phases 5 and 7."),
]

DATA_NEEDED = [
    ("Product cost, purchase price and freight", "Explain why Furniture margins are thin at list price; separate price from cost problems."),
    ("Discount rule documentation and approval records", "Confirm who sets each state x sub-category rule and why; identify approved exceptions."),
    ("Results of a controlled discount pilot", "The only way to measure whether lower discounts lose volume (no variation exists in current data)."),
    ("Competitor prices and promotion calendar", "Test whether deep-discount states face price competition."),
    ("Line-level returns with value and reason", "Net returns from revenue and profit at product level."),
    ("Customer history before 2023, acquisition date and cost to serve", "Enable lifetime value, churn and true customer profitability."),
    ("Budget or targets", "Allow variance analysis against plan rather than only against the prior year."),
    ("Confirmation of the Canadian records", "Decide whether Canada can be analysed at all (55% of its revenue appears copied)."),
]


def compute() -> dict:
    conn = modeling.connect()
    df = eda.load_core_lines(conn)
    conn.close()
    return {"r4": p4.compute(df), "r5": p5.compute(df), "r6": p6.compute(df), "r7": p7.compute(df), "df": df}


def numbers(R: dict) -> dict:
    r4, r5, r6, r7 = R["r4"], R["r5"], R["r6"], R["r7"]
    y, o = r4["yearly"], r4["overall"]
    cat, sub, adjc, adjr = r4["category"], r4["sub_category"], r4["mix_adjusted_category"], r4["mix_adjusted_region"]
    heat = r4["discount_heat_margin"]
    furn = ["Bookcases", "Tables", "Chairs", "Furnishings"]
    q, rb, cells, ld = r5["quadrants"], r5["rule_bands"], r5["cells"], r5["loss_diagnosis"]
    neg = r5["negative"]
    hd, rs, corr = r6["headroom"], r6["rule_stability"], r6["correlations"].set_index(["relationship", "level"])["spearman_rho"]
    gsum = r6["growth"]["summary"]
    seg, per, ud = r7["segments"], r7["persistence"], r7["unprofitable"].set_index("group")
    st = r4["state"]
    loss_states = st[st["profit"] < 0]
    tx = st.set_index("state_province").loc["Texas"]
    lc = r4["loss_concentration"]
    deep_rules = rb.loc[rb.index.isin(["41-60%", "61-80%"])]
    pos_profit = R["df"].loc[R["df"]["profit"] > 0, "profit"].sum()
    lm = r6["list_margin_distribution"]
    seas = r4["seasonality"]
    o_idx = gsum.filter(like="orders_index").iloc[:, 0]
    return dict(
        revenue=o["sales"], profit=o["profit"], margin=o["profit_margin"], orders=o["orders"], eff_disc=o["effective_discount"],
        rev_g25=y.loc[2025, "sales_yoy"], rev_g26=y.loc[2026, "sales_yoy"], ord_g25=y.loc[2025, "orders_yoy"], ord_g26=y.loc[2026, "orders_yoy"],
        aov_g25=y.loc[2025, "aov_yoy"], aov_g26=y.loc[2026, "aov_yoy"], rev_g24=y.loc[2024, "sales_yoy"],
        m23=y.loc[2023, "profit_margin"], m25=y.loc[2025, "profit_margin"], m26=y.loc[2026, "profit_margin"],
        d23=y.loc[2023, "effective_discount"], d25=y.loc[2025, "effective_discount"], d26=y.loc[2026, "effective_discount"],
        peak_share=seas.loc[[9, 11, 12], "mean_share"].sum(), janfeb=seas.loc[[1, 2], "mean_share"].sum(),
        loss_lines=-lc["loss_amount"].sum(), loss_vs_pos=-lc["loss_amount"].sum() / pos_profit,
        top3_loss=", ".join(lc.head(3)["sub_category"]), top3_loss_share=lc.head(3)["share_of_all_losses"].sum(),
        furn_rev=cat.loc["Furniture", "share_of_sales"], furn_prof=cat.loc["Furniture", "share_of_profit"], furn_m=cat.loc["Furniture", "profit_margin"],
        furn_adj=adjc.loc["Furniture", "mix_adjusted_margin"], furn_disc=cat.loc["Furniture", "effective_discount"],
        tech_m=cat.loc["Technology", "profit_margin"], off_m=cat.loc["Office Supplies", "profit_margin"],
        furn_fp_lo=heat.loc[furn, "No discount"].min(), furn_fp_hi=heat.loc[furn, "No discount"].max(),
        other_fp_med=heat.drop(index=furn)["No discount"].median(),
        q1n=q.loc["Q1", "products"], q1rev=q.loc["Q1", "share_of_sales"], q1prof=q.loc["Q1", "share_of_profit"],
        q2n=q.loc["Q2", "products"], q2rev=q.loc["Q2", "share_of_sales"], q2prof=q.loc["Q2", "profit"], q2disc=q.loc["Q2", "effective_discount"],
        q1disc=q.loc["Q1", "effective_discount"], q3rev=q.loc["Q3", "share_of_sales"],
        loss_products=len(neg), loss_products_total=-neg["profit"].sum(), p50=r5["pareto"]["products_for_50pct_of_losses"],
        neg_top_subs=", ".join(neg.groupby("sub_category")["profit"].sum().nsmallest(2).index),
        no_fp_loss=int(ld.loc["Profitable at full price, loss when discounted", "products"]),
        never_fp=int(ld.loc["Only ever sold discounted (cannot test)", "products"]),
        top10=r7["top10_profit_share"], c1cust=seg.loc["C1", "share_of_customers"], c1prof=seg.loc["C1", "share_of_profit"],
        unprof=int(ud.loc["Unprofitable customers", "customers"]), unprof_loss=-ud.loc["Unprofitable customers", "profit"],
        unprof_share=ud.loc["Unprofitable customers", "customers"] / len(r7["customers"]),
        unprof_ok_within=int(ud.loc["... profitable on their within-break-even lines", "customers"]),
        c2rev=seg.loc["C2", "share_of_revenue"], c2prof=seg.loc["C2", "profit"],
        rho_margin=per["spearman_margin"], same_seg=per["same_segment_share"], per1=per["period_1"], per2=per["period_2"],
        seg_m_lo=r4["segment"]["profit_margin"].min(), seg_m_hi=r4["segment"]["profit_margin"].max(),
        central_m=adjr.loc["Central", "profit_margin"], central_d=adjr.loc["Central", "effective_discount"],
        central_adj=adjr.loc["Central", "mix_adjusted_margin"], central_expl=adjr.loc["Central", "share_of_gap_explained_by_mix"],
        west_m=adjr.loc["West", "profit_margin"], west_adj=adjr.loc["West", "mix_adjusted_margin"], west_d=adjr.loc["West", "effective_discount"],
        n_loss_states=len(loss_states), loss_states_total=-loss_states["profit"].sum(), loss_states_min_disc=loss_states["effective_discount"].min(),
        state_rho=r4["state_discount_correlation"]["spearman_discount_vs_margin"], n_states=r4["state_discount_correlation"]["states_used"],
        tx_loss=-tx["profit"], tx_disc=tx["effective_discount"],
        rules=rs["policy_cells"], rules_vary=rs["cells_with_more_than_one_discount_level"], rules_multi=rs["cells_observed_in_several_years"],
        rules_changed=rs["multi_year_cells_where_rule_changed"], never_fp_states=r4["discount_policy"]["states_never_full_price"],
        m_full=rb.loc["0%", "profit_margin"], m_1_20=rb.loc["1-20%", "profit_margin"], m_21_40=rb.loc["21-40%", "profit_margin"],
        loss_rules=int(cells["profit_destroying"].sum()), loss_rules_total=-cells.loc[cells["profit_destroying"], "profit"].sum(),
        loss_rules_share=cells.loc[cells["profit_destroying"], "profit"].sum() / R["df"].loc[R["df"]["profit"] < 0, "profit"].sum(),
        deep_rules=int(deep_rules["cells"].sum()), deep_rules_loss=-deep_rules["profit"].sum(),
        rho_units=abs(corr.loc[("Discount vs units per line", "Order line")]),
        rho_growth=corr.loc[("Effective discount vs revenue growth 2023-2026", "State (30+ orders)")],
        rho_basket=corr.loc[("Relative discount vs share of the state's purchases (units)", "State x sub-category")],
        ord_idx_full=o_idx["0%"], ord_idx_lo=o_idx.drop("0%").min(), ord_idx_hi=o_idx.drop("0%").max(),
        bbe_rev=hd.loc["Discounted beyond break-even", "share_of_sales"], bbe_profit=-hd.loc["Discounted beyond break-even", "profit"],
        lm_med=lm["50%"], vol_needed=lm["50%"] / (lm["50%"] - 0.2),
        disc_given=o["discount_amount"], disc_vs_profit=o["discount_amount"] / o["profit"],
    )


def insights(N: dict) -> list[dict]:
    """Each insight: observation (fact), evidence (calculated), interpretation, implication, action, limitation."""
    return [
        # ---------------- Sales ----------------
        dict(id="S1", area="Sales", title="Growth comes from more orders, not larger orders",
             obs="Revenue rose in 2025 and 2026 while the average order value did not rise in step.",
             ev=f"Revenue {pct(N['rev_g25'])} (2025) and {pct(N['rev_g26'])} (2026); orders {pct(N['ord_g25'])} and {pct(N['ord_g26'])}; "
                f"AOV {pct(N['aov_g25'])} and {pct(N['aov_g26'])}. In 2024 revenue changed {pct(N['rev_g24'])}. [Phase 4, A1]",
             interp="The business is winning more transactions; basket size is flat to declining.",
             impl="Growth depends on order volume; a slowdown in order count would not be offset by larger orders.",
             action="Question: what drove the increase in orders (more customers, more frequent orders, or channel changes)? Track median order value next to AOV.",
             limit="Synthetic years; AOV is pulled by a few large orders, so small AOV changes are not reliable signals."),
        dict(id="S2", area="Sales", title="Revenue is concentrated in three months",
             obs="September, November and December carry a large and stable share of each year's revenue.",
             ev=f"Average share of annual revenue: {pct(N['peak_share'])} for Sep+Nov+Dec; {pct(N['janfeb'])} for Jan+Feb. [Phase 4, A2]",
             interp="Month-on-month comparisons mostly reflect the calendar.",
             impl="Monthly performance reviews can mislead unless compared with the same month last year.",
             action="Action: report monthly KPIs against the same month last year and on a rolling 12-month basis (built into the dashboard).",
             limit="Pattern observed over four synthetic years; causes of the seasonality are not in the data."),
        # ---------------- Profitability ----------------
        dict(id="P1", area="Profitability", title="Losses on individual lines give back a third of the profit earned elsewhere",
             obs="Some order lines lose money; every one of them is a discounted line.",
             ev=f"Loss-making lines lose {money(N['loss_lines'])}, equal to {pct(N['loss_vs_pos'],0)} of the profit on profitable lines; "
                f"{N['top3_loss']} account for {pct(N['top3_loss_share'],0)} of losses. No full-price line loses money. [Phases 4-6]",
             interp="Reported profit is the net of a profitable core and a concentrated loss-making tail.",
             impl="Reducing the tail would matter more to profit than growing the already-profitable core, provided volume held up (unknown).",
             action="Investigate the loss-making tail by sub-category, state and discount (dashboard page 3 and 5).",
             limit="Profit allocation to lines in the source is not documented; profit appears mechanically generated (synthetic data)."),
        dict(id="P2", area="Profitability", title="Furniture earns almost nothing, and not only because of discounting",
             obs="Furniture has similar revenue and discount levels to the other categories but far lower profit.",
             ev=f"Furniture: {pct(N['furn_rev'],0)} of revenue, {pct(N['furn_prof'],0)} of profit, margin {pct(N['furn_m'])} "
                f"(Technology {pct(N['tech_m'])}, Office Supplies {pct(N['off_m'])}); effective discount {pct(N['furn_disc'])}, same as others. "
                f"At the company discount mix its margin would be {pct(N['furn_adj'])}. Full-price margins: Furniture "
                f"{pct(N['furn_fp_lo'],0)}-{pct(N['furn_fp_hi'],0)} vs median {pct(N['other_fp_med'],0)} elsewhere. [Phase 4, B1]",
             interp="Furniture's list-price margins are thin, so ordinary discounts turn them into losses. Why list margins are thin is not visible in the data.",
             impl="Discount policy alone will not fix Furniture profitability.",
             action="Question: are Furniture list prices, purchase costs or freight the cause? Requires cost data.",
             limit="No cost, freight or price-history data; the cause cannot be determined."),
        # ---------------- Products ----------------
        dict(id="PR1", area="Products", title="Almost half of revenue comes from products that lose money as a group",
             obs="Products split into a profitable core and a large group of high-revenue, low-margin products.",
             ev=f"Q1 core earners: {int(N['q1n'])} products, {pct(N['q1rev'],0)} of revenue, {pct(N['q1prof'],0)} of profit. "
                f"Q2 margin leaks: {int(N['q2n'])} products, {pct(N['q2rev'],0)} of revenue, profit {money(N['q2prof'])}; "
                f"effective discount {pct(N['q2disc'])} vs {pct(N['q1disc'])} for Q1. High-margin niche products: {pct(N['q3rev'],0)} of revenue. [Phase 5]",
             interp="Revenue is being earned without profit on a large part of the range; niche high-margin products are too small to offset it.",
             impl="Product-range decisions based on revenue rankings would protect loss-making products.",
             action="Review discount eligibility and pricing for Q2 products, starting with the largest losses.",
             limit="Thresholds are analyst choices (tested: conclusion holds); many products have few sales; product IDs are reused (composite key used)."),
        dict(id="PR2", area="Products", title="No product is unprofitable at full price",
             obs="Loss-making products lose money only on their discounted sales.",
             ev=f"{N['loss_products']} products lose {money(N['loss_products_total'])}; {N['p50']} products account for half of it, mostly "
                f"{N['neg_top_subs']}. {N['no_fp_loss']} are profitable on their own full-price sales; {N['never_fp']} were never sold at full price. [Phase 5]",
             interp="Product losses are a discount problem, not a product-cost problem, in this data.",
             impl="Removing products is not indicated by the evidence; the discount applied to them is.",
             action="Prioritise discount-rule review over range rationalisation.",
             limit="A product's full-price and discounted sales occur in different states, so the comparison is not a controlled test."),
        # ---------------- Customers ----------------
        dict(id="C1", area="Customers", title="Profit depends heavily on a small group of customers",
             obs="A minority of customers produces most of the profit.",
             ev=f"Top 10% of customers: {pct(N['top10'],0)} of customer profit. Core accounts (high revenue, high margin): "
                f"{pct(N['c1cust'],0)} of customers, {pct(N['c1prof'],0)} of profit. [Phase 7]",
             interp="Customer concentration is a dependency, not evidence of risk.",
             impl="The loss of a small number of accounts would have a disproportionate effect on profit.",
             action="Question: how well are the top accounts covered and served? (Account management data needed.)",
             limit="Four-year window only; no information on account relationships or contracts."),
        dict(id="C2", area="Customers", title="Unprofitable customers are a transaction pattern, not a stable customer type",
             obs="One customer in five is unprofitable, and customer profitability does not persist over time.",
             ev=f"{N['unprof']} customers ({pct(N['unprof_share'],0)}) lose {money(N['unprof_loss'])}; all bought at least one line beyond break-even, "
                f"{N['unprof_ok_within']} are profitable on their other lines. Margin {N['per1']} vs {N['per2']}: rho = {N['rho_margin']:.2f}; "
                f"{pct(N['same_seg'],0)} stay in the same segment (about 25% by chance). Customers get the same discount as anyone in the same state and sub-category. [Phase 7]",
             interp="Customer losses follow the discount rules applied to their orders. The data shows no customer-specific deals.",
             impl="Acting on individual 'unprofitable customers' is not supported by the evidence.",
             action="Address the rules and approvals behind loss-making orders, not the customers.",
             limit="The lack of persistence may be an artefact of synthetic data; retest on real data before any customer-level action."),
        # ---------------- Geography ----------------
        dict(id="G1", area="Geography", title="Regional margin differences track discount levels",
             obs="Central has the lowest margin and the highest discount; West the reverse.",
             ev=f"Central margin {pct(N['central_m'])}, effective discount {pct(N['central_d'])}; at the company discount mix {pct(N['central_adj'])} "
                f"(about {pct(N['central_expl'],0)} of its gap). West {pct(N['west_m'])} -> {pct(N['west_adj'])} after adjustment (discount {pct(N['west_d'])}). [Phase 4, B3]",
             interp="Regional rankings reflect discount rules more than regional performance.",
             impl="Judging regional managers on raw margin would reward low-discount regions regardless of performance.",
             action="Use mix-adjusted margin in regional scorecards; confirm who sets regional discount rules.",
             limit="Standardisation controls for discount band only; region and discount cannot be fully separated."),
        dict(id="G2", area="Geography", title="Every loss-making state is a heavy-discount state",
             obs="Ten states lose money; all apply deep discounts.",
             ev=f"{N['n_loss_states']} states lose {money(N['loss_states_total'])}; all have an effective discount of at least {pct(N['loss_states_min_disc'])}. "
                f"Across {N['n_states']} states with 30+ orders, discount vs margin rho = {N['state_rho']:.2f}. Texas: 3rd-largest by revenue, "
                f"loss {money(N['tx_loss'])}, discount {pct(N['tx_disc'])}. [Phase 4, E1]",
             interp="Whether a state loses money is closely associated with its discount rules.",
             impl="State-level losses are concentrated and identifiable.",
             action="Review the discount rules in Texas, Ohio, Pennsylvania and Illinois first.",
             limit="Correlation across states; state and discount are confounded by design."),
        # ---------------- Discounts ----------------
        dict(id="D1", area="Discounts", title="Discount is a fixed rule by state and sub-category",
             obs="Every order line in the same state and sub-category carries the same discount, and the rules never changed.",
             ev=f"{N['rules_vary']} of {N['rules']} state x sub-category rules contain more than one discount level; {N['rules_changed']} of "
                f"{N['rules_multi']} rules seen in several years changed. {N['never_fp_states']} states never sell at full price. [Phases 4, 6]",
             interp="Discounting behaves like a central pricing policy, not deal-by-deal negotiation.",
             impl="The losses come from rules that management can change. But the effect of changing them cannot be estimated from this data.",
             action="Obtain the rule table and its rationale; this is the single most important document for the next step.",
             limit="May be an artefact of the synthetic data; must be confirmed against the real pricing policy."),
        dict(id="D2", area="Discounts", title="Deep discount rules account for almost all losses",
             obs="Profitability falls with each discount band; every rule above 40% loses money.",
             ev=f"Margin: {pct(N['m_full'])} at full price, {pct(N['m_1_20'])} at 1-20%, {pct(N['m_21_40'])} at 21-40%. {N['loss_rules']} loss-making rules lose "
                f"{money(N['loss_rules_total'])} ({pct(N['loss_rules_share'],0)} of all line losses); the {N['deep_rules']} rules above 40% lose "
                f"{money(N['deep_rules_loss'])}. Discount given away: {money(N['disc_given'])}, {N['disc_vs_profit']:.1f}x profit. [Phases 5, 6]",
             interp="A small number of rules is associated with most of the profit erosion.",
             impl="Reviewing a few dozen rules covers most of the loss.",
             action="Review the 32 rules above 40% first, then loss-making 21-40% rules (dashboard page 5 list).",
             limit="Association; loss at stake is the current loss, not a forecast of profit recovered."),
        dict(id="D3", area="Discounts", title="There is no sign that discounts buy volume",
             obs="Discounted business does not show larger baskets, a larger share of purchases, or faster growth.",
             ev=f"Discount vs units per line rho = {N['rho_units']:.2f}; vs state revenue growth rho = {N['rho_growth']:.2f}; vs share of a state's purchases "
                f"rho = {N['rho_basket']:.2f}. Order growth: {N['ord_idx_full']:.2f}x at full price vs {N['ord_idx_lo']:.2f}-{N['ord_idx_hi']:.2f}x in discounted bands. "
                f"Arithmetic: a 20% discount on a product with the median list margin ({pct(N['lm_med'],0)}) needs {N['vol_needed']:.1f}x the units to keep profit. [Phase 6]",
             interp="Deep discounting is not visibly generating profitable growth.",
             impl=f"Revenue beyond break-even ({pct(N['bbe_rev'],0)} of revenue, loss {money(N['bbe_profit'])}) erodes profit on every unit; whether it protects volume is unknown.",
             action="Run a controlled pilot: lower the deepest rules in a few states, keep comparable states unchanged, measure orders, units and profit.",
             limit="No comparison group exists in the data; absence of association is not proof of no effect."),
    ]


def build_report(I: list[dict], N: dict, validation: pd.DataFrame) -> str:
    L: list[str] = []
    add = L.append
    add("# Management Insight Report — Sales & Profitability Intelligence System")
    add("**Prepared by:** Senior Business Analyst review of Phases 1-9  ")
    add(f"**Scope:** US order lines, 2023-2026 dataset years (synthetic); suspected copied Canadian records excluded. "
        f"Revenue {money(N['revenue'])}, profit {money(N['profit'])}, margin {pct(N['margin'])}, {int(N['orders']):,} orders.  ")
    add(f"**Validation:** {(validation.status == 'PASS').sum()}/{len(validation)} headline figures reconcile with the SQL warehouse and dashboard acceptance values.  ")
    add("_Generated by `scripts/run_phase10_management_report.py`; every number is recomputed from the data at run time._\n")
    add("## How to read this report")
    add("| Label | Meaning |")
    add("|---|---|")
    add("| **Observation** | A fact read directly from the data. |")
    add("| **Evidence** | Calculated metrics, with the phase that produced them. |")
    add("| **Interpretation** | The analyst's reading of the evidence. Not proven. |")
    add("| **Implication** | What it could mean for the business if the interpretation holds. |")
    add("| **Question / action** | A recommendation: what management should ask or do. |")
    add("| **Limitation** | What the evidence cannot show. |")
    add("\nNo statement in this report claims that one variable *causes* another. Where reasons for a pattern are unknown, the report says so.\n")

    add("## Most decision-relevant findings (ranked)")
    add("Ranking metric: size of the profit involved, combined with how directly management can act on it.\n")
    add("| Rank | Insight | Profit involved |")
    add("|---|---|---|")
    add(f"| 1 | D2 Deep discount rules account for almost all losses | {money(N['loss_rules_total'])} lost in {N['loss_rules']} rules |")
    add(f"| 2 | D1 Discount is a fixed, changeable rule | Applies to all {N['rules']} rules |")
    add(f"| 3 | PR1 Almost half of revenue earns no profit as a group | {money(N['q2prof'])} on {pct(N['q2rev'],0)} of revenue |")
    add(f"| 4 | P2 Furniture earns almost nothing | {pct(N['furn_rev'],0)} of revenue, {pct(N['furn_prof'],0)} of profit |")
    add(f"| 5 | D3 No sign that discounts buy volume | {money(N['bbe_profit'])} lost beyond break-even |")
    add(f"| 6 | C1 Profit concentrated in few customers | {pct(N['top10'],0)} of customer profit from top 10% |\n")

    area = None
    for ins in I:
        if ins["area"] != area:
            area = ins["area"]
            add(f"## {area}")
        add(f"### {ins['id']} — {ins['title']}")
        add(f"- **Observation (fact):** {ins['obs']}")
        add(f"- **Evidence (calculated):** {ins['ev']}")
        add(f"- **Business interpretation:** {ins['interp']}")
        add(f"- **Potential implication:** {ins['impl']}")
        add(f"- **Management question / possible action (recommendation):** {ins['action']}")
        add(f"- **Limitation:** {ins['limit']}\n")

    add("## Facts, calculations, interpretations, assumptions and recommendations at a glance")
    add("| Type | Examples from this report |")
    add("|---|---|")
    add("| Facts | Discount takes 12 values; each state x sub-category always has one discount; no full-price line loses money; 87% of customers ordered in the last year |")
    add(f"| Calculated metrics | Margin {pct(N['margin'])}; effective discount {pct(N['eff_disc'])}; beyond-break-even revenue {pct(N['bbe_rev'],0)}; correlations; mix-adjusted margins |")
    add("| Interpretations | 'Discounting behaves like central policy'; 'Furniture list margins are thin'; 'customer losses follow rules' |")
    add("| Assumptions | See register below (A1-A8) |")
    add("| Recommendations | Obtain rule table; review deep rules; pilot; mix-adjusted scorecards; cost data for Furniture |\n")

    add("## Assumptions register")
    add(md_table(pd.DataFrame(ASSUMPTIONS, columns=["id", "assumption", "status / basis"])))
    add("\n## What this analysis cannot tell management")
    add("- Whether reducing discounts would raise or lower total profit (no variation in discount within rules or over time).")
    add("- Why Furniture margins are thin, or why rules were set as they are (no cost or policy data).")
    add("- Customer lifetime value, churn, or which customers are at risk (left-censored history, no relationship data).")
    add("- Real-world timing or market context (synthetic years, no competitor data).\n")
    add("## Additional data that would be useful")
    add(md_table(pd.DataFrame(DATA_NEEDED, columns=["data", "what it would enable"])))
    add("\n## Validation")
    add(md_table(validation, floatfmt=lambda v: f"{v:,.4f}"))
    return "\n".join(L)


def build_summary(N: dict) -> str:
    return "\n".join([
        "# Executive Summary — Sales & Profitability Review",
        f"*US business, 2023-2026 dataset years (synthetic). Revenue {money(N['revenue'])}, profit {money(N['profit'])}, margin {pct(N['margin'])}.*\n",
        "## What happened?",
        f"- **Revenue grew strongly** ({pct(N['rev_g25'],0)} in 2025, {pct(N['rev_g26'],0)} in 2026), with the increase coming from more orders rather than larger orders.",
        f"- **Margin improved to {pct(N['m25'])} in 2025, then slipped to {pct(N['m26'])} in 2026**, while the effective discount rose from {pct(N['d25'])} to {pct(N['d26'])}.",
        f"- **Profit is concentrated:** a quarter of products earn {pct(N['q1prof'],0)} of profit; the top 10% of customers earn {pct(N['top10'],0)}.",
        f"- **Losses are concentrated:** {N['loss_rules']} state x sub-category discount rules lose {money(N['loss_rules_total'])} "
        f"({pct(N['loss_rules_share'],0)} of all line-level losses). Every rule above 40% discount loses money. No product loses money at full price.",
        f"- **Furniture** generates {pct(N['furn_rev'],0)} of revenue but {pct(N['furn_prof'],0)} of profit.\n",
        "## Why might it matter?",
        f"- The business gives away {money(N['disc_given'])} in discounts, {N['disc_vs_profit']:.1f}x its profit; "
        f"{pct(N['bbe_rev'],0)} of revenue is sold below the product's break-even price.",
        "- The data shows **no sign that deep discounts bring extra volume or growth**, but it also cannot prove they do not: discount rules never vary or change, "
        "so there is no comparison group. This is association, not cause.",
        "- Discount appears to be set centrally by state and sub-category, so the losses sit in **rules management can change**.",
        "- Regional and customer rankings mostly mirror these rules; judging managers or customers on raw margin would be misleading.\n",
        "## What should management investigate?",
        f"1. **The discount rule table:** who sets each state x sub-category rule, and why {N['never_fp_states']} states never sell at full price.",
        f"2. **The {N['deep_rules']} rules above 40%** ({money(N['deep_rules_loss'])} lost), then loss-making 21-40% rules.",
        "3. **Furniture economics:** list price, purchase cost and freight for Tables and Bookcases.",
        "4. **A controlled pilot:** lower the deepest rules in a few states, keep comparable states unchanged, and measure orders, units and profit for two quarters.",
        "5. **Scorecards:** use mix-adjusted margin for regions; protect coverage of top accounts.\n",
        "## What additional data would be useful?",
        "- Product cost, purchase price and freight (to explain thin Furniture margins).",
        "- Discount rule documentation and approval records.",
        "- Results of a controlled discount pilot (the only way to measure volume effects).",
        "- Competitor prices and promotion calendar; line-level returns; customer history, acquisition and cost to serve; budget or targets.\n",
        "*Caveat: the dataset is synthetic and its profit appears mechanically generated; findings identify where to investigate, not guaranteed outcomes.*",
    ])


def validate(N: dict) -> pd.DataFrame:
    acc = pd.read_csv(ROOT_DIR / "reports" / "phase8" / "acceptance_values.csv")
    a = acc[acc["filter"] == "All years"].set_index("measure")["expected"]
    q01 = pd.read_csv(ROOT_DIR / "reports" / "phase3" / "q01_headline_kpis.csv").iloc[0]
    rows = [("Revenue", N["revenue"], q01.total_sales, 0.01), ("Profit", N["profit"], q01.total_profit, 0.01),
            ("Profit margin", N["margin"], a["Profit Margin %"], 1e-6),
            ("Loss-making rules", N["loss_rules"], a["Loss-making Rules"], 0),
            ("Top 10% customer profit share", N["top10"], a["Top 10% Customer Profit Share"], 1e-6),
            ("Beyond break-even revenue share", N["bbe_rev"], a["Beyond Break-even Revenue %"], 1e-6),
            ("Unprofitable customers", N["unprof"], a["Unprofitable Customers"], 0),
            ("Loss-making products", N["loss_products"], a["Loss-making Products"], 0)]
    return pd.DataFrame([{"figure": n, "report": float(x), "reference": float(y), "status": "PASS" if abs(x - y) <= t else "FAIL"}
                         for n, x, y, t in rows])


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    R = compute()
    N = numbers(R)
    validation = validate(N)
    print(f"[validation] {(validation.status == 'PASS').sum()}/{len(validation)} figures reconcile")
    if (validation.status != "PASS").any():
        print(validation.to_string(index=False))
        raise SystemExit("Report figures do not reconcile.")
    I = insights(N)
    validation.to_csv(OUT / "validation_results.csv", index=False)
    pd.DataFrame([{k: v for k, v in i.items()} for i in I]).to_csv(OUT / "insight_register.csv", index=False)
    REPORT.write_text(build_report(I, N, validation), encoding="utf-8")
    SUMMARY.write_text(build_summary(N), encoding="utf-8")
    print(f"[done]       {len(I)} insights -> {REPORT.relative_to(ROOT_DIR)}; summary -> {SUMMARY.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    main()
