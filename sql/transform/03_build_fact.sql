/* ==========================================================================
   03_build_fact.sql  -  staging  ->  fct_sales

   Grain: one order line (source row_id). Every staging row produces exactly
   one fact row; all joins are to dimensions on their natural keys, so an
   INNER JOIN that dropped a row would be caught by the reconciliation tests.
   ========================================================================== */

INSERT INTO fct_sales
SELECT
    o.row_id                                                     AS sales_line_id,
    o.order_id,
    CAST(strftime('%Y%m%d', o.order_date) AS INTEGER)            AS order_date_key,
    CAST(strftime('%Y%m%d', o.ship_date)  AS INTEGER)            AS ship_date_key,
    c.customer_key,
    p.product_key,
    l.location_key,
    sm.ship_mode_key,
    d.discount_key,

    -- source measures
    o.sales,
    o.quantity,
    o.discount                                                   AS discount_rate,
    o.profit,

    -- derived measures
    o.sales / (1.0 - o.discount)                                 AS gross_sales,
    o.sales / (1.0 - o.discount) - o.sales                       AS discount_amount,
    CAST(julianday(o.ship_date) - julianday(o.order_date) AS INTEGER) AS days_to_ship,
    1.0 - (1.0 - o.profit / o.sales) * (1.0 - o.discount)        AS implied_list_margin,

    -- flags
    CASE WHEN o.profit < 0 THEN 1 ELSE 0 END                     AS is_loss_line,
    CASE WHEN r.order_id IS NOT NULL THEN 1 ELSE 0 END           AS is_returned_order,
    CASE WHEN o.discount > 1.0 - (1.0 - o.profit / o.sales) * (1.0 - o.discount) + 1e-9
         THEN 1 ELSE 0 END                                       AS is_beyond_break_even,
    -- core scope = configured countries, never including suspected clone copies (DQ18)
    CASE WHEN o.country IN (SELECT value FROM stg_parameters
                            WHERE name = 'core_scope_country')
          AND o.dq_is_clone_copy = 0
         THEN 1 ELSE 0 END                                       AS is_core_scope,
    o.dq_is_clone_copy,
    o.dq_is_price_anomaly,
    o.dq_is_value_copy_suspect,
    o.dq_is_sales_outlier,
    o.dq_is_profit_outlier
FROM stg_orders AS o
JOIN dim_customer  AS c  ON c.customer_id = o.customer_id
JOIN dim_product   AS p  ON p.product_id = o.product_id AND p.product_name = o.product_name
JOIN dim_location  AS l  ON l.country = o.country
                        AND l.state_province = o.state_province
                        AND l.city = o.city
                        AND l.postal_code = o.postal_code
JOIN dim_ship_mode AS sm ON sm.ship_mode = o.ship_mode
JOIN dim_discount  AS d  ON d.discount_key = CAST(ROUND(o.discount * 100) AS INTEGER)
LEFT JOIN (SELECT DISTINCT order_id FROM stg_returns WHERE is_returned = 1) AS r
       ON r.order_id = o.order_id;
