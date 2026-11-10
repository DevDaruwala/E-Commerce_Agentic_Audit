"""The probes themselves, group by group. Each probe takes the shared ProbeContext, writes its CSV files and
its verdict rows into the results folder, and returns nothing. They use the DEV alerts and the library only.

Every probe is wrapped by the runner (boxes/run_probes.py): if one fails it is written as "not available"
with the reason, and the next probe runs. Only a HardStop ends the whole run.
"""
import re
import shutil
import tempfile
from collections import Counter

import numpy as np
import pandas as pd

from boxes.probes import (BGE, COLLECTIONS, LABELS, MODEL_OF, MPNET, V_PLAIN, V_RISK, VERSION_OF,
                          ProbeContext, bootstrap_interval, dev_sample, embed_dev_queries, library_vectors,
                          precision_at_k, save_probe_csv, save_run_info, save_verdict, top_k_neighbours,
                          verdict_from_interval, SEED)
from boxes.data_analysis import HINT_WORDS
from boxes.preprocessing import join_parts, make_text, tidy_text
from boxes.similar_alerts import CHROMA_DIR, TEXT_VERSIONS, embed_texts

CIDS = (1, 2, 3, 4)
THRESHOLDS = (0.90, 0.95, 0.98)   # the "near-copy" lines (C11)


class HardStop(Exception):
    """A check that must pass failed. The whole run stops."""


def bootstrap_stat(n: int, statistic, seed: int = SEED, n_boot: int = 1000):
    """95% interval of any number computed from a set of alert positions. statistic(positions) -> float."""
    rng = np.random.default_rng(seed)
    estimate = statistic(np.arange(n))
    draws = [statistic(rng.integers(0, n, size=n)) for _ in range(n_boot)]
    return float(estimate), float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def verdict_row(probe: str, cid, claim: str, estimate, low, high, decision: str, null: float = 0.0,
                direction: str = "greater", verdict: str | None = None) -> dict:
    """One row of verdicts.csv. The verdict comes from the interval unless it is given."""
    return {"probe": probe, "collection_id": cid, "claim": claim, "null_value": null,
            "estimate": round(float(estimate), 4) if estimate is not None else np.nan,
            "low": round(float(low), 4) if low is not None else np.nan,
            "high": round(float(high), 4) if high is not None else np.nan,
            "verdict": verdict or verdict_from_interval(estimate, low, high, null, direction), "decision": decision}


def _row(probe_cid_lists: dict) -> dict:
    return probe_cid_lists


# ===========================================================================================
# Group C: leaks and fairness
# ===========================================================================================
def probe_C10(ctx: ProbeContext) -> None:
    """C10. Chance level: precision@5 when the 5 neighbours are random library alerts (overall and per risk type)."""
    # Step 1: the exact chance of every dev alert (box 8), and a sampled cross-check with seed 0.
    rng = np.random.default_rng(SEED)
    library_ids = np.array([card["index"] for card in ctx.library])
    random_ids = library_ids[rng.integers(0, len(library_ids), size=(ctx.n_dev, 5))]
    sampled = precision_at_k(ctx.dev_risks, random_ids, ctx.lib_map)

    # Step 2: one row for "all dev alerts" and one per risk type (an alert counts for each of its risk types).
    rows = []
    types = ["ALL"] + sorted({risk for risks in ctx.dev_risks for risk in risks})
    for risk in types:
        mask = np.ones(ctx.n_dev, bool) if risk == "ALL" else np.array([risk in risks for risks in ctx.dev_risks])
        mean, low, high = bootstrap_interval(ctx.chance[mask])
        rows.append({"risk_type": risk, "n": int(mask.sum()), "chance_exact": round(mean, 4),
                     "chance_sampled": round(float(sampled[mask].mean()), 4), "low": round(low, 4),
                     "high": round(high, 4), "small_sample": bool(mask.sum() < 30)})
    save_probe_csv("C10_chance", rows, ctx.out_dir)
    save_verdict([verdict_row("C10", "all", "Random neighbours set the chance level for every score", rows[0]["chance_exact"],
                              rows[0]["low"], rows[0]["high"], "Read every score next to this chance level, never alone.",
                              verdict="baseline")], ctx.out_dir)
    save_run_info("C10", ctx.n_dev, ctx.out_dir)


def probe_C11(ctx: ProbeContext) -> None:
    """C11. Near-copy leakage: best library match of every dev alert; the score with and without near-copies."""
    same_words = np.array([bool(alert.get("same_words_in_library")) for alert in ctx.dev])
    best_rows, leak_rows, verdicts = [], [], []
    for cid in CIDS:
        best = ctx.neighbours(cid, 1)[1][:, 0]
        precision = ctx.precision(cid, 5)
        for alert, score, flag in zip(ctx.dev, best, same_words):
            best_rows.append({"collection_id": cid, "dev_index": alert["index"], "best_score": round(float(score), 4),
                              "in_same_words_group": bool(flag)})
        for threshold in THRESHOLDS:
            above = best >= threshold
            all_mean, all_low, all_high = bootstrap_interval(precision)
            wo_mean, wo_low, wo_high = bootstrap_interval(precision[~above])
            leak_rows.append({"collection_id": cid, "threshold": threshold, "n_above": int(above.sum()), "n_total": ctx.n_dev,
                              "n_above_in_same_words": int((above & same_words).sum()),
                              "precision_all": round(all_mean, 4), "all_low": round(all_low, 4), "all_high": round(all_high, 4),
                              "precision_without": round(wo_mean, 4), "without_low": round(wo_low, 4), "without_high": round(wo_high, 4),
                              "n_without": int((~above).sum())})
            if threshold == 0.95:
                def delta(positions, precision=precision, above=above):
                    keep = ~above[positions]
                    return precision[positions].mean() - (precision[positions][keep].mean() if keep.any() else precision[positions].mean())
                est, low, high = bootstrap_stat(ctx.n_dev, delta)
                verdicts.append(verdict_row("C11", cid, "Near-copies (similarity 0.95 or more) make the score look better", est, low, high,
                                            "Report the score with and without near-copies, and keep the near-copy count next to it."))
    save_probe_csv("C11_best_match", best_rows, ctx.out_dir)
    save_probe_csv("C11_leakage", leak_rows, ctx.out_dir)
    save_verdict(verdicts, ctx.out_dir)
    save_run_info("C11", ctx.n_dev, ctx.out_dir)


