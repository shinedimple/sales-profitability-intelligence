/* ==========================================================================
   02_build_dimensions.sql  -  staging  ->  dimensions

   Inputs (loaded by scripts/run_phase2_build_model.py from data/processed):
     stg_orders              clean order lines (Phase 1 output)
     stg_returns             returned order IDs
     stg_regional_managers   region -> manager
     stg_parameters          run parameters (e.g. core-scope countries)

   Surrogate keys are generated with ROW_NUMBER() over the sorted natural key,
   so the same input always produces the same keys (deterministic builds).
   ========================================================================== */

-- --------------------------------------------------------------------------
-- dim_date: continuous calendar from 1 Jan of the first order year to
-- 31 Dec of the last ship year (ship dates run into the following year).
-- --------------------------------------------------------------------------
INSERT INTO dim_date
WITH RECURSIVE bounds AS (
    SELECT date(MIN(order_date), 'start of year')                         AS first_day,
           date(MAX(ship_date), 'start of year', '+1 year', '-1 day')     AS last_day
    FROM stg_orders
),
calendar(d) AS (
    SELECT first_day FROM bounds
    UNION ALL
    SELECT date(d, '+1 day') FROM calendar, bounds WHERE d < bounds.last_day
)
SELECT
    CAST(strftime('%Y%m%d', d) AS INTEGER)                        AS date_key,
    d                                                             AS date,
    CAST(strftime('%Y', d) AS INTEGER)                            AS year,
    (CAST(strftime('%m', d) AS INTEGER) + 2) / 3                  AS quarter,
    'Q' || ((CAST(strftime('%m', d) AS INTEGER) + 2) / 3)         AS quarter_label,
    strftime('%Y', d) || '-Q' || ((CAST(strftime('%m', d) AS INTEGER) + 2) / 3) AS year_quarter,
    CAST(strftime('%m', d) AS INTEGER)                            AS month,
    CASE strftime('%m', d)
        WHEN '01' THEN 'January'  WHEN '02' THEN 'February' WHEN '03' THEN 'March'
        WHEN '04' THEN 'April'    WHEN '05' THEN 'May'      WHEN '06' THEN 'June'
        WHEN '07' THEN 'July'     WHEN '08' THEN 'August'   WHEN '09' THEN 'September'
        WHEN '10' THEN 'October'  WHEN '11' THEN 'November' ELSE 'December' END AS month_name,
    CASE strftime('%m', d)
        WHEN '01' THEN 'Jan' WHEN '02' THEN 'Feb' WHEN '03' THEN 'Mar' WHEN '04' THEN 'Apr'
        WHEN '05' THEN 'May' WHEN '06' THEN 'Jun' WHEN '07' THEN 'Jul' WHEN '08' THEN 'Aug'
        WHEN '09' THEN 'Sep' WHEN '10' THEN 'Oct' WHEN '11' THEN 'Nov' ELSE 'Dec' END AS month_short,
    strftime('%Y-%m', d)                                          AS year_month,
    date(d, 'start of month')                                     AS month_start_date,
    CAST(strftime('%d', d) AS INTEGER)                            AS day_of_month,
    ((CAST(strftime('%w', d) AS INTEGER) + 6) % 7) + 1            AS day_of_week,  -- ISO: Mon=1
    CASE strftime('%w', d)
        WHEN '1' THEN 'Monday' WHEN '2' THEN 'Tuesday' WHEN '3' THEN 'Wednesday'
        WHEN '4' THEN 'Thursday' WHEN '5' THEN 'Friday' WHEN '6' THEN 'Saturday'
        ELSE 'Sunday' END                                         AS day_name,
    CASE WHEN strftime('%w', d) IN ('0', '6') THEN 1 ELSE 0 END   AS is_weekend
FROM calendar;

