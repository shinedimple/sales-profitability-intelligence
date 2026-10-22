"""Unit tests for the profitability framework. Run with:  python -m pytest -q"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from spis import profitability as pr  # noqa: E402


def _products():
    return pd.DataFrame({
        "product_key": [1, 2, 3, 4, 5],
        "sales": [1000.0, 1000.0, 10.0, 10.0, 5000.0],
        "profit_margin": [0.30, -0.10, 0.40, -0.20, 0.50],
        "lines": [5, 5, 5, 5, 1],
    }).assign(eligible=lambda d: d["lines"] >= pr.MIN_LINES)


def test_quadrants_follow_stated_thresholds_and_evidence_rule():
    q = pr.assign_quadrants(_products(), company_margin=0.12)
    assert q.tolist() == ["Q1", "Q2", "Q3", "Q4", "NA"]   # single-line product is never classified


def test_within_product_diagnosis():
    p = pd.DataFrame({"product_key": [1, 2], "profit": [-5.0, 10.0],
                      "full_price_lines": [2, 2], "discounted_lines": [2, 2],
                      "full_price_margin": [0.20, 0.30], "discounted_margin": [-0.40, 0.10]})
    d = pr.discount_diagnosis(p).set_index("product_key")["diagnosis"]
    assert d[1] == "Profitable at full price, loss when discounted"
    assert d[2] == "Profitable in both, lower margin when discounted"