def probe_C12(ctx: ProbeContext) -> None:
    """C12. Risk-text leak demo (collections 2 and 4 only): the score WITH risk text in the dev query. Not a valid score."""
    rows, verdicts = [], []
    for cid in CIDS:
        if cid in (1, 3):
            rows.append({"collection_id": cid, "query_type": "not applicable", "status": "not applicable",
                         "precision_at_5": np.nan, "low": np.nan, "high": np.nan, "n": ctx.n_dev})
            verdicts.append(verdict_row("C12", cid, "Risk text in the question inflates the score", None, None, None,
                                        "Not applicable: this collection has no risk text on the library side.", verdict="not available"))
            continue
        # Step 1: the valid score (no risk text in the question), as in every other probe.
        valid = ctx.precision(cid, 5)
        # Step 2: the leak demo: dev queries WITH their risk text, embedded with this collection's model.
        leak_queries = embed_dev_queries(ctx.dev, MODEL_OF[cid], with_risk=True, cache_dir=ctx.cache_dir)[0]
        table, ids, _ = ctx.collection(cid)
        leak_ids, _ = top_k_neighbours(leak_queries, table, ids, k=5)
        leak = precision_at_k(ctx.dev_risks, leak_ids, ctx.lib_map)
        for label, values in (("valid: no risk text in the question", valid), ("LEAK, NOT A VALID SCORE: risk text in the question", leak)):
            mean, low, high = bootstrap_interval(values)
            rows.append({"collection_id": cid, "query_type": label, "status": "ok", "precision_at_5": round(mean, 4),
                         "low": round(low, 4), "high": round(high, 4), "n": ctx.n_dev})
        est, low, high = bootstrap_stat(ctx.n_dev, lambda p, a=leak, b=valid: a[p].mean() - b[p].mean())
        verdicts.append(verdict_row("C12", cid, "Risk text in the question inflates the score", est, low, high,
                                    "Never put risk text in a question. Only the valid score counts."))
    save_probe_csv("C12_risk_text_leak", rows, ctx.out_dir)
    save_verdict(verdicts, ctx.out_dir)
    save_run_info("C12", ctx.n_dev, ctx.out_dir)


def probe_C13(ctx: ProbeContext) -> None:
    """C13. Self-match (no dev id in any collection) and the load check (NumPy against ChromaDB, on a copy)."""
    import chromadb

    # Step 1: self-match. Every dev id (the full dev set) against the card list of every collection. Must be 0.
    from boxes.probes import load_dev
    dev_ids = {alert["index"] for alert in load_dev()}
    rows = []
    for cid in CIDS:
        found = len(dev_ids & set(ctx.collection(cid)[1]))
        rows.append({"collection_id": cid, "dev_ids_found": found, "dev_ids_checked": len(dev_ids)})
    save_probe_csv("C13_self_match", rows, ctx.out_dir)
    if any(r["dev_ids_found"] for r in rows):
        raise HardStop("C13: a dev alert is also in a collection (self-match is not 0)")

    # Step 2: copy the Chroma folder, so the real one is never opened for writing.
    work = tempfile.mkdtemp(prefix="probe_chroma_")
    try:
        copy = f"{work}/chroma"
        shutil.copytree(CHROMA_DIR, copy)
        client = chromadb.PersistentClient(path=copy)
        checks = []
        # Step 3: the ids in every Chroma collection must equal that collection's card list.
        for cid, version, model in COLLECTIONS:
            collection = client.get_collection(f"{version}__{model.split('/')[-1]}", embedding_function=None)
            same = set(collection.get(include=[])["ids"]) == {str(n) for n in ctx.collection(cid)[1]}
            checks.append({"collection_id": cid, "metric": "ids_equal_card_list", "value": float(same)})
            if not same:
                raise HardStop(f"load check: the ids in Chroma collection {cid} differ from its card list")
        # Step 4: precision@5 of collection 1 on 100 dev alerts, by NumPy and by a Chroma query.
        sample = dev_sample(ctx.dev, min(100, ctx.n_dev))
        position = {alert["index"]: i for i, alert in enumerate(ctx.dev)}
        rows_100 = [position[alert["index"]] for alert in sample]
        numpy_ids = ctx.neighbours(1, 5)[0][rows_100]
        collection = client.get_collection(f"{V_PLAIN}__{MPNET.split('/')[-1]}", embedding_function=None)
        chroma = collection.query(query_embeddings=ctx.queries(MPNET)[rows_100], n_results=5)
        chroma_ids = np.array([[int(i) for i in row] for row in chroma["ids"]])
        risks = [ctx.dev_risks[i] for i in rows_100]
        p_numpy = float(precision_at_k(risks, numpy_ids, ctx.lib_map).mean())
        p_chroma = float(precision_at_k(risks, chroma_ids, ctx.lib_map).mean())
        same_sets = float(np.mean([set(a) == set(b) for a, b in zip(numpy_ids, chroma_ids)]))
        checks += [{"collection_id": 1, "metric": "precision_at_5_numpy", "value": round(p_numpy, 4)},
                   {"collection_id": 1, "metric": "precision_at_5_chroma", "value": round(p_chroma, 4)},
                   {"collection_id": 1, "metric": "same_neighbour_sets_share", "value": round(same_sets, 4)},
                   {"collection_id": 1, "metric": "alerts_checked", "value": float(len(rows_100))}]
        save_probe_csv("load_check", checks, ctx.out_dir)
        # ChromaDB's search is approximate (HNSW), so small differences are normal. A real mix-up would be much larger.
        if abs(p_numpy - p_chroma) > 0.02:
            raise HardStop(f"load check: NumPy precision@5 {p_numpy:.4f} differs from Chroma {p_chroma:.4f}")
    finally:
        shutil.rmtree(work, ignore_errors=True)

    save_verdict([verdict_row("C13", "all", "No dev alert is in any collection, and NumPy and ChromaDB agree", 0, 0, 0,
                              "The library and dev are cleanly separated; the stored collections can be trusted.",
                              verdict="supported")], ctx.out_dir)
    save_run_info("C13", ctx.n_dev, ctx.out_dir)



# ===========================================================================================
# Group A: the shape of the space (vectors only)
# ===========================================================================================
def _random_pair_cosines(table: np.ndarray, n_pairs: int = 5000, seed: int = SEED) -> np.ndarray:
    """Cosine of n_pairs random pairs of different library vectors (all rows have length 1)."""
    rng = np.random.default_rng(seed)
    first = rng.integers(0, len(table), n_pairs)
    second = rng.integers(0, len(table), n_pairs)
    second = np.where(first == second, (second + 1) % len(table), second)   # never a vector with itself
    return (table[first] * table[second]).sum(axis=1)


def probe_A1(ctx: ProbeContext) -> None:
    """A1. Random-pair baseline: cosine of 5,000 random library pairs and its 50th, 95th and 99th percentile."""
    pair_rows, percentile_rows = [], []
    for cid in CIDS:
        cosines = _random_pair_cosines(ctx.collection(cid)[0])
        pair_rows += [{"collection_id": cid, "cosine": round(float(c), 5)} for c in cosines]
        p50, p95, p99 = np.percentile(cosines, [50, 95, 99])
        percentile_rows.append({"collection_id": cid, "p50": round(float(p50), 4), "p95": round(float(p95), 4), "p99": round(float(p99), 4)})
    save_probe_csv("A1_random_pairs", pair_rows, ctx.out_dir)
    save_probe_csv("A1_percentiles", percentile_rows, ctx.out_dir)
    save_verdict([verdict_row("A1", "all", "Random pairs of library alerts have a typical similarity (a baseline for 'close')", 0, 0, 0,
                              "Use these percentiles to judge how special a match is. A high similarity only means something above the 99th percentile.",
                              verdict="baseline")], ctx.out_dir)
    save_run_info("A1", ctx.n_dev, ctx.out_dir)


