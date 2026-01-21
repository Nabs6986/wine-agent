# Wine Agent — Wine Data Prepopulation & Ingestion Pipeline (Development Plan)

**Purpose:** Prepopulate Wine Agent with a large, searchable catalog of producers/wines/vintages/importers/distributors and allow users to attach tastings to canonical wine entries. This plan is designed to be handed to Claude Code so it can reconcile architecture decisions against the existing codebase and implement incrementally.

---

## 1. Goals & Non-Goals

### Goals

* Build a **scalable ingestion pipeline** to collect wine metadata from open/permissible sources.
* Maintain a **canonical entity graph** so users can:

  1. search for a wine/vintage/producer, and
  2. add tastings to a pre-existing canonical entry.
* Track **provenance** for every field (source URL, fetched time, extractor version, confidence).
* Support **incremental refresh** (re-crawl only what changes) with rate limiting and domain-level kill switches.
* Establish a framework for adding many sources via **adapters**.

### Non-Goals (for initial phases)

* Real-time pricing arbitrage or market price tracking across paywalled sites.
* Scraping any source requiring authentication / paywall / explicit ToS restrictions.
* Storing large amounts of copyrighted critic notes verbatim.
* Perfect global distributor mapping on day 1 (aim for importer/distributor relationships where public/allowed).

---

## 2. Operating Rules (Hard Requirements)

* Respect **robots.txt** and site ToS by default; make compliance a first-class design constraint.
* **No login/auth** scraping. If a source requires auth, treat it as “partner integration later.”
* Implement **rate limits**, backoff, retries, and caching from the start.
* Store **raw snapshots** (HTML/JSON/PDF) + parsed records; enable reprocessing without re-crawling.
* Every extracted field must be labeled with:

  * `source_url`, `fetched_at`, `extractor_version`, `confidence`, and `raw_reference` (pointer to snapshot).
* Build a **domain kill switch** and global disable for ingestion jobs.
* Prefer **JSON-LD/schema.org extraction** when present; fallback to HTML parsing.

---

## 3. Canonical Entity Model (Conceptual)

This model is intended to be reconciled with the current DB schema. Claude Code should implement or map as appropriate.

### Core canonical entities

* `Producer`

  * canonical_name, aliases[], country/region, website, identifiers (wikidata_id, etc.)
* `Wine` (a cuvée/product line)

  * producer_id, canonical_name, aliases[], style (red/white/sparkling/fortified), grapes[], appellation/region
* `Vintage`

  * wine_id, year, bottle_size_ml (optional), abv (optional), tech_sheet attributes (optional)
* `Region`

  * hierarchy (country → region → subregion → appellation), aliases, external IDs (wikidata)
* `GrapeVariety`

  * canonical_name, aliases, wikidata_id
* `Importer` / `Distributor` (separate entities; may overlap in the real world)

  * canonical_name, country, website, portfolio links (optional)

### “Source listing” entities (non-canonical)

* `Source`

  * domain, policy config, adapter type/version, rate limit config, allowlist/denylist
* `Listing`

  * source_id, url, title, sku, upc/ean, price(optional), parsed_fields(json), snapshot_id
* `Snapshot`

  * fetched binary/object reference + metadata (hash, mime type, fetched_at, status)

### Mapping

* `ListingMatch`

  * listing_id, matched_entity_type (Producer/Wine/Vintage), matched_entity_id, score, decision (auto/manual)

---

## 4. Search & User Flow Requirements

* User searches for:

  * Producer name OR wine name OR (producer + cuvée) OR UPC/EAN
* Results show:

  * canonical entry + key identifiers (producer, region, grape, vintage)
  * provenance indicator (“from X sources”)
* User selects an entry and adds a tasting.
* The tasting is associated with `Vintage` (preferred) or `Wine` if vintage unknown.

---

## 5. Sources Strategy (Phased)

### Tier A: “Backbone” sources (structured/open)

* Wikidata for producers/regions/grapes (seeding and aliases).
* Government/monopoly retailer open catalogs/APIs where legally accessible.
* Producer tech sheets (public PDFs) where allowed.

### Tier B: Retailer pages (allowed domains only)

* Focus on sources with JSON-LD/schema.org.
* Use listing data primarily for discovery and UPC/EAN anchors.

### Tier C: Importer/distributor catalogs

* Prefer explicit public catalogs.
* Otherwise treat as partnership/licensed integrations.

> Claude Code should implement a `SourceRegistry` that makes it easy to add/remove sources and configure policies.

---

## 6. System Architecture (Target State)

### 6.1 Ingestion pipeline modules

1. **Source Registry**

   * Config file(s): domains, crawl rules, parser adapter, throttling, allowed paths.
