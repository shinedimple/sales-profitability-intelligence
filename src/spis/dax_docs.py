"""
Documentation content for the DAX layer (docs/dax_guide.md).

CORE measures get a full write-up (plain explanation, where to use it, common
mistakes, how to validate). Every other measure in the library gets a compact
entry. The DAX code itself is NOT duplicated here: the guide generator reads it
from powerbi/dax_measures.dax, so the guide always shows the code that is used.
"""

# Requested names -> measure in the library
REQUESTED = [
    ("Total Sales", "Revenue", "Named 'Revenue' to make clear it is net revenue after discount."),
    ("Total Profit", "Profit", ""),
    ("Profit Margin", "Profit Margin %", ""),
    ("Total Orders", "Orders", ""),
    ("Total Customers", "Customers", "Plus 'Valid Customers' for per-customer ratios."),
    ("Total Quantity", "Units Sold", ""),
    ("Average Order Value", "Average Order Value", ""),
    ("Average Discount", "Effective Discount %", "Primary definition; 'Average Line Discount %' kept as the transparent secondary view."),
    ("Sales Growth", "Revenue Growth %", "Same measure as YoY sales growth: see 'Considered but not created'."),
    ("YoY Sales Growth", "Revenue Growth %", ""),
    ("Profit Growth", "Profit Growth %", "Same measure as YoY profit growth."),
    ("YoY Profit Growth", "Profit Growth %", ""),
    ("Profit per Customer", "Profit per Customer", ""),
    ("Profit per Order", "Profit per Order", ""),
]

# SQL used to validate (runs against data/warehouse/spis.sqlite)
SQL_CORE = "FROM fct_sales WHERE is_core_scope = 1"