def probe_A2(ctx: ProbeContext) -> None:
    """A2. Anisotropy: mean random-pair cosine, and the length of the mean vector."""
    rows, verdicts = [], []
    for cid in CIDS:
        table = ctx.collection(cid)[0]
        cosines = _random_pair_cosines(table)
        mean, low, high = bootstrap_interval(cosines)
        rows.append({"collection_id": cid, "mean_random_pair_cosine": round(mean, 4), "low": round(low, 4), "high": round(high, 4),
                     "mean_vector_length": round(float(np.linalg.norm(table.mean(axis=0))), 4)})
        verdicts.append(verdict_row("A2", cid, "Unrelated library alerts still look alike (the space leans one way)", mean, low, high,
                                    "If supported: try centring (A3) before trusting raw similarity scores."))
    save_probe_csv("A2_anisotropy", rows, ctx.out_dir)
    save_verdict(verdicts, ctx.out_dir)
    save_run_info("A2", ctx.n_dev, ctx.out_dir)


def _normalise(x: np.ndarray) -> np.ndarray:
    return x / (np.linalg.norm(x, axis=1, keepdims=True) + 1e-12)


def _eta_squared(values: np.ndarray, groups) -> float:
    """Share of the variation of 'values' that is explained by the group (0 to 1)."""
    groups = np.asarray(groups)
    overall = values.mean()
    total = ((values - overall) ** 2).sum()
    between = sum(((groups == g).sum()) * (values[groups == g].mean() - overall) ** 2 for g in np.unique(groups))
    return float(between / total) if total > 0 else 0.0


def probe_A3(ctx: ProbeContext) -> None:
    """A3. Top directions (PCA). Do they follow text length, category or year? Do centring or removing them help?"""
    variance_rows, point_rows, link_rows, fix_rows, verdicts = [], [], [], [], []
    categories = np.array([card["category"] for card in ctx.library])
    years = np.array([card["report_date"][:4] for card in ctx.library])
    for cid in CIDS:
        table, ids, _ = ctx.collection(cid)
        queries = ctx.queries(MODEL_OF[cid])
        mean = table.mean(axis=0)

        # Step 1: PCA of the library (fitted on the library only).
        centred = table - mean
        _, singular, directions = np.linalg.svd(centred, full_matrices=False)
        ratio = singular ** 2 / (singular ** 2).sum()
        variance_rows += [{"collection_id": cid, "component": i + 1, "explained_variance_ratio": round(float(ratio[i]), 5)} for i in range(10)]
        scores = centred @ directions[:2].T

        # Step 2: what do the first two directions follow? text length, category, year.
        build = TEXT_VERSIONS[VERSION_OF[cid]]
        lengths = np.array([len(build(ctx.cards[number])) for number in ids])
        order_in_library = {card["index"]: i for i, card in enumerate(ctx.library)}
        position = np.array([order_in_library[number] for number in ids])
        for component in (1, 2):
            link_rows.append({"collection_id": cid, "component": component,
                              "corr_text_length": round(float(np.corrcoef(scores[:, component - 1], lengths)[0, 1]), 4),
                              "eta2_category": round(_eta_squared(scores[:, component - 1], categories[position]), 4),
                              "eta2_year": round(_eta_squared(scores[:, component - 1], years[position]), 4)})
        rng = np.random.default_rng(SEED)
        for row in rng.choice(len(ids), size=min(3000, len(ids)), replace=False):
            point_rows.append({"collection_id": cid, "card_id": ids[row], "pc1": round(float(scores[row, 0]), 4), "pc2": round(float(scores[row, 1]), 4),
                               "category": categories[position[row]], "text_length": int(lengths[row])})

        # Step 3: the fixes, fitted on the library only: centred, and centred with the top 1 or 2 directions removed.
        variants = {"none": (table, queries), "centred": (_normalise(centred), _normalise(queries - mean))}
        for count, name in ((1, "top 1 removed"), (2, "top 2 removed")):
            top = directions[:count]
            library_fixed = centred - (centred @ top.T) @ top
            queries_fixed = (queries - mean) - ((queries - mean) @ top.T) @ top
            variants[name] = (_normalise(library_fixed), _normalise(queries_fixed))
        base = None
        for name, (library_vectors_, query_vectors) in variants.items():
            found, _ = top_k_neighbours(query_vectors, library_vectors_, ids, k=5)
            precision = precision_at_k(ctx.dev_risks, found, ctx.lib_map)
            base = precision if name == "none" else base
            mean_p, low_p, high_p = bootstrap_interval(precision)
            gain, gain_low, gain_high = bootstrap_stat(ctx.n_dev, lambda p, a=precision, b=base: a[p].mean() - b[p].mean())
            fix_rows.append({"collection_id": cid, "variant": name, "precision_at_5": round(mean_p, 4), "low": round(low_p, 4), "high": round(high_p, 4),
                             "gain": round(gain, 4), "gain_low": round(gain_low, 4), "gain_high": round(gain_high, 4),
                             "kept": bool(name != "none" and verdict_from_interval(gain, gain_low, gain_high) == "supported")})
            if name == "centred":
                verdicts.append(verdict_row("A3", cid, "Centring the vectors improves precision@5", gain, gain_low, gain_high,
                                            "Keep a fix only where its gain is clearly above zero and larger than one point (see the 'kept' column)."))
    save_probe_csv("A3_pca_variance", variance_rows, ctx.out_dir)
    save_probe_csv("A3_pca_points", point_rows, ctx.out_dir)
    save_probe_csv("A3_pca_links", link_rows, ctx.out_dir)
    save_probe_csv("A3_fixes", fix_rows, ctx.out_dir)
    save_verdict(verdicts, ctx.out_dir)
    save_run_info("A3", ctx.n_dev, ctx.out_dir)


# ===========================================================================================
# Group D: does "similar" mean "same danger"?
# ===========================================================================================
def probe_D14(ctx: ProbeContext) -> None:
    """D14. For every library alert, its single nearest library neighbour, bucketed by similarity; share with no shared danger."""
    buckets = [("below 0.80", -1.0, 0.80), ("0.80 to 0.90", 0.80, 0.90), ("0.90 to 0.95", 0.90, 0.95), ("0.95 or more", 0.95, 2.0)]
    rows, verdicts = [], []
    for cid in CIDS:
        table, ids, _ = ctx.collection(cid)
        found, scores = top_k_neighbours(table, table, ids, k=3)
        own = np.array(ids)[:, None]
        first_is_self = found[:, 0] == own[:, 0]
        nearest = np.where(first_is_self, found[:, 1], found[:, 0])
        nearest_score = np.where(first_is_self, scores[:, 1], scores[:, 0])
        shares = np.array([not (ctx.lib_map[a] & ctx.lib_map[int(b)]) for a, b in zip(ids, nearest)], dtype=float)   # 1 = no shared danger
        for name, lo, hi in buckets:
            mask = (nearest_score >= lo) & (nearest_score < hi)
            mean, low, high = bootstrap_interval(shares[mask]) if mask.any() else (np.nan, np.nan, np.nan)
            rows.append({"collection_id": cid, "bucket": name, "n_pairs": int(mask.sum()), "share_no_shared_risk": round(mean, 4),
                         "low": round(low, 4), "high": round(high, 4)})
        top = rows[-1]
        verdicts.append(verdict_row("D14", cid, "Even near-copies (0.95 or more) often share no danger, so voting has a ceiling",
                                    top["share_no_shared_risk"], top["low"], top["high"],
                                    "Do not expect vote accuracy above one minus this share, even for near-identical alerts."))
    save_probe_csv("D14_nn_buckets", rows, ctx.out_dir)
    save_verdict(verdicts, ctx.out_dir)
    save_run_info("D14", ctx.n_dev, ctx.out_dir)


