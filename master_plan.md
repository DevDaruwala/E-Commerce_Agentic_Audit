# E-Commerce Agentic Audit — Master Plan

*A living reference. Keep this one step away — update it as decisions change.*

**Related documents** — this file is a summary/index; details live in:
- `FIELD_DECISIONS.md` — per-field reasoning for every schema field
- `Dataset_Strategy.md` — dataset source, category selection, worked example
- `system-design.html` — current pipeline diagrams (open in a browser)

---

## 1. Project aim

An autonomous system that audits e-commerce product listings against
EU product-safety law (GPSR — Regulation (EU) 2023/988), the way a
real marketplace (Otto, Zalando, Amazon.de) would need to, at a scale
no human review team could handle.

**Why it matters:** marketplaces are legally liable for third-party
listings. Sending every listing through an expensive vision-language
model is financially unsustainable at scale. This system solves that
with a cost-tiered pipeline: cheap checks catch the obvious cases,
expensive AI only runs on what genuinely needs it.

## 2. What "compliance" actually means here

A digital auditor can't physically test a product (e.g. measure a
thermostat's failure temperature). Compliance is enforced through
**procedural and legal evidence** instead:

- **Instant blacklist match** — is this exact product (by GTIN/EAN
  barcode) already a known recall on EU Safety Gate?
- **Category → directive mapping** — does this product type (e.g. a
  220V appliance) trigger specific standards (e.g. Low Voltage
  Directive 2014/35/EU)?
- **Legal hygiene checks** — does the listing show a valid EU
  Responsible Person address/email (GPSR Art. 16), a Declaration of
  Conformity, an authentic CE mark, and safety warnings in the local
  language?

These three checks map directly onto `ProductListing`'s required
fields — worth keeping in mind when we finalize `schemas.py`.

## 3. Data strategy

A **symmetric 30-item benchmark** from real sources, to avoid the
model just learning "recalled items are formatted differently"
instead of real safety patterns:

- **15 unsafe listings** — real recalled products from **EU Safety
  Gate / RAPEX** open alerts.
- **15 safe listings** — real listings from **McAuley Amazon Review
  Data** (UCSD), not Open Products Facts — Open Products Facts is now
  only a secondary, optional cross-check (e.g. confirming a real
  barcode), since most of its entries are too sparse to use as the
  primary safe source.
- **Categories are data-driven, not assumed:** Toys, Electronics,
  Cosmetics, Baby/Childcare, Clothing — derived from real EU Safety
  Gate 2024/2025 annual report alert proportions. Cosmetics is
  actually the single largest real category and was missing from the
  original placeholder list.

Full reasoning (why Open Products Facts and Amazon Berkeley Objects
were rejected as the primary safe source, the real alert-proportion
data behind the category list, and a worked example converting a real
McAuley record into a `ProductListing`) lives in `Dataset_Strategy.md`.

## 4. System architecture

```
Product listing submitted
   (tagged: marketplace_id, distributor_id)
      |
      v
Step 0 -- Blacklist check (SQLite, RAPEX-seeded)
   Exact GTIN/EAN match against a known recall?
      |                                |
   no match                        match
      |                                |
      v                                v
Step 1 -- Hygiene check           Immediate REJECT ---------+
   Are mandatory fields                (reason recorded,     |
   populated at all?                    no LLM needed)       |
      |                                |                     |
   complete                        missing                   |
      |                                |                     |
      v                                v                     |
Audit agent team                  Instant FAIL ---------------+
  (every listing that reaches       (reason recorded,          |
   here -- no risk-tier split,       no LLM needed)            |
   no classifier to score one)                                 |
      |                                                        |
   Investigator agent (ReAct)                                  |
      |                                                        |
   MCP tool server:                                            |
      - Category -> directive mapping (RAG / GraphRAG,         |
        deferred, see Section 9/10)                            |
      - Hybrid rule search (Qdrant + BM25)                      |
      - Vision + OCR label check (Florence-2, Qwen2.5)          |
      |                                                         |
   Evidence bundle                                              |
      |                                                         |
   Reviewer agent                                               |
      |                                                         |
   +----+----+                                                  |
 confirm   escalate                                             |
   |            |                                               |
   v            v                                               |
Report writer  Human review queue                                |
(Gemini, prompted)                                                |
   |                                                             |
   v                                                             |
   +------------------------------+----------------------------+
                                  v
                         AuditResult stored
              (request_id: uuid4, submitted_at, risk_type, ...)
                                  |
                      +-----------+-----------+
                      v                       v
              Distributor view         Marketplace view
              (own listings only)      (all distributors, one tenant)

        Streamlit dashboard, filtered by distributor_id / marketplace_id
```

