/* ==========================================================================
   04_analysis_views.sql  -  reusable views for analysis and KPI reconciliation

   Views hold LOGIC, not stored results: they are recalculated on every query,
   so they can never go stale when the model is rebuilt.
   ========================================================================== */

-- --------------------------------------------------------------------------
-- vw_sales_line: the star schema flattened back to one row per order line.
-- Convenient for ad-hoc SQL and Python analysis (Phase 3/4).
-- --------------------------------------------------------------------------
CREATE VIEW vw_sales_line AS
SELECT
    f.sales_line_id, f.order_id,
    od.date            AS order_date,  od.year AS order_year, od.quarter AS order_quarter,
    od.month           AS order_month, od.month_short AS order_month_name,
    od.year_month      AS order_year_month,
    sd.date            AS ship_date,
    c.customer_id, c.customer_name, c.segment, c.is_excluded_from_customer_analysis,
    p.product_key, p.product_id, p.product_name, p.product_label, p.category, p.sub_category,
    l.country, l.region, l.regional_manager, l.state_province, l.city, l.city_state, l.postal_code,
    sm.ship_mode, sm.service_level_rank,
    dc.discount_label, dc.discount_band, dc.discount_band_sort,
    f.sales, f.quantity, f.discount_rate, f.profit, f.gross_sales, f.discount_amount,
    f.days_to_ship, f.implied_list_margin, f.is_beyond_break_even,
    f.is_loss_line, f.is_returned_order, f.is_core_scope,
    f.dq_is_clone_copy, f.dq_is_price_anomaly, f.dq_is_value_copy_suspect,
    f.dq_is_sales_outlier, f.dq_is_profit_outlier
FROM fct_sales f
JOIN dim_date      od ON od.date_key = f.order_date_key
JOIN dim_date      sd ON sd.date_key = f.ship_date_key
JOIN dim_customer  c  ON c.customer_key = f.customer_key
JOIN dim_product   p  ON p.product_key = f.product_key
JOIN dim_location  l  ON l.location_key = f.location_key
JOIN dim_ship_mode sm ON sm.ship_mode_key = f.ship_mode_key
JOIN dim_discount  dc ON dc.discount_key = f.discount_key;

-- --------------------------------------------------------------------------
-- vw_order_summary: ORDER grain (one row per order). Needed for order-level
-- questions (basket size, AOV distribution, shipping time) without the
-- line-weighting error of averaging line-level values.
-- --------------------------------------------------------------------------
CREATE VIEW vw_order_summary AS
SELECT
    f.order_id,
    MIN(od.date)               AS order_date,
    MIN(od.year)               AS order_year,
    MIN(f.customer_key)        AS customer_key,
    MIN(f.ship_mode_key)       AS ship_mode_key,
    MAX(f.days_to_ship)        AS days_to_ship,       -- identical on all lines of an order
    MAX(f.is_returned_order)   AS is_returned_order,
    MIN(f.is_core_scope)       AS is_core_scope,
    COUNT(*)                   AS order_lines,
    COUNT(DISTINCT f.product_key) AS distinct_products,
    SUM(f.quantity)            AS units,
    SUM(f.sales)               AS order_revenue,
    SUM(f.profit)              AS order_profit,
    SUM(f.discount_amount)     AS order_discount_amount,
    SUM(f.gross_sales)         AS order_gross_sales
FROM fct_sales f
JOIN dim_date od ON od.date_key = f.order_date_key
GROUP BY f.order_id;

-- --------------------------------------------------------------------------
-- vw_kpi_by_year: the official KPI definitions in SQL, by order year and
-- scope. This is the reference that Power BI/DAX results must reconcile to.
-- --------------------------------------------------------------------------
CREATE VIEW vw_kpi_by_year AS
WITH scopes AS (
    SELECT 'Core scope'    AS scope, 1 AS core_only
    UNION ALL
    SELECT 'All countries' AS scope, 0 AS core_only
),
base AS (
    SELECT s.scope, d.year, f.*, c.is_excluded_from_customer_analysis AS excl
    FROM fct_sales f
    JOIN dim_date d     ON d.date_key = f.order_date_key
    JOIN dim_customer c ON c.customer_key = f.customer_key
    JOIN scopes s       ON s.core_only = 0 OR f.is_core_scope = 1
),
yearly AS (
    SELECT
        scope,
        year,
        SUM(sales)                                          AS revenue,
        SUM(profit)                                         AS profit,
        COUNT(DISTINCT order_id)                            AS orders,
        COUNT(DISTINCT customer_key)                        AS customers,
        COUNT(DISTINCT CASE WHEN excl = 0 THEN customer_key END) AS valid_customers,
        SUM(CASE WHEN excl = 0 THEN profit ELSE 0 END)      AS valid_customer_profit,
        SUM(quantity)                                       AS units_sold,
        SUM(discount_amount)                                AS discount_amount,
        SUM(gross_sales)                                    AS gross_sales,
        AVG(discount_rate)                                  AS avg_line_discount_rate
    FROM base
    GROUP BY scope, year
)
SELECT
    scope,
    year,
    ROUND(revenue, 2)                                       AS revenue,
    ROUND(profit, 2)                                        AS profit,
    ROUND(profit / revenue, 4)                              AS profit_margin,
    orders,
    customers,
    valid_customers,
    units_sold,
    ROUND(revenue / orders, 2)                              AS avg_order_value,
    ROUND(discount_amount / gross_sales, 4)                 AS effective_discount_rate,
    ROUND(avg_line_discount_rate, 4)                        AS avg_line_discount_rate,
    ROUND(profit / orders, 2)                               AS profit_per_order,
    ROUND(valid_customer_profit / valid_customers, 2)       AS profit_per_customer,
    -- growth only against the immediately preceding year (guards against gaps)
    CASE WHEN LAG(year) OVER w = year - 1
         THEN ROUND(revenue / LAG(revenue) OVER w - 1, 4) END AS revenue_growth_yoy,
    CASE WHEN LAG(year) OVER w = year - 1
          AND LAG(profit) OVER w > 0                        -- growth % is meaningless
         THEN ROUND(profit / LAG(profit) OVER w - 1, 4)     -- when the base is <= 0
    END                                                     AS profit_growth_yoy
FROM yearly
WINDOW w AS (PARTITION BY scope ORDER BY year);