def _per_group_rows(ctx: ProbeContext, cid: int, group_names: list, member_masks: list, label: str) -> list:
    """precision@5 and chance for groups of dev alerts (one row per group), for one collection."""
    precision = ctx.precision(cid, 5)
    rows = []
    for name, mask in zip(group_names, member_masks):
        mean, low, high = bootstrap_interval(precision[mask])
        rows.append({"collection_id": cid, label: name, "n": int(mask.sum()), "precision_at_5": round(mean, 4), "low": round(low, 4),
                     "high": round(high, 4), "chance": round(float(ctx.chance[mask].mean()), 4) if mask.any() else np.nan,
                     "small_sample": bool(mask.sum() < 30)})
    return rows


def _beats_chance_verdict(ctx, cid, probe, names, masks, claim, decision) -> dict:
    """supported if every group with 30 or more alerts beats chance (interval above zero); not supported if none does."""
    precision = ctx.precision(cid, 5)
    results = []
    for mask in masks:
        if mask.sum() >= 30:
            _, low, _ = bootstrap_stat(int(mask.sum()), lambda p, m=mask: (precision[m][p] - ctx.chance[m][p]).mean())
            results.append(low > 0)
    if not results:
        return verdict_row(probe, cid, claim, None, None, None, "No group has enough alerts yet.", verdict="unclear")
    share = float(np.mean(results))
    verdict = "supported" if share == 1 else ("not supported" if share == 0 else "unclear")
    return verdict_row(probe, cid, claim, share, None, None, decision, verdict=verdict)


def probe_D15(ctx: ProbeContext) -> None:
    """D15. precision@5 per danger type, next to the chance level of that type."""
    types = sorted({risk for risks in ctx.dev_risks for risk in risks})
    masks = [np.array([risk in risks for risks in ctx.dev_risks]) for risk in types]
    rows, verdicts = [], []
    for cid in CIDS:
        rows += _per_group_rows(ctx, cid, types, masks, "risk_type")
        verdicts.append(_beats_chance_verdict(ctx, cid, "D15", types, masks, "The search beats luck for every danger type with at least thirty alerts",
                                              "Treat the danger types where the whisker touches the chance mark as weak."))
    save_probe_csv("D15_by_risk_type", rows, ctx.out_dir)
    save_verdict(verdicts, ctx.out_dir)
    save_run_info("D15", ctx.n_dev, ctx.out_dir)


def probe_D16(ctx: ProbeContext) -> None:
    """D16. precision@5 per category (the 10 biggest in dev, and 'other')."""
    counts = Counter(alert["category"] for alert in ctx.dev)
    top = [name for name, _ in counts.most_common(10)]
    names = top + ["other"]
    masks = [np.array([a["category"] == name for a in ctx.dev]) for name in top]
    masks.append(np.array([a["category"] not in top for a in ctx.dev]))
    rows, verdicts = [], []
    for cid in CIDS:
        rows += _per_group_rows(ctx, cid, names, masks, "category")
        verdicts.append(_beats_chance_verdict(ctx, cid, "D16", names, masks, "The search beats luck in every big category",
                                              "Look at the categories whose whisker touches the chance mark."))
    save_probe_csv("D16_by_category", rows, ctx.out_dir)
    save_verdict(verdicts, ctx.out_dir)
    save_run_info("D16", ctx.n_dev, ctx.out_dir)


def dangers_covered(risk_sets: list, neighbour_matrix, lib_map: dict):
    """For every alert: the share of its own dangers found among its neighbours' dangers, and whether ALL are found.

    risk_sets and neighbour_matrix must describe the SAME alerts in the SAME order (one row each).
    """
    shares, full = [], []
    for risks, neighbours in zip(risk_sets, neighbour_matrix):
        union = set().union(*(lib_map[int(n)] for n in neighbours))
        shares.append(len(risks & union) / len(risks))
        full.append(float(risks <= union))
    return np.array(shares), np.array(full)


def probe_D17(ctx: ProbeContext) -> None:
    """D17. Alerts with several dangers: how many of their dangers do the 5 neighbours cover (against random neighbours)?"""
    # Step 1: only the dev alerts with two or more dangers, and their own risk sets (same order everywhere below).
    multi = np.array([len(risks) >= 2 for risks in ctx.dev_risks])
    multi_risks = [risks for risks, flag in zip(ctx.dev_risks, multi) if flag]
    rng = np.random.default_rng(SEED)
    library_ids = np.array([card["index"] for card in ctx.library])
    rows, verdicts = [], []
    for cid in CIDS:
        found = ctx.neighbours(cid, 5)[0][multi]
        near_share, near_full = dangers_covered(multi_risks, found, ctx.lib_map)
        # Step 2: random neighbours for the same alerts, drawn 20 times and averaged.
        draws = [dangers_covered(multi_risks, library_ids[rng.integers(0, len(library_ids), size=(len(multi_risks), 5))], ctx.lib_map) for _ in range(20)]
        random_share = np.mean([d[0] for d in draws], axis=0)
        random_full = np.mean([d[1] for d in draws], axis=0)
        for source, share, full in (("neighbours", near_share, near_full), ("random", random_share, random_full)):
            mean, low, high = bootstrap_interval(share)
            rows.append({"collection_id": cid, "source": source, "coverage_share": round(mean, 4), "low": round(low, 4), "high": round(high, 4),
                         "fully_covered_share": round(float(full.mean()), 4), "n": len(multi_risks)})
        est, low, high = bootstrap_stat(len(multi_risks), lambda p, a=near_share, b=random_share: a[p].mean() - b[p].mean())
        verdicts.append(verdict_row("D17", cid, "The five neighbours cover more of a multi-danger alert's dangers than random neighbours", est, low, high,
                                    "Use all neighbours' dangers (not only the winner) when an alert may have several dangers."))
    save_probe_csv("D17_multi_risk", rows, ctx.out_dir)
    save_verdict(verdicts, ctx.out_dir)
    save_run_info("D17", ctx.n_dev, ctx.out_dir)


def two_sided_verdict(estimate: float, low: float, high: float, margin: float = 0.01) -> str:
    """Like verdict_from_interval, but the claim is 'something changes' (up or down)."""
    if any(np.isnan(x) for x in (estimate, low, high)):
        return "not available"
    if low >= -margin and high <= margin:
        return "not supported"
    return "supported" if (low > 0 or high < 0) else "unclear"


def _positions(ctx: ProbeContext, alerts: list) -> list:
    """Positions in ctx.dev of the given dev alerts (by card number)."""
    where = {alert["index"]: i for i, alert in enumerate(ctx.dev)}
    return [where[alert["index"]] for alert in alerts]


def _top_ids(query_vectors, library_table, library_ids, k=5, allowed=None):
    """Like top_k_neighbours, but 'allowed' (a True/False table, queries x library) can rule library cards out."""
    similarity = query_vectors @ library_table.T
    if allowed is not None:
        similarity = np.where(allowed, similarity, -np.inf)
    ids = np.asarray(library_ids)
    by_number = np.argsort(ids)
    best = np.argsort(-similarity[:, by_number], axis=1, kind="stable")[:, :k]
    return ids[by_number][best]


