# SQL Analytical Layer — Query Guide
_Generated from the headers in `sql/analysis/*.sql` by `scripts/run_phase3_sql_analysis.py`. Edit the SQL files, not this document._

**Scope of every query:** core scope (US order lines, suspected clone copies excluded). Customer queries additionally exclude placeholder and identity-anomaly customers.

| ID | Query | Covers | File |
|---|---|---|---|
| Q01 | Headline KPIs | 1 Total sales, 2 Total profit, 3 Total quantity, 4 Orders, 5 Customers, 6 Average order value, 7 Profit margin | `01_headline_kpis.sql` |
| Q02 | Sales and profit by year | 8 Sales by year, 10 Profit by year | `02_trends.sql` |
| Q03 | Sales and profit by month | 9 Sales by month, 11 Profit by month | `02_trends.sql` |
| Q04 | Seasonality: share of annual sales by calendar month | 9 Sales by month (seasonal pattern) | `02_trends.sql` |
| Q05 | Sales and profit by category | 12 Sales by category, 13 Profit by category | `03_product_hierarchy.sql` |
| Q06 | Sales and profit by sub-category | 14 Sales by sub-category, 15 Profit by sub-category | `03_product_hierarchy.sql` |
| Q07 | Sales and profit by region | 16 Sales by region, 17 Profit by region | `04_geography_and_segments.sql` |
| Q08 | Sales and profit by state | 18 Sales by state, 19 Profit by state | `04_geography_and_segments.sql` |
| Q09 | Sales and profit by customer segment | 20 Sales by customer segment, 21 Profit by customer segment | `04_geography_and_segments.sql` |
| Q10 | Top 10 products by sales | 22 Top products by sales | `05_products.sql` |
| Q11 | Top 10 products by profit | 23 Top products by profit | `05_products.sql` |
| Q12 | Bottom 10 products by profit | 24 Worst products by profit | `05_products.sql` |
| Q13 | High-sales but low-profit products | 25 High-sales but low-profit products | `05_products.sql` |
| Q14 | Sub-category portfolio quadrant (revenue vs margin) | 25 High-sales/low-profit (sub-category view), and the reverse case: low sales, strong margin | `05_products.sql` |
| Q15 | Profitability by discount band | 26 Discount vs profit | `06_discounts.sql` |
| Q16 | Profitability by exact discount level | 26 Discount vs profit (detail) | `06_discounts.sql` |
| Q17 | Discount band by category | 26 Discount vs profit (controlled for category) | `06_discounts.sql` |
| Q18 | Customer profitability table | 27 Customer profitability | `07_customers.sql` |
| Q19 | Customer profit by decile | 27 Customer profitability (concentration summary) | `07_customers.sql` |
| Q20 | Profitable vs unprofitable customers | 27 Customer profitability (headline) | `07_customers.sql` |
| Q21 | Repeat purchasing: customers by number of orders | 28 Repeat customer behaviour | `07_customers.sql` |
| Q22 | Year-over-year customer retention | 28 Repeat customer behaviour (over time) | `07_customers.sql` |

## Q01 — Headline KPIs
**Business question:** What is the overall size and profitability of the business over the full four dataset years?

**SQL logic:**
- One pass over the core-scope lines. Orders and customers use COUNT(DISTINCT) because one order has several lines.
- AOV = revenue / distinct orders; margin = total profit / total revenue (ratio of sums).
- Customers are shown twice: all active customers, and valid customers (placeholder and identity-anomaly customers excluded, DQ05/DQ06).

**How the result is used:** The baseline every other number is compared with: KPI cards on the executive page and the denominator for all "share of total" figures.

```sql
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
```

## Q02 — Sales and profit by year
**Business question:** Is the business growing, and is profit growing faster or slower than sales?

**SQL logic:**
- Aggregate by order year in a CTE, then LAG() over year for year-over-year growth.
- Profit growth is NULL when the prior-year profit is <= 0, because a % change from a non-positive base is misleading.
- Margin and AOV are recomputed from the yearly sums, not averaged from months.

**How the result is used:** Executive trend line and YoY KPI cards; tells management whether growth is profitable growth.

```sql
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
```

## Q03 — Sales and profit by month
**Business question:** How do sales and profit move month by month, and is each month better than the same month last year?

**SQL logic:**
- Aggregate by year-month. Same-month-last-year values come from LAG() partitioned by calendar month and ordered by year.
- Comparing with the same month last year removes seasonality, which a month-on-month comparison would not.

**How the result is used:** Monthly trend chart and the input for spotting months where profit fell while sales rose.

```sql
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
```

## Q04 — Seasonality: share of annual sales by calendar month
**Business question:** Which months carry the business, and is the pattern stable from year to year?

**SQL logic:**
- Each month's share of its own year's sales (window SUM over the year), then the average, minimum and maximum share across the four years.
- Shares, not amounts, are compared so that growth between years does not distort the seasonal pattern.

