/* ==========================================================================
   05_products.sql  -  product-level performance (scope: core)

   Product = product_key (product_id + product_name), because product_id alone
   is reused for different products in the source (DQ07). product_label is the
   unique display name.
   ========================================================================== */

-- query: Q10 | Top 10 products by sales
-- covers: 22 Top products by sales
-- question: Which individual products bring in the most revenue, and are they profitable?
-- logic: Aggregate per product, RANK() by sales, keep rank <= 10 (RANK keeps ties instead of cutting them arbitrarily).
-- logic: Profit and margin are shown next to sales, because a top seller is not automatically a top earner.
-- use: Revenue-critical products to protect; any loss-making product in this list is an immediate investigation item.
WITH product AS (
    SELECT product_key, product_label, category, sub_category,
           SUM(sales) AS sales, SUM(profit) AS profit,
           SUM(quantity) AS units, COUNT(DISTINCT order_id) AS orders
    FROM vw_sales_line
    WHERE is_core_scope = 1
    GROUP BY product_key, product_label, category, sub_category
),
ranked AS (
    SELECT *, RANK() OVER (ORDER BY sales DESC) AS sales_rank FROM product
)
SELECT sales_rank, product_label, category, sub_category,
       ROUND(sales, 2) AS sales, ROUND(profit, 2) AS profit,
       ROUND(profit / sales, 4) AS profit_margin, units, orders
FROM ranked
WHERE sales_rank <= 10
ORDER BY sales_rank;

-- query: Q11 | Top 10 products by profit
-- covers: 23 Top products by profit
-- question: Which products contribute the most profit?
-- logic: Same product aggregate, ranked by profit instead of sales.
-- use: Compared with Q10, shows whether profit leaders and revenue leaders are the same products.
WITH product AS (
    SELECT product_key, product_label, category, sub_category,
           SUM(sales) AS sales, SUM(profit) AS profit,
           SUM(quantity) AS units, COUNT(DISTINCT order_id) AS orders
    FROM vw_sales_line
    WHERE is_core_scope = 1
    GROUP BY product_key, product_label, category, sub_category
),
ranked AS (
    SELECT *, RANK() OVER (ORDER BY profit DESC) AS profit_rank FROM product
)
SELECT profit_rank, product_label, category, sub_category,
       ROUND(sales, 2) AS sales, ROUND(profit, 2) AS profit,
       ROUND(profit / sales, 4) AS profit_margin, units, orders
FROM ranked
WHERE profit_rank <= 10
ORDER BY profit_rank;

-- query: Q12 | Bottom 10 products by profit
-- covers: 24 Worst products by profit
-- question: Which products lose the most money, and is discounting involved?
-- logic: Rank by profit ascending. The effective discount rate and the number of loss-making lines are added
-- logic: to show whether the loss is systematic (every sale loses) or driven by a few deeply discounted orders.
-- use: The product-level loss investigation list for management.
WITH product AS (
    SELECT product_key, product_label, category, sub_category,
           SUM(sales) AS sales, SUM(profit) AS profit,
           SUM(discount_amount) AS discount_amount, SUM(gross_sales) AS gross_sales,
           COUNT(*) AS lines, SUM(is_loss_line) AS loss_lines
    FROM vw_sales_line
    WHERE is_core_scope = 1
    GROUP BY product_key, product_label, category, sub_category
),
ranked AS (
    SELECT *, RANK() OVER (ORDER BY profit ASC) AS loss_rank FROM product
)
SELECT loss_rank, product_label, category, sub_category,
       ROUND(sales, 2) AS sales, ROUND(profit, 2) AS profit,
       ROUND(profit / sales, 4) AS profit_margin,
       ROUND(discount_amount / gross_sales, 4) AS effective_discount_rate,
       lines, loss_lines
FROM ranked
WHERE loss_rank <= 10
ORDER BY loss_rank;

