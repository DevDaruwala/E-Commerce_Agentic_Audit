"""
generator.py — scales up mock_list.json once you understand the shape
by writing a few listings by hand first.

Phase 1, build task 3: write 4-5 listings yourself directly in
mock_list.json (a couple of each violation type) BEFORE running this
script to generate more. You need to understand what you're asking
the classifier to learn.
"""

import json
import random
from pathlib import Path

OUTPUT_PATH = Path(__file__).resolve().parent / "mock_list.json"


def generate_listings(n: int = 15):
    """TODO: generate n synthetic listings, injecting violations into
    some of them, based on the hand-written examples already in
    mock_list.json."""
    raise NotImplementedError


if __name__ == "__main__":
    generate_listings()
