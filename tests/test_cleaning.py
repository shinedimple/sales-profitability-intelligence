"""Unit tests for cleaning rules. Run with:  python -m pytest -q"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from spis.cleaning import (CleaningLog, fix_customer_id_case, fix_customer_name_case,  # noqa: E402
                           fix_postal_codes, remove_near_duplicates)


def test_us_postal_codes_are_zero_padded_and_canadian_kept():
    df = pd.DataFrame({"postal_code": [5401, 77095, "m7a"],
                       "country": ["United States", "United States", "Canada"]})
    out = fix_postal_codes(df, CleaningLog())
    assert out["postal_code"].tolist() == ["05401", "77095", "M7A"]


def test_customer_id_upper_cased():
    out = fix_customer_id_case(pd.DataFrame({"customer_id": ["Dl-13600", "DP-13000"]}), CleaningLog())
    assert out["customer_id"].tolist() == ["DL-13600", "DP-13000"]


def test_name_case_fixes_lower_starts_only():
    df = pd.DataFrame({"customer_name": ["Dorris liebe", "Mark Van Huff", "Corey-Lock"]})
    out = fix_customer_name_case(df, CleaningLog())
    assert out["customer_name"].tolist() == ["Dorris Liebe", "Mark Van Huff", "Corey-Lock"]


def test_near_duplicates_removed_and_logged():
    df = pd.DataFrame({"row_id": [2, 1, 3], "order_id": ["A", "A", "B"],
                       "sales": [10.0, 10.0, 5.0], "profit": [1.0, 1.0, 1.0]})
    log = CleaningLog()
    out = remove_near_duplicates(df, log)
    assert out["row_id"].tolist() == [1, 3]          # lowest row_id kept
    assert log.removed_rows["row_id"].tolist() == [2]


def test_raw_frame_not_mutated():
    df = pd.DataFrame({"postal_code": [5401], "country": ["United States"]})
    before = df.copy()
    fix_postal_codes(df, CleaningLog())
    pd.testing.assert_frame_equal(df, before)
