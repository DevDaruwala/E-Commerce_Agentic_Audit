"""Tests for embed_texts (uses the real all-mpnet-base-v2 model)."""
import numpy as np
import pytest

from boxes.similar_alerts import embed_texts

MPNET = "sentence-transformers/all-mpnet-base-v2"
DUCK = "Plastic duck. Yellow plastic duck."
TOY_DUCK = "Toy duck. Toy made of yellow plastic."
SCOOTER = "Electric scooter. Red electric scooter with a lithium battery."


def test_shape_type_and_length_of_each_row():
    numbers = embed_texts([DUCK, TOY_DUCK, SCOOTER], MPNET)
    assert numbers.shape == (3, 768)
    assert numbers.dtype == np.float32
    assert np.allclose(np.linalg.norm(numbers, axis=1), 1.0, atol=1e-4)   # every row has length 1


def test_the_two_ducks_are_closer_to_each_other_than_to_the_scooter():
    duck, toy_duck, scooter = embed_texts([DUCK, TOY_DUCK, SCOOTER], MPNET)
    assert duck @ toy_duck > duck @ scooter
    assert duck @ toy_duck > toy_duck @ scooter


def test_order_is_kept_and_repeats_are_not_merged():
    forward = embed_texts([DUCK, TOY_DUCK, SCOOTER], MPNET)
    backward = embed_texts([SCOOTER, TOY_DUCK, DUCK], MPNET)
    assert np.allclose(forward[::-1], backward, atol=1e-4)               # row i belongs to text i
    twice = embed_texts([DUCK, DUCK], MPNET)
    assert twice.shape == (2, 768) and np.allclose(twice[0], twice[1], atol=1e-6)


def test_empty_list_gives_an_empty_table():
    numbers = embed_texts([], MPNET)
    assert numbers.shape == (0, 768) and numbers.dtype == np.float32


@pytest.mark.parametrize("bad_text", ["", "   ", None, 5])
def test_empty_or_not_a_text_stops_and_says_which_position(bad_text):
    with pytest.raises(ValueError, match="text 1 is empty or not a text"):
        embed_texts([DUCK, bad_text], MPNET)


def test_wrong_model_name_stops():
    with pytest.raises(ValueError, match="unknown model"):
        embed_texts([DUCK], "nope")
