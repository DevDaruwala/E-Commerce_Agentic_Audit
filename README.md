# E-Commerce Agentic Audit

An autonomous EU product-safety (GPSR) compliance auditor. A product
listing goes through validation, a recall check, a hygiene check, and
an agentic audit team (every listing that clears both — no risk-tier
classifier, that slot is cut from the design; see `master_plan.md`),
ending in a compliance report.

**Status: Phase 1 — building the foundation** (no agent yet, on purpose).
See the project's 3-phase plan for what comes next.

## Project structure

```
app/
  main.py            FastAPI app — the one entry point
  schemas.py         Data shapes: ProductListing, AuditResult
  validation.py      Checks a listing is complete before anything else runs
  hygiene_check.py   GPSR compliance-completeness checks
  recall_check.py    Step 0 instant blacklist match (RAPEX-seeded)
  llm_audit.py       Phase 1: fixed 3-step check (becomes an agent in Phase 2)
  report.py          Turns a verdict into the final report
  dashboard.py       Bare Streamlit UI
data/
  fetch_rapex.py         Pulls real EU Safety Gate alert data
  rapex_blacklist.json   Barcode-bearing alerts for recall_check.py
  build_eval_dataset.py  Builds the agent's evaluation set
  agent_eval_set.csv     The agent's evaluation set (not training data)
tests/
  test_validation.py     Starter tests
```

## Setup

**1. Create and activate a virtual environment**

macOS / Linux:
```
python3 -m venv auditor
source auditor/bin/activate
```

Windows (PowerShell):
```
python -m venv venv
venv\Scripts\Activate.ps1
```

**2. Install dependencies**
```
pip install -r requirements.txt
```

**3. Set up your environment variables**
```
cp .env.example .env
```
Then open `.env` and paste in your real Gemini API key.

## Running it (once Phase 1 is built out)

Start the backend:
```
uvicorn app.main:app --reload
```

In a second terminal, start the dashboard:
```
streamlit run app/dashboard.py
```

Check the backend is alive: visit `http://localhost:8000/health`

## Running tests
```
pytest
```