CORE = {
    "Revenue": dict(
        plain="Adds up the `sales` column of every order line that survives the current filters. If the page is filtered to West and 2025, "
              "it adds only West lines from 2025. `sales` is already after discount, so this is net revenue.",
        use="Every page: KPI card (page 1, 2), trends, category and region visuals, and as the base of almost every ratio.",
        mistakes=["Building it as a calculated column on the fact table and then summing: unnecessary, slower, and it does not respond better to filters.",
                  "Forgetting the report-level scope filter: the card would then include Canadian copies and show 2,326k instead of 2,297k.",
                  "Calling it 'gross sales': the source value is net of discount; gross (list) value is a separate measure."],
        sql=f"SELECT SUM(sales) {SQL_CORE};",
    ),
    "Profit": dict(
        plain="Adds up the `profit` column for the lines in the current filter context. Profit can be negative on individual lines, so the total "
              "already nets losses against gains.",
        use="KPI cards (pages 1 and 3), profit trend, sub-category and region bars, and every margin calculation.",
        mistakes=["Filtering out loss-making lines 'to clean the data': losses are real business results.",
                  "Comparing it to 'gross profit': the dataset does not say which costs profit is net of."],
        sql=f"SELECT SUM(profit) {SQL_CORE};",
    ),
    "Profit Margin %": dict(
        plain="Divides total profit by total revenue for whatever is in the current filter context. Because both totals are recalculated for each "
              "cell of a visual, the margin of 'Furniture in the West' is that group's own profit divided by its own revenue.",
        use="KPI card (pages 1 and 3), category matrix, region labels, scatter Y-axis, heat maps.",
        mistakes=["Averaging line margins (AVERAGE of profit/sales): a 2-dollar line would count as much as a 2,000-dollar line. "
                  "In this data that gives 12.0% instead of the correct 12.5%.",
                  "Using '/' instead of DIVIDE: a cell with no revenue then shows an error instead of staying blank.",
                  "Storing margin as a calculated column and summing or averaging it in visuals."],
        sql=f"SELECT SUM(profit) * 1.0 / SUM(sales) {SQL_CORE};",
    ),
    "Orders": dict(
        plain="Counts how many different order IDs appear in the filtered lines. The table has one row per order line, and an order usually "
              "has two or more lines, so counting rows would overstate orders.",
        use="KPI cards (pages 1 and 2), the denominator of Average Order Value and Profit per Order, growth drivers on page 2.",
        mistakes=["Using COUNTROWS(fct_sales) or COUNT(order_id): that counts lines (9,993), not orders (5,009).",
                  "Summing orders across categories: one order can contain several categories, so category order counts add up to more than the total. "
                  "That is correct behaviour, not an error."],
        sql=f"SELECT COUNT(DISTINCT order_id) {SQL_CORE};",
    ),
    "Customers": dict(
        plain="Counts the different customers who have at least one order line in the current filters. In a year column it means customers active "
              "that year.",
        use="KPI card (page 1) and the base of Valid Customers.",
        mistakes=["Counting rows of dim_customer: that counts every customer in the list (804), including those with no sales in the current filter.",
                  "Expecting regional customer counts to add up to the total: customers order from several states and regions."],
        sql=f"SELECT COUNT(DISTINCT customer_key) {SQL_CORE};",
    ),
    "Valid Customers": dict(
        plain="The same distinct count, but CALCULATE first adds a filter that keeps only customers not flagged in the data-quality audit "
              "(the placeholder 'Sample Company A' and the identity-anomaly records).",
        use="Customer KPIs on page 4 and the denominator of Profit per Customer and Revenue per Customer.",
        mistakes=["Using Customers in per-customer ratios while the numerator uses all customers' profit: numerator and denominator must describe the same population."],
        sql=f"SELECT COUNT(DISTINCT f.customer_key) FROM fct_sales f JOIN dim_customer c USING (customer_key) "
            f"WHERE f.is_core_scope = 1 AND c.is_excluded_from_customer_analysis = 0;",
    ),
    "Units Sold": dict(
        plain="Adds up the quantity on every filtered line: the total number of items sold.",
        use="KPI card on page 1 (total quantity).",
        mistakes=["Comparing units across categories as if they were equivalent: a unit of paper and a unit of a copier are very different."],
        sql=f"SELECT SUM(quantity) {SQL_CORE};",
    ),
    "Average Order Value": dict(
        plain="Revenue divided by the number of distinct orders: how much a typical order is worth in the current filter context.",
        use="KPI cards (pages 1 and 2) and the growth-drivers visual (orders vs order value).",
        mistakes=["Averaging the sales column (AVERAGE(fct_sales[sales])): that is the average line value (230), not the average order value (459).",
                  "Under a category filter, reading it as the full basket value: it is the revenue of that category per order that contains it.",
                  "Treating it as typical: a few large orders pull the mean up; the median order is far smaller (Phase 4)."],
        sql=f"SELECT SUM(sales) * 1.0 / COUNT(DISTINCT order_id) {SQL_CORE};",
    ),
    "Effective Discount %": dict(
        plain="Total discount given away divided by total list value. It answers 'what share of the list price did we give up?' and weights each line by its size.",
        use="Page 5 KPI card, region tooltip (page 1), product tables (pages 3 and 4).",
        mistakes=["Using AVERAGE(discount_rate) as 'the' average discount: it ignores line size (15.6% vs the effective 19.8%).",
                  "Dividing discount amount by revenue instead of by list value: revenue is already reduced by the discount, which inflates the rate."],
        sql=f"SELECT SUM(discount_amount) * 1.0 / SUM(gross_sales) {SQL_CORE};",
    ),
    "Average Line Discount %": dict(
        plain="The simple average of the discount rate on each line. Every line counts equally, however large or small.",
        use="Only as the comparison label under the Effective Discount card on page 5, so readers can see why the two differ.",
        mistakes=["Presenting it as the company's average discount without saying it is unweighted."],
        sql=f"SELECT AVG(discount_rate) {SQL_CORE};",
    ),
    "Profit per Order": dict(
        plain="Total profit divided by the number of distinct orders: how much profit an average order earns.",
        use="Comparison label under the Profit per Customer card (page 4).",
        mistakes=["Averaging line profit: that is profit per line, not per order.",
                  "Comparing it across categories and adding the results up (same caveat as Orders)."],
        sql=f"SELECT SUM(profit) * 1.0 / COUNT(DISTINCT order_id) {SQL_CORE};",
    ),
    "Profit per Customer": dict(
        plain="Profit earned from valid customers divided by the number of valid customers. CALCULATE applies the same customer filter to the "
              "numerator that Valid Customers applies to the denominator, so both describe the same group.",
        use="Page 4 KPI card.",
        mistakes=["Dividing [Profit] (all customers) by [Valid Customers]: the placeholder customer's profit would be divided among the others.",
                  "Averaging a customer-level profit column: unnecessary, and it breaks when filters change."],
        sql="SELECT SUM(f.profit) * 1.0 / COUNT(DISTINCT f.customer_key) FROM fct_sales f JOIN dim_customer c USING (customer_key) "
            "WHERE f.is_core_scope = 1 AND c.is_excluded_from_customer_analysis = 0;",
    ),
    "Last Sales Date Key": dict(
        plain="Finds the latest order date in the whole dataset (REMOVEFILTERS ignores all slicers). It is a helper that stops time-intelligence "
              "measures from inventing values for dates after the data ends.",
        use="Hidden. Used inside PY Comparison Valid and the rolling 12-month measures.",
        mistakes=["Without it, the date table (which runs to the end of 2027 for ship dates) lets 'prior year' and rolling measures show values for "
                  "2027 months that have no sales, so a dashed prior-year line runs on past the real data."],
        sql=f"SELECT MAX(order_date_key) FROM fct_sales;",
    ),
    "PY Comparison Valid": dict(
        plain="Returns TRUE only when exactly one year is in the current filter context (HASONEVALUE) and that period does not start after the data ends. "
              "A month in a chart, a single selected year, or a row of a year matrix all qualify; 'all years' does not.",
        use="Hidden. Every prior-year measure starts with IF ( [PY Comparison Valid], ... ).",
        mistakes=["Leaving it out: with all four years selected, SAMEPERIODLASTYEAR shifts the range back one year, finds the same sales inside the "
                  "date table, and reports growth of 0%. That number looks plausible and is meaningless.",
                  "Replacing it with ISFILTERED(dim_date[year]): a month on a chart axis is not a year filter, so monthly growth would disappear."],
        sql="-- no SQL equivalent: it controls when a comparison is defined",
    ),
    "Revenue PY": dict(
        plain="Revenue for the same dates one year earlier. SAMEPERIODLASTYEAR takes the dates currently in the filter (for example March 2025) and "
              "shifts them back a year (March 2024); CALCULATE then evaluates Revenue for those dates.",
        use="Dashed comparison line on the page 1 revenue trend; comparison label on page 2; input to Revenue Growth %.",
        mistakes=["Not marking dim_date as a date table: time-intelligence functions may then return wrong or blank results.",
                  "Using the date column from the fact table instead of dim_date[date]: time intelligence needs the continuous date table."],
        sql=f"SELECT SUM(sales) {SQL_CORE} AND order_date_key BETWEEN 20250101 AND 20251231;  -- prior year of 2026",
    ),
    "Profit PY": dict(
        plain="Profit for the same dates one year earlier, built exactly like Revenue PY.",
        use="Input to Profit Growth % and Profit Change.",
        mistakes=["Same as Revenue PY."],
        sql=f"SELECT SUM(profit) {SQL_CORE} AND order_date_key BETWEEN 20250101 AND 20251231;",
    ),
    "Revenue Growth %": dict(
        plain="(Revenue this period - revenue same period last year) / revenue same period last year. VAR stores each value once so the formula is "
              "readable and each value is calculated only once. The IF returns BLANK when there is nothing to compare.",
        use="Sales growth and YoY sales growth everywhere: page 1 card label, page 2 card, monthly growth chart, growth drivers, breakdown labels.",
        mistakes=["Computing month-on-month growth and calling it growth: in this seasonal business it mostly measures the calendar (Phase 4).",
                  "Showing a growth figure for 'all years' (prevented by PY Comparison Valid).",
                  "Writing (CY - PY) / CY: the base must be the prior year."],
        sql="SELECT (SUM(CASE WHEN order_date_key >= 20260101 THEN sales END) * 1.0 / "
            "SUM(CASE WHEN order_date_key BETWEEN 20250101 AND 20251231 THEN sales END)) - 1 FROM fct_sales WHERE is_core_scope = 1;",
    ),
    "Profit Growth %": dict(
        plain="The same calculation for profit, with one extra rule: it returns BLANK when last year's profit was zero or negative. Growth from a "
              "negative base has a misleading sign (going from -10k to +5k would show -150%). Profit Change shows the absolute difference instead.",
        use="Profit YoY label on pages 1 and 3.",
        mistakes=["Allowing a negative base: a loss shrinking to a smaller loss can show as large negative 'growth'.",
                  "Comparing profit growth with revenue growth without looking at margin change (use Margin Change pp)."],
        sql="SELECT (SUM(CASE WHEN order_date_key >= 20260101 THEN profit END) * 1.0 / "
            "SUM(CASE WHEN order_date_key BETWEEN 20250101 AND 20251231 THEN profit END)) - 1 FROM fct_sales WHERE is_core_scope = 1;",
    ),
    "Margin Change pp": dict(
        plain="This period's margin minus the prior period's margin, in percentage points. A move from 13.4% to 12.7% is -0.7 points, not '-5%'.",
        use="Margin card label on pages 1 and 3.",
        mistakes=["Expressing a change in margin as a % growth of the margin: it confuses readers and exaggerates small changes."],
        sql="-- (2026 margin) - (2025 margin) from vw_kpi_by_year WHERE scope = 'Core scope'",
    ),
}

