"""Tests for load_embeddings and load_into_chroma (temporary database folder, no model needed)."""
import chromadb
import numpy as np
import pytest

from boxes.similar_alerts import (TEXT_VERSIONS, load_embeddings, load_into_chroma,
                                  save_embeddings)

MPNET = "sentence-transformers/all-mpnet-base-v2"
V1 = "category_product_and_description"
V2 = "category_product_description_and_risk"


def card(index, product, risks, laws=("Toy Safety Directive",), thin=False):
    """One made-up library card with every field load_into_chroma needs."""
    return {"index": index, "category": "Toys", "product": product, "description": f"{product} description.",
            "risk_description": "The paint contains lead.", "risk_types": list(risks), "law_names": list(laws),
            "is_thin": thin, "twin_group": index * 10, "report_date": "2024-03-05"}


# Card numbers have a gap on purpose (2773, 863, 1): row number is not card number.
CARDS = [card(2773, "Plastic duck", ["Chemical"]), card(863, "Toy duck", ["Choking"]),
         card(1, "Electric scooter", ["Fire", "Injuries"], laws=(), thin=True)]
NUMBERS = [2773, 863, 1]
TABLE = np.eye(3, 8, dtype=np.float32)      # 3 rows of length 1, all different


def collection(folder, version):
    name = f"{version}__all-mpnet-base-v2"
    return chromadb.PersistentClient(path=str(folder)).get_collection(name, embedding_function=None)


def test_collection_names_and_the_count(tmp_path):
    assert load_into_chroma(TABLE, NUMBERS, CARDS, V1, MPNET, tmp_path) == 3
    assert load_into_chroma(TABLE, NUMBERS, CARDS, V2, MPNET, tmp_path) == 3
    names = {getattr(c, "name", c) for c in chromadb.PersistentClient(path=str(tmp_path)).list_collections()}
    assert names == {f"{V1}__all-mpnet-base-v2", f"{V2}__all-mpnet-base-v2"}


def test_the_same_card_has_the_same_id_in_both_collections(tmp_path):
    load_into_chroma(TABLE, NUMBERS, CARDS, V1, MPNET, tmp_path)
    load_into_chroma(TABLE, NUMBERS, CARDS, V2, MPNET, tmp_path)
    for version in (V1, V2):
        item = collection(tmp_path, version).get(ids=["2773"], include=["metadatas", "embeddings", "documents"])
        assert item["ids"] == ["2773"]
        assert item["metadatas"][0]["index"] == 2773
        assert np.allclose(item["embeddings"][0], TABLE[0])               # row 0 of the table
        assert item["documents"][0] == TEXT_VERSIONS[version](CARDS[0])    # the sentence that was embedded


def test_the_labels(tmp_path):
    load_into_chroma(TABLE, NUMBERS, CARDS, V1, MPNET, tmp_path)
    label = collection(tmp_path, V1).get(ids=["1"], include=["metadatas"])["metadatas"][0]
    assert label == {"index": 1, "row": 2, "category": "Toys", "product": "Electric scooter",
                     "risk_types": "Fire | Injuries", "law_names": "", "is_thin": True,
                     "twin_group": 10, "report_date": "2024-03-05"}


def test_query_finds_the_card_itself_first_with_cosine_distance_zero(tmp_path):
    load_into_chroma(TABLE, NUMBERS, CARDS, V1, MPNET, tmp_path)
    result = collection(tmp_path, V1).query(query_embeddings=[TABLE[1]], n_results=2)
    assert result["ids"][0][0] == "863"
    assert result["distances"][0][0] == pytest.approx(0.0, abs=1e-5)


def test_running_twice_does_not_leave_duplicates(tmp_path):
    load_into_chroma(TABLE, NUMBERS, CARDS, V1, MPNET, tmp_path)
    assert load_into_chroma(TABLE, NUMBERS, CARDS, V1, MPNET, tmp_path) == 3


def test_adding_in_small_batches_gives_the_same_result(tmp_path):
    assert load_into_chroma(TABLE, NUMBERS, CARDS, V1, MPNET, tmp_path, batch_size=2) == 3
    assert collection(tmp_path, V1).get(ids=["1"])["ids"] == ["1"]


def test_inputs_that_do_not_fit_stop(tmp_path):
    with pytest.raises(ValueError, match="3 rows but the card list has 2"):
        load_into_chroma(TABLE, [2773, 863], CARDS, V1, MPNET, tmp_path)
    with pytest.raises(ValueError, match="card 99 is in the card list but not in the library cards"):
        load_into_chroma(TABLE, [2773, 863, 99], CARDS, V1, MPNET, tmp_path)
    with pytest.raises(ValueError, match="unknown text version"):
        load_into_chroma(TABLE, NUMBERS, CARDS, "nope", MPNET, tmp_path)


def test_load_embeddings_reads_back_what_save_embeddings_wrote(tmp_path):
    save_embeddings(TABLE, NUMBERS, V1, MPNET, folder=tmp_path)
    table, numbers = load_embeddings(V1, MPNET, folder=tmp_path)
    assert np.array_equal(table, TABLE) and numbers == NUMBERS
