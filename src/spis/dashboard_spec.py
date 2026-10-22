"""
Power BI dashboard specification as structured data.

This file is the single source of truth for the dashboard design. The Phase 8
runner turns it into the written specification, the page wireframes, and a set
of automated checks (layout on the 8 px grid, no overlapping visuals, every
measure exists in the DAX library, every field exists in the model).

Canvas 1280 x 720 (16:9). Coordinates are in pixels from the top-left corner.
"""
from __future__ import annotations

CANVAS_W, CANVAS_H, GRID, MARGIN = 1280, 720, 8, 24
MAX_DATA_VISUALS = 10   # declutter rule: data visuals per page (KPI cards counted separately)

# Vertical bands used on every page
HEADER_Y, FILTER_Y, KPI_Y, ROW_A_Y, ROW_B_Y, FOOTER_Y = 16, 64, 120, 224, 464, 696
ROW_H = 224

COLORS = {"profit": "#1D7874", "loss": "#C0392B", "neutral": "#5F6B7A", "accent": "#E39B2D",
          "muted": "#B8C0CA", "page": "#F4F6F8", "card": "#FFFFFF", "text": "#1F2933", "subtle": "#6B7785"}

REPORT_FILTERS = [
    "fct_sales[is_core_scope] = 1 (report level, locked and hidden): US lines, suspected copies excluded",
]


def V(id, title, type, x, y, w, h, fields=(), measures=(), filters=(), formatting="", purpose="", kind="data"):
    return dict(id=id, title=title, type=type, x=x, y=y, w=w, h=h, fields=list(fields), measures=list(measures),
                filters=list(filters), formatting=formatting, purpose=purpose, kind=kind)


def chrome(page_title: str) -> list[dict]:
    """Header, filter bar and footer shared by every page (synced slicers)."""
    return [
        V("hdr_title", page_title, "Text box", 24, HEADER_Y, 560, 40, kind="chrome",
          formatting="Segoe UI Semibold 20 pt, colour #1F2933; page question in 11 pt #6B7785 below the title"),
        V("hdr_nav", "Page navigator", "Page navigator (buttons)", 600, HEADER_Y, 656, 40, kind="chrome",
          formatting="Five tabs; selected tab filled #1D7874 with white text, others outline only"),
        V("sl_year", "Year", "Slicer (dropdown)", 24, FILTER_Y, 152, 40, fields=["dim_date[year]"], kind="slicer"),
        V("sl_region", "Region", "Slicer (dropdown)", 184, FILTER_Y, 152, 40, fields=["dim_location[region]"], kind="slicer"),
        V("sl_category", "Category", "Slicer (dropdown)", 344, FILTER_Y, 152, 40, fields=["dim_product[category]"], kind="slicer"),
        V("sl_segment", "Segment", "Slicer (dropdown)", 504, FILTER_Y, 152, 40, fields=["dim_customer[segment]"], kind="slicer"),
        V("ctx", "Filter context", "Card (text)", 664, FILTER_Y, 504, 40, measures=["Report Context Title"], kind="chrome",
          formatting="10 pt #6B7785, left aligned; shows the active filters in words"),
        V("btn_reset", "Reset", "Button (bookmark: Reset filters)", 1176, FILTER_Y, 80, 40, kind="chrome",
          formatting="Outline button, icon + 'Reset'"),
        V("ftr_scope", "Scope note", "Card (text)", 24, FOOTER_Y, 1232, 16, measures=["Data Scope Note"], kind="chrome",
          formatting="8 pt #6B7785"),
    ]


