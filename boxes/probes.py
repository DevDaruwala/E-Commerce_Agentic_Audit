"""Probes on the library embeddings. They use the DEV alerts and the library only.

Every function here is one "box" from the approved plan. Rules for this file:
  - the test split is never read (see ALLOWED_SPLITS)
  - the library, the splits and the saved embeddings are never changed
  - the random seed is always 0
"""
import hashlib
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from boxes.preprocessing import SPLITS_DIR
from boxes.Product_description import load_alerts
from boxes.similar_alerts import EMBEDDINGS_DIR, TEXT_VERSIONS, embed_texts, load_embeddings

# The only two splits a probe may read. The test split is deliberately NOT in this list.
ALLOWED_SPLITS = ("library", "dev")

# The random seed used everywhere, so every run gives the same numbers.
SEED = 0

# Where probe results go. Nothing is ever written to data/ by a probe.
PROBE_DIR = Path(__file__).resolve().parent.parent / "reports" / "probe_results"
CACHE_DIR = PROBE_DIR / "cache"   # saved query numbers, so a second run is instant


def _read_split(name: str) -> list[dict]:
    """Read one split file as a list of alerts. Only the names in ALLOWED_SPLITS work."""
    # Step 1: refuse any split that is not allowed (this is what keeps the test split closed).
    if name not in ALLOWED_SPLITS:
        raise ValueError(f"split '{name}' is not allowed. Allowed: {', '.join(ALLOWED_SPLITS)}")

    # Step 2: read the file data/splits/<name>.jsonl (load_alerts is defined in Product_description.py).
    return load_alerts(SPLITS_DIR / f"{name}.jsonl")


def load_dev() -> list[dict]:
    """Box 1. Read the dev alerts (1,658). Out: a list with one dict per alert."""
    return _read_split("dev")


def load_library() -> list[dict]:
    """Helper. Read the library alerts (11,913). Used to look up a card by its number."""
    return _read_split("library")


def dev_sample(dev: list[dict], n: int, seed: int = SEED) -> list[dict]:
    """Box 2. Pick n dev alerts at random with a fixed seed: the same n every time.

    The alerts keep their original order and none is picked twice.
    """
    # Step 1: stop if we are asked for more alerts than there are.
    if n > len(dev):
        raise ValueError(f"asked for {n} alerts but dev has only {len(dev)}")

    # Step 2: a random number generator that always starts from the same seed.
    rng = np.random.default_rng(seed)

    # Step 3: pick n different positions (replace=False means no position twice).
    positions = rng.choice(len(dev), size=n, replace=False)

    # Step 4: sort the positions, so the alerts come back in their original order.
    return [dev[position] for position in sorted(positions)]


def library_vectors(text_version: str, model_name: str, folder=EMBEDDINGS_DIR):
    """Box 3. Read the saved numbers of one collection, and a lookup "card number -> row".

    Returns (table, card_numbers, row_of):
      table        = one row of 768 numbers per library card (11,913 rows)
      card_numbers = the card number of every row, in row order
      row_of       = a dictionary: row_of[2773] is the row of card 2773
    A card is always found by its number, never by assuming its row position.
    """
    # Step 1: read the saved table and its card list (load_embeddings is defined in similar_alerts.py).
    table, card_numbers = load_embeddings(text_version, model_name, folder=folder)

    # Step 2: stop if the card list and the table do not have the same length.
    if len(table) != len(card_numbers):
        raise ValueError(f"the table has {len(table)} rows but the card list has {len(card_numbers)} numbers")

    # Step 3: build the lookup. enumerate gives (0, first card), (1, second card), ...
    row_of = {number: row for row, number in enumerate(card_numbers)}

    # Step 4: if a card number appeared twice, the lookup would be shorter than the list. Stop.
    if len(row_of) != len(card_numbers):
        raise ValueError("a card number appears more than once in the card list")

    # Step 5: hand back the table, the card numbers and the lookup.
    return table, card_numbers, row_of


