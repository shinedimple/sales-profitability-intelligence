"""Unit tests for EDA calculation rules. Run with:  python -m pytest -q"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from spis import eda  # noqa: E402


def _lines(**cols):
    base = dict(order_id=["o1", "o1", "o2", "o3"], customer_id="c1", sales_line_id=[1, 2, 3, 4],
                quantity=1, gross_sales=[10, 10, 10, 10], discount_amount=0, is_loss_line=0)
    base.update(cols)
    return pd.DataFrame(base)


def test_margin_is_ratio_of_sums_not_average_of_ratios():
    df = _lines(grp="A", sales=[100.0, 1.0, 1.0, 1.0], profit=[10.0, 1.0, 1.0, 1.0])
    out = eda.summarise(df, "grp")
    assert out.loc["A", "profit_margin"] == pytest.approx(13 / 103)   # not mean(0.1, 1, 1, 1)
    assert out.loc["A", "orders"] == 3                                 # distinct orders, not rows


def test_mix_adjustment_removes_pure_mix_effect():
    # Both groups have identical margins inside each band; B simply sells more at deep discount.
    df = pd.DataFrame({
        "grp": ["A", "A", "B", "B"], "discount_band": ["low", "deep", "low", "deep"],
        "sales": [90.0, 10.0, 10.0, 90.0], "profit": [27.0, -5.0, 3.0, -45.0],
        "order_id": list("abcd"), "customer_id": "c", "sales_line_id": [1, 2, 3, 4], "quantity": 1,
        "gross_sales": 1.0, "discount_amount": 0.0, "is_loss_line": 0})
    out = eda.mix_adjusted_margin(df, "grp")
    assert out.loc["A", "profit_margin"] != pytest.approx(out.loc["B", "profit_margin"])
    assert out.loc["A", "mix_adjusted_margin"] == pytest.approx(out.loc["B", "mix_adjusted_margin"])
