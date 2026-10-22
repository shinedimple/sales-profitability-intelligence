/* ==========================================================================
   07_customers.sql  -  customer profitability and repeat behaviour

   Scope: core lines AND valid customers only
          (is_excluded_from_customer_analysis = 0 removes DQ05/DQ06 customers).
   Limitation: history starts in 2023 (left-censored). We cannot tell whether a
   customer seen first in 2023 is new or long-standing, so no "new customer"
   or lifetime-value metrics are produced.
   ========================================================================== */

-- query: Q18 | Customer profitability table
-- covers: 27 Customer profitability
-- question: How much profit does each customer generate, and how concentrated is profit among customers?
-- logic: Aggregate per customer. Cumulative profit share uses a running window SUM ordered by profit (Pareto curve).
-- logic: Customers with negative profit pull the cumulative share above 100% before the tail brings it back to 100%.
-- use: Customer-level drill-down and source for the Pareto chart; the full table is exported for Excel and Power BI.
WITH customer AS (
    SELECT customer_id, customer_name, segment,
           COUNT(DISTINCT order_id) AS orders,
           SUM(sales)               AS sales,
           SUM(profit)              AS profit
    FROM vw_sales_line
    WHERE is_core_scope = 1 AND is_excluded_from_customer_analysis = 0
    GROUP BY customer_id, customer_name, segment
)
SELECT
    RANK() OVER (ORDER BY profit DESC)                         AS profit_rank,
    customer_id, customer_name, segment, orders,
    ROUND(sales, 2)                                            AS sales,
    ROUND(profit, 2)                                           AS profit,
    ROUND(profit / sales, 4)                                   AS profit_margin,
    ROUND(SUM(profit) OVER (ORDER BY profit DESC ROWS UNBOUNDED PRECEDING)
          / SUM(profit) OVER (), 4)                            AS cumulative_share_of_profit
FROM customer
ORDER BY profit DESC;

-- query: Q19 | Customer profit by decile
-- covers: 27 Customer profitability (concentration summary)
-- question: How much of total profit comes from the best 10%, 20%... of customers, and where are the unprofitable ones?
-- logic: NTILE(10) splits customers into ten equal-count groups by profit (decile 1 = most profitable).
-- logic: Each decile's profit share and the running cumulative share; unprofitable customers are counted per decile.
-- use: The concentration story in one table: how dependent the business is on its best customers.
WITH customer AS (
    SELECT customer_id, SUM(sales) AS sales, SUM(profit) AS profit
    FROM vw_sales_line
    WHERE is_core_scope = 1 AND is_excluded_from_customer_analysis = 0
    GROUP BY customer_id
),
deciles AS (
    SELECT *, NTILE(10) OVER (ORDER BY profit DESC) AS profit_decile FROM customer
),
summary AS (
    SELECT profit_decile,
           COUNT(*)                                  AS customers,
           SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END) AS unprofitable_customers,
           SUM(sales)                                AS sales,
           SUM(profit)                               AS profit,
           MIN(profit)                               AS min_customer_profit,
           MAX(profit)                               AS max_customer_profit
    FROM deciles
    GROUP BY profit_decile
)
SELECT
    profit_decile,
    customers,
    unprofitable_customers,
    ROUND(sales, 2)                                                  AS sales,
    ROUND(profit, 2)                                                 AS profit,
    ROUND(profit / SUM(profit) OVER (), 4)                           AS share_of_profit,
    ROUND(SUM(profit) OVER (ORDER BY profit_decile) / SUM(profit) OVER (), 4) AS cumulative_share_of_profit,
    ROUND(min_customer_profit, 2)                                    AS min_customer_profit,
    ROUND(max_customer_profit, 2)                                    AS max_customer_profit
FROM summary
ORDER BY profit_decile;