def kpis(cards: list[tuple[str, str, str, str]]) -> list[dict]:
    """Evenly spaced KPI cards: (id, title, measure, reference label measure)."""
    n, gap = len(cards), 16 if len(cards) <= 5 else 8
    w = ((CANVAS_W - 2 * MARGIN - (n - 1) * gap) // n) // GRID * GRID
    out = []
    for i, (cid, title, measure, ref) in enumerate(cards):
        out.append(V(cid, title, "Card (new card visual)", MARGIN + i * (w + gap), KPI_Y, w, 88,
                     measures=[measure] + ([ref] if ref else []), kind="kpi",
                     formatting=f"Callout = [{measure}]" + (f"; reference label = [{ref}]" if ref else "")
                                + "; callout 24-28 pt; label 9 pt #6B7785; no border, white card"))
    return out


PAGES = [
    # ======================================================================
    dict(
        id="P1", name="Executive Overview",
        question="How is the business performing, and is growth profitable?",
        purpose=("One-screen answer for senior management: the size and direction of the business, whether profit keeps pace with revenue, "
                 "and which categories and regions drive the result. Every KPI is shown against the prior year."),
        visuals=chrome("Executive Overview") + kpis([
            ("k_rev", "Revenue", "Revenue", "Revenue YoY Label"),
            ("k_profit", "Profit", "Profit", "Profit YoY Label"),
            ("k_margin", "Profit margin", "Profit Margin %", "Margin Change Label"),
            ("k_orders", "Orders", "Orders", "Orders Growth %"),
            ("k_cust", "Customers", "Customers", "Customers Growth %"),
            ("k_units", "Units sold", "Units Sold", "Units Growth %"),
            ("k_aov", "Average order value", "Average Order Value", "AOV Growth %"),
        ]) + [
            V("v_rev_trend", "Revenue trend: this year vs prior year", "Line chart", 24, ROW_A_Y, 608, ROW_H,
              fields=["dim_date[month_start_date] (X, continuous)"], measures=["Revenue", "Revenue PY", "Revenue Growth %"],
              formatting="Revenue solid #1D7874; Revenue PY dashed #B8C0CA; Revenue Growth % in tooltip only; no markers; display units K",
              purpose="Shows whether revenue is growing and how seasonal it is."),
            V("v_profit_trend", "Profit trend by month", "Column chart", 648, ROW_A_Y, 608, ROW_H,
              fields=["dim_date[month_start_date] (X)"], measures=["Profit", "Profit Colour", "Profit Margin Rolling 12M"],
              formatting="Column colour = field value [Profit Colour] (red for loss months); [Profit Margin Rolling 12M] in tooltip",
              purpose="Shows whether profit follows revenue, and flags loss-making months."),
            V("v_cat", "Category performance", "Matrix", 24, ROW_B_Y, 608, ROW_H,
              fields=["dim_product[category] (rows)"],
              measures=["Revenue", "Share of Revenue %", "Profit", "Share of Profit %", "Profit Margin %", "Revenue Growth %", "Margin Colour"],
              formatting="Data bars on Revenue; font colour of Profit Margin % = [Margin Colour]; stepped layout off; totals row on; "
                         "Revenue Growth % shows only when one year is selected",
              purpose="Exposes the gap between where revenue is earned and where profit is earned (Furniture)."),
            V("v_region", "Region performance: profit (label = margin)", "Clustered bar chart", 648, ROW_B_Y, 608, ROW_H,
              fields=["dim_location[region] (Y)", "dim_location[regional_manager] (tooltip)"],
              measures=["Profit", "Profit Colour", "Profit Margin %", "Effective Discount %", "Revenue"],
              formatting="Sorted by Profit descending; bar colour [Profit Colour]; data label = [Profit Margin %] (custom label); "
                         "tooltip shows manager, revenue and effective discount",
              purpose="Compares regions on profit and margin; the discount in the tooltip prevents misreading a discount-driven gap as a management gap."),
        ],
        dax=["Revenue", "Profit", "Profit Margin %", "Orders", "Customers", "Units Sold", "Average Order Value"],
    ),
    # ======================================================================
    dict(
        id="P2", name="Sales Performance",
        question="Where is revenue growth coming from?",
        purpose=("Explains revenue growth: the trend, growth against the same month last year, whether growth comes from more orders or larger orders, "
                 "the seasonal pattern, and the breakdown by category, sub-category, segment or region (user-selectable)."),
        visuals=chrome("Sales Performance") + kpis([
            ("k2_rev", "Revenue", "Revenue", "Revenue YoY Label"),
            ("k2_growth", "Revenue growth vs prior year", "Revenue Growth %", "Revenue PY"),
            ("k2_orders", "Orders", "Orders", "Orders Growth %"),
            ("k2_aov", "Average order value", "Average Order Value", "AOV Growth %"),
        ]) + [
            V("v2_trend", "Revenue trend with 12-month rolling total", "Line chart", 24, ROW_A_Y, 608, ROW_H,
              fields=["dim_date[month_start_date] (X)"], measures=["Revenue", "Revenue Rolling 12M"],
              formatting="Revenue line #1D7874 with markers off; [Revenue Rolling 12M] in the tooltip (it is on a different scale, "
                         "so it is not plotted on the same axis)",
              purpose="Separates the underlying trend from monthly noise."),
            V("v2_yoy", "Monthly growth vs same month last year", "Column chart", 648, ROW_A_Y, 608, ROW_H,
              fields=["dim_date[month_start_date] (X)"], measures=["Revenue Growth %", "Revenue", "Revenue PY"],
              formatting="Conditional colour: growth >= 0 #1D7874, < 0 #C0392B; zero line visible; first year is blank by design",
              purpose="Same-month comparison removes seasonality, which month-on-month comparison would not."),
            V("v2_decomp", "Growth drivers: orders vs order value", "Line and clustered column chart", 24, ROW_B_Y, 392, ROW_H,
              fields=["dim_date[year] (X)"], measures=["Orders Growth %", "AOV Growth %", "Revenue Growth %"],
              formatting="Columns: Orders Growth % #1D7874, AOV Growth % #E39B2D; line: Revenue Growth % #1F2933; all on ONE % axis",
              purpose="Shows whether growth comes from winning more orders or from larger orders (Phase 4, A1)."),
            V("v2_season", "Seasonality: revenue by month and year", "Matrix (heat map)", 432, ROW_B_Y, 392, ROW_H,
              fields=["dim_date[year] (rows)", "dim_date[month_short] (columns, sorted by month)"], measures=["Revenue"],
              formatting="Background colour scale white to #1D7874; display units K; no totals on columns",
              purpose="Makes the September/November/December peak and stability across years visible at a glance."),
            V("v2_breakdown_sel", "Break down by", "Slicer (buttons, single select)", 840, ROW_B_Y, 416, 32,
              fields=["Sales Breakdown (field parameter)"], kind="slicer",
              formatting="Horizontal tiles: Category | Sub-category | Segment | Region"),
            V("v2_breakdown", "Revenue by selected dimension", "Clustered bar chart", 840, ROW_B_Y + 40, 416, ROW_H - 40,
              fields=["Sales Breakdown (Y axis)"], measures=["Revenue", "Revenue Growth %", "Share of Revenue %"],
              formatting="Sorted by Revenue; data label = [Revenue Growth %] (custom label); tooltip Share of Revenue %",
              purpose="One visual answers category, sub-category, segment and region questions without four separate charts."),
        ],
        dax=["Revenue", "Revenue PY", "Revenue Growth %", "Orders Growth %", "AOV Growth %", "Revenue Rolling 12M"],
    ),
    # ======================================================================
    dict(
        id="P3", name="Profitability",
        question="Where is profit made, and where is it destroyed?",
        purpose=("Locates profit and losses: sub-categories that create or destroy profit, the product portfolio (high-sales/low-margin products), "
                 "margins by region and category, and the products with the largest losses."),
        visuals=chrome("Profitability") + kpis([
            ("k3_profit", "Profit", "Profit", "Profit YoY Label"),
            ("k3_margin", "Profit margin", "Profit Margin %", "Margin Change Label"),
            ("k3_loss", "Loss on loss-making lines", "Loss Amount", "Loss Line Share %"),
            ("k3_lossprod", "Loss-making products", "Loss-making Products", "Loss from Loss-making Products"),
            ("k3_rules", "Loss-making discount rules", "Loss-making Rules", "Loss from Loss-making Rules"),
        ]) + [
            V("v3_subcat", "Profit by sub-category (label = margin)", "Clustered bar chart", 24, ROW_A_Y, 400, ROW_B_Y + ROW_H - ROW_A_Y,
              fields=["dim_product[sub_category] (Y)", "dim_product[category] (tooltip)"],
              measures=["Profit", "Profit Colour", "Profit Margin %", "Loss Amount"],
              formatting="Sorted by Profit descending so losses sit at the bottom; colour [Profit Colour]; data label [Profit Margin %]; "
                         "tooltip adds category and Loss Amount (losses hidden inside positive totals)",
              purpose="Shows which sub-categories create profit and which destroy it (Tables, Bookcases, Supplies)."),
            V("v3_scatter", "Product portfolio: revenue vs margin", "Scatter chart", 440, ROW_A_Y, 520, ROW_H,
              fields=["dim_product[product_label] (values)", "dim_product[portfolio_label] (legend)"],
              measures=["Revenue", "Profit Margin %", "Profit", "Effective Discount %", "Order Lines", "Portfolio Margin %"],
              filters=["Visual: [Order Lines] >= 3 (evidence rule, Phase 5)"],
              formatting="X = Revenue (log scale), Y = Profit Margin %; legend colours Q1 #1D7874, Q2 #C0392B, Q3 #4C8BD6, Q4 #E39B2D; "
                         "Analytics: Y constant line = [Portfolio Margin %] (fx), X median line; tooltip Profit, discount, lines",
              purpose="Identifies high-sales/low-margin products (margin leaks) and low-sales/high-margin products."),
            V("v3_regcat", "Margin by region and category", "Matrix (heat map)", 976, ROW_A_Y, 280, ROW_H,
              fields=["dim_location[region] (rows)", "dim_product[category] (columns)"],
              measures=["Profit Margin %", "Margin vs Visible Total pp"],
              formatting="Background colour = diverging scale on [Margin vs Visible Total pp]: red below the visible total, white at 0, teal above",
              purpose="Shows whether weak margins are regional, category-driven or both."),
            V("v3_negprod", "Products with the largest losses", "Table", 440, ROW_B_Y, 816, ROW_H,
              fields=["dim_product[product_label]", "dim_product[sub_category]", "dim_product[portfolio_label]"],
              measures=["Revenue", "Profit", "Profit Margin %", "Effective Discount %", "Order Lines"],
              filters=["Visual: [Profit] < 0", "Visual: Top N = 15 products by Profit, ascending (largest loss first)"],
              formatting="Red data bars on Profit; Effective Discount % >= 30% in red font; column header states 'ranked by loss amount'",
              purpose="The product-level investigation list, ranked by loss amount (stated on the visual)."),
        ],
        dax=["Profit", "Profit Margin %", "Loss Amount", "Loss-making Products", "Loss-making Rules", "Portfolio Margin %"],
    ),
    # ======================================================================
    dict(
        id="P4", name="Customer & Product",
        question="Which customers and products create profit, and which dilute it?",
        purpose=("Applies the same revenue x margin framework to customers and products. Left half: customer profitability segments and their "
                 "composition by business segment. Right half: the product sales-vs-profit matrix and switchable product lists."),
        visuals=chrome("Customer & Product") + kpis([
            ("k4_cust", "Valid customers", "Valid Customers", "Revenue per Customer"),
            ("k4_ppc", "Profit per customer", "Profit per Customer", "Profit per Order"),
            ("k4_unprof", "Unprofitable customers", "Unprofitable Customers", ""),
            ("k4_top10", "Profit from top 10% of customers", "Top 10% Customer Profit Share", ""),
        ]) + [
            V("v4_cust_scatter", "Customer profitability: revenue vs margin", "Scatter chart", 24, ROW_A_Y, 608, ROW_H,
              fields=["dim_customer[customer_id] (values)", "dim_customer[profitability_label] (legend)",
                      "dim_customer[customer_name] (tooltip)", "dim_customer[segment] (tooltip)"],
              measures=["Revenue", "Profit Margin %", "Profit", "Orders", "Beyond Break-even Revenue %", "Portfolio Margin %"],
              filters=["Visual: dim_customer[is_excluded_from_customer_analysis] = 0"],
              formatting="X = Revenue (log), Y = Profit Margin %; Y constant line [Portfolio Margin %]; legend C1-C4 + Limited history",
              purpose="Shows high-revenue/high-profit, high-revenue/low-profit, low-revenue/high-margin and low-value customers."),
            V("v4_cust_matrix", "Customer segments by business segment", "Matrix", 24, ROW_B_Y, 608, ROW_H,
              fields=["dim_customer[profitability_label] (rows, sorted by code)", "dim_customer[segment] (columns)"],
              measures=["Valid Customers", "Profit", "Profit Margin %"],
              filters=["Visual: dim_customer[is_excluded_from_customer_analysis] = 0"],
              formatting="Profit with red/teal font via [Profit Colour]; subtitle: 'Segments describe 2023-2026 and are not stable over time (Phase 7)'",
              purpose="Sizes each profitability segment and shows that business segment does not explain profitability."),
            V("v4_matrix2x2", "Product sales vs profit matrix", "Matrix (2 x 2)", 648, ROW_A_Y, 608, ROW_H,
              fields=["dim_product[revenue_tier] (rows: High, Low)", "dim_product[margin_tier] (columns: Above hurdle, Below hurdle)"],
              measures=["Products Sold", "Share of Revenue %", "Profit"],
              formatting="Cell background on Profit: teal positive, red negative; large font; tiers are the 2023-2026 classification",
              purpose="The four product quadrants in one compact grid: how much revenue and profit each holds."),
            V("v4_toggle", "Product list selector", "Buttons (bookmarks)", 648, ROW_B_Y, 608, 32, kind="chrome",
              formatting="Two toggle buttons: 'Top 10 by profit' | 'Margin leaks (Q2)'; active state filled #1D7874"),
            V("v4_prodtable", "Products: top by profit / margin leaks", "Table (two bookmark states)", 648, ROW_B_Y + 40, 608, ROW_H - 40,
              fields=["dim_product[product_label]", "dim_product[sub_category]"],
              measures=["Revenue", "Profit", "Profit Margin %", "Effective Discount %", "Product Profit Rank"],
              filters=["State A: Top N = 10 by Profit (ranked by absolute profit)",
                       "State B: dim_product[portfolio_quadrant] = 'Q2', Top N = 15 by Profit ascending"],
              formatting="Data bars on Profit; title changes with the bookmark and states the ranking metric",
              purpose="Lists the products to protect and the high-revenue products that leak margin."),
        ],
        dax=["Valid Customers", "Profit per Customer", "Unprofitable Customers", "Top 10% Customer Profit Share", "Products Sold"],
    ),
    # ======================================================================
    dict(
        id="P5", name="Discount & Management Insights",
        question="Is discounting eroding profit, and what should management investigate?",
        purpose=("Connects discounting to profit and turns the analysis into action: the discount distribution, profit and margin by discount, "
                 "dynamic key findings, the loss-making discount rules to investigate, and the open management questions."),
        visuals=chrome("Discount & Management Insights") + kpis([
            ("k5_eff", "Effective discount", "Effective Discount %", "Average Line Discount %"),
            ("k5_share", "Lines discounted", "Discounted Line Share %", ""),
            ("k5_bbe", "Revenue beyond break-even", "Beyond Break-even Revenue %", "Revenue Beyond Break-even"),
            ("k5_bbe_profit", "Profit on beyond-break-even lines", "Profit Beyond Break-even", ""),
        ]) + [
            V("v5_dist", "Discount distribution", "Clustered column chart", 24, ROW_A_Y, 296, ROW_H,
              fields=["dim_discount[discount_label] (X, sorted by discount_key)"], measures=["Share of Lines %", "Share of Revenue %"],
              formatting="Lines #B8C0CA, revenue #5F6B7A; no legend title",
              purpose="How common each discount level is, by lines and by revenue."),
            V("v5_profit", "Profit by discount band", "Column chart", 336, ROW_A_Y, 296, ROW_H,
              fields=["dim_discount[discount_band] (X, sorted by discount_band_sort)"],
              measures=["Profit", "Profit Colour", "Revenue", "Order Lines", "Loss Line Share %"],
              formatting="Colour [Profit Colour]; tooltip revenue, lines and loss-line share",
              purpose="Discount vs profit: every band above 20% is loss-making in total."),
            V("v5_margin", "Margin by discount level", "Column chart", 648, ROW_A_Y, 296, ROW_H,
              fields=["dim_discount[discount_label] (X, sorted by discount_key)"], measures=["Profit Margin %", "Profit Colour", "Order Lines"],
              formatting="Colour [Profit Colour] (red = negative margin; same sign as profit); zero line; tooltip shows lines so thin levels are visible",
              purpose="Discount vs margin, at the exact levels used in pricing rules."),
            V("v5_findings", "Key findings (update with filters)", "Multi-row card", 960, ROW_A_Y, 296, ROW_H,
              measures=["Insight Break-even", "Insight Discount Margin", "Insight Customer Concentration", "Insight Loss Rules"],
              formatting="Four rows, 10 pt, left accent bar #E39B2D; descriptive statements only, no causal wording",
              purpose="Plain-language findings that recalculate for any filter selection."),
            V("v5_investigate", "Areas requiring investigation: loss-making discount rules", "Table", 24, ROW_B_Y, 816, ROW_H,
              fields=["dim_location[state_province]", "dim_product[sub_category]", "dim_discount[discount_label]"],
              measures=["Revenue", "Profit", "Profit Margin %", "Order Lines"],
              filters=["Visual: [Profit] < 0", "Visual: Top N = 12 state x sub-category rows by Profit, ascending"],
              formatting="Red data bars on Profit; header note 'ranked by loss amount; a rule = one state x sub-category, one discount'",
              purpose="The concrete pricing rules behind most losses (Phase 5 priority list)."),
            V("v5_questions", "Management questions", "Text box", 856, ROW_B_Y, 400, ROW_H, kind="text",
              formatting="Static, reviewed each quarter; each question cites the finding behind it",
              purpose="Keeps the dashboard focused on decisions that the data cannot make on its own."),
        ],
        dax=["Effective Discount %", "Discounted Line Share %", "Beyond Break-even Revenue %", "Profit Beyond Break-even"],
    ),
]

MANAGEMENT_QUESTIONS = [
    "Who sets the discount rule for each state and sub-category, and why do some states never sell at full price? (Phase 4, F3)",
    "Should any discount above a product's list margin require approval? (Phase 6)",
    "What volume would we expect to lose if the rules above 40% were removed? Can we pilot this in a few states? (Phase 6)",
    "Why are Furniture margins thin even at full price: list price, purchase cost or freight? (Phase 4, B1)",
]

BOOKMARKS = [
    ("Reset filters", "All pages", "Clears slicers to 'All'; data, display and current page off so it only resets filters"),
    ("P4 - Top products", "Customer & Product", "Shows product table state A; selected button highlighted"),
    ("P4 - Margin leaks", "Customer & Product", "Shows product table state B; selected button highlighted"),
]

NOT_SHOWN = [
    ("Pie, donut, gauge, 3-D and map visuals", "Harder to compare than bars; four regions do not need a map"),
    ("Dual-axis charts", "Two scales invite false comparisons; related % measures share one axis instead"),
    ("Customer lifetime value, churn, forecast", "Not supported by the data (left-censored history, no costs, synthetic years)"),
    ("Causal 'impact of discount' figures", "No variation within rules or over time; the dashboard shows associations only"),
    ("Returns netted from profit", "Returns are recorded per order only"),
]
