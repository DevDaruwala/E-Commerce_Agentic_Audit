"""Build and save the library embeddings, one file pair per text version.

What this script is: the "cook". It does not do any clever work itself.
It only calls the functions we already built, in the right order:

    load_alerts  ->  embed_library  ->  save_embeddings
    (read cards)     (make numbers)     (write files)

Run it from the project folder with:  python -m boxes.build_embeddings
For the second model:                 python -m boxes.build_embeddings BAAI/bge-base-en-v1.5
"""
# sys is used to read the model name typed after the command; time measures each round.
import sys
import time

# SPLITS_DIR = the folder data/splits, where the clean library file lives.
from boxes.preprocessing import SPLITS_DIR
# load_alerts reads a .jsonl file and gives back a list of cards (one dict per card).
from boxes.Product_description import load_alerts
# TEXT_VERSIONS = the two allowed text versions (a dictionary: name -> sentence-maker).
# embed_library  = cards + one text version + model name -> table of numbers + card list.
# save_embeddings = table + card list -> two files on disk.
from boxes.similar_alerts import TEXT_VERSIONS, embed_library, save_embeddings

# The model that turns the sentences into numbers. It must be one of the allowed
# names in ALLOWED_MODELS (similar_alerts.py). To try the other model later,
# change only this line.
DEFAULT_MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"


def main(model_name: str = DEFAULT_MODEL_NAME) -> None:
    # ------------------------------------------------------------------
    # Step 1: read the library file.
    # In : the path data/splits/library.jsonl
    # Out: `cards`, a list with 11,913 cards. One card looks like
    #      {"index": 2773, "category": "Toys", "product": "Plastic duck",
    #       "description": "Yellow plastic duck.", "risk_types": ["Chemical"], ...}
    # ------------------------------------------------------------------
    cards = load_alerts(SPLITS_DIR / "library.jsonl")
    print(f"{len(cards)} cards read from the library")

    # ------------------------------------------------------------------
    # Step 2: repeat the same work once for each text version.
    # TEXT_VERSIONS has two names, so this loop runs twice:
    #   1st round: "category_product_and_description"
    #   2nd round: "category_product_description_and_risk"
    # Each round creates its own pair of files, so the two embeddings stay apart.
    # To add a third text version later, you add it to TEXT_VERSIONS in
    # similar_alerts.py. This loop then runs three times, with no change here.
    # ------------------------------------------------------------------
    for text_version in TEXT_VERSIONS:
        # Remember the start time, only to print how long this round takes.
        started = time.time()

        # --------------------------------------------------------------
        # Step 2a: write the sentence of every card, and turn the sentences into numbers.
        # In : all the cards, the text version name, the model name
        # Out: `table`        = 11,913 rows x 768 numbers (row i belongs to card i)
        #      `card_numbers` = the "index" of every card, in the same order as the rows,
        #                       for example [1, 2, 3, ..., 2773, ...]
        # Inside embed_library this happens:
        #   - for every card, write its sentence (for example
        #     "Toys. Plastic duck. Yellow plastic duck.")
        #   - give all the sentences to embed_texts, which asks the model
        #     (loaded by load_model) for 768 numbers per sentence
        #   - collect the card numbers in the same order
        # --------------------------------------------------------------
        table, card_numbers = embed_library(cards, text_version, model_name)

        # --------------------------------------------------------------
        # Step 2b: save the table and the card list, so we never have to redo this.
        # In : the table, the card list, the text version and the model name
        # Out: the two file paths. The files are written to data/embeddings/ :
        #        <text_version>__<model>.npy         the numbers
        #        <text_version>__<model>_cards.json  the card numbers
        # The text version and the model are in the file name, so the two embeddings
        # never overwrite each other.
        # --------------------------------------------------------------
        table_path, cards_path = save_embeddings(table, card_numbers, text_version, model_name)

        # --------------------------------------------------------------
        # Step 2c: say what happened, so you can check it by eye.
        # table.shape is (11913, 768): 11,913 cards, 768 numbers each.
        # --------------------------------------------------------------
        print(f"{text_version}: table {table.shape}, {time.time() - started:.0f} s")
        print(f"   saved {table_path.name} and {cards_path.name}")


# This block runs only when you start the file directly with
# "python -m boxes.build_embeddings". It does not run when another file imports this one.
# If a model name was typed after the command, use it. Otherwise use the default.
if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MODEL_NAME)
