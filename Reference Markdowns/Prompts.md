# Wine Agent — Claude Code Phase Prompts (Full Prompts)

> Use each prompt as a single “one-shot” instruction to Claude Code.  
> Assumed stack: **Python 3.11+**, **FastAPI**, **SQLite**, **SQLModel or SQLAlchemy**, **Alembic**, **Pydantic v2**, **Jinja2 + HTMX** (preferred) + minimal JS, **Typer** for CLI, **pytest**.

---

## Global Operating Rules (apply to every phase)
- Do **not** redesign earlier phases unless required to satisfy acceptance criteria; prefer incremental changes.
- Keep a **single canonical schema** for tasting notes (Pydantic models) and use it everywhere (DB mapping, API, UI forms, export).
- Add **Alembic migrations** for every DB schema change; never mutate tables ad hoc.
- Store **raw inputs** and **raw AI outputs** for traceability.
- Validate all AI JSON strictly; implement a bounded repair loop and fail gracefully with actionable errors.
- Provide:
  - `README.md` with run instructions
  - `make` or `just` commands (or `scripts/`) for common tasks
  - Minimal tests proving core logic works
- Keep secrets in `.env` and document required env vars.
- No heavy frontend build unless necessary; prefer server-rendered + HTMX.

---

## Phase 1 — Repository scaffolding + canonical schema + project layout

**Prompt to Claude Code:**

You are implementing Phase 1 of a local-first app called “Wine Agent”. Create a Python project with a clean, production-oriented layout and a canonical tasting note schema.

### Goals
1) Create repo scaffolding with consistent tooling and clear dev commands.  
2) Implement **canonical Pydantic v2 models** for:
- InboxItem
- TastingNote (draft/published)
- AIConversionRun
- Revision
3) Define enums and constrained fields (e.g., structure levels, wine color, sweetness, confidence).  
4) Include a scoring model that supports a 100-point total from sub-scores.

### Deliverables
- Project structure:
  - `wine_agent/` (app package)
    - `core/` (domain models, scoring, utils)
    - `db/` (db init placeholder for later)
    - `services/` (placeholder)
    - `web/` (placeholder)
    - `cli/` (placeholder)
  - `tests/`
  - `pyproject.toml` (dependencies, tooling)
  - `.env.example`
  - `README.md`
- Provide a `wine_agent/core/schema.py` with Pydantic models and docstrings.
- Provide a `wine_agent/core/scoring.py` implementing:
  - total score calculation
  - validation (subscores ranges)
- Minimal tests: schema instantiation + scoring sum check.

### Acceptance Criteria
- `pytest` passes.
- A sample `TastingNote` object can be created and serialized to JSON.
- Total score is computed deterministically from subscores.

Implement now with code files only; do not include commentary. Ensure type hints throughout.

---

## Phase 2 — SQLite persistence + migrations + repositories

**Prompt to Claude Code:**

Implement Phase 2: persistence for Wine Agent using SQLite + Alembic, with repository classes to store and retrieve Inbox items, tasting notes, revisions, and AI conversion runs.

### Requirements
- Use SQLite as the primary DB.
- Use SQLModel or SQLAlchemy ORM (choose one and be consistent).
- Setup Alembic migrations.
- Create tables corresponding to canonical schema. Store structured note payloads as JSON where appropriate, but keep key index fields as columns (producer, vintage, region, grapes, score_total, created_at).
- Add SQLite FTS (can be Phase 6 if too much now) ONLY if easy; otherwise set the foundation (text columns ready).

### Deliverables
- `wine_agent/db/engine.py` + session management
- `wine_agent/db/models.py` (ORM models)
- `wine_agent/db/migrations/` with Alembic config and initial migration
- `wine_agent/db/repositories.py` with repositories:
  - `InboxRepository`
  - `TastingNoteRepository`
  - `RevisionRepository`
  - `AIConversionRepository`
