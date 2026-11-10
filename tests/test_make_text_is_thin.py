"""Tests for make_text and is_thin."""
import pytest

from boxes.preprocessing import is_thin, make_text
from boxes.similar_alerts import product_and_description


def test_make_text_duck():
    assert make_text("Plastic duck", "Yellow plastic duck.") == "Plastic duck. Yellow plastic duck."


def test_make_text_cleans_spaces_and_does_not_double_the_full_stop():
    assert make_text("Toy.", "Soft\tcuddly\nbear") == "Toy. Soft cuddly bear"
    assert make_text("Children´s head protection", "Head  protection") == "Children´s head protection. Head protection"


def test_make_text_stops_when_a_part_is_missing():
    with pytest.raises(ValueError, match="product is missing"):
        make_text("", "x")
    with pytest.raises(ValueError, match="description is missing"):
        make_text("x", None)


def test_old_name_still_works():
    assert product_and_description("Plastic duck", "Yellow plastic duck.") == make_text("Plastic duck", "Yellow plastic duck.")


@pytest.mark.parametrize("product, description, expected", [
    ("Motorcycle", "Motorcycle", True),                              # exact repeat
    ("Motorcycle", "motorcycle.", True),                             # capitals and full stop
    ("Skin-lightening lotion", "Skin lightening lotion.", True),     # reworded repeat
    ("Spray deodorant", "Deodorant spray", True),                    # word order
    ("Passenger car, hydrogen Fuel Cell Electric Vehicle", "Passenger car", True),  # shorter than product
    ("Plastic duck", "Yellow plastic duck.", False),                 # adds "yellow"
    ("Soft toy", "Soft cuddly toy representing a turtle", False),
    ("Perfume", "Perfume 50 ml", False),
    ("Motorcycle", "", True),                                        # empty description adds nothing
    ("Motorcycle", None, True),
])
def test_is_thin(product, description, expected):
    assert is_thin(product, description) is expected