**How the result is used:** Planning context (stock, staffing, promotion timing) and for judging whether a weak month is seasonal or a real problem.

```sql
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
```

## Q05 — Sales and profit by category
**Business question:** Which categories generate revenue, which generate profit, and are those the same categories?

**SQL logic:**
- Aggregate by category; share of total via SUM() OVER () across the result; separate ranks for sales and profit.
- Showing sales share next to profit share exposes categories whose contribution to profit differs from their contribution to revenue.

**How the result is used:** Top-level portfolio view for the executive page; the starting point for drilling into sub-categories.

```sql
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
```

## Q06 — Sales and profit by sub-category
**Business question:** Which sub-categories create profit and which destroy it, and how large are their losses?

**SQL logic:**
- Aggregate by sub-category with shares and ranks, as for categories.
- loss_amount sums only loss-making lines, so a sub-category with a positive total can still reveal large hidden losses.

**How the result is used:** Identifies where the category results come from; feeds the portfolio quadrant (Q14) and the loss investigation.

```sql
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
```

## Q07 — Sales and profit by region
**Business question:** Which regions perform well or poorly, and does discounting differ between them?

**SQL logic:**
- Aggregate by region with its regional manager. The effective discount rate (discount given away / list value) is included,
- because a weak margin can come from heavier discounting rather than from the region itself; Phase 4 tests this properly.

**How the result is used:** Regional manager scorecard and the first filter for the geography page.

```sql
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
```

## Q08 — Sales and profit by state
**Business question:** Which states drive results, and which lose money?

**SQL logic:**
- Aggregate by state with ranks for sales and profit, and a cumulative share of total sales (Pareto) via a running window SUM.
- States with fewer than 30 orders are labelled 'Low volume': their margins rest on few transactions and must not be over-interpreted.

**How the result is used:** State ranking and map; the low-volume label prevents management from acting on statistical noise.

```sql
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
```

## Q09 — Sales and profit by customer segment
**Business question:** Which customer segment is most valuable, in total and per customer?

**SQL logic:**
- Aggregate by segment. "Valuable" is shown three ways: total profit, margin, and profit per customer.
- Per-customer figures use valid customers only, with numerator and denominator from the same population (DQ05/DQ06 excluded).

**How the result is used:** Segment comparison page; tells whether a segment is large because of many customers or because each customer is worth more.

```sql
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
```

## Q10 — Top 10 products by sales
**Business question:** Which individual products bring in the most revenue, and are they profitable?

**SQL logic:**
- Aggregate per product, RANK() by sales, keep rank <= 10 (RANK keeps ties instead of cutting them arbitrarily).
- Profit and margin are shown next to sales, because a top seller is not automatically a top earner.

**How the result is used:** Revenue-critical products to protect; any loss-making product in this list is an immediate investigation item.

```sql
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
```

## Q11 — Top 10 products by profit
**Business question:** Which products contribute the most profit?

**SQL logic:**
- Same product aggregate, ranked by profit instead of sales.

**How the result is used:** Compared with Q10, shows whether profit leaders and revenue leaders are the same products.

```sql
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
```

## Q12 — Bottom 10 products by profit
**Business question:** Which products lose the most money, and is discounting involved?

**SQL logic:**
- Rank by profit ascending. The effective discount rate and the number of loss-making lines are added
- to show whether the loss is systematic (every sale loses) or driven by a few deeply discounted orders.

**How the result is used:** The product-level loss investigation list for management.

```sql
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
```

## Q13 — High-sales but low-profit products
**Business question:** Which products sell well but earn little or lose money?

**SQL logic:**
- "High sales" = top 20% of products by sales (NTILE(5) = 1).
- "Low profit" = margin below the company's overall margin. Both thresholds are relative to this data, not invented targets.
- Rows are labelled 'Loss-making' (profit < 0) or 'Below-average margin'.

**How the result is used:** Margin-leak list: products where revenue is already earned, so pricing or discount changes affect a large base.

```sql
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
```

## Q14 — Sub-category portfolio quadrant (revenue vs margin)
**Business question:** Which sub-categories are stars, margin leaks, niche earners or review candidates?

**SQL logic:**
- Thresholds: median sub-category sales (robust to one very large sub-category) and the company margin.
- SQLite has no MEDIAN(), so it is taken from the middle row(s) using ROW_NUMBER() and COUNT() OVER ().
- Comparisons use >=, so the median sub-category itself is classed as high-sales; treat it as a borderline case.
- Sub-category level is used because product-level margins rest on very few sales per product.

**How the result is used:** The 2x2 portfolio matrix for management: protect stars, fix margin leaks, consider growing niche earners.

```sql
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
```

## Q15 — Profitability by discount band
**Business question:** How does profitability change as discounts get deeper?

**SQL logic:**
- Group order lines by the fixed discount bands from dim_discount (defined before analysis, not tuned to results).
- Margin is ratio-of-sums per band; loss_line_share shows how often a line at that discount loses money.

