"""Tests for probe boxes 1 to 5 (written by Claude).

The tests for top_k_neighbours, precision_at_k and chance_precision are written by Dev,
so they are NOT in this file.
"""
import json
from pathlib import Path

import numpy as np
import pytest

import boxes.probes as probes
from boxes.probes import (ALLOWED_SPLITS, _read_split, check_stored_vectors, dev_sample,
                          embed_dev_queries, library_vectors, load_dev, load_library)
from boxes.similar_alerts import save_embeddings

MPNET = "sentence-transformers/all-mpnet-base-v2"
V1 = "category_product_and_description"
V2 = "category_product_description_and_risk"


# ---------------------------------------------------------------- box 1: load_dev
def test_load_dev_reads_the_dev_alerts_and_none_is_in_the_library():
    dev, library = load_dev(), load_library()
    assert len(dev) > 0 and all("index" in a and "risk_types" in a for a in dev)
    assert not ({a["index"] for a in dev} & {a["index"] for a in library})   # no dev alert is a library alert


def test_the_test_split_is_refused():
    with pytest.raises(ValueError, match="not allowed"):
        _read_split("test")
    assert "test" not in ALLOWED_SPLITS


def test_the_probe_source_never_names_the_test_file():
    source = Path(probes.__file__).read_text(encoding="utf-8")
    assert "test.jsonl" not in source


# ---------------------------------------------------------------- box 2: dev_sample
FAKE_DEV = [{"index": i} for i in range(100, 120)]       # 20 made-up dev alerts


def test_dev_sample_gives_the_same_alerts_for_the_same_seed():
    assert dev_sample(FAKE_DEV, 5, seed=0) == dev_sample(FAKE_DEV, 5, seed=0)


def test_dev_sample_gives_other_alerts_for_another_seed():
    assert dev_sample(FAKE_DEV, 5, seed=0) != dev_sample(FAKE_DEV, 5, seed=1)


def test_dev_sample_has_no_repeats_and_keeps_the_original_order():
    sample = dev_sample(FAKE_DEV, 10)
    numbers = [a["index"] for a in sample]
    assert len(set(numbers)) == 10 and numbers == sorted(numbers)


def test_dev_sample_asking_for_too_many_stops_and_asking_for_all_returns_all():
    with pytest.raises(ValueError, match="asked for 21 alerts but dev has only 20"):
        dev_sample(FAKE_DEV, 21)
    assert dev_sample(FAKE_DEV, 20) == FAKE_DEV


# ---------------------------------------------------------------- box 3: library_vectors
def test_library_vectors_finds_a_card_by_its_number_not_its_position(tmp_path):
    table = np.eye(3, 4, dtype=np.float32)
    save_embeddings(table, [2773, 863, 1], V1, MPNET, folder=tmp_path)      # card numbers with gaps
    got_table, numbers, row_of = library_vectors(V1, MPNET, folder=tmp_path)
    assert row_of == {2773: 0, 863: 1, 1: 2}
    assert np.array_equal(got_table[row_of[863]], table[1])


def test_library_vectors_stops_on_a_repeated_card_number(tmp_path):
    save_embeddings(np.eye(3, 4, dtype=np.float32), [1, 1, 2], V1, MPNET, folder=tmp_path)
    with pytest.raises(ValueError, match="more than once"):
        library_vectors(V1, MPNET, folder=tmp_path)


def test_library_vectors_stops_when_table_and_card_list_differ_in_length(tmp_path):
    stem = tmp_path / f"{V1}__all-mpnet-base-v2"
    np.save(f"{stem}.npy", np.eye(3, 4, dtype=np.float32))
    (tmp_path / f"{V1}__all-mpnet-base-v2_cards.json").write_text(json.dumps([1, 2]))
    with pytest.raises(ValueError, match="3 rows but the card list has 2"):
        library_vectors(V1, MPNET, folder=tmp_path)


def test_library_vectors_on_the_real_collection():
    table, numbers, row_of = library_vectors(V1, MPNET)
    assert table.shape == (11913, 768) and row_of[2773] == 2727 and numbers[row_of[2773]] == 2773


# ---------------------------------------------------------------- box 4: embed_dev_queries
def alert(index, risk_text="The paint contains lead."):
    return {"index": index, "category": "Toys", "product": "Plastic duck",
            "description": "Yellow plastic duck.", "risk_description": risk_text}


def test_embed_dev_queries_shape_order_and_length_one(tmp_path):
    alerts = [alert(5), alert(3), alert(9)]
    vectors, numbers = embed_dev_queries(alerts, MPNET, cache_dir=tmp_path)
    assert vectors.shape == (3, 768) and numbers == [5, 3, 9]
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-4)


def test_the_query_never_contains_the_risk_text_unless_asked(tmp_path):
    a, b = alert(1, "The paint contains lead."), alert(2, "A completely different danger text.")
    no_risk, _ = embed_dev_queries([a, b], MPNET, cache_dir=tmp_path)
    assert np.allclose(no_risk[0], no_risk[1], atol=1e-6)           # risk text changes nothing
    with_risk, _ = embed_dev_queries([a, b], MPNET, with_risk=True, cache_dir=tmp_path)
    assert not np.allclose(with_risk[0], with_risk[1], atol=1e-3)   # the leak demo does use it


def test_a_second_call_comes_from_the_cache(tmp_path, monkeypatch):
    first, _ = embed_dev_queries([alert(1)], MPNET, cache_dir=tmp_path)
    assert len(list(tmp_path.glob("*.npy"))) == 1

    def must_not_be_called(*args, **kwargs):
        raise AssertionError("the model was used although the numbers were cached")

    monkeypatch.setattr(probes, "embed_texts", must_not_be_called)
    second, _ = embed_dev_queries([alert(1)], MPNET, cache_dir=tmp_path)
    assert np.array_equal(first, second)


def test_embed_dev_queries_with_no_alerts_gives_an_empty_table(tmp_path):
    vectors, numbers = embed_dev_queries([], MPNET, cache_dir=tmp_path)
    assert vectors.shape == (0, 768) and numbers == []


# ---------------------------------------------------------------- box 5: check_stored_vectors
@pytest.mark.parametrize("version", [V1, V2])
def test_check_stored_vectors_passes_on_a_good_collection(version):
    result = check_stored_vectors(version, MPNET)
    assert result["collection"] == f"{version}__all-mpnet-base-v2"
    assert len(result["checked"]) == 3 and all(cosine > 0.999 for _, cosine in result["checked"])


def test_check_stored_vectors_notices_a_wrong_text_recipe(monkeypatch):
    # A recipe that writes the wrong sentence: the fresh numbers cannot match the stored ones.
    monkeypatch.setitem(probes.TEXT_VERSIONS, V1, lambda card: "a completely different sentence")
    with pytest.raises(ValueError, match="below 0.999"):
        check_stored_vectors(V1, MPNET)


def test_check_stored_vectors_matches_by_card_number_not_by_row(monkeypatch):
    real_table, numbers, row_of = library_vectors(V1, MPNET)
    shifted = np.roll(real_table, 1, axis=0)          # every row now belongs to the previous card
    monkeypatch.setattr(probes, "library_vectors", lambda *a, **k: (shifted, numbers, row_of))
    with pytest.raises(ValueError, match="below 0.999"):
        check_stored_vectors(V1, MPNET)
