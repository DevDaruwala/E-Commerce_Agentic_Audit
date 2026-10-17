# Knowledge Transfer — E-Commerce Agentic Audit

*Snapshot written 2026-10-14 by the chat assistant that mentored this
project from Sep 10. It moves the project from "mentored in a chat
window" to "developed with Claude Code".*

- **The repo is the source of truth.** If this file and the repo
  disagree, trust the repo and tell Dev.
- Where this file conflicts with `CODING_BUDDY_BRIEFING.md`, **this file
  wins**. The briefing still lists old categories, Groq as primary, and
  the LightGBM classifier.
- **Privacy:** this file may be pushed to GitHub. It contains no secrets
  and no personal details. Keep it that way.

---

# Part A — For Dev (plain language)

## What Claude Code is
- An AI assistant that works **inside your project folder** (VS Code
  panel, or `claude` in a terminal opened at the project root).
- Unlike a chat window, it can **read your files, run commands (tests,
  the server) and edit code**, asking your permission first. That means
  it can check the real repo instead of guessing.
- It **forgets everything between sessions.** What it "remembers" is
  what is written in files: `CLAUDE.md` (read automatically at the
  start) and this file.

## How to start a session
1. Open the project folder in VS Code and open the Claude Code panel.
2. Make sure `CLAUDE.md` contains this line: *"Read
   KNOWLEDGE_TRANSFER.md first."*
3. Paste this starter message:

```
Read CLAUDE.md and KNOWLEDGE_TRANSFER.md fully. Without editing
anything, do the "Resume checklist" (Part B, section 12) and report in
15 lines or fewer: what is committed vs not, which cleanup items
landed, and what the next step is. Then wait for my go-ahead.
```

## Habits that keep you in control
- **Plan Mode:** it shows its plan before touching files. Read it.
  Refuse or change anything you don't understand.
- **You approve every commit.** It proposes the message and shows the
  diff. It does not push silently.
- **When confused**, say: *"Explain this line using a real example."*
  `CLAUDE.md` tells it to do that.
- **End every session** with: *"Update the 'Where we left off' section
  of KNOWLEDGE_TRANSFER.md and SESSION_LOG.md, then show me the diff."*
  A stale file is worse than none.
- Run everything from the **project root**. Most of your past errors
  (paths, imports) came from running from inside `app/`.

---

# Part B — For the Claude Code session

## 1. Your role and how to work with Dev
Dev is building this to land AI Engineer roles. It is a portfolio
project, not a production system. **Understanding and demonstrable skill
beat speed and cost.** Be a coding buddy, not a code dispenser.

**Dev's level:** beginner in Python, OOP and FastAPI. Knows ML and deep
learning theory, with little practical experience.

**What works for Dev (learned over four weeks):**
- Short answers. **Long answers confuse him. Use bullets.**
- Plain language first, then the real term.
- Be **decisive**: give one recommendation, not a menu. He gets
  frustrated when options are handed back as questions.
- Trace a **real example with real values** when explaining code.
- Say **where** something is defined when code uses a name from another
  class or file. He won't assume it.
- Explain the *signature* before the *body*; read code as English
  sentences.
- Method for any new concept: short concept talk, then a **sandbox
  exercise on our own data**, then he **explains it back**, then commit.
  No tutorial trap: max 1 hour of video before code, never copy-paste
  wholesale.
- He corrects bluntly. Take it, don't over-apologize, keep moving.
- He needs external deadlines. Weekly check-ins, not daily.
- **Discipline rule:** any day he opens the project, the session ends on
  something built or fixed **and committed**.

**Process rules (authoritative version is in `CLAUDE.md`):**
- Plan Mode first. One task at a time, in roadmap order.
- Show the diff and a proposed commit message. Wait for approval.
- Never invent GPSR compliance values. Follow `Dataset_Strategy.md`.
- Streamlit only for frontend. No auto-accept edits.
- **Verify before building.** Several good catches came from checking
  assumptions against reality (e.g. a "time split" that did not exist,
  a library flag that no longer works). Keep doing that.
- **Be honest about shortfalls.** Never pad data with fabricated
  listings to hit a number. Report the real number.
