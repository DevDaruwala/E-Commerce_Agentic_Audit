"""
frontend/streamlit_app.py — the audit page.

Flow: drag a .json file of listings into the uploader (or click Browse) ->
press "Start audit" -> the file is sent to the backend's POST /listings/audit
in batches -> see audited results and blocked listings -> download the audit
report and the fail report.

Run from the PROJECT ROOT (two terminals):
    uvicorn app.main:app --reload
    streamlit run frontend/streamlit_app.py
"""

import json
import os
import sys
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

# `streamlit run frontend/streamlit_app.py` puts frontend/ on sys.path, not
# the project root, so add the root to be able to `import app....`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.report import build_audit_report, build_rejection_report  # noqa: E402
from app.schemas import AuditResult, RejectedListing  # noqa: E402
from frontend.audit_client import parse_upload, run_audit  # noqa: E402

DEFAULT_BACKEND = os.environ.get("BACKEND_URL", "http://localhost:8000")


st.set_page_config(page_title="GPSR listing audit", page_icon=":material/fact_check:", layout="wide")

with st.sidebar:
    st.header("Settings")
    backend_url = st.text_input("Backend URL", value=DEFAULT_BACKEND)
    st.caption("Start the backend first: `uvicorn app.main:app --reload`")

st.title("GPSR listing audit")
st.write(
    "Upload a JSON file of product listings. Listings with a broken structure are "
    "blocked and explained; the rest are audited (recall check, then legal hygiene check)."
)

uploaded_file = st.file_uploader(
    "Listings file (.json)",
    type="json",
    help="Drag and drop a file here, or click Browse files.",
)

# Forget old results when a different file is chosen (or the file is removed).
file_id = uploaded_file.file_id if uploaded_file else None
if st.session_state.get("file_id") != file_id:
    st.session_state.file_id = file_id
    st.session_state.audit = None

listings = None
if uploaded_file is not None:
    listings, error = parse_upload(uploaded_file)
    if error:
        st.error(error, icon=":material/error:")
    else:
        st.success(f"Found {len(listings)} listings in {uploaded_file.name}.", icon=":material/check_circle:")

if st.button("Start audit", type="primary", icon=":material/play_arrow:", disabled=listings is None):
    progress = st.progress(0.0, text="Starting…")
    try:
        with st.spinner("Auditing…"):
            st.session_state.audit = run_audit(
                listings,
                backend_url,
                on_progress=lambda done: progress.progress(
                    done / len(listings), text=f"Audited {done} of {len(listings)}"
                ),
            )
        progress.empty()
    except requests.exceptions.ConnectionError:
        progress.empty()
        st.error(
            f"Could not reach the backend at {backend_url}. "
            "Is it running? Start it with: uvicorn app.main:app --reload",
            icon=":material/cloud_off:",
        )
    except requests.exceptions.RequestException as e:
        progress.empty()
        st.error(f"The backend returned an error: {e}", icon=":material/error:")

audit = st.session_state.get("audit")
if audit:
    results = [AuditResult(**r) for r in audit["results"]]
    rejected = [RejectedListing(**r) for r in audit["rejected"]]
    audit_report = build_audit_report(results, audit["titles"])
    fail_report = build_rejection_report(rejected)

    compliant = sum(r.verdict == "compliant" for r in results)

    st.subheader("Summary")
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Uploaded", audit["total"])
        c2.metric("Audited", len(results))
        c3.metric("Compliant", compliant)
        c4.metric("Non-compliant", len(results) - compliant)
        st.caption(f"{len(rejected)} listings were blocked before the audit (see the Blocked tab).")

    audited_tab, blocked_tab = st.tabs(
        [f"Audit results ({len(results)})", f"Blocked listings ({len(rejected)})"]
    )

    with audited_tab:
        verdict = st.segmented_control(
            "Show", ["all", "compliant", "non_compliant"], default="all", key="verdict_filter",
        )
        rows = [
            {**row, "violations": " | ".join(row["violations"])}
            for row in audit_report["json"]
            if verdict in (None, "all") or row["verdict"] == verdict
        ]
        st.dataframe(
            pd.DataFrame(rows, columns=["title", "gtin", "verdict", "pipeline_stage",
                                        "risk_type", "risk_score", "violations"]),
            hide_index=True,
        )
        with st.container(horizontal=True):
            st.download_button(
                "Audit report (CSV)", audit_report["csv"], "audit_report.csv", "text/csv",
                icon=":material/download:",
            )
            st.download_button(
                "Audit report (JSON)", json.dumps(audit_report["json"], indent=2),
                "audit_report.json", "application/json", icon=":material/download:",
            )

    with blocked_tab:
        if not rejected:
            st.success("No listings were blocked.", icon=":material/check_circle:")
        else:
            st.write(
                "These listings were turned away because their structure is wrong. "
                "Fix them in the **correction file** and upload it again."
            )
            st.dataframe(
                pd.DataFrame(
                    [
                        {"index": r.index, "title": r.title, "gtin": r.gtin,
                         "distributor_id": r.distributor_id, "why blocked": " | ".join(r.errors)}
                        for r in rejected
                    ]
                ),
                hide_index=True,
            )
            with st.container(horizontal=True):
                st.download_button(
                    "Fail report: correction file (JSON)",
                    json.dumps(fail_report["correction_file"], indent=2),
                    "correction_file.json", "application/json",
                    icon=":material/download:", type="primary",
                )
                st.download_button(
                    "Fail report: table (CSV)", fail_report["table_csv"],
                    "fail_report.csv", "text/csv", icon=":material/download:",
                )
