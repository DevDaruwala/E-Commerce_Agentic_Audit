"""Tests for remove_duplicates: same product + same answer is removed, the oldest stays."""
import pandas as pd

from boxes.preprocessing import remove_duplicates


def alert(case="A1", date="2024-01-01", brand="Ford", risk_types=("Injuries",),
          law_names=("Motor Vehicles Approval Regulation",), product="Passenger car"):
    """One alert as a dict. Any field can be changed per test."""
    return {
        "case_number": case, "report_date": date, "category": "Motor vehicles",
        "product": product, "name": "Transit", "brand": brand,
        "description": "Passenger car", "country_of_origin": "Spain",
        "risk_types": list(risk_types), "law_names": list(law_names),
    }


def frame(*alerts):
    return pd.DataFrame(list(alerts))


def test_same_product_and_same_answer_is_removed():
    kept, counts = remove_duplicates(frame(alert("A1"), alert("A2", "2024-02-01")))
    assert kept["case_number"].tolist() == ["A1"]
    assert counts == {"rows_checked": 2, "duplicates_removed": 1, "rows_kept": 1}


def test_same_product_but_different_answer_is_kept():
    kept, counts = remove_duplicates(frame(alert("A1"), alert("A2", risk_types=("Fire",))))
    assert len(kept) == 2 and counts["duplicates_removed"] == 0


def test_capitals_spaces_and_list_order_do_not_matter():
    a = alert("A1", risk_types=("Fire", "Burns"))
    b = alert("A2", "2024-02-01", brand="  FORD ", product="passenger  CAR", risk_types=("burns", "fire"))
    kept, counts = remove_duplicates(frame(a, b))
    assert counts["duplicates_removed"] == 1


def test_the_oldest_is_kept_even_when_rows_are_not_in_date_order():
    kept, _ = remove_duplicates(frame(alert("NEW", "2025-05-01"), alert("OLD", "2023-05-01")))
    assert kept["case_number"].tolist() == ["OLD"]


def test_input_is_not_changed_and_row_index_is_kept():
    df = frame(alert("A1"), alert("A2", "2024-02-01"), alert("A3", brand="BMW"))
    before = df.copy()
    kept, _ = remove_duplicates(df)
    pd.testing.assert_frame_equal(df, before)
    assert kept.index.tolist() == [0, 2]