- When an idea expands scope, state the real cost and recommend the
  smaller option. Dev decides. Past good deferrals: per-category
  schemas, encrypting a public file, extra categories, extra datasets.

## 2. Ownership split
| Area | Who writes it |
|---|---|
| Stage 1 core (`schemas`, `main`, `validation`, `hygiene_check`, `recall_check`) | Dev. In practice he has delegated mechanical pieces when short on time. Fine when he asks explicitly. |
| Dataset and fetch scripts | Claude Code |
| **Stage 2: the agent** (LangGraph, RAG, tools, investigator, reviewer) | **Dev.** This is the skill employers hire for. Explain, review, debug. Do **not** write full implementations unless he explicitly asks. |
| Stage 3 (Docker, CI/CD, Azure, database setup, Streamlit polish, pytest scaffolding) | Claude Code writes, Dev reviews and explains back |

## 3. Project in one page
- **What:** an autonomous system that audits e-commerce listings against
  EU GPSR (Regulation (EU) 2023/988), the way a marketplace (Otto,
  Zalando, Amazon.de) must, at a scale no human team could handle.
- **Idea:** cheap deterministic gates first; the expensive LLM agent
  only on listings that survive them.
- **Why this project:** a real niche use case, and it exercises LLMs,
  RAG, agents, tool use, evaluation and deployment.
- **Key counter-example that justifies the agent:** a real recalled
  charger (EZRA HC88) had a visible CE mark and still failed
  (inadequate insulation). A logo check is never the whole audit.
- **Goal:** start applying around **Nov 10, 2026**, with a working
  pipeline and a 2-minute demo.

## 4. Architecture (current, after the classifier was removed)
```
Listing
  -> Step 0  recall_check   exact GTIN match vs rapex_blacklist.json
                            -> non_compliant (stage recall_check), no LLM
  -> Step 1  hygiene_check  Optional GPSR fields blank, or CE mark False
                            -> non_compliant (stage hygiene_check), no LLM
  -> Audit agent team       Investigator (tools) -> Reviewer   [NOT BUILT]
  -> Report writer          Gemini, prompted                   [NOT BUILT]
  -> AuditResult stored     (nothing is persisted yet)
  -> Distributor view (own listings) / Marketplace view (all distributors)
```
- **Today:** a listing that passes Steps 0 and 1 gets a **placeholder**
  `compliant` verdict in `main.py`. The agent replaces it.
- **Classifier: removed from the design entirely** (decided Oct 14). The
  training data had source-style leakage (see section 7). The slot is
  gone, not deferred. `app/classifier/` stubs should be deleted.
- **Cut from scope:** QLoRA fine-tuning and GGUF quantization, GraphRAG
  (Neo4j), per-category typed schemas, the competitor-scraping "SEO
  agent", real authentication, encrypting the blacklist file.
- **LLM provider:** Gemini (Flash models) through the `google-genai`
  SDK. Groq is a documented alternative only.

**Agent design principles (settled):**
- **Rigid:** a fixed LangGraph order (evidence, investigator, reviewer,
  result). The LLM never chooses the next node.
- The LLM chooses tools **only inside** the investigator, from a small
  set (rule lookup, similar past recalls), with a hard cap of ~3 calls.
- Every agent step returns a **Pydantic model**. On validation failure,
  retry once, then `escalated`.
- Temperature 0. Fixed step budget; running out means `escalated`.
- **Fast:** ~2 to 3 LLM calls per audit, independent tool calls in
  parallel, a Flash model, retrieve first then reason.
- Listing text is **untrusted input** (prompt-injection surface):
  `title`, `description`, `safety_warning_text`, `product_specs`.
  Keep instructions separate from listing text.

**Evaluation plan:**
- `data/classifier_training_data.csv` (500 rows, 250 unsafe / 250 safe)
  is now the agent's **evaluation set**.
- Start with a 50 to 100 row subset (free-tier rate limits).
- Report results with the caveats in section 7.
- **The agent's similar-recalls retrieval index must NOT contain the
  weeks 52 to 104 alerts** (they are the answer key). Build it from
  weeks 0 to 51, re-fetched with the richer fields (risk description,
  legal provisions). The current blacklist keeps only barcode, product
  name, category and alert reference.

