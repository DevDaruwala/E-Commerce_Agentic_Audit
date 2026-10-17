"""
Tests for the bulk bouncer door: POST /listings/audit, run_gates() and
build_rejection_report().

Fixtures come from the real raw_listings.json (not invented listings):
  - entry 0  "Radiance Retinol Night Serum"  -> fails hygiene (5 gaps)
  - entry with gtin 5449000123454            -> passes every gate
  - entry 25 gtin "not-a-barcode"            -> fails the schema (bad GTIN)
Run with: pytest
"""

import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app, run_gates
from app.recall_check import blacklist_by_barcode
from app.report import build_rejection_report
from app.schemas import ProductListing, RejectedListing

RAW = json.loads((Path(__file__).resolve().parent.parent / "raw_listings.json").read_text())
client = TestClient(app)


def _by_gtin(gtin: str) -> dict:
    return copy.deepcopy(next(x for x in RAW if x["gtin"] == gtin))


@pytest.fixture
def hygiene_fail() -> dict:
    return copy.deepcopy(RAW[0])  # Radiance serum


@pytest.fixture
def clean() -> dict:
    return _by_gtin("5449000123454")


@pytest.fixture
def bad_gtin() -> dict:
    return _by_gtin("not-a-barcode")


def test_run_gates_clean_listing_is_compliant(clean):
    result = run_gates(ProductListing(**clean))
    assert result.verdict == "compliant"


def test_run_gates_hygiene_failure(hygiene_fail):
    result = run_gates(ProductListing(**hygiene_fail))
    assert result.verdict == "non_compliant"
    assert result.pipeline_stage == "hygiene_check"
    assert "Missing safety warning text" in result.violations


def test_run_gates_recall_wins_over_hygiene(hygiene_fail):
    # A recalled barcode on a listing that ALSO fails hygiene must report
    # the recall (worst finding first).
    recalled_gtin = next(g for g in blacklist_by_barcode if len(g) == 13)
    hygiene_fail["gtin"] = recalled_gtin
    result = run_gates(ProductListing(**hygiene_fail))
    assert result.pipeline_stage == "recall_check"
    assert result.risk_type == "recalled_product"


def test_one_bad_listing_does_not_stop_the_party(clean, hygiene_fail, bad_gtin):
    response = client.post("/listings/audit", json=[clean, bad_gtin, hygiene_fail])
    assert response.status_code == 200
    body = response.json()
    assert (body["total"], body["rejected_count"], body["audited_count"]) == (3, 1, 2)

    blocked = body["rejected"][0]
    assert blocked["index"] == 1                       # position in the upload
    assert blocked["title"] == bad_gtin["title"]
    assert blocked["gtin"] == "not-a-barcode"
    assert blocked["errors"][0].startswith("gtin:")
    assert blocked["original"] == bad_gtin

    assert [r["verdict"] for r in body["results"]] == ["compliant", "non_compliant"]


def test_non_object_item_is_rejected_not_crashed():
    body = client.post("/listings/audit", json=["hello"]).json()
    assert body["rejected_count"] == 1
    assert body["rejected"][0]["errors"] == ["listing must be a JSON object"]
    assert body["rejected"][0]["title"] is None


def test_listing_missing_title_and_gtin_is_named_safely():
    body = client.post("/listings/audit", json=[{"price": 5}]).json()
    blocked = body["rejected"][0]
    assert blocked["title"] is None and blocked["gtin"] is None
    assert any(e.startswith("title:") for e in blocked["errors"])


def test_empty_list_returns_zeros():
    body = client.post("/listings/audit", json=[]).json()
    assert (body["total"], body["rejected_count"], body["audited_count"]) == (0, 0, 0)


def test_body_that_is_not_a_list_is_422():
    assert client.post("/listings/audit", json={"a": 1}).status_code == 422


def test_rejection_report_contents(bad_gtin):
    rejected = [RejectedListing(index=7, title="T", gtin="x", distributor_id="d",
                                errors=["gtin: bad", "price: bad"], original=bad_gtin),
                RejectedListing(index=8, errors=["listing must be a JSON object"],
                                original="hello")]
    report = build_rejection_report(rejected)

    assert report["correction_file"][0]["_errors"] == ["gtin: bad", "price: bad"]
    assert report["correction_file"][0]["title"] == bad_gtin["title"]   # original kept
    assert report["correction_file"][1] == {"_original": "hello",
                                            "_errors": ["listing must be a JSON object"]}
    lines = report["table_csv"].strip().splitlines()
    assert lines[0] == "index,title,gtin,distributor_id,errors"
    assert "gtin: bad | price: bad" in lines[1]


def test_correction_file_round_trip(clean, bad_gtin):
    """Fix the blocked listing in the correction file and re-upload it:
    it moves from rejected to audited, even with _errors still in it."""
    first = client.post("/listings/audit", json=[clean, bad_gtin]).json()
    rejected = [RejectedListing(**r) for r in first["rejected"]]
    correction = build_rejection_report(rejected)["correction_file"]

    correction[0]["gtin"] = "4006381333931"  # the user fixes the barcode
    second = client.post("/listings/audit", json=correction).json()
    assert second["rejected_count"] == 0
    assert second["audited_count"] == 1


def test_audit_report_rows_and_csv(clean, hygiene_fail):
    from app.report import build_audit_report

    body = client.post("/listings/audit", json=[clean, hygiene_fail]).json()
    from app.schemas import AuditResult
    results = [AuditResult(**r) for r in body["results"]]
    report = build_audit_report(results, [clean["title"], hygiene_fail["title"]])

    assert [row["verdict"] for row in report["json"]] == ["compliant", "non_compliant"]
    assert report["json"][1]["title"] == hygiene_fail["title"]
    assert "Missing safety warning text" in report["json"][1]["violations"]

    lines = report["csv"].strip().splitlines()
    assert lines[0].startswith("title,gtin,verdict,pipeline_stage")
    assert len(lines) == 1 + 2
    assert "Missing safety warning text" in report["csv"]  # joined with " | "