def embed_dev_queries(dev_alerts: list[dict], model_name: str, with_risk: bool = False,
                      cache_dir: Path = CACHE_DIR):
    """Box 4. Turn dev alerts into numbers: one row of 768 numbers per alert, same order.

    The sentence of every alert is category + product + description. It NEVER holds
    the risk text, because a real new product has none. The only exception is
    with_risk=True, which exists for the labelled leak demo (probe C12): LEAK, NOT A VALID SCORE.
    Returns (vectors, card_numbers).
    """
    # Step 1: pick the sentence recipe. Without risk text is the normal, honest one.
    recipe_name = "category_product_description_and_risk" if with_risk else "category_product_and_description"
    build_sentence = TEXT_VERSIONS[recipe_name]

    # Step 2: write the sentence of every dev alert, in order.
    sentences = [build_sentence(alert) for alert in dev_alerts]

    # Step 3: name the cache file after the model, the recipe and the sentences themselves,
    # so a different set of alerts never loads the wrong file.
    key = hashlib.md5("\n".join(sentences).encode("utf-8")).hexdigest()[:12]
    short_model = model_name.split("/")[-1]
    cache_path = cache_dir / f"dev_queries__{short_model}__{recipe_name}__{key}.npy"

    # Step 4: use the saved numbers if they are there and have the right size.
    vectors = None
    if cache_path.exists():
        saved = np.load(cache_path)
        if len(saved) == len(sentences):
            vectors = saved

    # Step 5: otherwise embed the sentences with this model and save them for next time.
    # embed_texts (similar_alerts.py) scales every row to length 1 and adds no prefix.
    if vectors is None:
        vectors = embed_texts(sentences, model_name)
        cache_dir.mkdir(parents=True, exist_ok=True)
        np.save(cache_path, vectors)

    # Step 6: hand back the numbers and the card number of every alert, in the same order.
    return vectors, [alert["index"] for alert in dev_alerts]


def check_stored_vectors(text_version: str, model_name: str, n: int = 3, seed: int = SEED,
                         tolerance: float = 0.999) -> dict:
    """Box 5. Safety check: re-embed n library cards and compare with the stored numbers.

    It uses THAT collection's own text recipe (the two "risk" collections include the
    risk text on the library side). Cards are matched by card number, never by row.
    "Almost equal" means cosine above the tolerance (both vectors have length 1).
    Returns {"collection", "checked": [(card number, cosine), ...]}, or raises if one is too low.
    """
    # Step 1: read the stored numbers (box 3) and the library cards (to rebuild the sentences).
    table, card_numbers, row_of = library_vectors(text_version, model_name)
    cards_by_number = {card["index"]: card for card in load_library()}

    # Step 2: pick n different cards at random, with the fixed seed.
    rng = np.random.default_rng(seed)
    picked = [card_numbers[position] for position in rng.choice(len(card_numbers), size=n, replace=False)]

    # Step 3: write the sentence of each picked card with THIS collection's recipe.
    sentences = [TEXT_VERSIONS[text_version](cards_by_number[number]) for number in picked]

    # Step 4: embed the sentences again with the model. These are the "fresh" numbers.
    fresh = embed_texts(sentences, model_name)

    # Step 5: take the "stored" numbers of the same cards, found BY CARD NUMBER.
    stored = table[[row_of[number] for number in picked]]

    # Step 6: both have length 1, so a row-by-row multiplication gives the cosine.
    cosines = (fresh * stored).sum(axis=1)

    # Step 7: stop if any card is not almost equal.
    name = f"{text_version}__{model_name.split('/')[-1]}"
    for number, cosine in zip(picked, cosines):
        if cosine < tolerance:
            raise ValueError(f"{name}: card {number} fresh vs stored cosine {cosine:.4f} is below {tolerance}")

    # Step 8: all good. Hand back what was checked.
    return {"collection": name, "checked": [(number, float(cosine)) for number, cosine in zip(picked, cosines)]}