- Unit tests using a temp SQLite DB:
  - create inbox item
  - convert to draft tasting note
  - publish note + revision
  - retrieve and verify fields

### Acceptance Criteria
- `alembic upgrade head` works.
- CRUD paths covered by tests.
- Repositories return domain models (Pydantic) or well-typed DTOs.

Implement with clear separation between domain models and DB models. No UI yet.

---

## Phase 3 — Inbox MVP (API + server-rendered UI)

**Prompt to Claude Code:**

Implement Phase 3: an Inbox MVP that runs locally and supports creating, viewing, editing, and converting inbox items (conversion button can be stubbed until Phase 4).

### Requirements
- Build a local web app using FastAPI.
- Server-rendered views with Jinja2 + HTMX preferred.
- Routes:
  - GET `/` redirects to `/inbox`
  - GET `/inbox` list items (status filters: open/archived)
  - GET `/inbox/new` form
  - POST `/inbox` create
  - GET `/inbox/{id}` detail view with raw text and metadata
  - POST `/inbox/{id}/archive` archive
  - POST `/inbox/{id}/convert` (stub: creates placeholder draft tasting note record and redirects to draft view)
- Add basic styling (simple CSS).
- Add minimal CLI command: `wine-agent run` to start server.

### Deliverables
- `wine_agent/web/app.py` FastAPI app
- `wine_agent/web/templates/` (inbox list, new, detail)
- `wine_agent/web/static/` (css)
- `wine_agent/cli/main.py` with Typer entrypoint
- Update README with run steps

### Acceptance Criteria
- `uvicorn wine_agent.web.app:app --reload` works.
- User can create and view inbox items.
- Convert stub creates a draft tasting note linked to inbox item.

Focus on clean code, no heavy JS.

---

## Phase 4 — AI conversion pipeline (free-form → structured template)

**Prompt to Claude Code:**

Implement Phase 4: AI-assisted conversion of free-form tasting notes into the canonical structured tasting note schema.

### Requirements
- Create an AI provider interface:
  - `AIClient` with `generate_structured_note(raw_text, hints)` returning validated `TastingNote` (draft).
- Support at least two providers via environment variables:
  - Anthropic (Claude)
  - OpenAI
(If one is faster, implement one fully and scaffold the second with identical interface.)
- Prompting strategy:
  - Ask model to output **strict JSON** matching a provided JSON Schema derived from Pydantic models.
  - Include explicit rules: do not invent unknown facts; use `null`/`"unknown"`; mark uncertainties.
- Parsing strategy:
  - First parse attempt: `json.loads`
  - If invalid: run a bounded repair step (max 2) using a “fix JSON” prompt that takes the invalid JSON + error message.
  - Validate with Pydantic; if still invalid, store failure with errors and show user.
- Store:
  - raw model response
  - parsed JSON
  - validation errors
  - model/provider metadata
- Wire into UI:
  - POST `/inbox/{id}/convert` triggers real conversion and redirects to `/notes/draft/{note_id}`

### Deliverables
- `wine_agent/services/ai/` (client, prompts, repair, provider implementations)
- `wine_agent/services/conversion_service.py`
- DB layer updates: store AIConversionRun records
- UI updates: show conversion status/errors on inbox item
- Tests:
  - unit test validator + repair loop with mocked responses
  - integration test conversion service stores records

### Acceptance Criteria
- A real conversion creates a draft tasting note with populated fields when given typical raw notes.
- Failures are captured and user sees actionable error message.
- No secrets committed; uses `.env`.

Implement now.

---

## Phase 5 — Draft review editor + publish + revisions

**Prompt to Claude Code:**

Implement Phase 5: a draft review/editor UI for tasting notes, publishing flow, and revision history.