# Short "common mistake" and "validation" text for non-core measures, by folder
FOLDER_DEFAULTS = {
    "1 Base": ("Building it as a calculated column instead of a measure.",
               "Compare with the SQL sum/count on fct_sales WHERE is_core_scope = 1."),
    "2 Ratios": ("Averaging a ratio instead of dividing two sums; using '/' instead of DIVIDE.",
                 "Recompute numerator and denominator separately in SQL and divide."),
    "3 Time Intelligence": ("Missing date table marking; showing comparisons across several years.",
                            "Compare one year with the next in vw_kpi_by_year."),
    "4 Losses & break-even": ("Filtering on a flag in a calculated column instead of inside CALCULATE.",
                              "SQL: same SUM with WHERE is_loss_line = 1 or is_beyond_break_even = 1."),
    "5 Products, customers & rules": ("Iterating over the fact table instead of the distinct keys (VALUES), which multiplies results.",
                                      "Phase 5/7 tables (reports/phase5, reports/phase7) give the same counts and totals."),
    "6 Formatting & labels": ("Using hard-coded colours in each visual instead of one measure.",
                              "Visual check: red only where the underlying value is negative or below hurdle."),
    "7 Insight text": ("Writing causal wording into the sentence.",
                       "Each number in the sentence equals the measure it formats."),
}