## 5. Repo map and status
Python 3.13. The project venv is **`auditor/`**. Run from the project
root.

| Path | Status |
|---|---|
| `app/main.py` | Working. Endpoints below. Placeholder verdict at the end of `/listings/audit`. |
| `app/schemas.py` | Working. Needs evidence / `cited_rule` fields and removal of `"classifier"` from `pipeline_stage`. |
| `app/validation.py` | Done. `validate_listing(raw_dict) -> (bool, [errors])`. Used by `/listings/validate`. |
| `app/hygiene_check.py` | Done. Returns `AuditResult \| None`. Whitespace-only counts as missing. |
| `app/recall_check.py` | Done. Loads `data/rapex_blacklist.json` at import into a dict keyed by barcode. Cites the matched alert. |
| `app/llm_audit.py`, `app/report.py`, `app/dashboard.py` | Stubs |
| `app/classifier/` | Stubs. Delete. |
| `frontend/streamlit_app.py` | Working validate page: paste or upload JSON, PASS/FAIL, confirm store. Does not call `/listings/audit` yet. |
| `data/fetch_rapex.py` | Fetches EU Safety Gate weekly XML reports. |
| `data/build_classifier_dataset.py` | Builds the 500-row evaluation CSV. |
| `data/rapex_blacklist.json` | 1,551 alerts, weeks 0 to 51, about 1,516 unique barcodes |
| `data/classifier_training_data.csv` | 500 rows (the evaluation set) |
| `raw_listings.json` | 30 synthetic listings. 27 pass validation. 3 have deliberately bad GTINs. Several lack responsible-person fields. |
| `tests/test_validation.py` | Placeholder (`assert True`). No real coverage. |
| Docs | `README.md`, `master_plan.md`, `Dataset_Strategy.md`, `FIELD_DECISIONS.md`, `system-design.html`, `CODING_BUDDY_BRIEFING.md`, `SESSION_LOG.md`, `BUILD_LOG.md`, `Git_Github_101.md`, `CLAUDE.md` |

**Endpoints:**
- `POST /listings/validate`: raw dict in, `{is_valid, errors}` out.
- `POST /listings/new_productlisting`: appends to an in-memory list.
- `GET /listings/productlisting`: latest listing, 404 if empty.
- `POST /listings/audit`: recall, then hygiene, then the placeholder.
  Malformed GTINs get a 422 from FastAPI before any check.
- Startup loads `raw_listings.json` into `stored_listings`.
- Storage is **in-memory**. Audit results are not persisted.

**Commands (from the project root):**
```
uvicorn app.main:app --reload
streamlit run frontend/streamlit_app.py
pytest
```
- `BUILD_LOG.md` is appended by a local git post-commit hook (not in the
  repo). It is dirty after every commit. That is expected.
- A redundant `.venv/` (about 687 MB) was once created by a Claude Code
  session. It is gitignored. Use `auditor/`. Safe to delete.

## 6. Schemas (current)
**`BrandProfile`:** `manufacturer_name`, `manufacturer_address`,
`manufacturer_email` (required `str`); `responsible_person_name`,
`responsible_person_address`, `responsible_person_email`
(`Optional[str] = None`).

**`ProductListing`:** `marketplace_id`, `distributor_id`, `title`
(min 1), `category` (plain `str`; 5 intended values), `price` (> 0),
`gtin` (8, 12, 13 or 14 digits), `description` (min 1), `product_specs`,
`brand_profile`, `safety_warning_text`, `safety_document_url`,
`declaration_of_conformity_url`, `ce_marking_present` (required bool),
`disposal_instructions`, `image_url`, `rating` (0 to 5),
`review_count`, `category_attributes` (open dict), `model_number`,
`country_of_origin`. Unlisted fields are optional.

**`AuditResult`:** `audit_id` (set by the caller, uuid4), `request_id`
and `submitted_at` (auto-generated), `listing_gtin`, `verdict`
(`compliant` / `non_compliant` / `escalated`), `risk_type` (str; the
literal `"none"` when compliant, enforced by a `model_validator`;
values in use: `none`, `legal_hygiene`, `recalled_product`),
`risk_score` (0 to 1), `violations: list[str]`, `pipeline_stage`
(`recall_check`, `hygiene_check`, `classifier`, `investigator_agent`,
`reviewer_agent`), `reasoning`.