**Why the blacklist check sits before everything else:** it's an
exact database lookup — cheaper than any LLM call. If a product is
already a known recall, there's no need to investigate or call an LLM
at all. This is the same "cheapest check first" principle behind the
whole triage design — the hygiene check sits at that same
cheap-deterministic tier, one step later, for the same reason: no
point running an LLM on a listing that's missing mandatory fields.

**Why the reviewer checks every listing that reaches it:** there's no
risk tier to bypass — the ML classifier that would have produced one
is cut from the design entirely (training data had source-style
leakage; see `Dataset_Strategy.md`). Every listing the agent
investigates gets the same reviewer sanity gate before anything
reaches the final report.

## 5. Tech stack

| Layer | Tool |
|---|---|
| Backend | FastAPI, Pydantic |
| Agent orchestration | LangGraph |
| Tool protocol | FastMCP (MCP SDK) |
| Reasoning model | Google Gemini (Flash) — primary; Groq documented as an evaluated alternative (faster, but tighter free daily token cap) |
| Vision + OCR | Florence-2, Qwen2.5 |
| Retrieval | Qdrant + BM25 (hybrid), Neo4j (graph, if we go GraphRAG) |
| Recall database | SQLite, seeded from RAPEX open data |
| Tracing | Langfuse |
| Frontend | Streamlit |
| Deployment | Docker, GitHub Actions, Azure Container Apps, Azure Blob Storage |