2. **Crawler**

   * Fetch pages/files (HTML/JSON/PDF)
   * Obeys robots.txt, domain rate limits, content hashing, dedupe.
3. **Snapshot Store**

   * Store raw content; link to DB record; avoid duplicates by hash.
4. **Extractor adapters**

   * `extract(listing|producer|tech_sheet)` returning normalized record + field-level provenance.
   * Priority: JSON-LD → HTML selectors → heuristics.
5. **Normalizer**

   * Normalize region strings, grape names, ABV formats, bottle size, vintage year parsing.
6. **Entity resolution**

   * Match to canonical entities with confidence scoring.
   * Keys: UPC/EAN strongest; otherwise (producer + wine + vintage + region).
7. **Canonical DB Upserter**

   * Creates/updates canonical records; records provenance; maintains aliases.
8. **Indexing**

   * Update search index (Meilisearch/OpenSearch/etc.) on canonical changes.
9. **Admin review tools**

   * UI/API for duplicates, manual merges, and reviewing low-confidence matches.

### 6.2 Job orchestration

* A job queue + worker(s) for crawling/extracting.
* Schedules for refresh:

  * retailer listings: weekly (or domain-specific)
  * producer tech sheets: quarterly
  * wikidata: monthly

---

## 7. Development Phases & Milestones

### Phase 0 — Codebase Recon & Decision Consolidation (Claude Code task)

**Objective:** Align this plan to the existing repo architecture and avoid duplicative systems.

**Deliverables**

* Architecture memo (in repo docs or as PR description) answering:

  * Current DB: Postgres? SQLite? Prisma? SQLAlchemy?
  * Existing entities: Producer/Wine/Vintage/Tasting present already?
  * Existing search: Meilisearch/OpenSearch/SQLite FTS/none?
  * Existing background jobs: BullMQ/Celery/Temporal/cron?
  * Existing storage for files: local FS/S3-compatible/minio?
  * Existing API patterns: REST/tRPC/GraphQL?
  * Existing auth/roles: any admin role?
* Proposed “minimal changes” path and “best long-term” path.

**Open Items (to be filled by Claude Code from the codebase)**

* [OPEN] Where and how tastings are stored and linked today.
* [OPEN] Current schema for wines and whether “Vintage” is a first-class entity.
* [OPEN] Search implementation and whether it supports fuzzy matching + filtering.
* [OPEN] Existing server framework + deployment model (local-only vs hosted).
* [OPEN] File storage strategy (snapshots and label images).
* [OPEN] Logging/monitoring patterns (structured logs, Sentry, etc.).
* [OPEN] Configuration management approach (dotenv, config files, etc.).

---

### Phase 1 — Canonical Schema + Provenance Foundation

**Objective:** Add/confirm canonical entities + provenance tables without any large-scale crawling yet.

**Work**

* Implement (or map to existing) tables/models:

  * Producer, Wine, Vintage, Region, GrapeVariety
  * Snapshot, Listing, ListingMatch, Source
  * Field-level provenance representation (see section 8)
* Add API endpoints (internal) to:

  * create/search producers/wines/vintages
  * attach a tasting to a Vintage/Wine
* Add a search index abstraction (even if backed by DB for now).

**Deliverables**

* Migrations + models.
* Seed script for a few producers/wines manually to validate UX.
* Search endpoint returns canonical records.

---

### Phase 2 — Ingestion Framework (No Big Sources Yet)

**Objective:** Build the pipeline skeleton with a single “toy” source adapter.

**Work**

* Implement Source Registry (config-driven).
* Implement crawler with:

  * robots.txt check
  * per-domain throttling
  * dedupe by hash
  * snapshot persistence
* Implement adapter interface:

  * `discover_urls()` (optional)
  * `fetch_targets()` (optional)
  * `extract_listing(snapshot)` (required for retailer sources)
  * `extract_producer(snapshot)` (optional)
* Implement normalizer + entity resolution v1.
* Implement upsert into canonical entities.
* Implement job runner/queue.

**Deliverables**

* One working adapter (choose a permissive, simple source).
* End-to-end pipeline run that adds records.
* CLI: `ingest --source=<name> --max=<n>`

---

### Phase 3 — Wikidata Seed + Aliases Backbone

**Objective:** Use Wikidata to seed canonical Producers/Regions/Grapes and alias tables for matching.

**Work**

* Create a Wikidata ingestion module (SPARQL / dumps).
* Seed:

  * grape varieties + aliases
  * region hierarchy + aliases
  * producers (where available) + website, country, region, IDs
* Add “alias-first” matching for producers/regions.

**Deliverables**

* Seeded DB with meaningful baseline (thousands+).
* Ability to search producers/regions even before retailers.

---

### Phase 4 — Retailer Crawling at Scale (Allowed Domains Only)

**Objective:** Expand breadth via listing ingestion and UPC anchors.

