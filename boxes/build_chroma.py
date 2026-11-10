"""Load the two saved library embeddings into ChromaDB, one collection per text version.

Run it from the project folder with:  python -m boxes.build_chroma
For the second model:                 python -m boxes.build_chroma BAAI/bge-base-en-v1.5
"""
import sys


from boxes.preprocessing import SPLITS_DIR
from boxes.Product_description import load_alerts
from boxes.similar_alerts import CHROMA_DIR, TEXT_VERSIONS, load_embeddings, load_into_chroma

# The model the embeddings were made with (it is part of the file and collection names).
DEFAULT_MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"


def main(model_name: str = DEFAULT_MODEL_NAME) -> None:
    # Step 1: read the library cards. They give the labels (category, risk types, ...).
    cards = load_alerts(SPLITS_DIR / "library.jsonl")
    print(f"{len(cards)} cards read from the library")

    # Step 2: do the same work once for each text version, each into its own collection.
    for text_version in TEXT_VERSIONS:
        # Step 2a: read the saved table of numbers and its card list.
        table, card_numbers = load_embeddings(text_version, model_name)

        # Step 2b: put them into ChromaDB, with the sentences and the labels.
        count = load_into_chroma(table, card_numbers, cards, text_version, model_name)

        # Step 2c: say what happened.
        print(f"{text_version}__{model_name.split('/')[-1]}: {count} items stored")

    print(f"database folder: {CHROMA_DIR}")


# If a model name was typed after the command, use it. Otherwise use the default.
if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MODEL_NAME)