# ===========================================================================================
# Group B: what drives the matches
# ===========================================================================================
def _two_group_rows(ctx, cid, precision, flag, names, label_col="group"):
    """Rows for two groups of dev alerts and the difference (second minus first)."""
    rows = []
    for name, mask in zip(names, (flag, ~flag)):
        mean, low, high = bootstrap_interval(precision[mask]) if mask.any() else (np.nan, np.nan, np.nan)
        rows.append({"collection_id": cid, label_col: name, "n": int(mask.sum()), "precision_at_5": round(mean, 4), "low": round(low, 4), "high": round(high, 4)})
    if flag.any() and (~flag).any():
        est, low, high = bootstrap_stat(len(precision), lambda p: precision[p][~flag[p]].mean() - precision[p][flag[p]].mean() if flag[p].any() and (~flag[p]).any() else 0.0)
    else:
        est = low = high = np.nan
    rows.append({"collection_id": cid, label_col: "difference", "n": len(precision), "precision_at_5": round(est, 4), "low": round(low, 4), "high": round(high, 4)})
    return rows, est, low, high


def probe_B4(ctx: ProbeContext) -> None:
    """B4. Length: precision@5 for thin-flagged dev alerts against normal ones."""
    thin = np.array([bool(alert.get("is_thin")) for alert in ctx.dev])
    rows, verdicts = [], []
    for cid in CIDS:
        new, est, low, high = _two_group_rows(ctx, cid, ctx.precision(cid), thin, ["thin", "normal"])
        # the rows are (thin, normal, difference) where 'difference' = normal minus thin
        rows += new
        verdicts.append(verdict_row("B4", cid, "Thin descriptions score lower than normal ones", est, low, high,
                                    "If supported, treat thin descriptions as low confidence.") if not np.isnan(est) else
                        verdict_row("B4", cid, "Thin descriptions score lower than normal ones", None, None, None, "Not enough thin alerts.", verdict="unclear"))
    save_probe_csv("B4_length", rows, ctx.out_dir)
    save_verdict(verdicts, ctx.out_dir)
    save_run_info("B4", ctx.n_dev, ctx.out_dir)


def _library_make_text_vectors(ctx: ProbeContext, model: str) -> np.ndarray:
    """The library embedded with 'product + description' only (no category), cached. Rows follow ctx.library."""
    path = ctx.cache_dir / f"library_make_text__{model.split('/')[-1]}.npy"
    if path.exists():
        return np.load(path)
    vectors = embed_texts([make_text(card["product"], card["description"]) for card in ctx.library], model)
    ctx.cache_dir.mkdir(parents=True, exist_ok=True)
    np.save(path, vectors)
    return vectors


def probe_B5(ctx: ProbeContext) -> None:
    """B5. Category: same-category share of the neighbours vs chance; and category in the text vs a category filter."""
    lib_categories = np.array([card["category"] for card in ctx.library])
    dev_categories = np.array([alert["category"] for alert in ctx.dev])
    category_share = {c: float((lib_categories == c).mean()) for c in set(lib_categories)}
    chance = np.array([category_share.get(c, 0.0) for c in dev_categories])
    rows, verdicts = [], []
    for cid in CIDS:
        found = ctx.neighbours(cid, 5)[0]
        same = np.array([np.mean([ctx.cards[int(n)]["category"] == c for n in row]) for row, c in zip(found, dev_categories)])
        mean, low, high = bootstrap_interval(same)
        rows.append({"collection_id": cid, "share_same_category": round(mean, 4), "low": round(low, 4), "high": round(high, 4),
                     "chance": round(float(chance.mean()), 4), "n": ctx.n_dev})
        est, lo, hi = bootstrap_stat(ctx.n_dev, lambda p, a=same: a[p].mean() - chance[p].mean())
        verdicts.append(verdict_row("B5", cid, "The neighbours share the category much more than random library alerts do", est, lo, hi,
                                    "The category is already strongly present in the neighbours; see the comparison of text versus filter."))
    save_probe_csv("B5_same_category", rows, ctx.out_dir)

    # Part 2: 'category in the text' against 'product + description' with and without a category filter, on 300 dev alerts.
    # This needs NEW embeddings (the library as 'product + description'); they are cached and never saved in data/.
    sample = dev_sample(ctx.dev, min(300, ctx.n_dev))
    where = np.array(_positions(ctx, sample))
    texts = [make_text(a["product"], a["description"]) for a in sample]
    allowed = np.array([lib_categories == a["category"] for a in sample])
    risks = [ctx.dev_risks[i] for i in where]
    lib_ids = [card["index"] for card in ctx.library]
    part2, verdicts2 = [], []
    for model, cid in ((MPNET, 1), (BGE, 3)):
        library_vectors_ = _library_make_text_vectors(ctx, model)
        query_vectors = embed_texts(texts, model)
        found_plain = _top_ids(query_vectors, library_vectors_, lib_ids)
        found_filter = _top_ids(query_vectors, library_vectors_, lib_ids, allowed=allowed)
        variants = {"category in the text": ctx.precision(cid)[where],
                    "product + description": precision_at_k(risks, found_plain, ctx.lib_map),
                    "product + description + category filter": precision_at_k(risks, found_filter, ctx.lib_map)}
        for name, values in variants.items():
            mean, low, high = bootstrap_interval(values)
            part2.append({"model": model.split("/")[-1], "variant": name, "precision_at_5": round(mean, 4), "low": round(low, 4), "high": round(high, 4), "n": len(sample)})
        est, lo, hi = bootstrap_stat(len(sample), lambda p, a=variants["product + description + category filter"], b=variants["category in the text"]: a[p].mean() - b[p].mean())
        verdicts2.append(verdict_row("B5b", cid, "A category filter (with product + description text) beats putting the category in the text", est, lo, hi,
                                     "Choose by the larger score: category in the text, or product + description with a category filter."))
    save_probe_csv("B5_text_vs_filter", part2, ctx.out_dir)
    save_verdict(verdicts + verdicts2, ctx.out_dir)
    save_run_info("B5", len(sample), ctx.out_dir)


def probe_B6(ctx: ProbeContext) -> None:
    """B6. Generic words: precision@5 for the 'same words in the library' dev alerts against the rest."""
    flag = np.array([bool(alert.get("same_words_in_library")) for alert in ctx.dev])
    rows, verdicts = [], []
    for cid in CIDS:
        new, est, low, high = _two_group_rows(ctx, cid, ctx.precision(cid), flag, ["same words", "rest"])
        rows += new
        verdicts.append(verdict_row("B6", cid, "Alerts with generic words (same words as a library alert) score lower than the rest", est, low, high,
                                    "If supported, report the score without these alerts as well.") if not np.isnan(est) else
                        verdict_row("B6", cid, "Alerts with generic words score lower than the rest", None, None, None, "Not enough alerts.", verdict="unclear"))
    save_probe_csv("B6_generic_words", rows, ctx.out_dir)
    save_verdict(verdicts, ctx.out_dir)
    save_run_info("B6", ctx.n_dev, ctx.out_dir)


