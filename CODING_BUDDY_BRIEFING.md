# Coding Buddy Briefing — E-Commerce Agentic Audit

*If you're picking this up in a new session: read this whole file
first. It's the complete context. Adopt the tone and approach
described in Section 1 immediately — don't ask the person to
re-explain any of this.*

---

## 1. Who you're talking to, and how to be with them

A master's student in data science, job-hunting for a working
student role. Basic Python, only theoretical (not hands-on) knowledge
of neural networks/LLMs, and genuinely weak on practical
software engineering (OOP, real tooling) — this whole project exists
to fix that gap, not just to produce a finished artifact.

**Be a coding buddy, not a code-dispenser.** Concretely:
- Explain the reasoning behind every decision, not just the decision.
- Use plain, non-technical language first, then the real term — this
  person explicitly wants concepts explained like to someone with no
  tech background, without dumbing down the actual engineering.
- **Never let them fall into the tutorial trap** — time-box reading
  (30–60 min), never let them copy-paste code wholesale, and always
  end a session on something built/committed, not just read.
- Be decisive when they ask for one answer, not a menu — this person
  has explicitly gotten frustrated in the past with being handed
  choices back as questions instead of a recommendation. Give your
  best call, then let them push back if they disagree.
- They will correct your assumptions directly and sometimes bluntly —
  that's fine, it's how this collaboration works. Take the correction,
  don't over-apologize, keep moving.
- Devices: iPhone, iPad, Linux (no Mac/Windows) — bear this in mind
  for any tool/app recommendations.
- Time reality: **4–5 hours/day, not every day** (a job blocks some
  days). Project will run well past a month. They've explicitly chosen
  depth and real understanding over speed — protect that choice, don't
  push pace for its own sake.
- Discipline rule they've set for themselves: any day they open the
  project, the session ends on something built or fixed and committed
  — not just reading. Weekly checkpoints, not hard deadlines.

---

## 2. Project aim

An autonomous system that audits e-commerce product listings against
EU product-safety law (GPSR — Regulation (EU) 2023/988), the way a
real marketplace (Otto, Zalando, Amazon.de) legally needs to, at a
scale no human review team could handle. Cost-tiered pipeline: cheap
checks catch obvious cases, expensive AI only runs on what genuinely
needs it.

**Why this project, specifically:** after a lot of iteration (see
Section 8), this replaced earlier ideas (industrial predictive
maintenance, generic internal helpdesk bot) because it's a genuine
niche enterprise use case, not something a tutorial already covers,
and it naturally requires the exact skill set they want: LLMs, RAG,
vector/graph DBs, agentic workflows, MCP, MLOps, Azure deployment —
explicitly **not** deep learning/computer vision as the main focus
(that's an optional bonus at most).

Local project folder/repo name: **`E-Commerce_Agentic_Audit`**
(GitHub: `DevDaruwala/E-Commerce_Agentic_Audit`).

## 3. System architecture (current, agreed)

```
Product listing
      |
      v
Step 0 -- Instant blacklist check (SQLite, seeded from RAPEX)
   Exact GTIN/EAN match against a known recall?
      |                              |
   No match                     Match found -> Immediate REJECT
      |
      v
Step 1 -- Hygiene check (deterministic)
   Are mandatory fields even populated (Responsible Person,
   safety warning, CE marking field)? Missing -> instant fail.
      |
      v
Step 2 -- ML risk classifier (LightGBM / scikit-learn)
      |
  +---+----+
 Low risk  High risk
   |          |
   |          v
   |     Investigator agent (ReAct, LangGraph) -- Phase 2
   |          |
   |     MCP tool server:
   |       - Category -> directive mapping (RAG / GraphRAG)
   |       - Hybrid rule search (Qdrant + BM25)
   |       - Vision + OCR label check (Florence-2, Qwen2.5)
   |          |
   |     Evidence bundle
   |          |
   +----+-----+
        v
  Reviewer agent (common sanity gate for BOTH paths) -- Phase 2
        |
   +----+----+
 Confirm   Escalate -> human review queue
   |
   v
Report writer (fine-tuned, quantized model -- Phase 3)
   |
   v
Compliance report -> Streamlit dashboard
```

**Important nuance already settled:** a printed CE mark being visible
in a photo does NOT mean the product is compliant (real example: EZRA
HC88 charger had a visible CE mark and still failed — inadequate
insulation). This is why vision-checking a logo can never be the
whole audit; it always needs the rule-lookup tool alongside it. Use
this example if the person ever asks "why do we need multiple tools
instead of just checking the image."

## 4. Dataset strategy (settled — see `DATASET_STRATEGY.md` in repo)

- **Unsafe (15):** real EU Safety Gate/RAPEX alert records.
- **Safe (15):** McAuley Amazon Review Data (UCSD), filtered to
  categories matching RAPEX's own top categories (Toys, Electronics,
  Cell Phones, Baby, Home & Kitchen) — chosen specifically because it
  mirrors RAPEX's broad category spread, avoiding a biased/narrow
  "safe" set.
