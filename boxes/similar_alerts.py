import json
from pathlib import Path

import numpy as np

from boxes.preprocessing import DATA_DIR
from boxes.preprocessing import join_parts as _join_parts
from boxes.preprocessing import make_text

# product_and_description is the same function as make_text (it now lives in
# preprocessing.py). The old name still works.
product_and_description = make_text


def category_product_and_description(category: str, product: str, description: str) -> str:
    """Join category, product and description into one text, ready to be embedded.

    Example: "Toys" + "Plastic duck" + "Yellow plastic duck."
             -> "Toys. Plastic duck. Yellow plastic duck."
    Same rules as product_and_description.
    """
    return _join_parts([("category", category), ("product", product), ("description", description)])


def category_product_description_and_risk(category: str, product: str, description: str, risk_description: str) -> str:
    """Join category, product, description and risk_description into one text.

    Example: "Toys" + "Plastic duck" + "Yellow plastic duck." + "The paint contains lead."
             -> "Toys. Plastic duck. Yellow plastic duck. The paint contains lead."
    Same rules as product_and_description.

    WARNING: risk_description is the inspector's answer, and it usually names the
    danger. Do not use this text for a product you want to judge (a query), and do
    not use it to score the search: the result would look far better than it is.
    """
    return _join_parts([
        ("category", category),
        ("product", product),
        ("description", description),
        ("risk_description", risk_description),
    ])


# ---------------------------------------------------------------------------
# Embedding: turning texts into numbers
# ---------------------------------------------------------------------------
# Rule 1: the only models we allow (the two from the plan).
ALLOWED_MODELS = [
    "sentence-transformers/all-mpnet-base-v2",
    "BAAI/bge-base-en-v1.5",
]

# Rule 3: every model that is already loaded, by name, so none is loaded twice.
_loaded_models: dict = {}


def load_model(model_name: str) -> "SentenceTransformer":
    """Load an embedding model once and give back the same one on every later call."""
    # Rule 1: stop with a clear message if the name is not one of the allowed models.
    if model_name not in ALLOWED_MODELS:
        raise ValueError(f"unknown model '{model_name}'. Allowed: {', '.join(ALLOWED_MODELS)}")

    # Only load if we have not loaded this model before.
    if model_name not in _loaded_models:
        # These two imports are slow, so they sit here and not at the top of the
        # file: the text functions above then stay fast to import.
        import torch
        from sentence_transformers import SentenceTransformer

        # Rule 2: use the GPU if there is one, otherwise the CPU.
        device = "cuda" if torch.cuda.is_available() else "cpu"
        # Rule 5: SentenceTransformer downloads the model by itself the first time.
        # Rule 4: we leave the model's own "longest text" setting as it is.
        _loaded_models[model_name] = SentenceTransformer(model_name, device=device)

    # Rule 3: hand back the remembered model.
    return _loaded_models[model_name]


def embed_texts(texts: list[str], model_name: str, batch_size: int = 64,
                show_progress: bool = False) -> np.ndarray:
    """Turn texts into numbers: one row of 768 numbers per text, in the same order.

    Every row is scaled to length 1, so "how close are two texts" is a plain
    multiplication (cosine similarity).
    """
    # Rule 2: stop with a clear message if a text is empty or not a text.
    for position, text in enumerate(texts):
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"text {position} is empty or not a text")

    # load_model remembers the model, so this is instant after the first call.
    model = load_model(model_name)

    # Rule 1: an empty list gives an empty table (0 rows, 768 columns), not an error.
    if len(texts) == 0:
        return np.empty((0, model.get_sentence_embedding_dimension()), dtype=np.float32)

    # Rule 3: encode keeps the order, and does not drop or merge repeated texts.
    # Rule 4: the numbers stay float32 (the model's own type).
    # Rule 5: no prefix is added to the texts.
    # normalize_embeddings=True scales every row to length 1.
    # Rule 6: the progress bar is off unless asked for.
    return model.encode(texts, batch_size=batch_size, normalize_embeddings=True,
                        show_progress_bar=show_progress)


