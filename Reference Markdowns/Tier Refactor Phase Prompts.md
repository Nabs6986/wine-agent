# Wine Agent — Phased Rollout & Claude Code Prompts

## Phase 1 — Foundation & Monetization Core

### 1.1 Tier System & Entitlements
**Goal:** Establish a single, authoritative subscription and entitlement layer.

**Claude Code Prompt:**
You are working in an existing Wine Agent codebase. Refactor the system to support three subscription tiers (FREE, PRO, CELLAR) using a centralized entitlement resolver. Remove any scattered feature flags or boolean access checks and ensure all feature access flows through this single system. Do not change user-facing behavior yet beyond enforcing entitlements.

---

### 1.2 Free Tier Limits
**Goal:** Enforce intentional constraints for lead capture.

**Claude Code Prompt:**
Implement hard enforcement of the Free tier limits: a maximum of 25 wines per user and free-form tasting notes only. Enforce limits at both the UI and API layers. Add explicit, respectful error messaging when limits are reached. Ensure no structured tasting functionality is accessible to Free users.

---

### 1.3 Billing Integration
**Goal:** Enable paid upgrades safely.

**Claude Code Prompt:**
Integrate subscription billing (monthly and annual) using Stripe or the existing billing provider. Map subscriptions cleanly to the entitlement system. Implement grace periods, downgrade handling, and ensure that downgrades never delete user data and only restrict access.

---

## Phase 2 — Core Pro Experience

### 2.1 Structured Tasting Conversion
**Goal:** Turn raw notes into structured intelligence.

**Claude Code Prompt:**
Design and implement a structured tasting system where free-form notes remain immutable and structured tastings are derived artifacts. Build a conversion pipeline that sends a selected free-form note to an LLM, validates the output against a tasting schema, allows user edits, and saves the result as a new structured tasting object. Restrict this feature to Pro and above.

---

### 2.2 Wine & Vintage Refactor
**Goal:** Enable vertical tracking and future cellar logic.

**Claude Code Prompt:**
Refactor the wine data model to separate Wine and WineVintage entities. Migrate existing wines to an `unknown_vintage` entry without breaking existing views. Update creation and display logic to support vintage-specific entries while preserving backward compatibility.

---

### 2.3 Exports
**Goal:** Allow users to own their data.

**Claude Code Prompt:**
Implement export functionality for Pro users, supporting PDF and CSV formats. Ensure exports include only the requesting user’s data, require explicit user action, and do not run automatically in the background.

---

## Phase 3 — Insights & Trust Layer

### 3.1 Personal Insights Engine
**Goal:** Deliver value through patterns, not scores.

**Claude Code Prompt:**
Build a lightweight insights system that aggregates user tasting data to generate plain-language insights (e.g., preferred regions, structural preferences, repeat producers). Store insights as user-private objects. Avoid complex ML; prioritize explainable aggregation logic.

---

### 3.2 Privacy & Trust Surfacing
**Goal:** Make privacy explicit.

**Claude Code Prompt:**
Audit the application for privacy guarantees. Ensure all data is private by default, with no public discovery or sharing. Add a clear “Your data is private” section in user settings explaining how data is handled. Do not introduce any social features.

---

## Phase 4 — Cellar Tier Expansion

### 4.1 Aging Notes & Drinking Windows
**Goal:** Support longitudinal wine tracking.

**Claude Code Prompt:**
Introduce aging notes tied to WineVintage entries, allowing users to log condition and readiness over time. Implement drinking windows with editable defaults and clear disclaimers that these are guidance, not authoritative facts. Restrict access to Cellar tier.

---

### 4.2 Advanced Analytics
**Goal:** High-margin power-user insights.

**Claude Code Prompt:**
Implement advanced analytics for Cellar users, such as preference changes over time, producer hit rates, and region-by-vintage performance. Build analytics as query-driven summaries rather than dashboards, focusing on explainability and clarity.

---

## Phase 5 — Migration & Hardening

### 5.1 User & Data Migration
**Goal:** Safely transition existing users.

**Claude Code Prompt:**
Design and execute a migration strategy for existing users and data, assigning appropriate default tiers, migrating wines to the new wine/vintage model, and preserving all tasting notes. Log all migrations and ensure failures are safe and reversible.

---

### 5.2 Final Entitlement Audit
**Goal:** Eliminate leakage.

**Claude Code Prompt:**
Audit the entire codebase to ensure no feature bypasses the entitlement system. Verify that downgrades result in read-only access where appropriate and that no data is lost. Refactor any remaining exceptions to comply with the centralized entitlement model.
