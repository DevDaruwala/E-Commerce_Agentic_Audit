# Dataset Strategy — E-Commerce Agentic Audit

*Reference doc. Read this before building the benchmark or training the
classifier. Revised: category list updated from placeholder guesses to
real EU Safety Gate alert data; schema structure updated to reflect
brand-level vs. article-level fields. No change to the three-tier
pipeline or system architecture below.*

---

## The core problem we solved

No real dataset — RAPEX, Open Products Facts, Amazon Berkeley Objects,
or McAuley's Amazon Review Data — contains GPSR-specific compliance
fields (EU Responsible Person, CE marking status, safety warning
text). None of them were built for a regulation that's barely two
years old. This is a real gap in the world's data, not something
findable with a better search.

**The strategy:** real product content (title, description, brand,
category, images) from real sources + honestly-labeled synthetic
compliance fields on top, with a hygiene-check tier that prevents the
synthetic fields from becoming a shortcut the classifier exploits.

---

## Category selection — now data-driven, not assumed

**Original list (placeholder, never verified):** Toys, Electronics, Cell
Phones, Baby, Home & Kitchen.

**Problem discovered:** this list was picked without checking real
RAPEX/Safety Gate alert proportions. Checked against the EU
Commission's own 2024 and 2025 annual Safety Gate reports, it turned
out wrong in two ways — it included categories that aren't actually
prominent in real alert data (Cell Phones, Home & Kitchen), and it
omitted the single largest real category entirely (Cosmetics).

**Real data, from the EU Safety Gate annual reports (2024/2025):**
- Cosmetics — ~33-36% of all alerts (largest category, 3 years running)
- Toys — ~15-16% of all alerts (2nd largest)
- Electrical appliances and equipment — ~10-11% of all alerts (3rd largest)
- Motor vehicles, clothing/textiles, childcare articles, jewellery — all
  real categories, trailing well behind the top 3

**Revised, final category list:**
```
Toys, Electronics, Cosmetics, Baby/Childcare, Clothing
```

**Reasoning per category:**
- **Toys** — real #2 category, unchanged from original list
- **Electronics** — covers "electrical appliances and equipment," real
  #3 category, unchanged from original list
- **Cosmetics** — real #1 category by a wide margin; was missing
  entirely from the original list, now added
- **Baby/Childcare** — a real, distinct Safety Gate category, retained
  from the original list
