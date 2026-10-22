"""Input/output helpers. The raw file is only ever READ, never written."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from . import config


def file_sha256(path: Path) -> str:
    """Fingerprint a file so we can prove the raw data was not modified."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_raw_workbook(path: Path = config.RAW_FILE) -> dict[str, pd.DataFrame]:
    """
    Load all three sheets exactly as stored in the source file.

    Nothing is renamed, converted or fixed here: the audit must see the data
    in its original state. `.xls` is a legacy format, so the `xlrd` engine
    is required.
    """
    if not path.exists():
        raise FileNotFoundError(f"Raw file not found: {path}")

    workbook = pd.ExcelFile(path, engine="xlrd")
    required = {config.SHEET_ORDERS, config.SHEET_RETURNS, config.SHEET_PEOPLE}
    missing = required - set(workbook.sheet_names)
    if missing:
        raise ValueError(f"Workbook is missing sheets: {sorted(missing)}")

    return {
        "orders": workbook.parse(config.SHEET_ORDERS),
        "returns": workbook.parse(config.SHEET_RETURNS),
        "people": workbook.parse(config.SHEET_PEOPLE),
    }


def write_csv(df: pd.DataFrame, path: Path) -> Path:
    """Write a processed table as UTF-8 CSV with ISO dates."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, date_format="%Y-%m-%d")
    return path


def read_orders_clean(path: Path = config.OUT_ORDERS) -> pd.DataFrame:
    """
    Read the processed orders file with the correct types.

    postal_code MUST be read as text, otherwise leading zeros are lost again.
    Downstream phases should always load the clean data through this function.
    """
    return pd.read_csv(
        path,
        dtype={"postal_code": "string", "customer_id": "string"},
        parse_dates=config.DATE_COLUMNS,
    )