-- query: Q20 | Profitable vs unprofitable customers
-- covers: 27 Customer profitability (headline)
-- question: How many customers lose money for the company over the four years, and how much do they cost?
-- logic: Classify each customer by the sign of their total profit, then aggregate the two groups.
-- use: Headline figure for the customer section and the size of the unprofitable-customer problem.
WITH customer AS (
    SELECT customer_id, SUM(sales) AS sales, SUM(profit) AS profit
    FROM vw_sales_line
    WHERE is_core_scope = 1 AND is_excluded_from_customer_analysis = 0
    GROUP BY customer_id
)
SELECT
    CASE WHEN profit >= 0 THEN 'Profitable' ELSE 'Unprofitable' END    AS customer_status,
    COUNT(*)                                                           AS customers,
    ROUND(COUNT(*) * 1.0 / SUM(COUNT(*)) OVER (), 4)                   AS share_of_customers,
    ROUND(SUM(sales), 2)                                               AS sales,
    ROUND(SUM(sales) / SUM(SUM(sales)) OVER (), 4)                     AS share_of_sales,
    ROUND(SUM(profit), 2)                                              AS profit
FROM customer
GROUP BY customer_status
ORDER BY customer_status;

-- query: Q21 | Repeat purchasing: customers by number of orders
-- covers: 28 Repeat customer behaviour
-- question: Do customers come back, and how much of the business comes from frequent buyers?
-- logic: Count distinct orders per customer over the four years, then group into frequency bands.
-- logic: The band sort key keeps the bands in business order rather than alphabetical order.
-- use: Shows reliance on repeat buyers vs one-off buyers; informs retention vs acquisition focus.
WITH customer AS (
    SELECT customer_id,
           COUNT(DISTINCT order_id) AS orders,
           SUM(sales)               AS sales,
           SUM(profit)              AS profit
    FROM vw_sales_line
    WHERE is_core_scope = 1 AND is_excluded_from_customer_analysis = 0
    GROUP BY customer_id
),
banded AS (
    SELECT *,
           CASE WHEN orders = 1  THEN '1 order'
                WHEN orders <= 3 THEN '2-3 orders'
                WHEN orders <= 6 THEN '4-6 orders'
                WHEN orders <= 10 THEN '7-10 orders'
                ELSE '11+ orders' END                            AS order_frequency_band,
           CASE WHEN orders = 1  THEN 1 WHEN orders <= 3 THEN 2
                WHEN orders <= 6 THEN 3 WHEN orders <= 10 THEN 4 ELSE 5 END AS band_sort
    FROM customer
)
SELECT
    order_frequency_band,
    COUNT(*)                                                     AS customers,
    ROUND(COUNT(*) * 1.0 / SUM(COUNT(*)) OVER (), 4)             AS share_of_customers,
    ROUND(SUM(sales) / SUM(SUM(sales)) OVER (), 4)               AS share_of_sales,
    ROUND(SUM(profit) / SUM(SUM(profit)) OVER (), 4)             AS share_of_profit,
    ROUND(SUM(profit) / COUNT(*), 2)                             AS profit_per_customer
FROM banded
GROUP BY order_frequency_band, band_sort
ORDER BY band_sort;

-- query: Q22 | Year-over-year customer retention
-- covers: 28 Repeat customer behaviour (over time)
-- question: Of the customers who bought in one year, what share bought again the following year?
-- logic: Build the distinct set of (customer, year) pairs, then LEFT JOIN each pair to the same customer in year + 1.
-- logic: The last data year has no following year, so it is excluded rather than shown as 0% retention.
-- use: Retention trend; a falling rate would signal a customer-loyalty problem even while revenue grows.
WITH customer_year AS (
    SELECT DISTINCT customer_id, order_year
    FROM vw_sales_line
    WHERE is_core_scope = 1 AND is_excluded_from_customer_analysis = 0
),
last_year AS (
    SELECT MAX(order_year) AS max_year FROM customer_year
)
SELECT
    cy.order_year                                                AS base_year,
    COUNT(*)                                                     AS active_customers,
    COUNT(nxt.customer_id)                                       AS retained_next_year,
    ROUND(COUNT(nxt.customer_id) * 1.0 / COUNT(*), 4)            AS retention_rate
FROM customer_year cy
LEFT JOIN customer_year nxt
       ON nxt.customer_id = cy.customer_id
      AND nxt.order_year  = cy.order_year + 1
CROSS JOIN last_year ly
WHERE cy.order_year < ly.max_year
GROUP BY cy.order_year
ORDER BY cy.order_year;