**Why it is shaped this way:**
- **Schema rejects garbage; hygiene judges compliance.** GPSR fields
  stay Optional so a non-compliant listing still flows through and gets
  a verdict, instead of vanishing as a generic "skipped" error.
- **The `model_validator` stays inside `AuditResult`.** That makes an
  inconsistent result impossible to construct anywhere.
- **`AuditResult` does not copy listing fields** (title, category...).
  Reports join the two records by `gtin`. This avoids stale duplicates.
  A get-by-gtin lookup does not exist yet and will be needed.
- Field provenance (GPSR Article 19 vs marketplace requirement vs
  project need) is documented per field in `FIELD_DECISIONS.md`.

## 7. Data
**Blacklist (Step 0):**
- Source: EU Safety Gate weekly XML export,
  `https://ec.europa.eu/safety-gate-alerts/api/download/weeklyReport/list/xml/en`.
  The data is public and updates weekly.
- Sync periodically into a local file. **Never call the live feed per
  request.**
- **Weeks 0 to 51** feed the blacklist. **Weeks 52 to 104** feed the
  evaluation set. Zero overlap, verified by `alert_reference`. Keep it
  that way, or recall_check will reject the test cases before the agent
  ever sees them.
- 5 categories: **Toys, Electronics, Cosmetics, Baby/Childcare,
  Clothing.** Chosen from real Safety Gate proportions (Cosmetics about
  33 to 36% of alerts, Toys about 15%, Electrical about 10%).
  Cell Phones and Home & Kitchen were dropped.

**Evaluation CSV:**
- Columns: `title, category, price, description, product_specs,
  safety_warning_text, country_of_origin, is_unsafe, source_id`.
- Unsafe rows: real alerts from weeks 52 to 104 (blacklist overlaps
  excluded). Safe rows: McAuley Amazon Reviews 2023 (**US marketplace**),
  read directly from Parquet or JSONL. The `datasets` library with
  `trust_remote_code` no longer works for this repo. The ID field is
  `parent_asin`.
- Backfilled values are label-blind, but **which rows need backfill is
  not label-blind**, so some columns leak the label.

**Known leakage, why the classifier was dropped, and what to do:**
- `source_id` contains "/" on every unsafe row. Exclude it from any
  feature use.
- `price`, `country_of_origin` are real on one class and synthetic on
  the other. `product_specs`, `safety_warning_text` are 100% synthetic.
  Treat all of them as reference only.
- **119 safe rows still carry the placeholder description** "No detailed
  description available..." (zero unsafe rows do). A resample fix was
  designed: skip empty-description McAuley rows during sampling and
  draw replacements (verify it landed).
- Description length and style differ by source (unsafe median about 80
  characters, safe mean about 400). Report this as a known limitation.
- McAuley rows are "not known to be recalled", not "verified compliant".
  Document that limitation.

**Safe-data search results (do not repeat this research):**
- EPREL (EU energy label registry) is public but covers electronics
  only. Possible later upgrade for Electronics safe rows.
- The cosmetics registry (CPNP) is closed to the public. Toys, baby
  products and clothing have no public registry (self-declared CE).
- Open Products Facts was rejected: no description field, mostly French
  text, noisy category tags, some entries are blacklisted recalls.
  Open Beauty Facts, Icecat and Web Data Commons are untested ideas.

## 8. Settled decisions (do not relitigate without new evidence)
- Classifier removed. Agent handles everything that passes Steps 0 to 1.
- Gemini primary. Fixed-order LangGraph. Pydantic outputs everywhere.
- No per-category schemas. `category_attributes` dict holds extras.
- The recall result cites the matched alert reference and product name.
- Batch auditing later: bounded concurrency (asyncio plus a semaphore),
  one agent definition run many times, job-id style API. Not built.
