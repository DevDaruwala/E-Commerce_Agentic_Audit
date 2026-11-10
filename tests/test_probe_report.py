"""Tests for the report side: chart helpers, the text, and 'no number typed by hand' (written by Claude)."""
import pathlib
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import pytest

import boxes.probe_charts as charts
import boxes.probe_report as report

ROOT = pathlib.Path(__file__).resolve().parent.parent
QMD = ROOT / "reports" / "probe.qmd"


@pytest.fixture(autouse=True)
def empty_results(tmp_path, monkeypatch):
    """Point the report at an empty results folder (nothing has run) and close figures afterwards."""
    monkeypatch.setattr(charts, "PROBE_DIR", tmp_path)
    yield tmp_path
    plt.close("all")


def test_a_missing_csv_gives_none_and_fmt_handles_missing_numbers():
    assert charts.load_csv("nothing_here") is None
    assert charts.fmt(0.12345) == "0.12" and charts.fmt(float("nan")) == "n/a" and charts.fmt(None) == "n/a"


def test_every_block_renders_without_error_when_nothing_has_run():
    for probe in report.SESSIONS:
        report.show(probe)                      # grey "Not run yet" boxes, never an error
    report.show("RANK")
    report.render_read_first()


def test_grouped_bars_draws_with_a_small_sample_and_the_chance_line():
    series = {1: {"value": [0.8, 0.6], "low": [0.7, 0.4], "high": [0.9, 0.8], "n": [100, 12]}}
    ax = charts.grouped_bars(["a", "b"], series, "score", "title", chance=0.3)
    hollow = [p for p in ax.patches if p.get_facecolor()[:3] == (1.0, 1.0, 1.0)]
    assert len(hollow) == 1                      # the n=12 bar is hollow
    assert any(line.get_linestyle() == "--" for line in ax.get_lines() + list(ax.collections))


def test_the_collection_colours_and_labels_are_fixed_and_in_order():
    assert list(charts.COLORS) == [1, 2, 3, 4]
    assert charts.LABELS == {1: "mpnet plain", 2: "mpnet + risk text", 3: "bge plain", 4: "bge + risk text"}
    assert charts.HATCH[1] == "" and charts.HATCH[2] and charts.HATCH[3] == "" and charts.HATCH[4]


def test_the_labels_agree_with_the_probe_code():
    from boxes.probes import LABELS
    assert LABELS == charts.LABELS


def test_the_five_bullets_are_filled_from_the_csv_files(empty_results):
    pd.DataFrame([{"collection_id": c, "metric": m, "value": v, "low": v, "high": v} for c, p, l in ((1, 0.80, 2.5), (2, 0.70, 2.0))
                  for m, v in (("precision_at_5", p), ("lift", l))]).to_csv(empty_results / "F21_compare_k5.csv", index=False)
    seen = []
    import boxes.probe_report as r
    original = r.say
    r.say = lambda text: seen.append(text)
    try:
        r.read_first_bullets()
    finally:
        r.say = original
    text = " ".join(seen)
    assert "mpnet plain" in text and "2.5 times" in text


def test_the_report_files_never_import_probe_or_embedding_code():
    for name in ("probe_report.py", "probe_charts.py"):
        source = (ROOT / "boxes" / name).read_text(encoding="utf-8")
        for forbidden in ("boxes.probes", "probe_groups", "similar_alerts", "sentence_transformers", "chromadb", "test.jsonl"):
            assert forbidden not in source, f"{name} mentions {forbidden}"


def test_no_number_is_typed_by_hand_in_the_prose_of_the_qmd():
    text = QMD.read_text(encoding="utf-8")
    text = re.sub(r"^---.*?---", "", text, count=1, flags=re.S)       # the settings block
    text = re.sub(r"```.*?```", "", text, flags=re.S)                  # the code cells
    prose = [line for line in text.splitlines() if line.strip() and not line.startswith("#")]   # headings may be numbered
    assert [line for line in prose if re.search(r"\d", line)] == []


def test_the_glossary_and_reading_help_contain_no_numbers_except_in_the_term_names():
    # "precision@5" and "Macro-F1" are names of measures, not results.
    for text in (report.GLOSSARY, report.HOW_TO_READ):
        assert not re.search(r"\d", re.sub(r"precision@5|Macro-F1", "", text))
