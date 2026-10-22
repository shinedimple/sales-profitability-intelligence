/* ==========================================================================
   Sales & Profitability Intelligence System
   01_create_schema.sql  -  star schema table definitions (SQLite dialect)

   Conventions
     dim_*   dimension tables: descriptive attributes, one row per member
     fct_*   fact tables: numeric events at a declared grain
     *_key   surrogate keys (integers generated in the warehouse)
     *_id    natural / business keys from the source system
     is_*    boolean flags stored as INTEGER 0/1 (SQLite has no BOOLEAN)

   The script is idempotent: running it again rebuilds the model from scratch.
   ========================================================================== */

PRAGMA foreign_keys = ON;

DROP VIEW  IF EXISTS vw_kpi_by_year;
DROP VIEW  IF EXISTS vw_order_summary;
DROP VIEW  IF EXISTS vw_sales_line;
DROP TABLE IF EXISTS fct_sales;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_customer;
DROP TABLE IF EXISTS dim_product;
DROP TABLE IF EXISTS dim_location;
DROP TABLE IF EXISTS dim_ship_mode;
DROP TABLE IF EXISTS dim_discount;

-- --------------------------------------------------------------------------
-- dim_date: one row per calendar day, continuous (required for time intelligence)
-- --------------------------------------------------------------------------
CREATE TABLE dim_date (
    date_key          INTEGER PRIMARY KEY,          -- yyyymmdd, e.g. 20240131
    date              TEXT    NOT NULL UNIQUE,      -- ISO 'YYYY-MM-DD'
    year              INTEGER NOT NULL,
    quarter           INTEGER NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    quarter_label     TEXT    NOT NULL,             -- 'Q1'
    year_quarter      TEXT    NOT NULL,             -- '2024-Q1'
    month             INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    month_name        TEXT    NOT NULL,             -- 'January'
    month_short       TEXT    NOT NULL,             -- 'Jan'
    year_month        TEXT    NOT NULL,             -- '2024-01'
    month_start_date  TEXT    NOT NULL,
    day_of_month      INTEGER NOT NULL,
    day_of_week       INTEGER NOT NULL,             -- 1 = Monday ... 7 = Sunday
    day_name          TEXT    NOT NULL,
    is_weekend        INTEGER NOT NULL CHECK (is_weekend IN (0, 1))
);

-- --------------------------------------------------------------------------
-- dim_customer: one row per customer; segment is an attribute (see design doc)
-- --------------------------------------------------------------------------
CREATE TABLE dim_customer (
    customer_key                       INTEGER PRIMARY KEY,
    customer_id                        TEXT    NOT NULL UNIQUE,
    customer_name                      TEXT    NOT NULL,
    segment                            TEXT    NOT NULL
        CHECK (segment IN ('Consumer', 'Corporate', 'Home Office')),
    is_placeholder_customer            INTEGER NOT NULL CHECK (is_placeholder_customer IN (0, 1)),
    is_identity_anomaly                INTEGER NOT NULL CHECK (is_identity_anomaly IN (0, 1)),
    is_excluded_from_customer_analysis INTEGER NOT NULL
        CHECK (is_excluded_from_customer_analysis IN (0, 1))
);

-- --------------------------------------------------------------------------
-- dim_product: one row per (product_id, product_name) combination.
-- product_id alone is NOT unique in the source (DQ07), so a surrogate key is required.
-- --------------------------------------------------------------------------
CREATE TABLE dim_product (
    product_key     INTEGER PRIMARY KEY,
    product_id      TEXT NOT NULL,
    product_name    TEXT NOT NULL,
    product_label   TEXT NOT NULL UNIQUE,   -- 'name [product_id]': unique display name
    sub_category    TEXT NOT NULL,
    category        TEXT NOT NULL
        CHECK (category IN ('Furniture', 'Office Supplies', 'Technology')),
    UNIQUE (product_id, product_name)
);

-- --------------------------------------------------------------------------
-- dim_location: one row per ship-to location (country, state, city, postal code).
-- Region and regional manager are denormalised here (no snowflake).
-- --------------------------------------------------------------------------
CREATE TABLE dim_location (
    location_key      INTEGER PRIMARY KEY,
    country           TEXT NOT NULL,
    region            TEXT NOT NULL CHECK (region IN ('Central', 'East', 'South', 'West')),
    regional_manager  TEXT NOT NULL,
    state_province    TEXT NOT NULL,
    city              TEXT NOT NULL,
    city_state        TEXT NOT NULL,        -- 'Springfield, Illinois': unique city label
    postal_code       TEXT NOT NULL,        -- text: preserves leading zeros
    UNIQUE (country, state_province, city, postal_code)
);

