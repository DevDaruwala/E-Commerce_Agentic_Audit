"""
Tests for the audit page: the non-UI logic in frontend/audit_client.py
(batching, index offsets, title recovery) and a smoke test of the page.
The backend is the real FastAPI app, called in-process through TestClient,
so no server needs to be running.
"""

import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from app.main import app
from frontend import audit_client

RAW = json.loads((Path(__file__).resolve().parent.parent / "raw_listings.json").read_text())
backend = TestClient(app)


class FakeUpload:
    """Stands in for Streamlit's UploadedFile (only .getvalue() is used)."""
    def __init__(self, content: bytes):
        self._content = content

    def getvalue(self) -> bytes:
        return self._content


def _by_gtin(gtin: str) -> dict:
    return copy.deepcopy(next(x for x in RAW if x["gtin"] == gtin))


def test_parse_upload_accepts_a_list():
    listings, error = audit_client.parse_upload(FakeUpload(b'[{"a": 1}]'))
    assert listings == [{"a": 1}] and error is None


@pytest.mark.parametrize("content", [b"not json", b'{"a": 1}', b"[]", b"\xff\xfe"])
def test_parse_upload_rejects_bad_files(content):
    listings, error = audit_client.parse_upload(FakeUpload(content))
    assert listings is None and error


def test_run_audit_batches_keep_original_indices_and_titles(monkeypatch):
    # Route the page's HTTP calls to the in-process backend, tiny batches.
    monkeypatch.setattr(audit_client.requests, "post", backend.post)
    monkeypatch.setattr(audit_client, "BATCH_SIZE", 2)

    clean = _by_gtin("5449000123454")        # index 0 -> compliant
    bad_gtin = _by_gtin("not-a-barcode")     # index 1 -> blocked
    hygiene = copy.deepcopy(RAW[0])          # index 2 -> non_compliant
    no_title = {"price": 5}                  # index 3 -> blocked
    listings = [clean, bad_gtin, hygiene, no_title, "hello"]  # index 4 -> blocked

    seen = []
    out = audit_client.run_audit(listings, "", on_progress=seen.append)

    assert out["total"] == 5
    assert [r["index"] for r in out["rejected"]] == [1, 3, 4]   # not batch-relative
    assert out["titles"] == [clean["title"], hygiene["title"]]
    assert [r["verdict"] for r in out["results"]] == ["compliant", "non_compliant"]
    assert seen == [2, 4, 5]                                    # progress per batch


def test_page_loads_with_start_button_disabled():
    at = AppTest.from_file("../frontend/streamlit_app.py").run()
    assert not at.exception
    start = next(b for b in at.button if b.label == "Start audit")
    assert start.disabled