-- query: Q13 | High-sales but low-profit products
-- covers: 25 High-sales but low-profit products
-- question: Which products sell well but earn little or lose money?
-- logic: "High sales" = top 20% of products by sales (NTILE(5) = 1).
-- logic: "Low profit" = margin below the company's overall margin. Both thresholds are relative to this data, not invented targets.
-- logic: Rows are labelled 'Loss-making' (profit < 0) or 'Below-average margin'.
-- use: Margin-leak list: products where revenue is already earned, so pricing or discount changes affect a large base.
WITH product AS (
    SELECT product_key, product_label, category, sub_category,
           SUM(sales) AS sales, SUM(profit) AS profit,
           SUM(discount_amount) AS discount_amount, SUM(gross_sales) AS gross_sales
    FROM vw_sales_line
    WHERE is_core_scope = 1
    GROUP BY product_key, product_label, category, sub_category
),
company AS (
    SELECT SUM(profit) / SUM(sales) AS company_margin
    FROM vw_sales_line WHERE is_core_scope = 1
),
classified AS (
    SELECT p.*,
           NTILE(5) OVER (ORDER BY p.sales DESC) AS sales_quintile,
           c.company_margin
    FROM product p CROSS JOIN company c
)
SELECT product_label, category, sub_category,
       ROUND(sales, 2)                            AS sales,
       ROUND(profit, 2)                           AS profit,
       ROUND(profit / sales, 4)                   AS profit_margin,
       ROUND(company_margin, 4)                   AS company_margin,
       ROUND(discount_amount / gross_sales, 4)    AS effective_discount_rate,
       CASE WHEN profit < 0 THEN 'Loss-making' ELSE 'Below-average margin' END AS issue_type
FROM classified
WHERE sales_quintile = 1
  AND profit / sales < company_margin
ORDER BY profit ASC;

-- query: Q14 | Sub-category portfolio quadrant (revenue vs margin)
-- covers: 25 High-sales/low-profit (sub-category view), and the reverse case: low sales, strong margin
-- question: Which sub-categories are stars, margin leaks, niche earners or review candidates?
-- logic: Thresholds: median sub-category sales (robust to one very large sub-category) and the company margin.
-- logic: SQLite has no MEDIAN(), so it is taken from the middle row(s) using ROW_NUMBER() and COUNT() OVER ().
-- logic: Comparisons use >=, so the median sub-category itself is classed as high-sales; treat it as a borderline case.
-- logic: Sub-category level is used because product-level margins rest on very few sales per product.
-- use: The 2x2 portfolio matrix for management: protect stars, fix margin leaks, consider growing niche earners.
WITH sub AS (
    SELECT category, sub_category, SUM(sales) AS sales, SUM(profit) AS profit
    FROM vw_sales_line
    WHERE is_core_scope = 1
    GROUP BY category, sub_category
),
median_sales AS (
    SELECT AVG(sales) AS median_sales
    FROM (SELECT sales,
                 ROW_NUMBER() OVER (ORDER BY sales) AS rn,
                 COUNT(*)     OVER ()              AS n
          FROM sub)
    WHERE rn IN ((n + 1) / 2, (n + 2) / 2)
),
company AS (
    SELECT SUM(profit) / SUM(sales) AS company_margin
    FROM vw_sales_line WHERE is_core_scope = 1
)
SELECT
    s.category,
    s.sub_category,
    ROUND(s.sales, 2)                    AS sales,
    ROUND(s.profit, 2)                   AS profit,
    ROUND(s.profit / s.sales, 4)         AS profit_margin,
    CASE
        WHEN s.sales >= m.median_sales AND s.profit / s.sales >= c.company_margin THEN 'Star: high sales, high margin'
        WHEN s.sales >= m.median_sales                                          THEN 'Margin leak: high sales, low margin'
        WHEN s.profit / s.sales >= c.company_margin                              THEN 'Niche earner: low sales, high margin'
        ELSE 'Review: low sales, low margin'
    END                                  AS portfolio_quadrant,
    ROUND(m.median_sales, 2)             AS median_sales_threshold,
    ROUND(c.company_margin, 4)           AS margin_threshold
FROM sub s CROSS JOIN median_sales m CROSS JOIN company c
ORDER BY portfolio_quadrant, s.sales DESC;