- Security notes: API keys live in `.env` (never committed; update
  `.env.example` for Gemini), validation is a security control, rate
  limiting and a real database come in Phase 3, a prompt-injection test
  is planned.
- Every phase needs one deliberate **fail-forward exercise** (a planned
  failure to learn from). Not yet recorded for Phase 1. The prompt
  injection test can serve as one.

## 9. Known issues and open items (verify, then prioritize)
**Cleanup in flight (status unknown at time of writing; check git):**
1. Commit the untracked data files (`rapex_blacklist.json`,
   `fetch_rapex.py`, `build_classifier_dataset.py`, the CSV) plus
   `requirements.txt`, `CLAUDE.md`, `BUILD_LOG.md`. **Until
   `rapex_blacklist.json` is committed, a fresh clone crashes on
   startup.** This has bitten three times.
2. Hygiene whitespace fix and recall citation: reported done in a
   commit being approved.
3. Placeholder-description resample: not confirmed.
4. Classifier removal across `system-design.html` (diagrams 1 and 2),
   `master_plan.md`, `README.md`, `CODING_BUDDY_BRIEFING.md`; Gemini
   replacing Groq in docs; report writer box changed from "fine-tuned"
   to "prompted"; `Dataset_Strategy.md` filename casing; delete
   `app/classifier/`; prune unused deps (`lightgbm`, `scikit-learn`,
   `sentence-transformers`). Not confirmed.

**Real but lower priority:**
- `recall_check`: about 151 of 1,516 blacklist barcodes can never match
  because the GTIN pattern rejects them (some are 2 to 4 concatenated
  EAN-13s). UPC-A vs EAN-13 forms are not normalized. "Most recent
  alert" is sorted by a parsed `alert_reference`; the blacklist has no
  date field. Add `notification_date` in `fetch_rapex.py` when
  re-fetching.
- `hygiene_check` always requires a Responsible Person. GPSR requires it
  mainly when the manufacturer is outside the EEA, and the schema has no
  manufacturer-country field.
- `category` is a plain `str`; `review_count` allows negatives;
  `image_url` is unvalidated.
- `@app.on_event("startup")` is deprecated (use `lifespan`). It works.
- No real tests; `httpx` is missing from `requirements.txt` (needed by
  `TestClient`). `README` mentions `/health`, which does not exist.
- Stray scratch file `app/sandbox_pandas.py`. Sandbox work belongs in a
  top-level `sandbox/` folder.
- The `.agents/` and `.claude/` skill symlinks point into the
  gitignored venv and dangle on a clone.

## 10. Roadmap
Original 8-week plan started **Sep 10**, with applications targeted for
Oct 15 to 21. That date has passed. Revised plan (about 4 sessions of
3 to 4 hours per week; slide the whole plan if life intervenes, never
skip a learning step):

| Week | Learn | Build | Milestone |
|---|---|---|---|
| 1 (Oct 14-20) | LLM call + structured output; tool calling | Cleanup; schema and rule-corpus design | Structured Gemini call and a tool call, committed |
| 2 (Oct 21-27) | LangGraph basics | Minimal investigator graph, fixed order, one tool | One listing audited by a graph |
| 3 (Oct 28-Nov 3) | RAG basics | Rule corpus (GPSR plus 2 to 3 category laws), rule-lookup tool | Agent cites a real rule and article |
| 4 (Nov 4-10) | Evaluation habits | Reviewer agent; eval on 50 to 100 rows; prompt-injection test | A real catch rate with caveats |
| 5 (Nov 11-17) | none | Report, dashboard, README, demo video, mock interview | Shareable repo |
| 6+ | as needed | Hybrid search (BM25), tracing (Langfuse), Docker/CI | Added while applications are out |

- **Start applying at the end of Week 4** (about Nov 10), once the agent
  catches the recall, hygiene and violation cases on the eval subset.
- Prepare in parallel (about 30 minutes a week): CV project line,
  README that explains each decision, a target list of working-student
  AI/ML roles. German is at A1, so English-language postings are the
  realistic pool.
- Check-in with Dev every Tuesday on what is committed.

**Week 1 task list:**
1. Cleanup (section 9). Gemini key in `.env`; confirm `.env` is
   gitignored; add `google-genai` and `python-dotenv` to requirements.
