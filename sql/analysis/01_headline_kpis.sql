/* ==========================================================================
   Phase 3 - SQL analytical layer
   01_headline_kpis.sql

   Conventions for every analysis file
     * Source: vw_sales_line (the star schema flattened to one row per order line).
     * Scope:  WHERE is_core_scope = 1  -> US order lines, suspected clone copies excluded.
     * Ratios are always ratio-of-sums (SUM(profit) / SUM(sales)), never averages of ratios.
     * Orders and customers are DISTINCT counts, because the grain is the order line.
     * ROUND() is applied only in the final SELECT, never before a calculation.
   ========================================================================== */

-- query: Q01 | Headline KPIs
-- covers: 1 Total sales, 2 Total profit, 3 Total quantity, 4 Orders, 5 Customers, 6 Average order value, 7 Profit margin
-- question: What is the overall size and profitability of the business over the full four dataset years?
-- logic: One pass over the core-scope lines. Orders and customers use COUNT(DISTINCT) because one order has several lines.
-- logic: AOV = revenue / distinct orders; margin = total profit / total revenue (ratio of sums).
-- logic: Customers are shown twice: all active customers, and valid customers (placeholder and identity-anomaly customers excluded, DQ05/DQ06).
-- use: The baseline every other number is compared with: KPI cards on the executive page and the denominator for all "share of total" figures.
SELECT
    ROUND(SUM(sales), 2)                                          AS total_sales,
    ROUND(SUM(profit), 2)                                         AS total_profit,
    SUM(quantity)                                                 AS total_units,
    COUNT(DISTINCT order_id)                                      AS orders,
    COUNT(DISTINCT customer_id)                                   AS customers,
    COUNT(DISTINCT CASE WHEN is_excluded_from_customer_analysis = 0
                        THEN customer_id END)                     AS valid_customers,
    ROUND(SUM(sales) / COUNT(DISTINCT order_id), 2)               AS avg_order_value,
    ROUND(SUM(profit) / SUM(sales), 4)                            AS profit_margin
FROM vw_sales_line
WHERE is_core_scope = 1;