**How the result is used:** Core evidence for a discount policy discussion, e.g. where margin turns negative.

```sql
SELECT
    discount_band,
    COUNT(*)                                                AS lines,
    ROUND(COUNT(*) * 1.0 / SUM(COUNT(*)) OVER (), 4)        AS share_of_lines,
    ROUND(SUM(sales), 2)                                    AS sales,
    ROUND(SUM(sales) / SUM(SUM(sales)) OVER (), 4)          AS share_of_sales,
    ROUND(SUM(profit), 2)                                   AS profit,
    ROUND(SUM(profit) / SUM(sales), 4)                      AS profit_margin,
    ROUND(AVG(is_loss_line), 4)                             AS loss_line_share,
    ROUND(SUM(discount_amount), 2)                          AS discount_amount
FROM vw_sales_line
WHERE is_core_scope = 1
GROUP BY discount_band, discount_band_sort
ORDER BY discount_band_sort;
```

## Q16 — Profitability by exact discount level
**Business question:** At which exact discount level does a typical line stop being profitable?

**SQL logic:**
- Same measures at each of the observed discount levels. Bands can hide a break point inside a band.
- Levels with few lines are kept but should be read with their line count.

**How the result is used:** Pinpoints the threshold for a potential discount cap; read together with the line counts.

```sql
SELECT
    discount_label,
    discount_rate,
    COUNT(*)                                    AS lines,
    ROUND(SUM(sales), 2)                        AS sales,
    ROUND(SUM(profit), 2)                       AS profit,
    ROUND(SUM(profit) / SUM(sales), 4)          AS profit_margin,
    ROUND(AVG(is_loss_line), 4)                 AS loss_line_share
FROM vw_sales_line
WHERE is_core_scope = 1
GROUP BY discount_label, discount_rate
ORDER BY discount_rate;
```

## Q17 — Discount band by category
**Business question:** Does the discount-profit relationship hold inside each category, or is it caused by which categories get discounted?

**SQL logic:**
- Same band measures split by category, plus each band's share of the category's sales (window SUM per category).
- If margin falls with discount inside every category, product mix alone cannot explain the pattern.

**How the result is used:** Separates "discounting hurts" from "we discount the wrong categories" before any recommendation is made.

```sql
SELECT
    category,
    discount_band,
    COUNT(*)                                                                    AS lines,
    ROUND(SUM(sales), 2)                                                        AS sales,
    ROUND(SUM(sales) / SUM(SUM(sales)) OVER (PARTITION BY category), 4)         AS share_of_category_sales,
    ROUND(SUM(profit), 2)                                                       AS profit,
    ROUND(SUM(profit) / SUM(sales), 4)                                          AS profit_margin
FROM vw_sales_line
WHERE is_core_scope = 1
GROUP BY category, discount_band, discount_band_sort
ORDER BY category, discount_band_sort;
```

## Q18 — Customer profitability table
**Business question:** How much profit does each customer generate, and how concentrated is profit among customers?

**SQL logic:**
- Aggregate per customer. Cumulative profit share uses a running window SUM ordered by profit (Pareto curve).
- Customers with negative profit pull the cumulative share above 100% before the tail brings it back to 100%.

**How the result is used:** Customer-level drill-down and source for the Pareto chart; the full table is exported for Excel and Power BI.

```sql
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
```

## Q19 — Customer profit by decile
**Business question:** How much of total profit comes from the best 10%, 20%... of customers, and where are the unprofitable ones?

**SQL logic:**
- NTILE(10) splits customers into ten equal-count groups by profit (decile 1 = most profitable).
- Each decile's profit share and the running cumulative share; unprofitable customers are counted per decile.

**How the result is used:** The concentration story in one table: how dependent the business is on its best customers.

```sql
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
```

## Q20 — Profitable vs unprofitable customers
**Business question:** How many customers lose money for the company over the four years, and how much do they cost?

**SQL logic:**
- Classify each customer by the sign of their total profit, then aggregate the two groups.

**How the result is used:** Headline figure for the customer section and the size of the unprofitable-customer problem.

```sql
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
```

## Q21 — Repeat purchasing: customers by number of orders
**Business question:** Do customers come back, and how much of the business comes from frequent buyers?

**SQL logic:**
- Count distinct orders per customer over the four years, then group into frequency bands.
- The band sort key keeps the bands in business order rather than alphabetical order.

**How the result is used:** Shows reliance on repeat buyers vs one-off buyers; informs retention vs acquisition focus.

```sql
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
```

## Q22 — Year-over-year customer retention
**Business question:** Of the customers who bought in one year, what share bought again the following year?

**SQL logic:**
- Build the distinct set of (customer, year) pairs, then LEFT JOIN each pair to the same customer in year + 1.
- The last data year has no following year, so it is excluded rather than shown as 0% retention.

**How the result is used:** Retention trend; a falling rate would signal a customer-loyalty problem even while revenue grows.

```sql
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
```