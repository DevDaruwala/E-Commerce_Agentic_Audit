# Status Check — 2026-10-14

**Summary:** Hygiene/recall/schema pipeline runs end-to-end and the clean/recall/hygiene/malformed-GTIN test cases all behave correctly. Two concrete carry-over bugs from last time are still unfixed (whitespace-only hygiene fields, unused `numpy` import + no recall citation). The bigger issue: `data/rapex_blacklist.json` — which `app/main.py` imports transitively at startup — is **untracked**, so a fresh clone will crash on boot. Phase 2 (agent) groundwork is essentially unstarted: no Gemini key/SDK, no LangGraph, no rule corpus, and `AuditResult` has no evidence/citation field. Docs (`CODING_BUDDY_BRIEFING.md`, `system-design.html`, `README.md`) still describe the LightGBM classifier and Groq as current plan, not the new skip-to-agent plan.

---

## 1. Where we left off — **ISSUE**
Reproducibility is broken on a fresh clone.

- Last 15 commits: `367e81e` 2026-09-19 "Bug fixed, None and empy in hygine" · `863048c` 2026-09-19 "Add recall_check.py, update schemas/hygiene_check, real RAPEX data + classifier dataset" · `add796e` 2026-09-15 "new plan changes and hygiene_check" · `291efc0` 2026-09-11 "test: verify post-commit hook" · `852ac4a` 2026-09-11 "Phase 1: schemas.py + main.py skeleton" · `44dc56e` 2026-09-08 merge · `c1388ae`/`d116443`/`63721c6` 2026-09-08 scaffold commits. (Only 9 commits exist total.)
- Untracked: `data/build_classifier_dataset.py`, `data/classifier_training_data.csv`, `data/fetch_rapex.py`, `data/rapex_blacklist.json` (all new dataset work, never committed). Modified-not-staged: `BUILD_LOG.md`, `CLAUDE.md`, `requirements.txt`.
- **main.py imports something not committed, again:** `app/main.py` → `app.recall_check` → `open(BASE_DIR/"data"/"rapex_blacklist.json")` at *module import time*. That file is untracked. A fresh `git clone` would fail on `uvicorn app.main:app` before even reaching the startup event. Confirmed via `git ls-files data/` (only `generator.py`, `mock_list.json` tracked).
- No stashes, no extra branches (`main` only, 2 commits ahead of `origin/main`).

