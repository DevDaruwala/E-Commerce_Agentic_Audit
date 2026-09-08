"""
llm_audit.py — Phase 1 version: a plain function that ALWAYS runs the
same 3 steps in order. No agent, no decision-making yet — that's
Phase 2. Resist the urge to make this "smart" right now.

Steps: fetch relevant GPSR rules -> check labels in the product photo
-> evaluate the listing text -> return a verdict.
"""

from app.schemas import ProductListing


def fetch_rules(listing: ProductListing):
    """TODO: call the Groq API with the listing's category, asking
    what GPSR rules apply. Keep the prompt simple for now — no vector
    search yet, that's Phase 2."""
    raise NotImplementedError


def check_labels(listing: ProductListing):
    """TODO: for Phase 1, this can be a simple placeholder — e.g.
    assume no image check yet, or do a trivial check. Real vision
    model wiring comes with the agent in Phase 2."""
    raise NotImplementedError


def check_text(listing: ProductListing, rules):
    """TODO: ask the LLM whether the listing text satisfies `rules`."""
    raise NotImplementedError


def run_audit(listing: ProductListing) -> dict:
    """The fixed pipeline: fetch_rules -> check_labels -> check_text -> verdict."""
    rules = fetch_rules(listing)
    label_result = check_labels(listing)
    text_result = check_text(listing, rules)
    raise NotImplementedError("Combine label_result + text_result into a verdict dict.")
