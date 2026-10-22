/* ==========================================================================
   02_trends.sql  -  sales and profit over time (scope: core)
   ========================================================================== */

-- query: Q02 | Sales and profit by year
-- covers: 8 Sales by year, 10 Profit by year
-- question: Is the business growing, and is profit growing faster or slower than sales?
-- logic: Aggregate by order year in a CTE, then LAG() over year for year-over-year growth.
-- logic: Profit growth is NULL when the prior-year profit is <= 0, because a % change from a non-positive base is misleading.
-- logic: Margin and AOV are recomputed from the yearly sums, not averaged from months.
-- use: Executive trend line and YoY KPI cards; tells management whether growth is profitable growth.
WITH yearly AS (
    SELECT order_year,
           SUM(sales)               AS sales,
           SUM(profit)              AS profit,
           COUNT(DISTINCT order_id) AS orders
    FROM vw_sales_line
    WHERE is_core_scope = 1
    GROUP BY order_year
)
SELECT
    order_year,
    ROUND(sales, 2)                                               AS sales,
    ROUND(profit, 2)                                              AS profit,
    ROUND(profit / sales, 4)                                      AS profit_margin,
    orders,
    ROUND(sales / orders, 2)                                      AS avg_order_value,
    ROUND(sales / LAG(sales) OVER (ORDER BY order_year) - 1, 4)   AS sales_growth_yoy,
    CASE WHEN LAG(profit) OVER (ORDER BY order_year) > 0
         THEN ROUND(profit / LAG(profit) OVER (ORDER BY order_year) - 1, 4)
    END                                                           AS profit_growth_yoy,
    ROUND(orders * 1.0 / LAG(orders) OVER (ORDER BY order_year) - 1, 4) AS orders_growth_yoy
FROM yearly
ORDER BY order_year;

-- query: Q03 | Sales and profit by month
-- covers: 9 Sales by month, 11 Profit by month
-- question: How do sales and profit move month by month, and is each month better than the same month last year?
-- logic: Aggregate by year-month. Same-month-last-year values come from LAG() partitioned by calendar month and ordered by year.
-- logic: Comparing with the same month last year removes seasonality, which a month-on-month comparison would not.
-- use: Monthly trend chart and the input for spotting months where profit fell while sales rose.
WITH monthly AS (
    SELECT order_year, order_month, order_year_month,
           SUM(sales)  AS sales,
           SUM(profit) AS profit
    FROM vw_sales_line
    WHERE is_core_scope = 1
    GROUP BY order_year, order_month, order_year_month
)
SELECT
    order_year_month,
    ROUND(sales, 2)                                               AS sales,
    ROUND(profit, 2)                                              AS profit,
    ROUND(profit / sales, 4)                                      AS profit_margin,
    ROUND(LAG(sales)  OVER same_month_py, 2)                      AS sales_same_month_py,
    ROUND(sales / LAG(sales) OVER same_month_py - 1, 4)           AS sales_growth_vs_py,
    ROUND(profit - LAG(profit) OVER same_month_py, 2)             AS profit_change_vs_py
FROM monthly
WINDOW same_month_py AS (PARTITION BY order_month ORDER BY order_year)
ORDER BY order_year_month;

-- query: Q04 | Seasonality: share of annual sales by calendar month
-- covers: 9 Sales by month (seasonal pattern)
-- question: Which months carry the business, and is the pattern stable from year to year?
-- logic: Each month's share of its own year's sales (window SUM over the year), then the average, minimum and maximum share across the four years.
-- logic: Shares, not amounts, are compared so that growth between years does not distort the seasonal pattern.
-- use: Planning context (stock, staffing, promotion timing) and for judging whether a weak month is seasonal or a real problem.
WITH monthly AS (
    SELECT order_year, order_month, order_month_name,
           SUM(sales)  AS sales,
           SUM(profit) AS profit
    FROM vw_sales_line
    WHERE is_core_scope = 1
    GROUP BY order_year, order_month, order_month_name
),
shares AS (
    SELECT *,
           sales  / SUM(sales)  OVER (PARTITION BY order_year) AS share_of_year_sales,
           profit / SUM(profit) OVER (PARTITION BY order_year) AS share_of_year_profit
    FROM monthly
)
SELECT
    order_month,
    order_month_name,
    ROUND(AVG(share_of_year_sales), 4)    AS avg_share_of_year_sales,
    ROUND(MIN(share_of_year_sales), 4)    AS min_share_of_year_sales,
    ROUND(MAX(share_of_year_sales), 4)    AS max_share_of_year_sales,
    ROUND(AVG(share_of_year_profit), 4)   AS avg_share_of_year_profit,
    ROUND(SUM(profit) / SUM(sales), 4)    AS profit_margin_all_years
FROM shares
GROUP BY order_month, order_month_name
ORDER BY order_month;
