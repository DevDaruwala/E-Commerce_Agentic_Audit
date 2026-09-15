# Field Decisions — ProductListing Schema

*Purpose: a permanent record of why each field in `schemas.py` exists,
what it's based on, and why fields we considered were deferred or
excluded. Written so future sessions (and anyone reviewing the repo,
e.g. in an interview) don't have to re-derive this reasoning from
scratch. Every decision below traces to a real source — GPSR Article
19 text, real marketplace documentation (Amazon, Otto, Zalando), or a
deliberate project-scope trade-off.*

---

## Legend

- **GPSR** — legally required by Regulation (EU) 2023/988, Article 19
- **Marketplace** — required by real marketplaces (Amazon/Otto/Zalando)
  but not by GPSR itself
- **Project** — needed for our system to function (agent evidence,
  classifier signal), not required by law or any marketplace

---

## Brand-level fields (nested in `BrandProfile`)

| Field | Basis | Reasoning |
|---|---|---|
| `manufacturer_name` | GPSR | Article 19 — manufacturer identification |
| `manufacturer_address` | GPSR | Article 19 — manufacturer postal address |
| `manufacturer_email` | GPSR | Article 19 — manufacturer electronic contact |
| `responsible_person_name` | GPSR | Article 19 — EU Responsible Person, required when manufacturer is outside the EEA |
| `responsible_person_address` | GPSR | Article 19 — responsible person postal address |
| `responsible_person_email` | GPSR | Article 19 — responsible person electronic contact; confirmed by real Zalando data as a distinct required field, not merely implied |

**Why nested, not flat:** confirmed from Zalando's own GPSR data
requirements sheet — these fields are explicitly documented as
"Partner/Brand level data," submitted once per brand and reused across
every listing, not resubmitted per article. Flattening them onto every
`ProductListing` would duplicate data that's genuinely shared.

---

## Article-level fields (on `ProductListing` directly)

| Field | Basis | Reasoning |
|---|---|---|
| `title` | GPSR | Article 19 — product identification |
| `category` | Project | Needed for routing/analysis; one of 5 data-driven categories (see `DATASET_STRATEGY.md`) |
| `price` | Marketplace | Standard listing field; not GPSR-mandated but required for a realistic listing |
| `gtin` | GPSR | Article 19 — product identification via barcode; validated as 8, 12, 13, or 14 digits (EAN-8 / UPC-A / EAN-13 / GTIN-14) — real GTINs aren't all EAN-13 |
| `description` | Project | Not a GPSR requirement (confirmed — Article 19 does not name it), but confirmed as marketplace-mandatory by Amazon (mandatory for several categories since 2020, expanded 2022/2023). Primarily needed as the main evidence text for the Investigator agent |
| `product_specs` | Project | Optional free-text specs (voltage, materials, age range); not universally applicable, kept Optional |
| `safety_warning_text` | GPSR | Article 19 — warning/safety information; kept as free text for direct LLM reasoning |
| `safety_document_url` | Marketplace | Otto and Zalando both treat safety information as a document/image link (datasheet, warning label image), separate from inline text; this is the hook for the future vision/OCR tool (Florence-2, Qwen2.5) in Phase 2 |
| `declaration_of_conformity_url` | Marketplace | Confirmed from Zalando data as a PDF document, not free text |
| `ce_marking_present` | GPSR-adjacent | Confirmed relevant per original project spec; CE marking presence alone does not equal compliance (see EZRA HC88 charger example in `MASTER_PLAN.md`) |
| `disposal_instructions` | Marketplace | Explicitly required by Otto per their integration documentation |
| `image_url` | GPSR | Article 19 — product identification includes a picture of the product |
| `rating` | Project | Not a compliance signal; legitimate use is audit-priority triage (a dangerous product with many reviews reaches more consumers) |
| `review_count` | Project | Pairs with `rating` for the same triage reasoning |
| `category_attributes` | Project | Open dict for category-specific data (e.g. `energy_class` for electronics) that doesn't warrant a dedicated typed field yet — see "Deferred" section below |
| `model_number` | GPSR | Article 19 — "type, batch or serial number" identification, distinct from `title` |
| `country_of_origin` | GPSR | Article 19 — country of origin, required where the manufacturer cannot be identified |

