"""
frontend/streamlit_app.py — a temporary page to test the validation
pipeline by hand: paste or upload raw listing JSON, see which listings
pass ProductListing's schema, then optionally store the passed ones.

Not part of the later app/dashboard.py — this is a standalone testing
tool for Phase 1.
"""

import json

import requests
import streamlit as st

BACKEND_URL = "http://localhost:8000"

st.title("Listing Validation Tester")
st.write(
    "Paste raw listing JSON (a single object or an array) or upload a "
    ".json file, then click Validate to check each listing against "
    "ProductListing's schema."
)

if "results" not in st.session_state:
    st.session_state.results = None

text_input = st.text_area("Paste raw JSON here", height=250)
uploaded_file = st.file_uploader("...or upload a .json file", type="json")

if st.button("Validate"):
    st.session_state.results = None

    if uploaded_file is not None:
        raw_text = uploaded_file.read().decode("utf-8")
    else:
        raw_text = text_input

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as e:
        st.error(f"Couldn't parse that as JSON: {e}")
        parsed = None

    if parsed is not None:
        listings = parsed if isinstance(parsed, list) else [parsed]

        results = []
        try:
            for i, listing in enumerate(listings):
                label = listing.get("title") or f"Listing {i + 1}"
                response = requests.post(
                    f"{BACKEND_URL}/listings/validate", json=listing
                )
                response.raise_for_status()
                outcome = response.json()
                results.append(
                    {
                        "raw": listing,
                        "label": label,
                        "is_valid": outcome["is_valid"],
                        "errors": outcome["errors"],
                    }
                )
            st.session_state.results = results
        except requests.exceptions.ConnectionError:
            st.error(
                "Couldn't reach the backend at "
                f"{BACKEND_URL}. Is it running? "
                "(uvicorn app.main:app --reload)"
            )

if st.session_state.results:
    results = st.session_state.results
    st.subheader("Results")

    for r in results:
        if r["is_valid"]:
            st.success(f"{r['label']}: PASS")
        else:
            st.error(f"{r['label']}: FAIL")
            for msg in r["errors"]:
                st.write(f"- {msg}")

    passed = [r for r in results if r["is_valid"]]
    failed = [r for r in results if not r["is_valid"]]
    st.write(f"**{len(passed)} passed, {len(failed)} failed**")

    if passed:
        st.subheader("Store the passed listings?")
        col1, col2 = st.columns(2)

        if col1.button("Store passed listings"):
            stored_count = 0
            for r in passed:
                response = requests.post(
                    f"{BACKEND_URL}/listings/new_productlisting",
                    json=r["raw"],
                )
                if response.ok:
                    stored_count += 1
            st.success(f"Added {stored_count} listings.")
            st.session_state.results = None

        if col2.button("Discard"):
            st.info("Discarded — nothing was stored.")
            st.session_state.results = None
