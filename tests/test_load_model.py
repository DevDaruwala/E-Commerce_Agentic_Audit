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
