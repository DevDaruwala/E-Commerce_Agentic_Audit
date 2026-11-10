"""Tests for the probe statistics, the writers and the shared probe helpers (written by Claude)."""
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import boxes.probe_groups as groups
from boxes.probes import (bootstrap_interval, fingerprint_inputs, save_probe_csv, save_run_info, save_verdict,
                          verdict_from_interval)


# ---- bootstrap_interval
def test_bootstrap_interval_gives_the_mean_inside_its_interval_and_is_repeatable():
    values = [0.2, 0.4, 0.6, 0.8, 1.0]
    mean, low, high = bootstrap_interval(values)
    assert mean == pytest.approx(0.6) and low < mean < high
    assert bootstrap_interval(values) == (mean, low, high)            # seed 0: the same every time


def test_bootstrap_interval_of_nothing_is_nan():
    assert all(np.isnan(x) for x in bootstrap_interval([]))


def test_bootstrap_stat_matches_the_mean_for_a_plain_mean():
    values = np.array([0.0, 1.0, 1.0, 0.0, 1.0, 1.0])
    est, low, high = groups.bootstrap_stat(len(values), lambda p: values[p].mean())
    assert est == pytest.approx(values.mean()) and low <= est <= high


# ---- verdicts
@pytest.mark.parametrize("est, low, high, null, direction, expected", [
    (0.10, 0.05, 0.15, 0.0, "greater", "supported"),
    (0.002, -0.004, 0.008, 0.0, "greater", "not supported"),          # whole interval within +-1 point
    (0.05, -0.05, 0.15, 0.0, "greater", "unclear"),
    (-0.10, -0.20, -0.05, 0.0, "greater", "not supported"),           # excluded on the other side
    (-0.10, -0.20, -0.05, 0.0, "less", "supported"),
    (float("nan"), 0.0, 0.1, 0.0, "greater", "not available"),
])
def test_verdict_from_interval(est, low, high, null, direction, expected):
    assert verdict_from_interval(est, low, high, null, direction) == expected


def test_two_sided_verdict():
    assert groups.two_sided_verdict(-0.1, -0.2, -0.05) == "supported"
    assert groups.two_sided_verdict(0.0, -0.005, 0.005) == "not supported"
    assert groups.two_sided_verdict(0.0, -0.1, 0.1) == "unclear"


# ---- writers
def test_save_probe_csv_writes_the_table(tmp_path):
    path = save_probe_csv("X1_demo", [{"collection_id": 1, "value": 0.5}], tmp_path)
    assert path.name == "X1_demo.csv" and pd.read_csv(path).iloc[0]["value"] == 0.5


def test_save_verdict_replaces_the_same_probe_and_collection_and_keeps_the_rest(tmp_path):
    row = lambda probe, cid, verdict: {"probe": probe, "collection_id": cid, "verdict": verdict, "claim": "c", "decision": "d"}
    save_verdict([row("C11", 1, "unclear"), row("C11", 2, "unclear")], tmp_path)
    save_verdict([row("C11", 1, "supported"), row("A2", 1, "supported")], tmp_path)
    table = pd.read_csv(tmp_path / "verdicts.csv")
    assert len(table) == 3
    assert table[(table.probe == "C11") & (table.collection_id.astype(str) == "1")]["verdict"].iloc[0] == "supported"
    assert table[(table.probe == "C11") & (table.collection_id.astype(str) == "2")]["verdict"].iloc[0] == "unclear"


def test_save_run_info_keeps_one_row_per_probe(tmp_path):
    save_run_info("C10", 50, tmp_path)
    save_run_info("C10", 1658, tmp_path)
    save_run_info("A1", 1658, tmp_path)
    table = pd.read_csv(tmp_path / "run_info.csv")
    assert len(table) == 2 and int(table[table.probe == "C10"]["n_dev_used"].iloc[0]) == 1658


def test_the_fingerprint_never_includes_the_test_split():
    names = " ".join(fingerprint_inputs())
    assert "test" not in names.replace("data/embeddings", "") and "library.jsonl" in names and "dev.jsonl" in names


# ---- the vote and the score helpers
def fake_context(library_risks):
    return SimpleNamespace(lib_map={k: set(v) for k, v in library_risks.items()})


def test_the_vote_winner_is_the_most_common_danger():
    ctx = fake_context({1: ["Fire"], 2: ["Fire", "Burns"], 3: ["Chemical"]})
    assert groups.vote_winners(ctx, np.array([[1, 2, 3]])) == ["Fire"]


def test_a_tie_goes_to_the_closest_neighbour():
    ctx = fake_context({1: ["Chemical"], 2: ["Fire"]})
    assert groups.vote_winners(ctx, np.array([[1, 2]])) == ["Chemical"]     # one vote each: the closest (card 1) wins
    assert groups.vote_winners(ctx, np.array([[2, 1]])) == ["Fire"]


def test_macro_f1_is_one_for_a_perfect_vote_and_zero_for_a_wrong_one():
    ctx = SimpleNamespace(dev_risks=[{"Fire"}, {"Chemical"}])
    predicted, truth, types = groups._macro_f1_parts(ctx, ["Fire", "Chemical"])
    assert groups._macro_f1(predicted, truth, np.arange(2)) == pytest.approx(1.0)
    predicted, truth, _ = groups._macro_f1_parts(ctx, ["Chemical", "Fire"])
    assert groups._macro_f1(predicted, truth, np.arange(2)) == pytest.approx(0.0)


def test_top_ids_with_an_allowed_table_only_returns_allowed_cards():
    library = np.array([[1, 0], [0.9, 0.1], [0, 1]], dtype=np.float32)
    query = np.array([[1, 0]], dtype=np.float32)
    allowed = np.array([[False, True, True]])
    assert groups._top_ids(query, library, [10, 20, 30], k=2, allowed=allowed)[0].tolist() == [20, 30]


def test_the_probe_code_never_names_the_test_file():
    import pathlib
    for module in (groups, __import__("boxes.run_probes", fromlist=["x"])):
        assert "test.jsonl" not in pathlib.Path(module.__file__).read_text(encoding="utf-8")


def test_dangers_covered_pairs_each_alert_with_its_own_neighbours():
    lib = {1: {"Fire"}, 2: {"Chemical"}, 3: {"Choking", "Burns"}}
    risk_sets = [{"Fire", "Burns"}, {"Chemical"}]            # two alerts
    neighbours = np.array([[1, 3], [1, 1]])                  # alert 0 sees Fire+Choking+Burns, alert 1 sees only Fire
    shares, full = groups.dangers_covered(risk_sets, neighbours, lib)
    assert shares.tolist() == [1.0, 0.0] and full.tolist() == [1.0, 0.0]


def test_running_a_probe_again_replaces_its_verdict_rows_even_with_mixed_collection_ids(tmp_path):
    row = lambda probe, cid, verdict: {"probe": probe, "collection_id": cid, "verdict": verdict, "claim": "c", "decision": "d"}
    save_verdict([row("C13", "all", "supported"), row("D17", 1, "not supported"), row("D17", 2, "not supported")], tmp_path)
    save_verdict([row("D17", 1, "supported"), row("D17", 2, "supported")], tmp_path)     # the same probe, run again
    table = pd.read_csv(tmp_path / "verdicts.csv", dtype=str)
    assert len(table) == 3                                          # no duplicates
    assert set(table[table.probe == "D17"]["verdict"]) == {"supported"}
