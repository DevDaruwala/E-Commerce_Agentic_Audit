"""Tests for save_embeddings (no model needed)."""
import json

import numpy as np
import pytest

from boxes.similar_alerts import save_embeddings

MPNET = "sentence-transformers/all-mpnet-base-v2"
V1 = "category_product_and_description"
V2 = "category_product_description_and_risk"


def test_the_files_can_be_read_back_exactly(tmp_path):
    table = np.random.rand(3, 768).astype(np.float32)
    table_path, cards_path = save_embeddings(table, [2773, 863, 1], V1, MPNET, folder=tmp_path)
    assert np.array_equal(np.load(table_path), table)                 # same numbers back
    assert json.load(open(cards_path, encoding="utf-8")) == [2773, 863, 1]   # same card list back


def test_file_names_hold_the_version_and_the_model(tmp_path):
    table = np.zeros((1, 768), dtype=np.float32)
    table_path, cards_path = save_embeddings(table, [1], V1, MPNET, folder=tmp_path)
    assert table_path.name == f"{V1}__all-mpnet-base-v2.npy"
    assert cards_path.name == f"{V1}__all-mpnet-base-v2_cards.json"


def test_two_versions_do_not_overwrite_each_other(tmp_path):
    save_embeddings(np.zeros((1, 768), dtype=np.float32), [1], V1, MPNET, folder=tmp_path)
    save_embeddings(np.ones((1, 768), dtype=np.float32), [1], V2, MPNET, folder=tmp_path)
    assert len(list(tmp_path.glob("*.npy"))) == 2


def test_a_table_and_card_list_of_different_length_stop(tmp_path):
    with pytest.raises(ValueError, match="3 rows but the card list has 2"):
        save_embeddings(np.zeros((3, 768), dtype=np.float32), [1, 2], V1, MPNET, folder=tmp_path)


def test_the_folder_is_made_if_missing(tmp_path):
    folder = tmp_path / "new" / "embeddings"
    save_embeddings(np.zeros((1, 768), dtype=np.float32), [1], V1, MPNET, folder=folder)
    assert folder.exists()
