/* ==========================================================================
   04_geography_and_segments.sql  -  where and to whom we sell (scope: core)
   ========================================================================== */

-- query: Q07 | Sales and profit by region
-- covers: 16 Sales by region, 17 Profit by region
-- question: Which regions perform well or poorly, and does discounting differ between them?
-- logic: Aggregate by region with its regional manager. The effective discount rate (discount given away / list value) is included,
-- logic: because a weak margin can come from heavier discounting rather than from the region itself; Phase 4 tests this properly.
-- use: Regional manager scorecard and the first filter for the geography page.
WITH region AS (
    SELECT region, regional_manager,
           SUM(sales)               AS sales,
           SUM(profit)              AS profit,
           SUM(discount_amount)     AS discount_amount,
           SUM(gross_sales)         AS gross_sales,
           COUNT(DISTINCT order_id) AS orders
    FROM vw_sales_line
    WHERE is_core_scope = 1
    GROUP BY region, regional_manager
)
SELECT
    region,
    regional_manager,
    ROUND(sales, 2)                                 AS sales,
    ROUND(profit, 2)                                AS profit,
    ROUND(profit / sales, 4)                        AS profit_margin,
    ROUND(discount_amount / gross_sales, 4)         AS effective_discount_rate,
    orders,
    ROUND(sales / orders, 2)                        AS avg_order_value,
    ROUND(sales  / SUM(sales)  OVER (), 4)          AS share_of_sales,
    ROUND(profit / SUM(profit) OVER (), 4)          AS share_of_profit
FROM region
ORDER BY profit DESC;

-- query: Q08 | Sales and profit by state
-- covers: 18 Sales by state, 19 Profit by state
-- question: Which states drive results, and which lose money?
-- logic: Aggregate by state with ranks for sales and profit, and a cumulative share of total sales (Pareto) via a running window SUM.
-- logic: States with fewer than 30 orders are labelled 'Low volume': their margins rest on few transactions and must not be over-interpreted.
-- use: State ranking and map; the low-volume label prevents management from acting on statistical noise.
WITH state AS (
    SELECT state_province, region,
           SUM(sales)               AS sales,
           SUM(profit)              AS profit,
           SUM(discount_amount)     AS discount_amount,
           SUM(gross_sales)         AS gross_sales,
           COUNT(DISTINCT order_id) AS orders
    FROM vw_sales_line
    WHERE is_core_scope = 1
    GROUP BY state_province, region
)
SELECT
    state_province,
    region,
    ROUND(sales, 2)                                             AS sales,
    ROUND(profit, 2)                                            AS profit,
    ROUND(profit / sales, 4)                                    AS profit_margin,
    ROUND(discount_amount / gross_sales, 4)                     AS effective_discount_rate,
    orders,
    CASE WHEN orders < 30 THEN 'Low volume' ELSE 'OK' END       AS volume_flag,
    RANK() OVER (ORDER BY sales DESC)                           AS sales_rank,
    RANK() OVER (ORDER BY profit DESC)                          AS profit_rank,
    ROUND(SUM(sales) OVER (ORDER BY sales DESC
                           ROWS UNBOUNDED PRECEDING)
          / SUM(sales) OVER (), 4)                              AS cumulative_share_of_sales
FROM state
ORDER BY sales DESC;

-- query: Q09 | Sales and profit by customer segment
-- covers: 20 Sales by customer segment, 21 Profit by customer segment
-- question: Which customer segment is most valuable, in total and per customer?
-- logic: Aggregate by segment. "Valuable" is shown three ways: total profit, margin, and profit per customer.
-- logic: Per-customer figures use valid customers only, with numerator and denominator from the same population (DQ05/DQ06 excluded).
-- use: Segment comparison page; tells whether a segment is large because of many customers or because each customer is worth more.
WITH segment AS (
    SELECT segment,
           SUM(sales)                AS sales,
           SUM(profit)               AS profit,
           COUNT(DISTINCT order_id)  AS orders,
           COUNT(DISTINCT CASE WHEN is_excluded_from_customer_analysis = 0
                               THEN order_id END)                                AS valid_customer_orders,
           COUNT(DISTINCT CASE WHEN is_excluded_from_customer_analysis = 0
                               THEN customer_id END)                             AS valid_customers,
           SUM(CASE WHEN is_excluded_from_customer_analysis = 0 THEN profit END) AS valid_customer_profit,
           SUM(CASE WHEN is_excluded_from_customer_analysis = 0 THEN sales END)  AS valid_customer_sales
    FROM vw_sales_line
    WHERE is_core_scope = 1
    GROUP BY segment
)
SELECT
    segment,
    ROUND(sales, 2)                                         AS sales,
    ROUND(profit, 2)                                        AS profit,
    ROUND(profit / sales, 4)                                AS profit_margin,
    orders,
    valid_customers,
    ROUND(sales / orders, 2)                                AS avg_order_value,
    ROUND(valid_customer_orders * 1.0 / valid_customers, 2) AS orders_per_customer,
    ROUND(valid_customer_sales  / valid_customers, 2)       AS sales_per_customer,
    ROUND(valid_customer_profit / valid_customers, 2)       AS profit_per_customer,
    ROUND(sales  / SUM(sales)  OVER (), 4)                  AS share_of_sales,
    ROUND(profit / SUM(profit) OVER (), 4)                  AS share_of_profit
FROM segment
ORDER BY profit DESC;
