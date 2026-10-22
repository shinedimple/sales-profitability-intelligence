/* ==========================================================================
   03_product_hierarchy.sql  -  category and sub-category performance (scope: core)
   ========================================================================== */

-- query: Q05 | Sales and profit by category
-- covers: 12 Sales by category, 13 Profit by category
-- question: Which categories generate revenue, which generate profit, and are those the same categories?
-- logic: Aggregate by category; share of total via SUM() OVER () across the result; separate ranks for sales and profit.
-- logic: Showing sales share next to profit share exposes categories whose contribution to profit differs from their contribution to revenue.
-- use: Top-level portfolio view for the executive page; the starting point for drilling into sub-categories.
WITH category AS (
    SELECT category,
           SUM(sales)  AS sales,
           SUM(profit) AS profit,
           SUM(quantity) AS units
    FROM vw_sales_line
    WHERE is_core_scope = 1
    GROUP BY category
)
SELECT
    category,
    ROUND(sales, 2)                                 AS sales,
    ROUND(profit, 2)                                AS profit,
    ROUND(profit / sales, 4)                        AS profit_margin,
    units,
    ROUND(sales  / SUM(sales)  OVER (), 4)          AS share_of_sales,
    ROUND(profit / SUM(profit) OVER (), 4)          AS share_of_profit,
    RANK() OVER (ORDER BY sales DESC)               AS sales_rank,
    RANK() OVER (ORDER BY profit DESC)              AS profit_rank
FROM category
ORDER BY sales DESC;

-- query: Q06 | Sales and profit by sub-category
-- covers: 14 Sales by sub-category, 15 Profit by sub-category
-- question: Which sub-categories create profit and which destroy it, and how large are their losses?
-- logic: Aggregate by sub-category with shares and ranks, as for categories.
-- logic: loss_amount sums only loss-making lines, so a sub-category with a positive total can still reveal large hidden losses.
-- use: Identifies where the category results come from; feeds the portfolio quadrant (Q14) and the loss investigation.
WITH sub AS (
    SELECT category, sub_category,
           SUM(sales)                                        AS sales,
           SUM(profit)                                       AS profit,
           SUM(CASE WHEN is_loss_line = 1 THEN profit END)   AS loss_amount,
           COUNT(*)                                          AS lines
    FROM vw_sales_line
    WHERE is_core_scope = 1
    GROUP BY category, sub_category
)
SELECT
    category,
    sub_category,
    ROUND(sales, 2)                                 AS sales,
    ROUND(profit, 2)                                AS profit,
    ROUND(profit / sales, 4)                        AS profit_margin,
    ROUND(COALESCE(loss_amount, 0), 2)              AS loss_amount,
    lines,
    ROUND(sales  / SUM(sales)  OVER (), 4)          AS share_of_sales,
    ROUND(profit / SUM(profit) OVER (), 4)          AS share_of_profit,
    RANK() OVER (ORDER BY sales DESC)               AS sales_rank,
    RANK() OVER (ORDER BY profit DESC)              AS profit_rank
FROM sub
ORDER BY profit DESC;