def top_k_neighbours(query_vectors: np.ndarray, library_table: np.ndarray, library_ids: list[int],
                     k: int = 5, block_size: int = 500):
    """Box 6. For every query, find the k closest library cards (by cosine).

    Returns (neighbour_ids, scores), both with one row per query and k columns,
    best first. The ids are CARD NUMBERS, not row positions.
    All vectors have length 1, so the cosine is a plain multiplication.
    If two cards have exactly the same score, the lower card number comes first.
    """
    # Step 1: stop if the inputs do not fit together.
    if query_vectors.ndim != 2 or library_table.ndim != 2 or query_vectors.shape[1] != library_table.shape[1]:
        raise ValueError("queries and library must be tables with the same number of columns")
    if len(library_ids) != len(library_table):
        raise ValueError(f"the library has {len(library_table)} rows but {len(library_ids)} card numbers")
    if len(set(library_ids)) != len(library_ids):
        raise ValueError("a card number appears more than once in the library ids")
    if not 1 <= k <= len(library_table):
        raise ValueError(f"k must be between 1 and {len(library_table)}, not {k}")

    # Step 2: put the library in order of card number, once. A stable sort later then
    # keeps this order for equal scores, which gives "lower card number first".
    ids = np.asarray(library_ids)
    by_number = np.argsort(ids)
    sorted_ids = ids[by_number]
    sorted_table = library_table[by_number]

    # Step 3: prepare the two result tables (one row per query, k columns).
    neighbour_ids = np.empty((len(query_vectors), k), dtype=sorted_ids.dtype)
    scores = np.empty((len(query_vectors), k), dtype=np.float32)

    # Step 4: work through the queries one block at a time, to save memory.
    for start in range(0, len(query_vectors), block_size):
        block = query_vectors[start:start + block_size]

        # Step 4a: the cosine of every query in the block with every library card.
        similarity = block @ sorted_table.T

        # Step 4b: sort each row from big to small. "-similarity" turns big into small,
        # and kind="stable" keeps the card-number order when two scores are equal.
        best = np.argsort(-similarity, axis=1, kind="stable")[:, :k]

        # Step 4c: write down the card numbers and the scores of the k best.
        neighbour_ids[start:start + block_size] = sorted_ids[best]
        scores[start:start + block_size] = np.take_along_axis(similarity, best, axis=1)

    # Step 5: hand back the card numbers and the scores.
    return neighbour_ids, scores


def risk_sets_of(alerts: list[dict]) -> list[set]:
    """Helper. The risk types of every alert as a set, in the same order as the alerts."""
    return [set(alert["risk_types"]) for alert in alerts]


def library_risk_map(library: list[dict]) -> dict:
    """Helper. A lookup: card number -> the set of risk types of that library card."""
    return {card["index"]: set(card["risk_types"]) for card in library}


def precision_at_k(dev_risk_sets: list[set], neighbour_ids, library_risks: dict) -> np.ndarray:
    """Box 7. For every dev alert: the share of its k neighbours that share a risk type with it.

    A neighbour "hits" when it has at least one risk type in common with the dev alert.
    Neighbours are looked up by CARD NUMBER in library_risks, so no row order is assumed.
    Returns one number per dev alert (between 0 and 1).
    """
    # Step 1: the neighbour card numbers must be a table with one row per dev alert.
    neighbour_ids = np.asarray(neighbour_ids)
    if neighbour_ids.ndim != 2 or len(neighbour_ids) != len(dev_risk_sets):
        raise ValueError(f"{len(dev_risk_sets)} dev alerts but the neighbour table has shape {neighbour_ids.shape}")

    # Step 2: k is the number of neighbours per alert (the number of columns).
    k = neighbour_ids.shape[1]

    # Step 3: for every alert, count the neighbours that share at least one risk type.
    precision = np.empty(len(dev_risk_sets))
    for position, (risks, neighbours) in enumerate(zip(dev_risk_sets, neighbour_ids)):
        hits = 0
        for card_number in neighbours:
            # Step 3a: find the neighbour's risk types BY CARD NUMBER. Stop if the card is unknown.
            if int(card_number) not in library_risks:
                raise ValueError(f"neighbour card {int(card_number)} is not in the library risk lookup")
            # Step 3b: "risks & ..." is the set of risk types they have in common. Not empty = a hit.
            if risks & library_risks[int(card_number)]:
                hits += 1
        # Step 3c: hits out of k.
        precision[position] = hits / k

    # Step 4: one number per dev alert.
    return precision