## 2. Leftover tasks from last health check
- **a. GET /listings/productlisting 404 when empty — DONE.** [main.py:44-48](app/main.py#L44-L48) raises `HTTPException(404, ...)` when `stored_listings` is empty; confirmed live (empty-store call returned 404).
- **b. hygiene_check treats "" and whitespace-only as missing — PARTIAL / NOT DONE.** [hygiene_check.py:22-31](app/hygiene_check.py#L22-L31) uses plain `if not field`. Empty string `""` is falsy → caught correctly (verified: empty-field test returned `['Missing responsible person name', 'Missing safety warning text']`). Whitespace-only (`"   "`) is **truthy** in Python, so it slips through uncaught (verified live: a listing with `safety_warning_text="   "` did **not** get flagged). Needs `.strip()`.
- **c. Placeholder description count — gone from CSV: FALSE, still present.** `grep -c "No detailed description available" data/classifier_training_data.csv` → **119** occurrences (out of 500 rows).
- **d. recall_check.py cleanup — NOT DONE (both parts).** [recall_check.py:5](app/recall_check.py#L5) still has `from numpy import block`, unused. The recall AuditResult ([recall_check.py:19-28](app/recall_check.py#L19-L28)) does **not** cite the matched `alert_reference` or product name — violations/reasoning are generic strings ("Product barcode matches a known EU Safety Gate recall" / "This GTIN matches a real, recorded product recall."), even though `blacklist_gtins[gtin]` has both fields available.
- **e. "recall_check" in AuditResult.pipeline_stage — DONE.** [schemas.py:81-83](app/schemas.py#L81-L83) Literal includes `"recall_check"`.
- **f. Other carry-overs found:** CLAUDE.md references `DATASET_STRATEGY.md` (all caps) but the real file is `Dataset_Strategy.md` — case mismatch still present (matches known memory note). `data/mock_list.json` is a 3-byte stub (likely `[]`), so `train.py`/`predict.py` have no real data even if finished.

## 3. Tests right now — **OK** (pipeline logic), **NOT BUILT** (test suite)
- App imports and starts cleanly via `TestClient(app)` — no errors.
- `POST /listings/audit`:
  - Clean listing → `verdict=compliant`, `stage=hygiene_check`, violations `[]`.
  - Recalled GTIN (real blacklist barcode `8001280024351`) → `verdict=non_compliant`, `stage=recall_check`, violations `['Product barcode matches a known EU Safety Gate recall']` (generic, see 2d).
  - Hygiene failure (missing RP name + whitespace-only safety text) → `verdict=non_compliant`, `stage=hygiene_check`, violations `['Missing responsible person name']` only — confirms the whitespace bug in 2b (the whitespace warning should also have been flagged).
  - Malformed GTIN (`"abc123"`) → HTTP **422** (Pydantic field validation, not even reaching the handler) — correct and intentional, not a 500.
- `pytest` runs (1 passed in 0.12s), but `tests/test_validation.py` is still the **placeholder** (`assert True`) — no real coverage of validation, hygiene, recall, or schema constraints exists in the committed test suite.

## 4. Readiness for the agent phase — **NOT BUILT**
- `.env.example` only has `GROQ_API_KEY`; no `GEMINI_API_KEY`. `requirements.txt` lists `groq`, not a Gemini SDK; `langgraph`/`mcp`/`qdrant` appear only in a comment ("we'll add more ... in Phase 2") — nothing installed or pinned yet.
- `llm_audit.py`, `report.py`, `app/classifier/train.py`, `app/classifier/predict.py`, `dashboard.py` are all **stubs** — every function body is either `raise NotImplementedError` or a TODO comment. None of this is wired into `main.py` (confirmed — `main.py` only imports `recall_check`, `hygiene_check`, `schemas`, `validation`).
- `AuditResult` ([schemas.py:44-98](app/schemas.py#L44-L98)) has `verdict` (includes `"escalated"` ✓), `risk_type`, `risk_score`, `violations: list[str]`, `reasoning: str` — but **no dedicated `cited_rule`/`evidence` field**. `violations`/`reasoning` are free text, so an agent citing a specific rule section would have nowhere structured to put it. Gap, not fixed here.
- No rule corpus anywhere in the repo (no GPSR, Cosmetics Regulation, Toy Safety Directive, or Low Voltage Directive text files found by search).

## 5. Risk check — **ISSUE**
- **Secrets:** none found — grepped tracked files and full `git log -p` history for API-key-shaped strings (`sk-`, `gsk_`, `AIza`, `api_key=...`); no hits.
- **Prompt injection surface:** none active yet (no LLM call exists), but the future surface is already defined: `ProductListing.title`, `.description`, `.safety_warning_text`, and `.product_specs` ([schemas.py:21-41](app/schemas.py#L21-L41)) are all free-text, seller-supplied fields with no sanitization — these are what will eventually flow into an LLM prompt in `llm_audit.py`/the investigator agent.
- **Reproducibility:** a fresh clone would **break** — `data/rapex_blacklist.json` is untracked but required at import time by `app.recall_check` (see Section 1). `data/mock_list.json` is tracked but essentially empty. No dangling symlinks found, no `.pkl` committed (correctly gitignored), the `DATASET_STRATEGY.md` vs `Dataset_Strategy.md` casing mismatch would also bite on a case-sensitive filesystem if something actually opens it by that name (nothing does yet, but CLAUDE.md tells a human/agent to read it).
- **Docs contradicting the plan:** `CODING_BUDDY_BRIEFING.md` (lines 83, 144) and `system-design.html` (line 116) still show "Step 2 — ML risk classifier (LightGBM/scikit-learn)" as the next build step, not "deferred." `README.md:55` still tells you to paste in a "Groq API key." `master_plan.md` is actually already updated in places (Gemini Flash as primary, Groq as "documented alternative," line 154) — it's the most current doc, but the diagram text (line 89-ish) still draws the ML classifier inline rather than marked deferred.
- **Evaluation hygiene:** confirmed by direct check — `rapex_blacklist.json` (1,551 alert refs, weeks 0-51) and `classifier_training_data.csv`'s 250 unsafe rows (all 250 carry a `source_id`) have **zero overlap** in `alert_reference`/`source_id`. Per the new plan, the agent's future similar-recalls retrieval index must **NOT** contain `classifier_training_data.csv`'s rows (that's now the held-out evaluation set) — it should be built from `rapex_blacklist.json` (or a fresh pull) only.

## 6. Recommended next 3 steps
1. Commit (or re-derive) `data/rapex_blacklist.json` and the other three untracked `data/*` files so a fresh clone doesn't crash on import — this is the same class of bug that broke clean clones before.
2. Fix the two concrete carry-over bugs you already know about: `.strip()` the hygiene checks so whitespace-only fields count as missing, and remove the dead `numpy` import + add `alert_reference`/`product_name` citation to the recall-check result.
3. Before writing any agent code, add an `evidence`/`cited_rule` field to `AuditResult` and drop at least one real rule-corpus document (GPSR text) into the repo, since the investigator agent has nothing to retrieve from yet.