def probe_B7(ctx: ProbeContext) -> None:
    """B7. Names: 200 dev alerts that have a name, embedded with and without the name (the query side only)."""
    named = [alert for alert in ctx.dev if alert.get("name")]
    sample = dev_sample(named, min(200, len(named)))
    where = np.array(_positions(ctx, sample))
    texts = [join_parts([("category", a["category"]), ("product", a["product"]), ("name", a["name"]), ("description", a["description"])]) for a in sample]
    risks = [ctx.dev_risks[i] for i in where]
    rows, verdicts = [], []
    for model in (MPNET, BGE):
        with_name = embed_texts(texts, model)
        for cid in CIDS:
            if MODEL_OF[cid] != model:
                continue
            table, ids, _ = ctx.collection(cid)
            found_with, _ = top_k_neighbours(with_name, table, ids, k=5)
            found_without = ctx.neighbours(cid, 5)[0][where]
            p_without = precision_at_k(risks, found_without, ctx.lib_map)
            p_with = precision_at_k(risks, found_with, ctx.lib_map)
            kept = np.array([len(set(a) & set(b)) for a, b in zip(found_without, found_with)])
            rows += [{"collection_id": cid, "dev_index": a["index"], "kept_of_5": int(k), "precision_without_name": round(float(x), 3),
                      "precision_with_name": round(float(y), 3)} for a, k, x, y in zip(sample, kept, p_without, p_with)]
            est, low, high = bootstrap_stat(len(sample), lambda p, a=p_with, b=p_without: a[p].mean() - b[p].mean())
            verdicts.append(verdict_row("B7", cid, "Adding the product name to the question changes the score", est, low, high,
                                        "If supported, decide deliberately whether names belong in the question.", verdict=two_sided_verdict(est, low, high)))
    save_probe_csv("B7_names", rows, ctx.out_dir)
    save_verdict(verdicts, ctx.out_dir)
    save_run_info("B7", len(sample), ctx.out_dir)


# The words removed in B8: the danger words used in the leakage check, plus the examples from the project plan.
EXTRA_HINTS = [("detach", "plan example"), ("sharp", "plan example"), ("small parts?", "plan example"), ("battery", "plan example")]


def _hint_patterns() -> list:
    """[(regular expression, group name)]: every hint word is removed together with the rest of the word."""
    patterns = []
    for risk, words in HINT_WORDS.items():
        for word in words:
            patterns.append((rf"\b{word}" + ("" if word.endswith("\\b") else r"\w*"), risk))
    for word, group in EXTRA_HINTS:
        patterns.append((rf"\b{word}\w*", group))
    return patterns


def probe_B8(ctx: ProbeContext) -> None:
    """B8. Hint words: delete a fixed word list from the dev queries and re-score."""
    patterns = _hint_patterns()
    base = TEXT_VERSIONS[V_PLAIN]
    original = [base(alert) for alert in ctx.dev]
    cleaned = []
    for text in original:
        new = text
        for pattern, _ in patterns:
            new = re.sub(pattern, "", new, flags=re.IGNORECASE)
        new = tidy_text(new)
        cleaned.append(new if new else text)             # never leave a query empty
    changed = np.array([a != b for a, b in zip(original, cleaned)])
    word_rows = [{"word_pattern": pattern, "risk_type": group,
                  "n_queries_changed": int(sum(bool(re.search(pattern, t, re.IGNORECASE)) for t in original))} for pattern, group in patterns]
    save_probe_csv("B8_hint_word_list", word_rows, ctx.out_dir)
    rows, verdicts = [], []
    for cid in CIDS:
        queries = ctx.queries(MODEL_OF[cid]).copy()
        if changed.any():
            queries[changed] = embed_texts([cleaned[i] for i in np.where(changed)[0]], MODEL_OF[cid])
        table, ids, _ = ctx.collection(cid)
        after = precision_at_k(ctx.dev_risks, top_k_neighbours(queries, table, ids, k=5)[0], ctx.lib_map)
        before = ctx.precision(cid)
        est, low, high = bootstrap_stat(ctx.n_dev, lambda p, a=before, b=after: a[p].mean() - b[p].mean())
        rows.append({"collection_id": cid, "n_changed": int(changed.sum()), "precision_before": round(float(before.mean()), 4),
                     "precision_after": round(float(after.mean()), 4), "diff": round(est, 4), "diff_low": round(low, 4), "diff_high": round(high, 4)})
        verdicts.append(verdict_row("B8", cid, "The search works mainly because of the hint words (the score drops when they are removed)", est, low, high,
                                    "If the score barely moves, hints are not the reason the search works."))
    save_probe_csv("B8_hint_words", rows, ctx.out_dir)
    save_verdict(verdicts, ctx.out_dir)
    save_run_info("B8", ctx.n_dev, ctx.out_dir)


def probe_B9(ctx: ProbeContext) -> None:
    """B9. Chemical names: waiting for Dev to read and approve the substance list. Not run on purpose."""
    save_verdict([verdict_row("B9", "all", "Chemical dev alerts have neighbours that share the substance name", None, None, None,
                              "Waiting for Dev: the substance list has not been approved.", verdict="not run")], ctx.out_dir)


# ===========================================================================================
# Group E: time and style
# ===========================================================================================
def _same_share_probe(ctx, probe, csv, getter, claim, decision):
    """Share of the 5 neighbours with the same value (country, alert type) as the dev alert, against chance."""
    library_values = np.array([getter(card) for card in ctx.library])
    dev_values = np.array([getter(alert) for alert in ctx.dev])
    share_of = {v: float((library_values == v).mean()) for v in set(library_values)}
    chance = np.array([share_of.get(v, 0.0) for v in dev_values])
    rows, verdicts = [], []
    for cid in CIDS:
        found = ctx.neighbours(cid, 5)[0]
        same = np.array([np.mean([getter(ctx.cards[int(n)]) == v for n in row]) for row, v in zip(found, dev_values)])
        mean, low, high = bootstrap_interval(same)
        rows.append({"collection_id": cid, "share_same": round(mean, 4), "low": round(low, 4), "high": round(high, 4), "chance": round(float(chance.mean()), 4), "n": ctx.n_dev})
        est, lo, hi = bootstrap_stat(ctx.n_dev, lambda p, a=same: a[p].mean() - chance[p].mean())
        verdicts.append(verdict_row(probe, cid, claim, est, lo, hi, decision))
    save_probe_csv(csv, rows, ctx.out_dir)
    save_verdict(verdicts, ctx.out_dir)
    save_run_info(probe, ctx.n_dev, ctx.out_dir)


def probe_E19(ctx: ProbeContext) -> None:
    """E19. Notifying country: share of neighbours from the same country against chance."""
    if not all(alert.get("notifying_country") for alert in ctx.dev):
        raise ValueError("the notifying country is not stored for every dev alert")
    _same_share_probe(ctx, "E19", "E19_country", lambda a: a["notifying_country"],
                      "Neighbours come from the same country more often than chance",
                      "If supported, the writing style of a country is pulling matches together.")


