/* ==========================================================================
   05_model_tests.sql  -  data tests for the star schema

   Format: each test starts with a line "-- test: <name>" followed by ONE
   SELECT that returns a single column "failures". A test passes when
   failures = 0. The runner executes every test and stops the build on failure.
   ========================================================================== */

-- test: fact grain - one fact row per staging row
SELECT ABS((SELECT COUNT(*) FROM fct_sales) - (SELECT COUNT(*) FROM stg_orders)) AS failures;

-- test: fact grain - sales_line_id is unique
SELECT COUNT(*) - COUNT(DISTINCT sales_line_id) AS failures FROM fct_sales;

-- test: reconciliation - revenue equals staging
SELECT CASE WHEN ABS((SELECT SUM(sales) FROM fct_sales) - (SELECT SUM(sales) FROM stg_orders)) < 1e-6
            THEN 0 ELSE 1 END AS failures;

-- test: reconciliation - profit equals staging
SELECT CASE WHEN ABS((SELECT SUM(profit) FROM fct_sales) - (SELECT SUM(profit) FROM stg_orders)) < 1e-6
            THEN 0 ELSE 1 END AS failures;

-- test: reconciliation - units equal staging
SELECT ABS((SELECT SUM(quantity) FROM fct_sales) - (SELECT SUM(quantity) FROM stg_orders)) AS failures;

-- test: reconciliation - distinct orders equal staging
SELECT ABS((SELECT COUNT(DISTINCT order_id) FROM fct_sales)
         - (SELECT COUNT(DISTINCT order_id) FROM stg_orders)) AS failures;

-- test: integrity - no orphan customer keys
SELECT COUNT(*) AS failures FROM fct_sales f
LEFT JOIN dim_customer d ON d.customer_key = f.customer_key WHERE d.customer_key IS NULL;

-- test: integrity - no orphan product keys
SELECT COUNT(*) AS failures FROM fct_sales f
LEFT JOIN dim_product d ON d.product_key = f.product_key WHERE d.product_key IS NULL;

-- test: integrity - no orphan location keys
SELECT COUNT(*) AS failures FROM fct_sales f
LEFT JOIN dim_location d ON d.location_key = f.location_key WHERE d.location_key IS NULL;

-- test: integrity - no orphan order or ship dates
SELECT COUNT(*) AS failures FROM fct_sales f
LEFT JOIN dim_date o ON o.date_key = f.order_date_key
LEFT JOIN dim_date s ON s.date_key = f.ship_date_key
WHERE o.date_key IS NULL OR s.date_key IS NULL;

-- test: dim_date - continuous calendar (no missing days)
SELECT (CAST(julianday(MAX(date)) - julianday(MIN(date)) AS INTEGER) + 1) - COUNT(*) AS failures
FROM dim_date;

-- test: dim_date - starts 1 Jan and ends 31 Dec (complete years for time intelligence)
SELECT (CASE WHEN strftime('%m-%d', MIN(date)) = '01-01' THEN 0 ELSE 1 END)
     + (CASE WHEN strftime('%m-%d', MAX(date)) = '12-31' THEN 0 ELSE 1 END) AS failures
FROM dim_date;

-- test: dim_customer - one name and one segment per customer in staging
SELECT COUNT(*) AS failures FROM (
    SELECT customer_id FROM stg_orders GROUP BY customer_id
    HAVING COUNT(DISTINCT customer_name) > 1 OR COUNT(DISTINCT segment) > 1);

-- test: dim_customer - customer flags constant across a customer's lines
SELECT COUNT(*) AS failures FROM (
    SELECT customer_id FROM stg_orders GROUP BY customer_id
    HAVING COUNT(DISTINCT exclude_from_customer_analysis) > 1);

-- test: dim_product - one category and sub-category per product
SELECT COUNT(*) AS failures FROM (
    SELECT product_id FROM stg_orders GROUP BY product_id
    HAVING COUNT(DISTINCT category) > 1 OR COUNT(DISTINCT sub_category) > 1);

-- test: dim_location - one region per location and every region has a manager
SELECT (SELECT COUNT(*) FROM (
            SELECT country, state_province, city, postal_code FROM stg_orders
            GROUP BY 1, 2, 3, 4 HAVING COUNT(DISTINCT region) > 1))
     + (SELECT COUNT(*) FROM dim_location WHERE regional_manager IS NULL) AS failures;

-- test: dim_ship_mode - every ship mode has a service level rank
SELECT COUNT(*) AS failures FROM dim_ship_mode WHERE service_level_rank IS NULL;

-- test: dim_discount - all levels within the defined band range (0 to 80%)
SELECT COUNT(*) AS failures FROM dim_discount WHERE discount_rate < 0 OR discount_rate > 0.80;

-- test: derived - gross_sales >= sales and discount_amount >= 0
SELECT COUNT(*) AS failures FROM fct_sales
WHERE gross_sales < sales - 1e-9 OR discount_amount < -1e-9;

-- test: derived - gross_sales minus discount_amount equals sales
SELECT COUNT(*) AS failures FROM fct_sales
WHERE ABS(gross_sales - discount_amount - sales) > 1e-6;

-- test: derived - order-level attributes identical on every line of an order
SELECT COUNT(*) AS failures FROM (
    SELECT order_id FROM fct_sales GROUP BY order_id
    HAVING COUNT(DISTINCT order_date_key) > 1 OR COUNT(DISTINCT days_to_ship) > 1
        OR COUNT(DISTINCT is_returned_order) > 1 OR COUNT(DISTINCT customer_key) > 1
        AND MAX(customer_key) NOT IN (SELECT customer_key FROM dim_customer
                                      WHERE is_identity_anomaly = 1));

-- test: returns - every returned order is flagged in the fact table
SELECT (SELECT COUNT(DISTINCT order_id) FROM stg_returns WHERE is_returned = 1)
     - (SELECT COUNT(DISTINCT order_id) FROM fct_sales WHERE is_returned_order = 1) AS failures;

-- test: scope - every clone copy is outside the core scope
SELECT COUNT(*) AS failures FROM fct_sales WHERE dq_is_clone_copy = 1 AND is_core_scope = 1;

-- test: break-even - implied list margin is constant within each product (core scope)
-- (Canadian rows are excluded from core scope; their margins do not follow the same
--  cost structure, which is further evidence for DQ18.)
SELECT COUNT(*) AS failures FROM (
    SELECT product_key FROM fct_sales WHERE is_core_scope = 1 GROUP BY product_key
    HAVING MAX(implied_list_margin) - MIN(implied_list_margin) > 1e-9);
