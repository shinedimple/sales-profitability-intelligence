"""Unit tests for discount analysis rules. Run with:  python -m pytest -q"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from spis import discount_analysis as da  # noqa: E402


def test_implied_list_margin_and_break_even():
    # Product: list price 100, unit cost 70 -> list margin 30%. Sold at 0%, 20% and 40% discount.
    price, cost, d = 100.0, 70.0, np.array([0.0, 0.2, 0.4])
    sales = price * (1 - d)
    df = pd.DataFrame({"product_key": 1, "sales": sales, "profit": sales - cost, "discount_rate": d})
    out = da.add_unit_economics(df)
    assert out["implied_list_margin"].tolist() == pytest.approx([0.3, 0.3, 0.3])
    assert out["beyond_break_even"].tolist() == [False, False, True]     # loses money only above 30%
    assert (out["profit"] < 0).tolist() == out["beyond_break_even"].tolist()


def test_break_even_volume_arithmetic():
    t = da.break_even_volume(list_margins=(0.30,), discounts=(0.10, 0.30))
    assert t.iloc[0, 0] == pytest.approx(1.5)        # 0.30 / (0.30 - 0.10)
    assert np.isinf(t.iloc[1, 0])                     # discount = margin: cannot pay for itself
