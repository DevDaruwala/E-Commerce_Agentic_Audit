"""Tests for flag_thin: a label is added, nothing is removed or changed."""
import pandas as pd

from boxes.preprocessing import flag_thin


def test_flag_marks_thin_rows_and_counts_them():
    df = pd.DataFrame({
        "product": ["Motorcycle", "Plastic duck", "Soft toy"],
        "description": ["Motorcycle", "Yellow plastic duck.", None],   # repeat / adds "yellow" / missing
    })
    flagged, counts = flag_thin(df)
    assert flagged["is_thin"].tolist() == [True, False, True]
    assert counts == {"rows_checked": 3, "thin_flagged": 2}


def test_no_row_is_removed_and_the_input_is_not_changed():
    df = pd.DataFrame({"product": ["Motorcycle", "Plastic duck"], "description": ["Motorcycle", "Yellow plastic duck."]},
                      index=[10, 20])
    before = df.copy()
    flagged, _ = flag_thin(df)
    pd.testing.assert_frame_equal(df, before)                  # original frame has no new column
    assert flagged.index.tolist() == [10, 20]                  # every row is still there
    assert flagged["description"].tolist() == df["description"].tolist()   # text untouched
