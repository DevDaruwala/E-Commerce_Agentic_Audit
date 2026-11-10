"""DEMO: give a new product text, see the 5 closest library cards and their risk types.

This only shows how the functions connect. The real search box (find_neighbours)
comes next. Run it from the project folder with:  python -m boxes.demo_search
"""
import json
from collections import Counter

import numpy as np

from boxes.preprocessing import SPLITS_DIR
from boxes.Product_description import load_alerts
from boxes.similar_alerts import EMBEDDINGS_DIR, TEXT_VERSIONS, embed_texts

MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"
SHORT_MODEL = MODEL_NAME.split("/")[-1]

# Three made-up new products, like a seller would write them (no risk text, of course).
NEW_PRODUCTS = [
    {"category": "Toys", "product": "Rubber duck", "description": "Yellow rubber duck for the bath, it squeaks when squeezed."},
    {"category": "Machinery", "product": "Electric scooter", "description": "Folding electric scooter with a 500 W motor and a lithium battery."},
    {"category": "Cosmetics", "product": "Perfume", "description": "Eau de parfum for women, 50 ml spray bottle."},
]


def closest_cards(table: np.ndarray, card_numbers: list[int], query: np.ndarray, k: int = 5):
    """Return the k closest cards as (score, card_number), best first."""
    # Every row has length 1, so one multiplication gives the closeness to every card.
    scores = table @ query
    # argsort sorts small to big, so "-scores" puts the biggest first; keep the first k.
    best_rows = np.argsort(-scores)[:k]
    return [(float(scores[row]), card_numbers[row]) for row in best_rows]


def main() -> None:
    # Step 1: read the library cards, so we can look up a card by its number.
    cards_by_number = {card["index"]: card for card in load_alerts(SPLITS_DIR / "library.jsonl")}

    # Step 2: write the sentence of each new product. We always use the version WITHOUT
    # the risk text, because a real new product has no risk text.
    build_sentence = TEXT_VERSIONS["category_product_and_description"]
    sentences = [build_sentence(product) for product in NEW_PRODUCTS]

    # Step 3: turn the new sentences into numbers (one row per new product).
    queries = embed_texts(sentences, MODEL_NAME)

    # Step 4: do the search once for each saved embedding.
    for text_version in TEXT_VERSIONS:
        # Step 4a: load the saved table and its card list.
        stem = EMBEDDINGS_DIR / f"{text_version}__{SHORT_MODEL}"
        table = np.load(f"{stem}.npy")
        card_numbers = json.load(open(f"{stem}_cards.json", encoding="utf-8"))
        print(f"\n===== library embedded as: {text_version} =====")

        # Step 4b: for each new product, find the 5 closest cards and show them.
        for sentence, query in zip(sentences, queries):
            print(f"\nNEW: {sentence}")
            risks = Counter()
            for score, number in closest_cards(table, card_numbers, query):
                card = cards_by_number[number]
                print(f"   {score:.3f}  card {number:<6} {card['product'][:28]:<28} risk: {', '.join(card['risk_types'])}")
                risks.update(card["risk_types"])
            # Step 4c: the vote. The risk type seen most often among the 5 cards.
            top_risk, votes = risks.most_common(1)[0]
            print(f"   -> guess: {top_risk} ({votes} of 5 cards)")


if __name__ == "__main__":
    main()