-- --------------------------------------------------------------------------
-- dim_ship_mode: tiny reference dimension; carries the business sort order
-- --------------------------------------------------------------------------
CREATE TABLE dim_ship_mode (
    ship_mode_key       INTEGER PRIMARY KEY,
    ship_mode           TEXT    NOT NULL UNIQUE,
    service_level_rank  INTEGER NOT NULL UNIQUE      -- 1 = fastest (Same Day)
);

-- --------------------------------------------------------------------------
-- dim_discount: one row per observed discount level, grouped into fixed bands.
-- Bands are 20-point ranges defined BEFORE analysis (not tuned to the results).
-- --------------------------------------------------------------------------
CREATE TABLE dim_discount (
    discount_key        INTEGER PRIMARY KEY,         -- discount in whole percent, e.g. 20
    discount_rate       REAL    NOT NULL UNIQUE CHECK (discount_rate >= 0 AND discount_rate < 1),
    discount_label      TEXT    NOT NULL,            -- '20%'
    discount_band       TEXT    NOT NULL,            -- '1-20%'
    discount_band_sort  INTEGER NOT NULL
);

-- --------------------------------------------------------------------------
-- fct_sales: GRAIN = one order line (one product line within one order),
-- identified by the source row_id. Measures are additive unless noted.
-- --------------------------------------------------------------------------
CREATE TABLE fct_sales (
    sales_line_id       INTEGER PRIMARY KEY,         -- source row_id
    order_id            TEXT    NOT NULL,            -- degenerate dimension
    order_date_key      INTEGER NOT NULL REFERENCES dim_date (date_key),
    ship_date_key       INTEGER NOT NULL REFERENCES dim_date (date_key),
    customer_key        INTEGER NOT NULL REFERENCES dim_customer (customer_key),
    product_key         INTEGER NOT NULL REFERENCES dim_product (product_key),
    location_key        INTEGER NOT NULL REFERENCES dim_location (location_key),
    ship_mode_key       INTEGER NOT NULL REFERENCES dim_ship_mode (ship_mode_key),
    discount_key        INTEGER NOT NULL REFERENCES dim_discount (discount_key),

    -- source measures
    sales               REAL    NOT NULL CHECK (sales > 0),          -- net of discount (A1)
    quantity            INTEGER NOT NULL CHECK (quantity >= 1),
    discount_rate       REAL    NOT NULL CHECK (discount_rate >= 0 AND discount_rate < 1), -- NON-additive
    profit              REAL    NOT NULL,

    -- derived measures (row-level, additive)
    gross_sales         REAL    NOT NULL,            -- sales / (1 - discount_rate)   (A1, A4)
    discount_amount     REAL    NOT NULL,            -- gross_sales - sales
    days_to_ship        INTEGER NOT NULL CHECK (days_to_ship >= 0),  -- NON-additive
    implied_list_margin REAL    NOT NULL,            -- 1 - (1 - profit/sales)(1 - discount): margin at list price (Phase 6), NON-additive

    -- flags
    is_loss_line            INTEGER NOT NULL CHECK (is_loss_line IN (0, 1)),
    is_returned_order       INTEGER NOT NULL CHECK (is_returned_order IN (0, 1)),
    is_beyond_break_even    INTEGER NOT NULL CHECK (is_beyond_break_even IN (0, 1)),  -- discount > list margin
    is_core_scope           INTEGER NOT NULL CHECK (is_core_scope IN (0, 1)),
    dq_is_clone_copy        INTEGER NOT NULL CHECK (dq_is_clone_copy IN (0, 1)),
    dq_is_price_anomaly     INTEGER NOT NULL CHECK (dq_is_price_anomaly IN (0, 1)),
    dq_is_value_copy_suspect INTEGER NOT NULL CHECK (dq_is_value_copy_suspect IN (0, 1)),
    dq_is_sales_outlier     INTEGER NOT NULL CHECK (dq_is_sales_outlier IN (0, 1)),
    dq_is_profit_outlier    INTEGER NOT NULL CHECK (dq_is_profit_outlier IN (0, 1))
);

CREATE INDEX ix_fct_sales_order_date ON fct_sales (order_date_key);
CREATE INDEX ix_fct_sales_customer   ON fct_sales (customer_key);
CREATE INDEX ix_fct_sales_product    ON fct_sales (product_key);
CREATE INDEX ix_fct_sales_location   ON fct_sales (location_key);
CREATE INDEX ix_fct_sales_order_id   ON fct_sales (order_id);