### Requirements
- Views:
  - GET `/notes/draft/{id}` editable form (key identity fields + sensory notes + subscores)
  - POST `/notes/draft/{id}` save draft
  - POST `/notes/draft/{id}/publish` publish note
  - GET `/notes/{id}` published note detail (read-only)
  - GET `/notes/{id}/revisions` list revisions
- Revision logic:
  - On publish: create a revision snapshot and mark note as published
  - On subsequent edits (if allowed): store revision snapshots or diffs (choose snapshots for simplicity)
- Validation:
  - Server-side validate all fields and show inline errors
- Computed score:
  - Auto-calculate total score from subscores on save; display clearly

### Deliverables
- Web templates for draft editor, published detail, revisions
- Service layer for publish + revision creation
- Tests:
  - publish creates revision
  - score calculation persists
  - invalid subscores rejected

### Acceptance Criteria
- User can convert → edit draft → publish → view published note.
- Revision list shows at least one snapshot with timestamps.

Keep UX simple but solid.

---

## Phase 6 — Search + filters + export (Markdown/YAML + CSV/JSON)

**Prompt to Claude Code:**

Implement Phase 6: powerful retrieval and export.

### Requirements
- Library view:
  - GET `/library` with filters:
    - text query
    - score range
    - region/country
    - grape
    - producer
    - vintage
    - readiness (drink/hold)
- Implement SQLite FTS if feasible:
  - index raw_text, nose, palate, conclusion, tags
  - fallback: LIKE-based search if FTS too heavy, but structure it so FTS can be added later
- Export:
  - GET `/notes/{id}/export/md` returns Markdown note with YAML frontmatter matching the scoring template
  - GET `/export/csv` exports a flat summary dataset
  - GET `/export/json` exports full structured notes

### Deliverables
- Search repositories + query builder
- Templates for library results
- Export module:
  - `wine_agent/services/export_service.py`
  - YAML frontmatter generator
- Tests:
  - export formatting stable (golden file)
  - filters return expected results

### Acceptance Criteria
- User can find notes quickly and export them cleanly.

---

## Phase 7 — Analytics dashboards + “high impact” polish

**Prompt to Claude Code:**

Implement Phase 7: analytics and quality-of-life features.

### Requirements
- Analytics page `/analytics`:
  - score distribution (bins)
  - top regions/producers by average score (min n)
  - descriptor frequency (simple token counts from nose/palate text)
- Calibration page `/calibration`:
  - user-defined score meaning notes
  - view personal scoring averages over time
- Comparative tasting “flight mode” (lightweight):
  - select multiple notes → side-by-side view

### Deliverables
- Simple charts (server-rendered tables acceptable; JS charts optional)
- New services: `analytics_service`, `calibration_service`
- Tests for aggregation logic

### Acceptance Criteria
- Analytics works on sample data and is performant on hundreds of notes.

---

## Phase 8 — Packaging, backups, and release checklist

**Prompt to Claude Code:**

Implement Phase 8: make Wine Agent easy to run and safe to use.

### Requirements
- Add backup command:
  - `wine-agent backup` creates timestamped copy of SQLite DB and exports all notes to a folder
- Add restore command (safe, prompts user)
- Add configuration UI page `/settings`:
  - AI provider selection + key presence checks
  - export directory
- Packaging plan:
  - Provide a documented path to package as a desktop app later (optional), but at minimum produce a polished local server experience.

### Deliverables
- CLI backup/restore
- Settings UI
- Release checklist in README

### Acceptance Criteria
- A non-technical user can run the app locally with copy/paste instructions and not lose data.

---

## Phase X (Optional) — Vault mode (Obsidian-first)
**Prompt to Claude Code:**

Add optional “vault mode” where each published note is saved as a Markdown file in a user-chosen directory with YAML frontmatter. The DB remains source-of-truth, but exports are updated automatically on publish. Implement idempotent filenames and safe updates. Include an import utility that reads these files back into the DB.

Acceptance criteria: publishing a note writes a deterministic Markdown file and re-import produces identical structured data.