def probe_E20(ctx: ProbeContext) -> None:
    """E20. Alert type (the letters at the start of the case number): same test."""
    kind = lambda a: re.match(r"[A-Za-z0-9]+", a["case_number"]).group(0)
    _same_share_probe(ctx, "E20", "E20_alert_type", kind, "Neighbours have the same alert type more often than chance",
                      "If supported, the alert type (not the product) is pulling matches together.")


def probe_E18(ctx: ProbeContext) -> None:
    """E18. precision@5 by month of the dev alerts, and whether neighbours come from the same year."""
    months = np.array([alert["report_date"][:7] for alert in ctx.dev])
    years = np.array([alert["report_date"][:4] for alert in ctx.dev])
    lib_years = np.array([card["report_date"][:4] for card in ctx.library])
    year_share = {y: float((lib_years == y).mean()) for y in set(lib_years)}
    chance = np.array([year_share.get(y, 0.0) for y in years])
    month_rows, year_rows, verdicts = [], [], []
    for cid in CIDS:
        precision = ctx.precision(cid)
        usable = []
        for month in sorted(set(months)):
            mask = months == month
            mean, low, high = bootstrap_interval(precision[mask])
            month_rows.append({"collection_id": cid, "month": month, "n": int(mask.sum()), "precision_at_5": round(mean, 4), "low": round(low, 4), "high": round(high, 4)})
            if mask.sum() >= 30:
                usable.append(mask)
        found = ctx.neighbours(cid, 5)[0]
        same = np.array([np.mean([ctx.cards[int(n)]["report_date"][:4] == y for n in row]) for row, y in zip(found, years)])
        mean, low, high = bootstrap_interval(same)
        year_rows.append({"collection_id": cid, "share_same_year": round(mean, 4), "low": round(low, 4), "high": round(high, 4), "chance": round(float(chance.mean()), 4)})
        if len(usable) >= 2:
            first, last = usable[0], usable[-1]
            est, lo, hi = bootstrap_stat(ctx.n_dev, lambda p, a=first, b=last: (precision[p][a[p]].mean() if a[p].any() else np.nan) - (precision[p][b[p]].mean() if b[p].any() else np.nan))
            verdicts.append(verdict_row("E18", cid, "The score changes between the first and the last month with enough alerts", est, lo, hi,
                                        "Dev covers almost one year only, so time effects stay hard to see.", verdict=two_sided_verdict(est, lo, hi)))
        else:
            verdicts.append(verdict_row("E18", cid, "The score changes between months", None, None, None,
                                        "Fewer than two months have thirty alerts or more, so this cannot be judged.", verdict="unclear"))
    save_probe_csv("E18_by_month", month_rows, ctx.out_dir)
    save_probe_csv("E18_same_year", year_rows, ctx.out_dir)
    save_verdict(verdicts, ctx.out_dir)
    save_run_info("E18", ctx.n_dev, ctx.out_dir)


# ===========================================================================================
# Groups F and G: comparison and calibration
# ===========================================================================================
def vote_winners(ctx: ProbeContext, neighbour_ids: np.ndarray) -> list:
    """The risk type that wins the vote of the neighbours (each danger of each neighbour is one vote).

    A tie goes to the closest neighbour that has one of the tied dangers (the first alphabetically if it has several).
    """
    winners = []
    for neighbours in neighbour_ids:
        votes = Counter(risk for n in neighbours for risk in ctx.lib_map[int(n)])
        top = max(votes.values())
        tied = {risk for risk, count in votes.items() if count == top}
        for n in neighbours:                                  # closest first
            candidates = sorted(ctx.lib_map[int(n)] & tied)
            if candidates:
                winners.append(candidates[0])
                break
    return winners


def _macro_f1_parts(ctx: ProbeContext, winners: list):
    """One-hot tables: predicted (n x types) and true (n x types), and the list of types in dev truth."""
    types = sorted({risk for risks in ctx.dev_risks for risk in risks})
    column = {risk: i for i, risk in enumerate(types)}
    truth = np.zeros((len(winners), len(types)))
    predicted = np.zeros((len(winners), len(types)))
    for row, (risks, winner) in enumerate(zip(ctx.dev_risks, winners)):
        for risk in risks:
            truth[row, column[risk]] = 1
        if winner in column:
            predicted[row, column[winner]] = 1
    return predicted, truth, types


def _macro_f1(predicted: np.ndarray, truth: np.ndarray, positions: np.ndarray) -> float:
    p, t = predicted[positions], truth[positions]
    tp, fp, fn = (p * t).sum(0), (p * (1 - t)).sum(0), (t * (1 - p)).sum(0)
    present = t.sum(0) > 0
    f1 = np.where(2 * tp + fp + fn > 0, 2 * tp / np.maximum(2 * tp + fp + fn, 1e-12), 0.0)
    return float(f1[present].mean()) if present.any() else 0.0


def _compare(ctx: ProbeContext, k: int, probe: str, csv: str, with_confusion: bool) -> None:
    """F21 / F22: precision@k, lift, vote accuracy, macro-F1 for the 4 collections, plus the category-majority baseline."""
    n = ctx.n_dev
    majority = {}
    by_category: dict = {}
    for card in ctx.library:
        by_category.setdefault(card["category"], Counter()).update(card["risk_types"])
    for category, counts in by_category.items():
        majority[category] = counts.most_common(1)[0][0]
    base_winners = [majority.get(alert["category"], "") for alert in ctx.dev]
    rows, verdicts, confusion = [], [], []
    columns = lambda m: dict(value=round(m[0], 4), low=round(m[1], 4), high=round(m[2], 4))

    def add(cid, metric, triple):
        rows.append({"collection_id": cid, "metric": metric, **columns(triple)})

    for cid in CIDS:
        found = ctx.neighbours(cid, k)[0]
        precision = precision_at_k(ctx.dev_risks, found, ctx.lib_map)
        winners = vote_winners(ctx, found)
        hit = np.array([w in risks for w, risks in zip(winners, ctx.dev_risks)], dtype=float)
        predicted, truth, types = _macro_f1_parts(ctx, winners)
        add(cid, f"precision_at_{k}", bootstrap_interval(precision))
        add(cid, "lift", bootstrap_stat(n, lambda p: precision[p].mean() / ctx.chance[p].mean()))
        add(cid, "vote_accuracy", bootstrap_interval(hit))
        add(cid, "macro_f1", bootstrap_stat(n, lambda p: _macro_f1(predicted, truth, p)))
        est, low, high = bootstrap_stat(n, lambda p: (precision[p] - ctx.chance[p]).mean())
        if probe == "F21":
            verdicts.append(verdict_row(probe, cid, "The search beats luck", est, low, high, "Compare the four collections in the ranking at the end."))
        else:
            five = ctx.precision(cid, 5)
            est, low, high = bootstrap_stat(n, lambda p: (precision[p] - five[p]).mean())
            verdicts.append(verdict_row(probe, cid, "Ten neighbours score higher than five", est, low, high, "Use five neighbours unless ten clearly score higher."))
        if with_confusion:
            for t_index, true_risk in enumerate(types):
                members = truth[:, t_index] == 1
                if not members.any():
                    continue
                voted = Counter(w for w, m in zip(winners, members) if m)
                for voted_risk, count in voted.items():
                    confusion.append({"collection_id": cid, "true_risk": true_risk, "voted_risk": voted_risk, "share_of_true": round(count / members.sum(), 4)})
    base_hit = np.array([w in risks for w, risks in zip(base_winners, ctx.dev_risks)], dtype=float)
    base_pred, base_truth, _ = _macro_f1_parts(ctx, base_winners)
    add("baseline", "vote_accuracy", bootstrap_interval(base_hit))
    add("baseline", "macro_f1", bootstrap_stat(n, lambda p: _macro_f1(base_pred, base_truth, p)))
    save_probe_csv(csv, rows, ctx.out_dir)
    if with_confusion:
        save_probe_csv("F21_confusion", confusion, ctx.out_dir)
    save_verdict(verdicts, ctx.out_dir)
    save_run_info(probe, n, ctx.out_dir)