- **Clothing** — a real Safety Gate category ("clothing, textiles and
  fashion items"); replaces Cell Phones and Home & Kitchen, neither of
  which are prominent in real alert data

**McAuley Amazon Review Data compatibility check:** McAuley has direct
or near-direct category equivalents for all five: "Beauty" → Cosmetics,
"Toys and Games" → Toys, "Electronics" → Electronics, "Baby Products" →
Baby/Childcare, "Clothing, Shoes and Jewelry" → Clothing. No
compatibility issue introduced by this change.

**34-subcategory consolidation approach:** RAPEX/Safety Gate's
underlying system uses ~34 granular subcategories (e.g. "laser
pointers," "gas appliances and components," "lighting equipment").
Rather than hand-picking which of these to merge, each subcategory
maps into whichever of the 5 buckets above it best fits, following the
EU's own top-level groupings in its annual report — not an invented
grouping.

---

## Data sources — final decision

| Class | Source | Why |
|---|---|---|
| **Unsafe (15)** | EU Safety Gate / RAPEX open alerts, drawn from the 5 categories above | Real recall records: product, brand, model, barcode, category, risk type, risk description, legal provisions. |
| **Safe (15)** | McAuley Amazon Review Data (UCSD), filtered to the McAuley category equivalents above (Beauty, Toys and Games, Electronics, Baby Products, Clothing/Shoes/Jewelry) | Real Amazon listings, spread across the same 5 real-world-weighted categories as the unsafe set — the key fix for keeping the benchmark unbiased. |

**Rejected: scraping live marketplaces (Amazon, Otto, etc.)**
- Violates marketplace Terms of Service.
- Ironic given the project audits exactly this kind of scraping-based
  enforcement.
- Fragile — breaks reproducibility (`docker compose up` should always
  work from a clean clone; a scraper can silently stop working).
- "Still listed" isn't a strong safety signal — some live listings are
  simply not caught yet.

**Rejected/limited: Amazon Berkeley Objects (ABO) as the main safe source**
- Real and rich, but skews toward furniture/home decor based on its
  documented attributes (material, dimensions, pattern, style).
  Doesn't reliably cover RAPEX's actual top-risk categories (toys,
  electronics, cosmetics) — so it doesn't solve the actual problem.

**Open Products Facts** — kept as a secondary, optional cross-check
(e.g. for a real barcode) rather than the primary safe source, since
most entries are too sparse (see the Apple charger vs. blank fields
example we found).

---

## Schema structure — brand-level vs. article-level

**Confirmed from real Zalando GPSR documentation (Partner University,
GPSR-related data requirements):** GPSR-driven fields split cleanly
into two tiers:

- **Brand-level data** — submitted once per manufacturer/brand, shared
  across every listing from that brand: manufacturer name, manufacturer
  address, manufacturer electronic contact, responsible person name,
  responsible person address, responsible person electronic contact.
- **Article-level data** — specific to one individual product listing:
  title, category, price, GTIN, description, product specs, safety
  warning text, safety document (image/PDF link), declaration of
  conformity (PDF link), CE marking status, disposal instructions,
  image URL, rating, review count.

**Why this matters:** avoids redundantly duplicating manufacturer/
responsible-person data across every listing from the same brand — one
`BrandProfile` object is nested inside each `ProductListing`, rather
than flattening brand fields onto every single record.

**Safety information is split into two fields, not one:** Otto and
Zalando both treat safety information as a document/image link
(datasheet photo, warning label image), separate from inline warning
text. `safety_warning_text` stays free text for direct LLM reasoning;
`safety_document_url` is a pointer the future vision/OCR tool
(Florence-2, Qwen2.5, Phase 2) is meant to inspect. Same logic applied
to `declaration_of_conformity_url`, confirmed as a PDF document in
real Zalando data, not free text.

**Category-specific attributes are deferred, not discarded.** Real
marketplace data includes dozens of category-specific attributes
irrelevant outside their own category (UPF rating for sunglasses,
energy class for major appliances). Building per-category schemas
(discriminated unions) to properly type these is deferred past Phase 1
— added complexity across the classifier, hygiene check, and agent
logic outweighs the benefit right now. Raw data may still carry such
fields as noise (`ProductListing` doesn't declare them, so Pydantic
drops them automatically), or — where worth preserving for future
analysis — they land in an open `category_attributes: dict` field. Full
per-field reasoning lives in `FIELD_DECISIONS.md`.

---

## The three-tier structure per listing (unchanged)

1. **Hygiene check (deterministic, cheap):** is the Responsible
   Person, safety warning, and CE marking field populated at all?
   Missing → instant fail, no ML or LLM needed.
2. **ML classifier (real signal):** trained on category, description,
   and risk-indicator features — must NOT be trainable on "field
   present/absent" alone, or it just learns the hygiene check's job
   instead of real risk patterns.
3. **Agent investigation:** for genuinely ambiguous, substantive risk
   (the product might have every procedural field correct and still
   be physically dangerous — see the EZRA charger example below).

**Rule to avoid the trap:** synthetic field presence/absence must vary
independently of the safe/unsafe label. Some safe listings should also
be missing a minor field; some unsafe listings should have everything
procedurally correct. Otherwise the classifier just learns "empty
field = unsafe," which is a shortcut, not real learning. This
independence rule applies to both the real dataset and any raw/
synthetic test data generated for schema testing.

---

## Worked example — from a real McAuley record to a ProductListing

Real record (McAuley Amazon Review Data):
```json
{
  "asin": "0000031852",
  "title": "Girls Ballet Tutu Zebra Hot Pink",
  "feature": ["Botiquecutie Trademark exclusive Brand", "Hot Pink Layered Zebra Print Tutu", "Fits girls up to a size 4T"],
  "description": "This tutu is great for dress up play for your little ballerina...",
  "price": 3.17,
  "imageURL": "http://ecx.images-amazon.com/images/I/51fAmVkTbyL._SY300_.jpg",
  "brand": "Coxlures",
  "categories": [["Sports & Outdoors", "Other Sports", "Dance"]]
}
```

| Field | Status | Handling |
|---|---|---|
| title | Real | Use as-is |
| description / feature | Real | Combine into description |
| brand ("Coxlures") | Real, but not legally = manufacturer | Use as stand-in for brand_profile.manufacturer_name, document as simplification |
| categories | Real | Map to nearest of our 5 categories (Clothing, here) |
| price | Real | Use as-is |
| image_url | Real | Use as-is |
| gtin (GTIN/EAN) | **Missing** — `asin` is Amazon's own ID, not a real barcode | Synthetic (or real, via an optional Open Products Facts cross-check by brand/title) |
| brand_profile.manufacturer_address | Missing | Synthetic |
| brand_profile.responsible_person_* | Missing | Synthetic / absent (varied independently of label) |
| safety_warning_text | Missing | Synthetic / absent (varied independently of label) |
| safety_document_url | Missing | Synthetic / absent (varied independently of label) |
| ce_marking_present | Missing | Synthetic (varied independently of label) |
| declaration_of_conformity_url | Missing | Synthetic / absent |

Resulting `ProductListing` (matches current `schemas.py` field names):
```json
{
  "title": "Girls Ballet Tutu Zebra Hot Pink",
  "category": "Clothing",
  "price": 3.17,
  "gtin": "SYNTHETIC-0000031852",
  "description": "This tutu is great for dress up play for your little ballerina. Fits girls up to a size 4T.",
  "product_specs": null,
  "brand_profile": {
    "manufacturer_name": "Coxlures",
    "manufacturer_address": "Synthetic — not present in source record",
    "manufacturer_email": "synthetic@example.com",
    "responsible_person_name": null,
    "responsible_person_address": null,
    "responsible_person_email": null
  },
  "safety_warning_text": null,
  "safety_document_url": null,
  "declaration_of_conformity_url": null,
  "ce_marking_present": true,
  "disposal_instructions": null,
  "image_url": "http://ecx.images-amazon.com/images/I/51fAmVkTbyL._SY300_.jpg",
  "rating": null,
  "review_count": null,
  "category_attributes": null
}
```

---

## Reminder: the counter-example that justifies the agent existing at all

From a real RAPEX alert (EZRA HC88 charger): CE marking was **visibly
present** in the packaging photo, and the product still failed —
inadequate insulation, doesn't meet EN 60335-1. A printed CE logo
looks identical whether real or counterfeit/falsely applied. This is
why the vision tool (checking a logo is present) can never be the
whole audit — it must work alongside the rule-lookup tool (checking
the underlying standard is actually met).