# The two text versions we can embed. Each name points to a small function that
# builds the sentence for ONE card, picking the fields it needs out of the card.
TEXT_VERSIONS = {
    "category_product_and_description": lambda card: category_product_and_description(
        card["category"], card["product"], card["description"]
    ),
    "category_product_description_and_risk": lambda card: category_product_description_and_risk(
        card["category"], card["product"], card["description"], card["risk_description"]
    ),
}


def embed_library(cards: list[dict], text_version: str, model_name: str) -> tuple[np.ndarray, list[int]]:
    """Turn a list of library cards into one table of numbers, for ONE text version.

    Returns (table, card_numbers):
      table        = one row of 768 numbers per card, in the same order as the cards
      card_numbers = the "index" of every card, in the same order as the rows
    It saves nothing. Saving is a separate step.
    """
    # Step 1: the one new rule. Stop if the text version is not one of the allowed names.
    if text_version not in TEXT_VERSIONS:
        raise ValueError(
            f"unknown text version '{text_version}'. Allowed: {', '.join(TEXT_VERSIONS)}"
        )

    # Step 2: write the sentence of this text version for every card, in the same order.
    # If a card has a missing part, the sentence function stops with its own message.
    build_sentence = TEXT_VERSIONS[text_version]
    sentences = [build_sentence(card) for card in cards]

    # Step 3: turn all the sentences into numbers (the order of the rows stays the same).
    table = embed_texts(sentences, model_name)

    # Step 4: write down the card number of every card, in the same order.
    card_numbers = [card["index"] for card in cards]

    # Step 5: hand back the table and the card list.
    return table, card_numbers


# The folder where the embeddings are saved (temporary files, until we set up ChromaDB).
EMBEDDINGS_DIR = DATA_DIR / "embeddings"


def save_embeddings(table: np.ndarray, card_numbers: list[int], text_version: str,
                    model_name: str, folder: Path = EMBEDDINGS_DIR) -> tuple[Path, Path]:
    """Save one table of numbers and its card list as two files. Returns both paths.

    The file names hold the text version and the model, so two versions (or two
    models) never overwrite each other:
      <folder>/<text_version>__<model>.npy         the numbers
      <folder>/<text_version>__<model>_cards.json  the card numbers (the "index" list)
    A file with the same name is replaced.
    """
    # Step 1: stop if the table and the card list do not have the same length.
    # Otherwise a row of numbers could point to the wrong card.
    if len(table) != len(card_numbers):
        raise ValueError(f"the table has {len(table)} rows but the card list has {len(card_numbers)} numbers")

    # Step 2: make the folder if it is not there yet.
    folder.mkdir(parents=True, exist_ok=True)

    # Step 3: build the two file names. The model name keeps only its last part,
    # for example "all-mpnet-base-v2".
    short_model = model_name.split("/")[-1]
    table_path = folder / f"{text_version}__{short_model}.npy"
    cards_path = folder / f"{text_version}__{short_model}_cards.json"

    # Step 4: write the table of numbers, and the card list.
    np.save(table_path, table)
    with open(cards_path, "w", encoding="utf-8") as f:
        json.dump(card_numbers, f)

    # Step 5: hand back where the files are.
    return table_path, cards_path


if __name__ == "__main__":
    # Quick check on the duck row (index 2767) and on row 1 (the scooter).
    print(product_and_description("Plastic duck", "Yellow plastic duck."))
    print(category_product_and_description("Toys", "Plastic duck", "Yellow plastic duck."))
    print(category_product_and_description(
        "Machinery", "Electric scooter",
        "Red, blue, grey or black electric scooter with a lithium battery of 800 W. Product sold online.",
    ))
    print(category_product_description_and_risk(
        "Toys", "Plastic duck", "Yellow plastic duck.", "The paint contains lead.",
    ))
