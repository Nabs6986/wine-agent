# Wine Agent — Development Plan (Claude Code Reference)

## Purpose
This document is the **single source of truth** for Wine Agent’s product architecture and feature intent. Claude Code should ingest and reference this file throughout all phases of development to ensure consistency, correct abstractions, and alignment with the tiered business model.

The codebase already contains core scaffolding. This plan prioritizes **refactoring, entitlement discipline, and data-model clarity** over feature sprawl.

---

## Core Product Principles
- Private by default (no social surface area)
- Trust > features
- Insight > content volume
- Free tier is intentionally restrictive
- Derived intelligence must never overwrite raw user input
- Downgrades never delete data

---

## Subscription Tiers (Canonical)
All access control must reference a centralized entitlement system.

- **FREE**
- **PRO**
- **CELLAR**

No feature-level logic should independently determine access.

---

## Tier Definitions

### Level 0 — Free (Lead Magnet)
**Goal:** Capture email + habit formation

**Includes**
- Save up to 25 wines (hard cap)
- Free-form tasting notes only
- Label photo upload
- Basic wine info auto-fill

**Excludes**
- Structured tastings
- Note conversion
- Exports
- Insights
- Vintage tracking beyond a single entry

Free tier limits must be enforced at both UI and API layers.

---

### Level 1 — Wine Agent Pro (Core Revenue)
**Goal:** Primary paid experience

**Includes**
- Unlimited wines
- Free-form → structured tasting conversion
- Vintage-specific wine entries
- Personal taste insights
- Export (PDF / CSV)
- Private-by-default guarantees

Structured tastings must be **derived artifacts**, not replacements.

---

### Level 2 — Wine Agent Cellar (Prestige Tier)
**Goal:** High-margin power users

**Includes**
- Multi-vintage tracking
- Aging notes over time
- Drinking windows
- Advanced analytics
- (Future) Private cellar valuation

All analytics must be explainable and user-owned.

---

## Data Model Expectations

### Wine Identity
Refactor from:
- `Wine = Producer + Name`

To:
- `Wine = Producer + Name`
- `WineVintage = Wine + VintageYear`

Existing wines should migrate to `unknown_vintage`.

---

### Notes
- Free-form notes are immutable
- Structured tastings are derived and editable
- Conversion must be traceable and reversible

Never merge free-form and structured data.

---

### Insights
- Stored as user-private artifacts
- Generated via aggregation logic (not opaque ML)
- Expressed in plain language (“You tend to prefer…”)

---

## Conversion Pipeline (Pro+)
1. User selects free-form note
2. LLM converts to structured schema
3. Output validated
4. User reviews/edits
5. Structured tasting saved as separate object

---

## Privacy & Trust Requirements
- No public profiles
- No discovery
- No default sharing
- No training on private data without explicit opt-in
- Clear, explicit privacy language in UI

---

## Monetization Rules
- Stripe (or equivalent) subscription handling
- Monthly + annual pricing
- Grace periods on failure
- Read-only access on downgrade
- No data deletion on downgrade

---

## Migration Rules
- Existing users default to Free or Pro trial
- All migrations logged
- Fail-safe behavior required
- No silent data loss

---

## Claude Code Global Rules
- Prefer refactor over bolt-on
- Centralize entitlement logic
- Keep models explicit
- Treat trust as a first-class feature
- Ask clarifying questions only when data integrity is at risk