def chance_precision(dev_risk_sets: list[set], library_risk_sets: list[set]) -> np.ndarray:
    """Box 8. The score a dev alert would get with 5 RANDOM library neighbours.

    For one dev alert this is the share of the whole library that shares at least one
    risk type with it. It is the yardstick: a search score only means something next to it.
    Returns one number per dev alert (between 0 and 1).
    """
    # Step 1: stop if there is no library to draw random neighbours from.
    if len(library_risk_sets) == 0:
        raise ValueError("the library is empty")

    # Step 2: list every risk type that exists in the library, and give each one a column.
    risk_types = sorted(set().union(*library_risk_sets))
    column_of = {risk: column for column, risk in enumerate(risk_types)}

    # Step 3: a table with one row per library card and one column per risk type.
    # True means "this card has this risk type".
    has_risk = np.zeros((len(library_risk_sets), len(risk_types)), dtype=bool)
    for row, risks in enumerate(library_risk_sets):
        for risk in risks:
            has_risk[row, column_of[risk]] = True

    # Step 4: for every dev alert, the share of library cards that have ANY of its risk types.
    # The same combination of risks always gives the same answer, so each is worked out once.
    already_done: dict = {}
    chance = np.empty(len(dev_risk_sets))
    for position, risks in enumerate(dev_risk_sets):
        combination = frozenset(risks)
        if combination not in already_done:
            # Only risk types that exist in the library can match. Others give no columns.
            columns = [column_of[risk] for risk in combination if risk in column_of]
            if columns:
                already_done[combination] = float(has_risk[:, columns].any(axis=1).mean())
            else:
                already_done[combination] = 0.0
        chance[position] = already_done[combination]

    # Step 5: one number per dev alert.
    return chance


# ===========================================================================
# Shared pieces for all the probes: the 4 collections, statistics, writers, context
# ===========================================================================
MPNET = "sentence-transformers/all-mpnet-base-v2"
BGE = "BAAI/bge-base-en-v1.5"
V_PLAIN = "category_product_and_description"
V_RISK = "category_product_description_and_risk"

# The four collections: (collection id, text version, model). The id is the order 1 to 4 used in every chart.
COLLECTIONS = [(1, V_PLAIN, MPNET), (2, V_RISK, MPNET), (3, V_PLAIN, BGE), (4, V_RISK, BGE)]
LABELS = {1: "mpnet plain", 2: "mpnet + risk text", 3: "bge plain", 4: "bge + risk text"}
MODEL_OF = {cid: model for cid, _, model in COLLECTIONS}
VERSION_OF = {cid: version for cid, version, _ in COLLECTIONS}


