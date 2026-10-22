"""Unit tests for customer segmentation rules. Run with:  python -m pytest -q"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from spis import customer_analysis as ca  # noqa: E402


def test_segments_follow_thresholds_and_evidence_rule():
    c = pd.DataFrame({"revenue": [5000.0, 5000.0, 500.0, 500.0, 9000.0],
                      "profit_margin": [0.30, 0.05, 0.30, -0.10, 0.40],
                      "orders": [5, 5, 5, 5, 2]})
    c["eligible"] = c["orders"] >= ca.MIN_ORDERS
    assert ca.assign_segments(c, company_margin=0.12).tolist() == ["C1", "C2", "C3", "C4", "NA"]


def test_eta_is_one_for_perfect_grouping_and_zero_for_none():
    y = pd.Series([1.0, 1.0, 5.0, 5.0])
    assert ca._eta(y, pd.Series(["a", "a", "b", "b"])) == 1.0
    assert abs(ca._eta(y, pd.Series(["a", "b", "a", "b"]))) < 1e-12