NOT_CREATED = [
    ("Period-over-period growth (vs the previous month or quarter)",
     "In a strongly seasonal business it mostly measures the calendar: November vs October looks like growth every year. 'Sales Growth' and "
     "'YoY Sales Growth' are therefore the same measure here.",
     "Revenue Prev Period =\nVAR _first = MIN ( dim_date[date] )\nVAR _days = MAX ( dim_date[date] ) - _first + 1\nRETURN\n"
     "    CALCULATE ( [Revenue], DATESBETWEEN ( dim_date[date], _first - _days, _first - 1 ) )"),
    ("Year-to-date measures", "Every dataset year is complete, so YTD equals the yearly total. Kept in dax_optional_measures.dax.", ""),
    ("Return and shipping measures", "Not part of the profitability question; returns are recorded per order only. Kept in the optional file.", ""),
    ("Margin as a calculated column", "A stored ratio cannot be re-aggregated correctly; a measure recalculates it for every filter.", ""),
    ("Separate 'YoY' copies of each growth measure", "Duplicates of the same logic would drift apart; one measure per concept.", ""),
]

PRIMER = [
    ("Measure vs calculated column",
     "A calculated column is computed once per row when the data loads and stored. A measure is computed when a visual asks for it, for exactly "
     "the cells in that visual. Totals and ratios belong in measures, because they must change with filters."),
    ("Filter context",
     "The set of filters active when a measure is evaluated: slicers, the row and column of a matrix cell, the bar of a chart, page and report "
     "filters. [Revenue] in the 'West' bar is evaluated with the filter region = West. Measures never need to 'know' which visual they are in."),
    ("How filters travel",
     "Filters flow from a dimension to the fact table along the one-to-many relationships (dim_location -> fct_sales). Because all relationships "
     "are single-direction, a filter on fct_sales does not filter the dimensions back; this keeps results predictable."),
    ("CALCULATE",
     "CALCULATE ( expression, filter, ... ) evaluates the expression after changing the filter context: adding a filter "
     "(dim_customer[is_excluded_from_customer_analysis] = 0), replacing dates (SAMEPERIODLASTYEAR), or removing filters (REMOVEFILTERS, ALLSELECTED)."),
    ("Row context and context transition",
     "Iterators such as SUMX and FILTER walk a table row by row. When a measure like [Profit] is used inside them, Power BI turns the current row "
     "into a filter (context transition). FILTER ( VALUES ( fct_sales[product_key] ), [Profit] < 0 ) therefore evaluates each product's own profit."),
    ("ALL, REMOVEFILTERS and ALLSELECTED",
     "REMOVEFILTERS ( table ) ignores filters on that table (used for the portfolio hurdle). ALLSELECTED () keeps the user's slicer choices but ignores "
     "the grouping of the visual (used for 'share of total')."),
    ("BLANK",
     "BLANK means 'no value'. DIVIDE returns BLANK for an empty or zero denominator, and visuals hide blank cells. That is why growth measures return "
     "BLANK, not 0, when no comparison exists: 0% would be a false statement."),
    ("Time intelligence prerequisites",
     "A continuous date table (every day, full years), marked as the date table, with an active relationship to the fact table. dim_date meets all three."),
]