**Work**

* Add 10–20 retailer adapters:

  * JSON-LD extraction first
  * HTML fallback
* Improve entity resolution:

  * UPC/EAN match
  * fuzzy matching on producer/wine names
  * vintage year parse from titles
  * bottle size normalization
* Add duplicate detection metrics and an admin review endpoint.

**Deliverables**

* “Catalog coverage” increases significantly.
* Search results show multiple sources per wine/vintage.
* Low-confidence matches are queued for review.

---

### Phase 5 — Tech Sheet Mining (Producer Sites / PDFs)

**Objective:** Enrich canonical wines with detailed attributes.

**Work**

* PDF snapshot ingestion + extraction:

  * ABV, grape %, élevage, dosage, RS/pH/TA (when present)
* Attach to wine/vintage with field-level provenance + confidence.
* Add UI display of “Wine Facts” with source indicators.

**Deliverables**

* Enriched wine pages, visibly “knowledgeable.”
* Reprocessing pipeline to improve extraction without re-crawl.

---

### Phase 6 — Importer / Distributor Mapping (Public + Partner)

**Objective:** Create importer/distributor entities and map relationships where allowed.

**Work**

* Ingest from public registries or label approval sources (jurisdiction-dependent).
* Map `Vintage/Wine -> Importer/Distributor` with provenance.
* Add search by importer/distributor portfolio.

**Deliverables**

* “Importer view” working with at least one reliable public source.
* Clear boundary for partner integrations.

---

### Phase 7 — Operations & Maintenance

**Objective:** Make it robust.

**Work**

* Scheduling, incremental refresh, dead link handling.
* Observability:

  * ingestion run summaries
  * errors per domain
  * match confidence distribution
* Admin merge tooling:

  * merge duplicate producers/wines
  * alias management
* Compliance tooling:

  * per-domain kill switch
  * robots cache refresh
  * request headers + user agent policy

**Deliverables**

* Stable weekly ingestion runs with predictable results.
* Easy remediation of duplicates and extraction regressions.

---

## 8. Provenance & Confidence (Implementation Guidance)

**Recommended approach**

* Store extracted facts as either:

  1. canonical columns + separate `FieldProvenance` rows, or
  2. canonical “facts” table where each fact is an attributed claim.

**Minimum fields**

* entity_type, entity_id
* field_path (e.g., `vintage.abv`, `wine.grapes[0]`)
* value (typed or JSON)
* source_id, source_url
* fetched_at
* extractor_version
* confidence (0–1)
* snapshot_id

This enables “show your work” and safe overwrites (choose highest confidence / most recent / trusted source).

---

## 9. Entity Resolution v1 (Rules of Thumb)

* If UPC/EAN exists → treat as strongest match anchor.
* Otherwise compute a match score from:

  * normalized producer name similarity
  * cuvée name similarity
  * vintage year match
  * region/appellation match
  * bottle size match (optional)
* Set thresholds:

  * `>=0.90` auto-merge
  * `0.70–0.89` queue for review
  * `<0.70` create new canonical candidate

---

## 10. Security, Legal, and Compliance Notes

* Do not store or display copyrighted tasting notes scraped from third parties.
* Keep a domain allowlist; ingest only from domains explicitly configured.
* Maintain a “source policy” file and keep it versioned.

---

## 11. Acceptance Criteria (MVP for “Prepopulated Catalog”)

* User can search and select a canonical wine/vintage and attach a tasting.
* Ingestion pipeline can run end-to-end for at least:

  * Wikidata seed, and
  * one retailer adapter
* Provenance is visible in DB and (optionally) surfaced in UI (“data from X sources”).
* Duplicate prevention is functional enough to avoid obvious explosions.

---

## 12. Implementation Checklist (Claude Code Friendly)

* [ ] Recon existing schema & jobs; fill Open Items (Phase 0)
* [ ] Add/migrate canonical entities and provenance structures (Phase 1)
* [ ] Build ingestion skeleton + toy adapter + CLI (Phase 2)
* [ ] Implement Wikidata seed (Phase 3)
* [ ] Add retailer adapters + UPC-based matching + admin review (Phase 4)
* [ ] Add tech sheet PDF extraction (Phase 5)
* [ ] Add importer/distributor entities & mappings (Phase 6)
* [ ] Add scheduling, monitoring, and merge tools (Phase 7)

---

## 13. Notes for Claude Code

When consolidating with the existing codebase:

* Prefer reusing existing DB models and adding “Listing/Snapshot/Provenance” tables rather than rewriting the canonical wine/tasting model.
* Prefer an adapter interface so new sources can be added without touching core ingestion logic.
* Keep ingestion and canonicalization separable: ingestion produces raw + normalized candidates; canonicalization resolves and upserts.

---