2. `sandbox/01_structured.py`: plain call; temperature 0 vs 1; a
   `Finding` Pydantic model from a real description; a "no safety info"
   break test; a 10-minute injection test.
3. `sandbox/02_tools.py`: wrap `check_blacklist` as a tool with a clear
   docstring; trace the call loop; a no-tool question; a hard cap of 3
   calls.
4. Schema design (Dev writes, you review): add evidence and
   `cited_rule`, remove `"classifier"` from `pipeline_stage`, define the
   investigator output model. Pick 4 to 6 legal texts (GPSR, Cosmetics
   Regulation, Low Voltage Directive, a toy safety text; check which toy
   text is in force) and download them to `data/rules/`.
5. Explain-back after sessions 2 and 3, then commit.

**Learning sources (Dev prefers video):**
- CampusX, "Agentic AI using LangGraph" playlist: videos 1, 4, 5, 7,
  then "Tools in LangGraph", "RAG using LangGraph" and "Parallel
  Workflows". Skim 2 and 3. Skip the MCP and blog-project videos for now.
- CampusX LangChain playlist (structured output) and LLM Evals playlist:
  exact titles still to be picked.
- Google's Gemini docs for the `google-genai` SDK and structured output.
  Model names change between doc pages; copy the current one from the
  docs or AI Studio.
- The videos are about 15 months old. Concepts hold; copied code may not.

## 11. Learning profile
**Already learned (don't re-teach from zero):** classes, instances,
`self`, `__init__`; Pydantic models, `Optional`, `Field()`, nested
models, cross-field validators; FastAPI path params, request bodies,
`HTTPException`, `/docs`, the idea of `async`; `try/except`; sets vs
dicts and hashing; `**` unpacking; falsy checks; reading tracebacks
bottom-up; basic git.

**Recurring confusions (explain these with a concrete example):**
- Dot chaining through nested models (`listing.brand_profile.x`).
- Where a name is defined (point to the file and line).
- Circular imports. Rule: a module should not import from `main.py`.
- Path and working-directory errors. Always run from the project root;
  build paths with `Path(__file__).resolve().parent...`.
- `{}` as set vs dict (a colon means dict).
- Decorators and the `->` return hint.
- GET vs POST: look at the function's parameters, not its return type.
- Pseudocode pasted into real code (missing colons, "Then"); outputs
  retyped loosely instead of pasted exactly.

**Reading advice he was given:** skim headers, read the first sentence of
each section, zoom in only where confused, then ask. Read tracebacks
from the bottom up and look for your own filenames, ignoring
`site-packages` lines.

## 12. Resume checklist (first 30 minutes, read-only)
1. Read `CLAUDE.md` and this file. Skim `master_plan.md`,
   `system-design.html`, `FIELD_DECISIONS.md`, `Dataset_Strategy.md`.
2. Run `git status`, `git log --oneline -15`, `git ls-files data/`.
3. Check each cleanup item in section 9 for evidence (file and line, or
   a command result). Include
   `grep -c "No detailed description available" data/classifier_training_data.csv`.
4. Confirm the app boots (`uvicorn app.main:app`) and `/listings/audit`
   handles a clean, a recalled, a hygiene-failing and a malformed-GTIN
   listing.
5. Report to Dev in 15 lines or fewer: committed vs not, what landed,
   what is stale in this file, and the recommended next step. Then
   wait for approval.
6. Next step is almost certainly the rest of Week 1. Then run the
   "How to explain code" rules from `CLAUDE.md` for the learning
   sessions.

## Where we left off
*(Replace this section at the end of every session.)*
- **2026-10-17:** step 0.1 done. Cleanup committed (`af2cb2d`, `d05ccfd`):
  `groq` -> `google-genai`, `.env.example` -> `GEMINI_API_KEY`, roadmap
  and docs added. A fresh `git clone` boots `uvicorn app.main:app` and
  loads 27 listings. `BUILD_LOG.md` is appended by a post-commit hook,
  so it shows as modified after every commit. Next: step 0.2, Dev
  writes `MY_MAP.md` (one line per hop of a request) in his own words.