def bootstrap_interval(values, seed: int = SEED, n_boot: int = 1000):
    """Mean of the values with a 95% interval, from 1,000 resamples of the alerts (seed 0).

    Returns (mean, low, high). With no values it returns (nan, nan, nan).
    """
    # Step 1: nothing to measure.
    values = np.asarray(values, dtype=float)
    if len(values) == 0:
        return float("nan"), float("nan"), float("nan")

    # Step 2: draw n_boot resamples (with replacement) of the same size, and take each mean.
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, len(values), size=(n_boot, len(values)))
    means = values[picks].mean(axis=1)

    # Step 3: the 95% interval is the middle 95% of those means.
    return float(values.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def verdict_from_interval(estimate: float, low: float, high: float, null: float = 0.0,
                          direction: str = "greater", margin: float = 0.01) -> str:
    """supported / not supported / unclear, from the 95% interval and the "no effect" value.

    direction "greater": the claim is that the true value is ABOVE the null.
    "not supported" also when the WHOLE interval lies within +-margin (1 point) of the null.
    """
    # Step 1: no interval, no verdict.
    if any(np.isnan(x) for x in (estimate, low, high)):
        return "not available"

    # Step 2: the whole interval is within 1 point of "no effect": too small to matter.
    if low >= null - margin and high <= null + margin:
        return "not supported"

    # Step 3: the interval excludes the null on the claimed side: supported.
    if direction == "greater":
        if low > null:
            return "supported"
        if high < null:
            return "not supported"
    else:
        if high < null:
            return "supported"
        if low > null:
            return "not supported"

    # Step 4: the interval includes the null: we cannot tell.
    return "unclear"


def save_probe_csv(name: str, table, out_dir: Path = PROBE_DIR) -> Path:
    """Write one result table as reports/probe_results/<name>.csv (a DataFrame, or a list of dicts)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    frame = table if isinstance(table, pd.DataFrame) else pd.DataFrame(table)
    path = out_dir / f"{name}.csv"
    frame.to_csv(path, index=False)
    return path


def _merge_csv(path: Path, new_rows: pd.DataFrame, key_columns: list[str]) -> None:
    """Add rows to a CSV; rows with the same key are replaced, the others stay."""
    if path.exists():
        # Read everything as text first: a column that holds both numbers and words (collection_id: 1, 2, "all")
        # would otherwise be numbers on one side and text on the other, and old rows would never be replaced.
        old = pd.read_csv(path, dtype={column: str for column in key_columns})
        old_keys = old[key_columns].astype(str).apply(tuple, axis=1)
        new_keys = set(new_rows[key_columns].astype(str).apply(tuple, axis=1))
        new_rows = pd.concat([old[~old_keys.isin(new_keys)], new_rows], ignore_index=True)
    new_rows.to_csv(path, index=False)


def save_verdict(rows: list[dict], out_dir: Path = PROBE_DIR) -> Path:
    """Add verdict rows to verdicts.csv. A row is replaced when its probe and collection_id match.

    Columns: probe, collection_id, verdict, claim, null_value, estimate, low, high, decision.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    columns = ["probe", "collection_id", "verdict", "claim", "null_value", "estimate", "low", "high", "decision"]
    frame = pd.DataFrame(rows).reindex(columns=columns)
    path = out_dir / "verdicts.csv"
    _merge_csv(path, frame, ["probe", "collection_id"])
    return path


def save_run_info(probe: str, n_dev_used: int, out_dir: Path = PROBE_DIR, seed: int = SEED) -> Path:
    """Add one row to run_info.csv: which probe ran, on how many dev alerts, and when."""
    out_dir.mkdir(parents=True, exist_ok=True)
    row = pd.DataFrame([{"probe": probe, "n_dev_used": n_dev_used, "seed": seed,
                         "written_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}])
    path = out_dir / "run_info.csv"
    _merge_csv(path, row, ["probe"])
    return path


def fingerprint_inputs() -> dict:
    """md5 of the library file, the dev file and every saved embedding file (the test split is NOT touched)."""
    paths = [SPLITS_DIR / "library.jsonl", SPLITS_DIR / "dev.jsonl"] + sorted(EMBEDDINGS_DIR.glob("*"))
    result = {}
    for path in paths:
        digest = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                digest.update(chunk)
        result[str(path.relative_to(SPLITS_DIR.parent.parent))] = digest.hexdigest()
    return result


class ProbeContext:
    """Everything the probes share, loaded once: dev alerts, library, vectors, neighbours.

    n_dev=None means the FULL dev set (1,658 alerts). A number means a seed-0 sample of that size.
    Each text is embedded once (the cache does the rest), and one model is used at a time.
    """

    def __init__(self, n_dev: int | None = None, out_dir: Path = PROBE_DIR, cache_dir: Path = CACHE_DIR):
        # Step 1: the alerts (dev and library only) and their risk types.
        all_dev = load_dev()
        self.dev = all_dev if n_dev is None else dev_sample(all_dev, n_dev)
        self.library = load_library()
        self.dev_risks = risk_sets_of(self.dev)
        self.lib_risks = risk_sets_of(self.library)
        self.lib_map = library_risk_map(self.library)
        self.cards = {card["index"]: card for card in self.library}
        self.out_dir, self.cache_dir = out_dir, cache_dir
        self._collections, self._queries, self._neighbours = {}, {}, {}

        # Step 2: the chance level of every dev alert (it does not depend on any vectors).
        self.chance = chance_precision(self.dev_risks, self.lib_risks)

    @property
    def n_dev(self) -> int:
        return len(self.dev)

    def collection(self, cid: int):
        """(table, card ids, row_of) of one collection, read once."""
        if cid not in self._collections:
            self._collections[cid] = library_vectors(VERSION_OF[cid], MODEL_OF[cid])
        return self._collections[cid]

    def queries(self, model: str):
        """The dev query numbers (no risk text) made with one model, embedded once."""
        if model not in self._queries:
            self._queries[model] = embed_dev_queries(self.dev, model, cache_dir=self.cache_dir)[0]
        return self._queries[model]

    def neighbours(self, cid: int, k: int = 5):
        """(card ids, scores) of the k closest library cards for every dev alert, in collection cid."""
        if cid not in self._neighbours:
            table, ids, _ = self.collection(cid)
            self._neighbours[cid] = top_k_neighbours(self.queries(MODEL_OF[cid]), table, ids, k=10)
        found_ids, found_scores = self._neighbours[cid]
        return found_ids[:, :k], found_scores[:, :k]

    def precision(self, cid: int, k: int = 5) -> np.ndarray:
        """precision@k of every dev alert in collection cid."""
        return precision_at_k(self.dev_risks, self.neighbours(cid, k)[0], self.lib_map)


def write_foundation_check(ctx: ProbeContext) -> dict:
    """Foundation check for the report: vectors verified, 2 example alerts with their 5 neighbours.

    Stops (raises) if a stored vector does not match its re-embedded vector.
    Writes F0_vector_check.csv, F0_example_neighbours.csv, F0_inputs_fingerprint.csv and a run_info row.
    """
    # Step 1: take the md5 of the input files before anything else.
    start = fingerprint_inputs()

    # Step 2: re-embed 3 library cards per collection (with its own recipe) and compare. Stops on a mismatch.
    vector_rows = []
    for cid, version, model in COLLECTIONS:
        result = check_stored_vectors(version, model)
        for card_id, cosine in result["checked"]:
            vector_rows.append({"collection_id": cid, "card_id": card_id, "cosine": round(cosine, 6), "ok": True})
    save_probe_csv("F0_vector_check", vector_rows, ctx.out_dir)

    # Step 3: the 5 neighbours of the first 2 dev alerts, in every collection.
    example_rows = []
    for cid in (1, 2, 3, 4):
        found_ids, found_scores = ctx.neighbours(cid, 5)
        for position in (0, 1):
            alert = ctx.dev[position]
            for rank in range(5):
                card = ctx.cards[int(found_ids[position, rank])]
                example_rows.append({
                    "collection_id": cid, "dev_index": alert["index"], "dev_product": alert["product"],
                    "dev_risks": " | ".join(sorted(alert["risk_types"])), "rank": rank + 1,
                    "neighbour_index": card["index"], "neighbour_product": card["product"],
                    "neighbour_risks": " | ".join(sorted(card["risk_types"])),
                    "score": round(float(found_scores[position, rank]), 4)})
    save_probe_csv("F0_example_neighbours", example_rows, ctx.out_dir)

    # Step 4: md5 again. The input files must be unchanged by this check.
    end = fingerprint_inputs()
    save_fingerprint(start, end, ctx.out_dir)
    save_run_info("F0", ctx.n_dev, ctx.out_dir)
    return {"vector_rows": len(vector_rows), "example_rows": len(example_rows), "inputs_unchanged": start == end}


def save_fingerprint(start: dict, end: dict, out_dir: Path = PROBE_DIR) -> Path:
    """Write F0_inputs_fingerprint.csv: the md5 of every input file at the start and at the end."""
    rows = [{"path": path, "md5_start": start[path], "md5_end": end.get(path), "same": start[path] == end.get(path)}
            for path in start]
    return save_probe_csv("F0_inputs_fingerprint", rows, out_dir)