---

## Deferred (real, valid, not built in Phase 1)

| Field / Feature | Basis | Why deferred |
|---|---|---|
| Per-category typed schemas (`ElectronicsListing`, `ToyListing`, etc. via discriminated unions) | Marketplace | Real, standard pattern (confirmed: Amazon uses per-product-type JSON Schema; Zalando has category-specific mandatory attributes). Deferred because it multiplies complexity across the classifier, hygiene check, and agent logic — disproportionate cost for Phase 1's timeline |
| `energy_class`, `energy_label` | Marketplace | Confirmed real (Zalando data), but only relevant to a narrow slice of Electronics (major appliances). Preserved via `category_attributes` if present in raw data, not built as a dedicated field |
| `risk_assessment_doc`, `bill_of_materials`, `test_reports` | Marketplace | Confirmed real in Zalando's technical documentation fields, but explicitly marked "optional/not displayed to customers" by Zalando itself — low audit value relative to build cost for Phase 1 |
| Category-specific fashion/eyewear attributes (UPF rating, lens type, filter type) | Marketplace | Not applicable to our 5 chosen categories at all — excluded outright, not deferred |

---

## Design decisions (not single fields)

**Why `category_attributes` is a plain `dict`, not typed fields:**
Different categories need entirely different extra attributes (energy
class for appliances, choking hazard flags for toys). Declaring a fixed
field for every possible category's extras would require the same
per-category schema branching we deliberately deferred above. A dict
preserves the raw data for later use without committing to that
complexity now. Trade-off, stated plainly: no type-checking *inside*
this field for now — acceptable since it isn't used by core hygiene/
classifier logic in Phase 1.

**Why Pydantic's "drop undeclared fields" behavior is treated as a
feature, not a risk, in our raw synthetic data:** any raw listing may
carry category-irrelevant noise (e.g. `upf_rating` on a Toys listing,
injected as realistic clutter). Since `ProductListing` doesn't declare
these fields, they're automatically dropped during validation — proving
the schema extracts only genuinely relevant data even from messy,
unfiltered input, without any extra code.

---

## AuditResult fields

| Field | Basis | Reasoning |
|---|---|---|
| `risk_type` | Project | Compulsory `str`, not `Optional` — every AuditResult, including a "compliant" verdict, must set it. A compliant verdict passes the literal string `"none"` rather than omitting the field. Keeping it required avoids `Optional`-handling branches in every downstream consumer (report generation, classifier training) just to special-case the absence of risk. |

---

## Submission-level fields (tenant & request tracking — span `ProductListing` and `AuditResult`)

| Field | Model | Basis | Reasoning |
|---|---|---|---|
| `marketplace_id` | `ProductListing` | Project | Forward-compatible only. The current demo scope is a single marketplace, so this field is functionally inert today — nothing branches on it. Included now so the multi-marketplace model doesn't require a schema migration later. See `MASTER_PLAN.md` §10 for the full future-scaling reasoning. |
| `distributor_id` | `ProductListing` | Project | Functional now, not just forward-looking — the demo has 2-3 distributors under one marketplace, and the dashboard's Distributor view vs Marketplace view filters on this field. |
| `request_id` | `AuditResult` | Project | `uuid.uuid4()`, generated via Pydantic `default_factory` (never caller-supplied). Chosen specifically over a sequential counter because a shared counter would need synchronization across concurrent bulk JSON-dump uploads from multiple distributors — a real scenario here. Not a privacy-motivated choice. Identifies one audit *attempt*; a seller resubmitting a fixed listing gets a new `request_id` against the same listing. |
| `submitted_at` | `AuditResult` | Project | `datetime.now()`, also via `default_factory`. Lets multiple audit attempts on the same listing be ordered by time, rather than relying on `request_id` or `audit_id` ordering (UUIDs aren't sortable by creation time). |