-- --------------------------------------------------------------------------
-- dim_customer: one row per customer_id. Phase 1 verified that each customer
-- has exactly one name and one segment, and that DQ flags are constant per
-- customer, so MAX() simply carries the flag (tests re-verify this).
-- --------------------------------------------------------------------------
INSERT INTO dim_customer
SELECT
    ROW_NUMBER() OVER (ORDER BY customer_id)          AS customer_key,
    customer_id,
    MIN(customer_name)                                AS customer_name,
    MIN(segment)                                      AS segment,
    MAX(dq_is_placeholder_customer)                   AS is_placeholder_customer,
    MAX(dq_is_identity_anomaly)                       AS is_identity_anomaly,
    MAX(exclude_from_customer_analysis)               AS is_excluded_from_customer_analysis
FROM stg_orders
GROUP BY customer_id;

-- --------------------------------------------------------------------------
-- dim_product: key on (product_id, product_name) because product_id is reused
-- for different names in the source (DQ07). Hierarchy is constant per product_id.
-- --------------------------------------------------------------------------
INSERT INTO dim_product
SELECT
    ROW_NUMBER() OVER (ORDER BY product_id, product_name)   AS product_key,
    product_id,
    product_name,
    product_name || ' [' || product_id || ']'               AS product_label,
    MIN(sub_category)                                       AS sub_category,
    MIN(category)                                           AS category
FROM stg_orders
GROUP BY product_id, product_name;

-- --------------------------------------------------------------------------
-- dim_location: ship-to location. Region depends on state (verified 1:1);
-- the regional manager is denormalised from the People sheet.
-- --------------------------------------------------------------------------
INSERT INTO dim_location
SELECT
    ROW_NUMBER() OVER (ORDER BY o.country, o.state_province, o.city, o.postal_code) AS location_key,
    o.country,
    o.region,
    m.regional_manager,
    o.state_province,
    o.city,
    o.city || ', ' || o.state_province        AS city_state,
    o.postal_code
FROM (
    SELECT country, state_province, city, postal_code, MIN(region) AS region
    FROM stg_orders
    GROUP BY country, state_province, city, postal_code
) AS o
JOIN stg_regional_managers AS m ON m.region = o.region;

-- --------------------------------------------------------------------------
-- dim_ship_mode: business service-level order (fastest first)
-- --------------------------------------------------------------------------
INSERT INTO dim_ship_mode
SELECT
    ROW_NUMBER() OVER (ORDER BY rank)  AS ship_mode_key,
    ship_mode,
    rank                               AS service_level_rank
FROM (
    SELECT DISTINCT ship_mode,
           CASE ship_mode
               WHEN 'Same Day'       THEN 1
               WHEN 'First Class'    THEN 2
               WHEN 'Second Class'   THEN 3
               WHEN 'Standard Class' THEN 4
           END AS rank
    FROM stg_orders
);

-- --------------------------------------------------------------------------
-- dim_discount: observed discount levels -> fixed 20-point bands
-- --------------------------------------------------------------------------
INSERT INTO dim_discount
SELECT
    CAST(ROUND(discount * 100) AS INTEGER)                         AS discount_key,
    discount                                                       AS discount_rate,
    CAST(ROUND(discount * 100) AS INTEGER) || '%'                  AS discount_label,
    CASE WHEN ROUND(discount, 4) = 0     THEN 'No discount'
         WHEN ROUND(discount, 4) <= 0.20 THEN '1-20%'
         WHEN ROUND(discount, 4) <= 0.40 THEN '21-40%'
         WHEN ROUND(discount, 4) <= 0.60 THEN '41-60%'
         ELSE '61-80%' END                                         AS discount_band,
    CASE WHEN ROUND(discount, 4) = 0     THEN 1
         WHEN ROUND(discount, 4) <= 0.20 THEN 2
         WHEN ROUND(discount, 4) <= 0.40 THEN 3
         WHEN ROUND(discount, 4) <= 0.60 THEN 4
         ELSE 5 END                                                AS discount_band_sort
FROM (SELECT DISTINCT discount FROM stg_orders);
