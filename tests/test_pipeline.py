"""Test run_pipeline on a made-up pool of 10 alerts (70/10/20 split = 7 library, 1 dev, 2 test)."""
import json

import pytest

from boxes.preprocessing import run_pipeline


def alert(case, date, product, name="N", brand="B", description=None, risk=("Injuries",)):
    """One alert with every field the pipeline needs."""
    return {
        "case_number": case, "report_date": date, "category": "Motor vehicles",
        "product": product, "name": name, "brand": brand,
        "description": product if description is None else description,
        "country_of_origin": "Spain", "risk_types": list(risk),
        "law_names": ["Some Regulation"], "risk_description": "risk text",
    }


POOL = [
    alert("C01", "2022-01-01", "Lamp", brand=None, description="Desk lamp"),    # brand missing -> must be written as null
    alert("C02", "2022-01-02", "Lamp", brand=None, description="Desk lamp"),    # exact duplicate of C01 -> removed
    alert("C03", "2022-01-03", "Motorcycle"),                                   # thin (description = product)
    alert("C04", "2022-01-04", "Passenger car", name="Transit", brand="Ford"),
    alert("C05", "2022-01-05", "Kettle", description="Red kettle"),
    alert("C06", "2022-01-06", "Chair", description="Wooden chair"),
    alert("C07", "2022-01-07", "Sofa", description="Grey sofa"),
    alert("C08", "2022-01-08", "Passenger car", name="X", brand="BMW"),         # dev: same words as C04, other brand -> Group 2 (and thin)
    alert("C09", "2022-01-09", "Soft toy", description="Red dragon", risk=("Choking",)),   # test: no twin
    alert("C10", "2022-01-10", "Soft toy", description="Red dragon", risk=("Choking",)),   # test: duplicate of C09 -> removed
]


@pytest.fixture
def folders(tmp_path):
    """A data folder with the three old files (everything in knowledge.jsonl) and an empty output folder."""
    data = tmp_path / "data"
    data.mkdir()
    (data / "knowledge.jsonl").write_text("".join(json.dumps(a) + "\n" for a in POOL), encoding="utf-8")
    (data / "dev.jsonl").write_text("", encoding="utf-8")
    (data / "test.jsonl").write_text("", encoding="utf-8")
    return data, tmp_path / "out"


def read(path):
    return [json.loads(line) for line in open(path, encoding="utf-8")]


def test_counts_after_every_step(folders):
    data, out = folders
    frames, summary = run_pipeline(data, out)
    parts = summary["parts"]
    assert summary["pool"] == 10
    assert parts["library"]["after_split"] == 7 and parts["library"]["duplicates_removed"] == 1
    assert parts["dev"]["after_split"] == 1 and parts["dev"]["group1_removed"] == 0 and parts["dev"]["group2_marked"] == 1
    assert parts["test"]["after_split"] == 2 and parts["test"]["duplicates_removed"] == 1
    assert {n: len(f) for n, f in frames.items()} == {"library": 6, "dev": 1, "test": 1}


def test_saved_files_have_the_flags(folders):
    data, out = folders
    run_pipeline(data, out)
    library, dev, test = (read(out / f"{n}.jsonl") for n in ("library", "dev", "test"))
    assert [a["case_number"] for a in library] == ["C01", "C03", "C04", "C05", "C06", "C07"]   # C02 removed
    assert [a["case_number"] for a in dev] == ["C08"] and [a["case_number"] for a in test] == ["C09"]  # C10 removed
    assert dev[0]["same_words_in_library"] is True and dev[0]["is_thin"] is True
    assert test[0]["same_words_in_library"] is False and test[0]["is_thin"] is False
    assert all("same_words_in_library" not in a for a in library)       # library is not compared with itself
    # C03 and C04 have a description equal to the product (the default in alert()).
    assert {a["case_number"] for a in library if a["is_thin"]} == {"C03", "C04"}
    assert (out / "pipeline_summary.json").exists()


def test_missing_values_are_null_not_nan(folders):
    data, out = folders
    run_pipeline(data, out)
    text = (out / "library.jsonl").read_text(encoding="utf-8")
    assert "NaN" not in text
    assert read(out / "library.jsonl")[0]["brand"] is None


def test_running_twice_gives_identical_files(folders):
    data, out = folders
    run_pipeline(data, out)
    first = {n: (out / f"{n}.jsonl").read_bytes() for n in ("library", "dev", "test")}
    run_pipeline(data, out)
    assert first == {n: (out / f"{n}.jsonl").read_bytes() for n in ("library", "dev", "test")}


def test_save_false_writes_nothing(folders):
    data, out = folders
    run_pipeline(data, out, save=False)
    assert not out.exists()
