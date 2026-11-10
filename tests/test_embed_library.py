"""Tests for embed_library (uses the real all-mpnet-base-v2 model)."""
import json

import numpy as np
import pytest

from boxes.preprocessing import SPLITS_DIR
from boxes.similar_alerts import TEXT_VERSIONS, embed_library, embed_texts

MPNET = "sentence-transformers/all-mpnet-base-v2"
V1 = "category_product_and_description"
V2 = "category_product_description_and_risk"


def card(index, product, description, risk="The paint contains lead."):
    """One made-up library card with the fields the text versions need."""
    return {"index": index, "category": "Toys", "product": product,
            "description": description, "risk_description": risk}


CARDS = [
    card(2773, "Plastic duck", "Yellow plastic duck."),
    card(863, "Toy duck", "Toy made of yellow plastic."),
    card(1, "Electric scooter", "Red electric scooter."),
]


def test_one_table_and_the_card_numbers_in_the_same_order():
    table, card_numbers = embed_library(CARDS, V1, MPNET)
    assert table.shape == (3, 768)
    assert card_numbers == [2773, 863, 1]
    # Row 0 must be the numbers of the sentence of card 2773.
    sentence = TEXT_VERSIONS[V1](CARDS[0])
    assert np.allclose(table[0], embed_texts([sentence], MPNET)[0], atol=1e-4)


def test_the_two_versions_give_two_different_tables():
    table_1, numbers_1 = embed_library(CARDS, V1, MPNET)
    table_2, numbers_2 = embed_library(CARDS, V2, MPNET)
    assert numbers_1 == numbers_2                      # same cards, same order
    assert not np.allclose(table_1, table_2, atol=1e-3)  # the risk text changes the numbers


def test_empty_list_gives_an_empty_table_and_an_empty_card_list():
    table, card_numbers = embed_library([], V1, MPNET)
    assert table.shape == (0, 768) and card_numbers == []


def test_same_card_twice_is_kept_twice():
    table, card_numbers = embed_library([CARDS[0], CARDS[0]], V1, MPNET)
    assert table.shape == (2, 768) and card_numbers == [2773, 2773]


def test_unknown_text_version_stops_and_lists_the_allowed_names():
    with pytest.raises(ValueError) as error:
        embed_library(CARDS, "category_product_and_descripton", MPNET)
    assert V1 in str(error.value) and V2 in str(error.value)


def test_a_missing_part_stops_with_the_sentence_functions_own_message():
    broken = [card(5, "Plastic duck", "")]
    with pytest.raises(ValueError, match="description is missing or empty"):
        embed_library(broken, V1, MPNET)


@pytest.mark.skipif(not (SPLITS_DIR / "library.jsonl").exists(), reason="library.jsonl not built yet")
@pytest.mark.parametrize("version", [V1, V2])
def test_first_20_real_library_cards(version):
    with open(SPLITS_DIR / "library.jsonl", encoding="utf-8") as f:
        cards = [json.loads(next(f)) for _ in range(20)]
    table, card_numbers = embed_library(cards, version, MPNET)
    assert table.shape == (20, 768)
    assert card_numbers == [c["index"] for c in cards]
