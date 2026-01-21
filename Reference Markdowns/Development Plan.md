# Wine Agent — Reference Outline (for Claude Code)

## 0) Purpose and non-goals
**Purpose:** A local-first desktop workflow for capturing wine tastings, converting free-form notes into a structured scoring template, organizing tastings via an **Inbox → Review → Published** pipeline, and enabling fast search/analytics/export.

**Non-goals (v1):**
- Social features / multi-user collaboration
- Cloud sync (optional later)
- Marketplace integrations (Vivino/CellarTracker scraping)

## 1) Core user workflows
### 1.1 Capture (fast)
- User creates a new tasting note in **Inbox**:
  - Paste free-flowing notes (raw text)
  - Optional: add bottle label text / quick facts
  - Minimal required fields to save: `raw_text` OR `title`
- Inbox items are “unstructured” until processed.

### 1.2 Convert (AI-assisted)
- User clicks **Convert** on an Inbox item:
  - LLM produces a **Structured Tasting Note** matching the Wine Scoring Template schema
  - The output is validated, normalized (types/enums), and saved as a draft structured note linked to the inbox item
  - User can regenerate / edit / accept

### 1.3 Review & publish
- User reviews the structured note:
  - Fill missing details, adjust scoring, add tags
  - Mark as **Published** (immutable audit trail via revisions)

### 1.4 Retrieve and learn
- Search/filter by:
  - score, producer, region, grape(s), vintage, style, price, tasting date, readiness window
- Analytics:
  - average score by region/producer/grape
  - “most consistent producers”
  - personal preference patterns (acidity/tannin levels, oak preference)

### 1.5 Export
- Export a tasting note (Markdown + YAML frontmatter)
- Export dataset (CSV/JSON)
- Print-friendly view

## 2) Product requirements
### 2.1 “Local-first” storage
- Primary store: SQLite
- Optional filesystem “vault mode”: save notes as Markdown files (Obsidian-friendly) with YAML frontmatter
- Keep both modes compatible (DB as source of truth; export generates files)

### 2.2 Strict schema + flexible raw input
- A single canonical schema for tasting notes
- Raw notes stored verbatim; conversion outputs stored separately
- Validation with clear user-visible errors

### 2.3 Determinism and traceability
- Every AI conversion stores:
  - model/provider, prompt version, timestamp
  - input hash
  - raw response
  - parsed structured payload
- Revisions: keep history of edits and regenerated outputs

## 3) System architecture (laptop app)
### 3.1 Modules
1. **Core Domain**
   - Pydantic models (canonical schema)
   - Scoring logic / normalization
2. **Persistence**
   - SQLite schema + migrations
   - Repository layer (CRUD, search)
3. **AI Conversion**
   - Provider interface (Anthropic/OpenAI/local optional)
   - Prompt templates + JSON schema output
   - Parser + validator + repair loop (bounded)
4. **Application Services**
   - Inbox service, conversion service, publish service, export service
5. **UI**
   - Local web app (FastAPI + server-rendered templates/HTMX) OR minimal React (prefer HTMX for speed)
   - Views: Inbox, Draft Review, Note Detail, Search/Library, Analytics, Settings
6. **CLI**
   - Power-user commands for import/export, batch convert, backup

### 3.2 Data flow
- InboxItem created → (Convert) → StructuredNoteDraft created → (Edit/Publish) → PublishedNote created (+ revision record) → Export/search/analytics.

## 4) Data model (conceptual)
### 4.1 Entities
- **InboxItem**
  - id, created_at, source (paste/mobile/other), raw_text, attachments (future), status
- **TastingNote**
  - id, state (draft/published), wine_identity fields, tasting context, structured sensory notes, scores, tags, timestamps
- **Revision**
  - id, tasting_note_id, created_at, actor (user/ai), diff/patch or full snapshot, notes
- **AIConversionRun**
  - id, inbox_item_id, tasting_note_id (draft), provider, model, prompt_version, input_hash, raw_response, parsed_json, validation_errors

### 4.2 Indexing/search targets
- Full-text (SQLite FTS) over: producer, cuvée, region, grapes, raw_text, nose/palate notes, tags.

## 5) Scoring model (v1)
- 100-point total built from sub-scores:
  - **Appearance** (0–2)
  - **Nose** (0–12)
  - **Palate** (0–20)
  - **Structure & Balance** (0–20)
  - **Length/Finish** (0–10)
  - **Typicity/Complexity** (0–16)
  - **Overall Quality Judgment** (0–20)
- Also record:
  - readiness (drink/hold), aging window
  - confidence level (low/med/high)
  - faults (TCA/VA/Brett/oxidation, etc.)

## 6) Inbox feature (explicit)
- Default landing view is Inbox.
- Inbox list shows: created date, short preview, guessed wine identity (if AI extraction), status.
- Actions:
  - Convert → creates draft note
  - Quick tag (e.g., “to research”, “gift”, “restaurant”)
  - Archive/Delete
- Batch operations:
  - Batch convert selected
  - Batch tag selected

## 7) “Free-flow notes → template” feature (explicit)
- Two-stage AI:
  1) **Extraction**: infer wine identity + sensory descriptors + structure levels + faults
  2) **Synthesis**: populate full template with coherent prose, preserve user voice where possible
- Guardrails:
  - Never invent specifics like vintage/producer if not present; mark as `unknown` and flag “needs confirmation”
  - Prefer conservative claims; store uncertainty

## 8) High-impact features (recommended additions)
1. **Calibration & consistency**
   - Personal calibration notes: “what does 90 mean for me?”
   - Score distribution dashboard
2. **Comparative tastings**
   - Flight mode: compare multiple notes side-by-side; common descriptors and ranking
3. **Cellar/Inventory (lightweight)**
   - Bottles owned, quantity, location, drink window; link to tasting notes
4. **Recommendation engine (simple v1)**
   - “If you liked X, try Y” based on tags/structure similarity
5. **Import utilities**
   - Import from CSV/JSON; optional parsing of existing notes

## 9) Operating rules for implementation
- Canonical schema lives in one place; UI and DB both derive from it.
- All DB changes require migrations.
- AI outputs must be machine-validated; never trust raw model output.
- Store raw inputs and raw model outputs for traceability.
- Keep v1 offline-capable except for the optional AI provider calls.
- Every phase must ship with a runnable demo and minimal tests.

## 10) Development phases (overview)
1. Repo + scaffolding + canonical schema
2. SQLite persistence + migrations + repositories
3. Inbox MVP + CRUD UI
4. AI conversion pipeline + validation/repair loop
5. Draft review editor + publish + revision history
6. Search (FTS) + filters + exports
7. Analytics dashboards + quality-of-life polish
8. Packaging (local app) + backups + release checklist
