"""
dashboard.py — the bare Streamlit page. Phase 1 goal: just show the
raw JSON result from the FastAPI endpoint. No styling, no login yet.

Run with: streamlit run app/dashboard.py
(make sure the FastAPI server is also running: uvicorn app.main:app --reload)
"""

import streamlit as st
import requests

st.title("E-Commerce Agentic Audit — Phase 1")

st.write("Paste a product listing below and submit it for audit.")

# TODO: build a simple form matching ProductListing's fields,
# POST it to http://localhost:8000/listings/audit, and st.json() the result.