def probe_F21(ctx: ProbeContext) -> None:
    _compare(ctx, 5, "F21", "F21_compare_k5", True)


def probe_F22(ctx: ProbeContext) -> None:
    _compare(ctx, 10, "F22", "F22_compare_k10", False)


def probe_F23(ctx: ProbeContext) -> None:
    """F23. A 2-D picture (PCA) of collection 1, coloured by the first danger of each library alert. Intuition only."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    table, ids, _ = ctx.collection(1)
    centred = table - table.mean(axis=0)
    _, _, directions = np.linalg.svd(centred, full_matrices=False)
    scores = centred @ directions[:2].T
    rng = np.random.default_rng(SEED)
    chosen = rng.choice(len(ids), size=min(3000, len(ids)), replace=False)
    first_risk = [ctx.cards[ids[i]]["risk_types"][0] for i in chosen]
    rows = [{"collection_id": 1, "card_id": ids[i], "pc1": round(float(scores[i, 0]), 4), "pc2": round(float(scores[i, 1]), 4), "risk_type": r}
            for i, r in zip(chosen, first_risk)]
    save_probe_csv("F23_points", rows, ctx.out_dir)
    top = [name for name, _ in Counter(first_risk).most_common(8)]
    fig, ax = plt.subplots(figsize=(8, 4))
    for j, name in enumerate(top):
        pick = [i for i, r in zip(chosen, first_risk) if r == name]
        ax.scatter(scores[pick, 0], scores[pick, 1], s=5, label=name, alpha=0.7)
    ax.legend(fontsize=6, markerscale=2)
    fig.savefig(ctx.out_dir / "F23_pca_collection1.png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    save_run_info("F23", ctx.n_dev, ctx.out_dir)


def probe_F24(ctx: ProbeContext) -> None:
    """F24. 20 random dev alerts and their 5 neighbours (text and dangers) in collections 1 and 3, for Dev to read by hand."""
    sample = dev_sample(ctx.dev, min(20, ctx.n_dev))
    where = _positions(ctx, sample)
    rows, lines = [], ["# Hand review: 20 random dev alerts and their five neighbours", "",
                       "Collections 1 (mpnet plain) and 3 (bge plain). Read them yourself; nothing here is judged by the program.", ""]
    build = TEXT_VERSIONS[V_PLAIN]
    for position, alert in zip(where, sample):
        lines += [f"## Dev alert {alert['index']}: {alert['product']}", f"Text: {build(alert)}", f"Dangers: {', '.join(sorted(alert['risk_types']))}", ""]
        for cid in (1, 3):
            lines.append(f"**{LABELS[cid]}**")
            for rank, number in enumerate(ctx.neighbours(cid, 5)[0][position], start=1):
                card = ctx.cards[int(number)]
                rows.append({"dev_index": alert["index"], "dev_text": build(alert), "dev_risks": " | ".join(sorted(alert["risk_types"])), "rank": rank,
                             "collection_id": cid, "neighbour_text": build(card), "neighbour_risks": " | ".join(sorted(card["risk_types"]))})
                lines.append(f"{rank}. {build(card)} | dangers: {', '.join(sorted(card['risk_types']))}")
            lines.append("")
    save_probe_csv("F24_hand_review", rows, ctx.out_dir)
    (ctx.out_dir / "hand_review_collections_1_and_3.md").write_text("\n".join(lines), encoding="utf-8")
    save_run_info("F24", len(sample), ctx.out_dir)


def probe_G25(ctx: ProbeContext) -> None:
    """G25. Calibration: precision@5 and vote accuracy for dev alerts grouped by how good their best match is (deciles)."""
    rows, cutoffs, verdicts = [], [], []
    for cid in CIDS:
        found, scores = ctx.neighbours(cid, 5)
        best = scores[:, 0]
        precision = ctx.precision(cid, 5)
        winners = vote_winners(ctx, found)
        hit = np.array([w in risks for w, risks in zip(winners, ctx.dev_risks)], dtype=float)
        edges = np.quantile(best, np.linspace(0, 1, 11))
        decile = np.clip(np.digitize(best, edges[1:-1]), 0, 9)
        per_decile = []
        for d in range(10):
            mask = decile == d
            if not mask.any():
                continue
            p_mean, p_low, p_high = bootstrap_interval(precision[mask])
            v_mean, v_low, v_high = bootstrap_interval(hit[mask])
            rows.append({"collection_id": cid, "decile": d + 1, "sim_low": round(float(best[mask].min()), 4), "sim_high": round(float(best[mask].max()), 4),
                         "n": int(mask.sum()), "precision_at_5": round(p_mean, 4), "p_low": round(p_low, 4), "p_high": round(p_high, 4),
                         "vote_accuracy": round(v_mean, 4), "v_low": round(v_low, 4), "v_high": round(v_high, 4)})
            per_decile.append((float(best[mask].min()), p_mean))
        overall = float(precision.mean())
        cut = per_decile[-1][0]
        for index in range(len(per_decile)):
            if all(p >= overall for _, p in per_decile[index:]):
                cut = per_decile[index][0]
                break
        cutoffs.append({"collection_id": cid, "suggested_cutoff": round(cut, 4),
                        "rule": "the lowest similarity from which every higher decile scores at least the overall precision@5"})
        verdicts.append(verdict_row("G25", cid, "A low best-match similarity warns that the answer is weak", None, None, None,
                                    "Mark the answer low confidence when the best match is below the suggested cut-off.", verdict="baseline"))
    save_probe_csv("G25_calibration", rows, ctx.out_dir)
    save_probe_csv("G25_cutoff", cutoffs, ctx.out_dir)
    save_verdict(verdicts, ctx.out_dir)
    save_run_info("G25", ctx.n_dev, ctx.out_dir)


GROUP_PROBES = {"C": [("C10", probe_C10), ("C11", probe_C11), ("C12", probe_C12), ("C13", probe_C13)],
                "A": [("A1", probe_A1), ("A2", probe_A2), ("A3", probe_A3)],
                "D": [("D14", probe_D14), ("D15", probe_D15), ("D16", probe_D16), ("D17", probe_D17)],
                "B": [("B4", probe_B4), ("B5", probe_B5), ("B6", probe_B6), ("B7", probe_B7), ("B8", probe_B8), ("B9", probe_B9)],
                "E": [("E18", probe_E18), ("E19", probe_E19), ("E20", probe_E20)],
                "F": [("F21", probe_F21), ("F22", probe_F22), ("F23", probe_F23), ("F24", probe_F24)],
                "G": [("G25", probe_G25)]}
