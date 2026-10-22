"""
Central configuration for the Sales & Profitability Intelligence System.

Every path, expected value and threshold used by the pipeline lives here,
so that rules are defined once and never hard-coded inside functions.
"""
from pathlib import Path

# --------------------------------------------------------------------------
# Paths (all relative to the project root, so the project runs anywhere)
# --------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
REPORT_DIR = PROJECT_ROOT / "reports" / "phase1"

RAW_FILE = RAW_DIR / "superstore_raw.xls"

SHEET_ORDERS = "Orders"
SHEET_RETURNS = "Returns"
SHEET_PEOPLE = "People"

OUT_ORDERS = PROCESSED_DIR / "orders_clean.csv"
OUT_RETURNS = PROCESSED_DIR / "returns_clean.csv"
OUT_PEOPLE = PROCESSED_DIR / "regional_managers_clean.csv"

# --------------------------------------------------------------------------
# Schema: raw column name -> standard snake_case name
# --------------------------------------------------------------------------
ORDERS_COLUMN_MAP = {
    "Row ID": "row_id",
    "Order ID": "order_id",
    "Order Date": "order_date",
    "Ship Date": "ship_date",
    "Ship Mode": "ship_mode",
    "Customer ID": "customer_id",
    "Customer Name": "customer_name",
    "Segment": "segment",
    "Country/Region": "country",
    "City": "city",
    "State/Province": "state_province",
    "Postal Code": "postal_code",
    "Region": "region",
    "Product ID": "product_id",
    "Category": "category",
    "Sub-Category": "sub_category",
    "Product Name": "product_name",
    "Sales": "sales",
    "Quantity": "quantity",
    "Discount": "discount",
    "Profit": "profit",
}
RETURNS_COLUMN_MAP = {"Order ID": "order_id", "Returned": "returned"}
PEOPLE_COLUMN_MAP = {"Regional Manager": "regional_manager", "Region": "region"}

EXPECTED_ORDER_COLUMNS = list(ORDERS_COLUMN_MAP.keys())

NUMERIC_COLUMNS = ["sales", "quantity", "discount", "profit"]
DATE_COLUMNS = ["order_date", "ship_date"]
TEXT_COLUMNS = [
    "order_id", "ship_mode", "customer_id", "customer_name", "segment",
    "country", "city", "state_province", "postal_code", "region",
    "product_id", "category", "sub_category", "product_name",
]

# --------------------------------------------------------------------------
# Expected categorical domains (business reference data)
# --------------------------------------------------------------------------
EXPECTED_DOMAINS = {
    "ship_mode": {"Standard Class", "Second Class", "First Class", "Same Day"},
    "segment": {"Consumer", "Corporate", "Home Office"},
    "region": {"Central", "East", "South", "West"},
    "country": {"United States", "Canada"},
    "category": {"Furniture", "Office Supplies", "Technology"},
}

# Product ID prefix must agree with Category
PRODUCT_PREFIX_TO_CATEGORY = {
    "FUR": "Furniture",
    "OFF": "Office Supplies",
    "TEC": "Technology",
}
# Order ID prefix must agree with Country
ORDER_PREFIX_TO_COUNTRY = {"US": "United States", "CA": "Canada"}

# --------------------------------------------------------------------------
# Identifier formats (regular expressions)
# --------------------------------------------------------------------------
ORDER_ID_PATTERN = r"^(US|CA)-\d{4}-\d{6}$"
PRODUCT_ID_PATTERN = r"^(FUR|OFF|TEC)-[A-Z]{2}-\d{8}$"
CUSTOMER_ID_PATTERN = r"^[A-Z]{2}-\d{5}$"
US_POSTAL_PATTERN = r"^\d{5}$"
CA_POSTAL_PATTERN = r"^[A-Z]\d[A-Z]$"  # Forward Sortation Area (first 3 chars)

# The primary market. When an order line in another country is an exact copy of a
# line in this market, the copy (not the primary-market line) is flagged.
PRIMARY_MARKET = "United States"

# Names that indicate placeholder / test records rather than real customers
PLACEHOLDER_NAME_PATTERN = r"\b(?:sample|test|dummy|demo)\b"

# --------------------------------------------------------------------------
# Thresholds
# --------------------------------------------------------------------------
IQR_MULTIPLIER_MILD = 1.5      # classic Tukey fence
IQR_MULTIPLIER_EXTREME = 3.0   # "far out" fence, used for flagging
PRICE_DEVIATION_THRESHOLD = 0.50  # implied list price >50% away from product median
MAX_PLAUSIBLE_SHIP_DAYS = 30
VALID_DISCOUNT_RANGE = (0.0, 1.0)  # discount must be >= 0 and < 1

# --------------------------------------------------------------------------
# Phase 2: analytical data model
# --------------------------------------------------------------------------
SQL_DIR = PROJECT_ROOT / "sql"
WAREHOUSE_DIR = PROJECT_ROOT / "data" / "warehouse"
WAREHOUSE_DB = WAREHOUSE_DIR / "spis.sqlite"
MODEL_EXPORT_DIR = PROJECT_ROOT / "data" / "model"     # CSVs for Power BI / Excel
PHASE2_REPORT_DIR = PROJECT_ROOT / "reports" / "phase2"

# Ordered build steps (executed top to bottom)
SQL_BUILD_STEPS = [
    SQL_DIR / "ddl" / "01_create_schema.sql",
    SQL_DIR / "transform" / "02_build_dimensions.sql",
    SQL_DIR / "transform" / "03_build_fact.sql",
    SQL_DIR / "views" / "04_analysis_views.sql",
]
SQL_TEST_FILE = SQL_DIR / "tests" / "05_model_tests.sql"

# Countries included in the core analysis scope. Suspected clone copies (DQ18)
# are always excluded from core scope. To include Canada, add "Canada" here.
CORE_SCOPE_COUNTRIES = ["United States"]

MODEL_TABLES = ["dim_date", "dim_customer", "dim_product", "dim_location",
                "dim_ship_mode", "dim_discount", "fct_sales"]
