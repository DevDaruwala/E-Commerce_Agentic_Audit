"""A smoke run of most probes on a small sample of dev alerts (written by Claude). Slow ones (D14, C13) are left to the full run."""
import pandas as pd
import pytest

import boxes.probe_groups as groups
from boxes.probes import ProbeContext

FAST = ["C10", "C11", "C12", "A1", "A2", "A3", "D15", "D16", "D17", "B4", "B5", "B6", "B7", "B8", "B9", "E18", "E19", "E20", "F21", "F22", "F23", "F24", "G25"]


@pytest.fixture(scope="module")
def results(tmp_path_factory):
    out = tmp_path_factory.mktemp("probe_results")
    ctx = ProbeContext(n_dev=40, out_dir=out)
    table = {name: function for probes in groups.GROUP_PROBES.values() for name, function in probes}
    for name in FAST:
        table[name](ctx)
    return out


def test_every_fast_probe_wrote_its_verdict_and_run_info(results):
    verdicts = pd.read_csv(results / "verdicts.csv")
    run_info = pd.read_csv(results / "run_info.csv")
    for name in FAST:
        if name not in ("F23", "F24"):
            assert name in set(verdicts["probe"]), f"{name} wrote no verdict"
    # B7 only uses alerts that have a name, F24 only twenty, so the numbers can be smaller than 40, never larger.
    assert all(0 < n <= 40 for n in run_info["n_dev_used"].astype(int))


def test_the_verdict_words_are_the_allowed_ones(results):
    allowed = {"supported", "not supported", "unclear", "baseline", "not run", "not available"}
    assert set(pd.read_csv(results / "verdicts.csv")["verdict"]) <= allowed


def test_the_results_have_the_agreed_columns(results):
    assert {"collection_id", "metric", "value", "low", "high"} <= set(pd.read_csv(results / "F21_compare_k5.csv").columns)
    assert {"risk_type", "n", "chance_exact", "small_sample"} <= set(pd.read_csv(results / "C10_chance.csv").columns)
    assert {"collection_id", "decile", "sim_low", "sim_high", "precision_at_5", "vote_accuracy"} <= set(pd.read_csv(results / "G25_calibration.csv").columns)


def test_the_risk_text_leak_demo_only_applies_to_collections_2_and_4(results):
    table = pd.read_csv(results / "C12_risk_text_leak.csv")
    assert set(table[table["status"] == "ok"]["collection_id"]) == {2, 4}
    assert set(table[table["status"] == "not applicable"]["collection_id"]) == {1, 3}


def test_chance_does_not_depend_on_the_collection_and_is_below_the_search_score(results):
    c10 = pd.read_csv(results / "C10_chance.csv")
    f21 = pd.read_csv(results / "F21_compare_k5.csv")
    chance = float(c10[c10.risk_type == "ALL"]["chance_exact"].iloc[0])
    best = f21[f21.metric == "precision_at_5"]["value"].max()
    assert 0 < chance < best <= 1


def test_b9_is_marked_as_waiting_and_not_run(results):
    verdicts = pd.read_csv(results / "verdicts.csv")
    assert verdicts[verdicts.probe == "B9"]["verdict"].iloc[0] == "not run"