**Open decision:** category→directive mapping can be a knowledge
graph (Neo4j, more advanced, more setup) or a simpler flat hybrid
search (matches Audit_Core.pdf's simpler suggestion). We'll decide
this concretely at the start of Phase 2.

**Cut from scope entirely (not deferred):** the ML risk classifier
(scikit-learn/LightGBM) is removed from the design after its training
data turned out to have source-style leakage (see `Dataset_Strategy.md`).
The 500-row dataset built for it is repurposed as the agent's
evaluation set instead. QLoRA fine-tuning/quantization for the report
writer is also cut — it's Gemini, prompted, not fine-tuned.

**Deferred, not active:** GraphRAG (Neo4j) — see Section 9/10; hybrid
search only is what's actually being built for Phase 2.

---

## 6. Phase 1 — Foundation

**Focus:** one honest, working system. No agent yet, on purpose.

**Build tasks:**
1. `schemas.py` — define `ProductListing` (including
   `marketplace_id`, `distributor_id`, and the legal-hygiene fields
   from Section 2) and `AuditResult` (including `request_id` [uuid4,
   `default_factory`] and `submitted_at`). **Done.**
2. `validation.py` — structural checks (types, required-ness), tested
   against 3 deliberately broken listings.
3. `hygiene_check.py` — GPSR compliance-*completeness* checks (is the
   Responsible Person, safety warning, and CE marking field actually
   populated) — distinct from `validation.py`'s structural checks.
4. **Build the real 30-item benchmark** — 15 RAPEX recalls + 15
   McAuley Amazon Review Data listings, same schema. See Section 3 /
   `Dataset_Strategy.md`.
5. `recall_check.py` — the Step 0 instant blacklist match against the
   RAPEX-seeded SQLite table.
6. `llm_audit.py` — fixed 3-step pipeline (no agent logic yet; stands
   in for the real agent until Phase 2).
7. Wire it behind one FastAPI endpoint + a bare Streamlit page.

**Done so far (Week 1):** `schemas.py` and `app/main.py` (FastAPI
skeleton, startup loading from `raw_listings.json`, basic CRUD +
placeholder audit endpoint).

**Fail-forward exercise:** feed it a listing with a missing field, a
dead image URL, and one that's hygiene-complete but still physically
dangerous. Fix only what actually breaks.

**Definition of done:** a real verdict, with a cited reason, on a real
recalled product and a real compliant one — not just synthetic
placeholders.

## 7. Phase 2 — Agentic + smarter retrieval

**Focus:** turn the fixed pipeline into a real agent, add hybrid
search/graph retrieval, add the reviewer agent (checking every
listing that reaches it — single path, no bypass; there's no risk
tier to bypass with).

**Build tasks:**
1. Write the agent's decision logic in plain English before touching
   LangGraph.
2. Build the MCP tool server, one tool at a time — hybrid search
   first, then category mapping, then vision+OCR.
3. Add the reviewer agent.
4. Add Langfuse tracing once the agent already works.

**Deferred:** GraphRAG is cut from active scope — hybrid search
(Qdrant + BM25) only is being built now. GraphRAG stays a documented
future extension (see Section 9/10), not part of this phase's build
tasks.

**Fail-forward exercise:** ask the agent to audit a listing with no
photo and no matching directive — make sure it says "uncertain"
instead of hallucinating a confident answer.

**Definition of done:** the agent visibly skips tools it doesn't need,
the reviewer catches at least one deliberately-planted bad verdict,
and every listing that reaches the reviewer gets checked before the
final report.

## 8. Phase 3 — Make it real

**Focus:** a prompted (not fine-tuned) report-writing model, proper
testing, and a real cloud deployment.

**Build tasks:**
1. Write 20–30 example reports by hand to prompt-engineer the Gemini
   report writer against.
2. Build and test the Dockerfile locally before any CI/CD.
3. GitHub Actions: tests first, deployment step second.
4. Deploy to Azure Container Apps; reports/images in Azure Blob
   Storage.

**Cut from scope:** QLoRA fine-tuning/quantization for the report
writer — see Section 5's tech stack note. Gemini, prompted, is the
whole plan; there's no model to fine-tune.

**Fail-forward exercise:** deliberately break the Docker build and the
CI pipeline once each, on purpose, and practice reading the failure.

**Definition of done:** `docker compose up` works from a clean clone,
CI runs automatically, the system is live at a real Azure URL.

---

## 9. Notes on Audit_Core.pdf

**Worth adopting as-is:**
- The real RAPEX + Open Products Facts data strategy (verified
  accessible — see Section 3).
- The instant blacklist match as a Step 0, before any LLM call.
- The specific legal-hygiene fields (EU Responsible Person, DoC, CE
  mark, language warnings) — good input for `schemas.py`.

**Worth treating as a starting guess, not a fixed fact:**
- The **0.35 risk threshold** — Audit_Core.pdf states this as an
  already-decided classifier confidence cutoff for the low/high-risk
  split. Moot now: the classifier (and the risk tier it would have
  produced) is cut from the design entirely, so there's no score left
  to threshold. Noted here only so a future re-read of Audit_Core.pdf
  doesn't resurrect it as a live decision.
- Whether category mapping is a knowledge graph or flat hybrid search
  — Audit_Core.pdf implies the simpler option; we still have this as
  an open decision for Phase 2.

---

## 10. Actors & Extensibility — Future Scaling (not built)

**Status: documentation of reasoning only.** Same treatment as the
GraphRAG note elsewhere in this file — a designed-but-deferred
decision, not a to-do. The current build uses the simple version: a
flat `marketplace_id` / `distributor_id` string pair on
`ProductListing`, no pairwise derivation, no product/listing split.
See `FIELD_DECISIONS.md`'s "Submission-level fields" section for what
actually exists today.

**The real production model, if this went multi-marketplace for
real:** split today's single `ProductListing` into two objects —

- `DistributorProduct` — the marketplace-agnostic master content for
  one product (title, description, images, brand profile). Owned by
  the distributor, exists once regardless of how many marketplaces
  it's sold on.
- `MarketplaceListing` — one per marketplace a `DistributorProduct` is
  published to. Carries the marketplace-specific bits (price, listing
  status) and its own `AuditResult`, since compliance requirements and
  audit history can differ per marketplace even for the same
  underlying product.

**Pairwise distributor IDs:** rather than a distributor having one
`distributor_id` visible to every marketplace it sells on, derive a
*different* external ID per marketplace from one private account —
the same idea as Sign in with Apple's pairwise identifiers. This
prevents marketplace A and marketplace B from trivially joining their
data on a shared ID to discover a seller is active on both.

**The caveat that makes this incomplete on its own:** GPSR Article 19
itself requires disclosing the real manufacturer/Responsible Person
identity on every listing. That means a purely cryptographic pairwise-
ID scheme doesn't fully solve cross-marketplace correlation — two
humans reading real business names and addresses off two different
marketplace dashboards can still connect the same seller by hand,
regardless of what the machine-readable ID says. A real fix for that
needs a legal/contractual data-boundary between marketplaces, not just
an engineering trick. Worth remembering so this isn't oversold as a
complete privacy solution if it's ever discussed (e.g. in an
interview).

**Related fix this implies:** `product_id` — the internal key linking
a `DistributorProduct` to its `MarketplaceListing` copies — must never
appear in any marketplace-facing API response or dashboard. It's an
internal join key only; exposing it would hand marketplaces exactly
the cross-marketplace correlation handle the pairwise-ID scheme is
trying to avoid.