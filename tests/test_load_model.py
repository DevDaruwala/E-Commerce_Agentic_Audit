"""Tests for load_model."""
import pytest

from boxes.similar_alerts import ALLOWED_MODELS, load_model

MPNET = "sentence-transformers/all-mpnet-base-v2"


def test_wrong_name_stops_and_lists_the_allowed_models():
    with pytest.raises(ValueError) as error:
        load_model("all-mpnet-base-v3")
    message = str(error.value)
    assert "unknown model 'all-mpnet-base-v3'" in message
    assert all(name in message for name in ALLOWED_MODELS)


def test_the_model_loads_and_a_second_call_gives_the_same_one():
    first = load_model(MPNET)
    second = load_model(MPNET)
    assert type(first).__name__ == "SentenceTransformer"
    assert first.get_sentence_embedding_dimension() == 768   # numbers per text
    assert first.max_seq_length == 384                       # longest text it reads (tokens)
    assert first is second                                    # remembered, not loaded again


BGE = "BAAI/bge-base-en-v1.5"


def test_the_second_model_loads_with_its_own_limit_and_gives_different_numbers():
    from boxes.similar_alerts import embed_texts

    bge = load_model(BGE)
    assert bge.get_sentence_embedding_dimension() == 768     # same number of numbers per text
    assert bge.max_seq_length == 512                         # a longer limit than the first model
    first = embed_texts(["Plastic duck. Yellow plastic duck."], MPNET)
    second = embed_texts(["Plastic duck. Yellow plastic duck."], BGE)
    assert first.shape == second.shape == (1, 768)
    assert abs(float(first[0] @ second[0])) < 0.9            # two models: two different "languages" of numbers