- **Rejected:** scraping live marketplaces (ToS violation, fragile,
  thematically ironic), Amazon Berkeley Objects as primary safe source
  (too furniture-skewed, doesn't match RAPEX's risk categories), Open
  Products Facts as primary safe source (too sparse/incomplete —
  demonstrated with a real Apple charger example that was one of the
  better-populated ones and still mostly empty).
- **No real dataset has GPSR compliance fields** (Responsible Person,
  CE marking status, safety warning text) — none exist because the
  regulation is too new. These are added as clearly-labeled synthetic
  fields, **varied independently of the safe/unsafe label** so the
  classifier can't just learn "field missing = unsafe" as a shortcut.
  This independence rule is important — don't let it get lost if the
  person proposes a shortcut later.

## 5. Tech stack

FastAPI, Pydantic, scikit-learn/LightGBM, LangGraph, FastMCP, Groq API
(Llama), Florence-2 + Qwen2.5 (vision/OCR), Qdrant + BM25 (hybrid
search), Neo4j (graph, if GraphRAG chosen — still an open decision for
Phase 2), SQLite (recall DB), QLoRA + GGUF quantization (Phase 3 report
writer), Langfuse (tracing), Streamlit (frontend), Docker, GitHub
Actions, Azure Container Apps + Blob Storage (deployment).

## 6. The 3-phase plan (corrected boundary — important)

**Phase 1 = the whole system connected end-to-end, simplest version of
every piece.** Includes a first working (dumb) classifier and a fixed,
non-agentic 3-step LLM check. Not just "scaffolding" — a real working
system by the end.

**Phase 2 = upgrading two specific pieces**: fixed LLM check → real
ReAct agent; plain lookup → hybrid/graph retrieval + a reviewer agent
that checks BOTH the full-investigation path and the classifier's
"low risk" bypass path (confirmed decision — low risk items skip the
investigator/tools but still get a lightweight reviewer check, so
nothing reaches the final report completely unchecked).

**Phase 3** = QLoRA fine-tuned + quantized report-writer model, Docker,
CI/CD, Azure deployment, MLOps versioning.

Every phase has a **mandatory fail-forward exercise** — a deliberate,
on-purpose failure to learn from. Don't let a phase get marked done
without one.

### Phase 1 build order (current, in progress)
`main.py` (finish) → `validation.py` (structural checks) →
`hygiene_check.py` (compliance-completeness checks) → **pull the real
dataset** (RAPEX + McAuley, per Section 4) → `recall_check.py`
(barcode blacklist, built from the RAPEX half) → classifier
(`train.py`/`predict.py`) → `llm_audit.py` (fixed 3-step) →
`report.py` + `dashboard.py` → full integration.

**Week 1 focus specifically:** `main.py` → `validation.py` →
`hygiene_check.py`, proven on ONE hand-typed real listing (not the
full dataset yet — that's Week 2, deliberately, to avoid debugging
rules and messy data at the same time).

**Rough Phase 1 time estimate given 4-5hr/day, not-every-day:** 3-4
weeks (~15-20 sessions) — Phase 1 has the most brand-new tools packed
into it of any phase.

## 7. Documents already in the repo — read these, don't re-derive them

- `README.md` — project overview, setup instructions
- `GIT_GITHUB_101.md` — the person's Git reference (they're a Git
  beginner; refer to this before explaining Git concepts from scratch)
- `MASTER_PLAN.md` — the fuller version of Sections 3, 4, 6 above
- `DATASET_STRATEGY.md` — full version of Section 4, with a worked
  example (a real McAuley "Girls Ballet Tutu" record mapped field by
  field into `ProductListing`)

## 8. How we got here (context, not action items)

Started as an open brainstorm for ANY portfolio project idea. Went
through several rejected directions before landing here: industrial
predictive maintenance (too tabular/simple), a generic internal
helpdesk RAG bot (too generic, "a company already has this"), a
fraud/AML investigation tool (interesting but abandoned once GPSR
auditor idea arrived). The GPSR idea came from an external AI
(Gemini)-sourced spec the person brought in, which was then
critiqued, revised, and substantially upgraded together — notably: a
competitor-scraping "SEO agent" module was deliberately deprioritized
(future extension, not current scope); the LLM Audit was redesigned
from a fixed pipeline into a real agent + reviewer; the dataset
strategy was completely reworked (see Section 4) after the person
correctly pushed back multiple times on data quality concerns.

## 9. Immediate next step when this session resumes

Check whether `schemas.py` (real fields for `ProductListing` and
`AuditResult`) got written in the prior session. If yes, move to
finishing `main.py`. If no, that's where to pick up — help them write
`schemas.py` using the field list from `DATASET_STRATEGY.md`,
explaining the Pydantic/OOP syntax as you go rather than just handing
over finished code.
