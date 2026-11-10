"""Tests for split_twins: your three examples, plus missing values and "inputs unchanged"."""
import pandas as pd

from boxes.preprocessing import split_twins


def alert(category="Motor vehicles", product="Passenger car", name="Transit",
          brand="Ford", description="Passenger car", country_of_origin="Spain"):
    """One alert as a one-row frame. Any field can be changed per test."""
    return pd.DataFrame([{
        "category": category, "product": product, "name": name, "brand": brand,
        "description": description, "country_of_origin": country_of_origin,
    }])


def test_example_1_same_in_every_field_is_group_1_and_removed():
    kept, counts = split_twins(alert(), alert())
    assert len(kept) == 0
    assert counts == {"rows_checked": 1, "group1_removed": 1, "group2_kept": 0}


def test_example_2_same_words_other_brand_is_group_2_and_marked_true():
    kept, counts = split_twins(alert(brand="Ford"), alert(brand="BMW"))
    assert len(kept) == 1
    assert kept["same_words_in_library"].tolist() == [True]
    assert counts == {"rows_checked": 1, "group1_removed": 0, "group2_kept": 1}


def test_example_3_different_description_is_no_twin_and_marked_false():
    library = alert(category="Toys", product="Soft toy", description="Green turtle")
    other = alert(category="Toys", product="Soft toy", description="Red dragon")
    kept, counts = split_twins(library, other)
    assert kept["same_words_in_library"].tolist() == [False]
    assert counts == {"rows_checked": 1, "group1_removed": 0, "group2_kept": 0}


def test_capital_letters_and_extra_spaces_do_not_matter():
    kept, counts = split_twins(alert(), alert(product="  PASSENGER   car ", name="transit "))
    assert counts["group1_removed"] == 1


def test_missing_value_counts_as_empty_text_on_both_sides():
    # None in both frames = "" = "" -> still a real twin.
    kept, counts = split_twins(alert(name=None), alert(name=None))
    assert counts["group1_removed"] == 1
    # Missing on one side only -> the name differs -> same words only.
    kept, counts = split_twins(alert(name="Transit"), alert(name=None))
    assert counts["group2_kept"] == 1


def test_inputs_are_not_changed_and_row_index_is_kept():
    library = alert()
    other = pd.concat([alert(), alert(brand="BMW"), alert(product="Soft toy", description="x")],
                      ignore_index=True)
    library_before, other_before = library.copy(), other.copy()
    kept, counts = split_twins(library, other)
    pd.testing.assert_frame_equal(library, library_before)
    pd.testing.assert_frame_equal(other, other_before)   # no new column, no changed text
    assert kept.index.tolist() == [1, 2]                  # row 0 (Group 1) removed, others keep their number
    assert kept["same_words_in_library"].tolist() == [True, False]
