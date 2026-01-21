# Wine Agent — Mediterranean Design Refinement Prompt (Claude Code Reference)

## Purpose

This document is a **one-shot design refinement prompt** intended for use with **Claude Code** after the Wine Agent application has already been fully implemented functionally.

Its purpose is to guide a **pure UI/UX and visual design pass** that upgrades the application’s aesthetic to a **light, breezy, Mediterranean wine-country vibe** while preserving all existing logic, data models, and behavior.

This file should be provided to Claude Code as a **reference document** during the design iteration phase.

---

## One-Shot Claude Code Prompt  
### Mediterranean Design Pass

---

### Role & Objective

You are a senior product designer and frontend engineer working on an already-functional Wine Agent application.

The core functionality is complete. Your task is to execute a **comprehensive design and UI/UX refinement pass only**, without altering business logic, data models, or application behavior.

The goal is to give the app a **light, breezy, Mediterranean wine-country aesthetic**—something that feels equally at home in Provence, Tuscany, or the Basque coast—while remaining **sleek, modern, and professional**.

---

### 1. Design North Star

Design for the following emotional and aesthetic qualities:

- Light and airy — no visual heaviness
- Mediterranean calm — sun, stone, linen, sea air
- Wine-centric elegance — restrained, confident luxury
- Modern and dynamic — clean lines, subtle motion
- Simplicity as confidence — fewer borders, more space

Avoid:

- Brutalist or industrial UI
- Neon or high-contrast cyberpunk palettes
- Corporate enterprise dashboards
- Overly rustic, faux-vintage, or kitschy wine motifs

---

### 2. Color System

Implement or refine a cohesive color palette inspired by Mediterranean landscapes.

**Primary tones**
- Warm off-white or parchment backgrounds (not pure white)
- Limestone / sand neutrals
- Muted olive green
- Sun-washed terracotta accents
- Deep but soft navy or slate for contrast

**Usage rules**
- Light, breathable backgrounds dominate
- Accent colors used intentionally (buttons, highlights, tags)
- Avoid harsh black; prefer charcoal or slate
- Maintain WCAG-compliant contrast

If a theme or token system exists, update it cleanly.  
If none exists, introduce one.

---

### 3. Typography System

Typography should feel **editorial and modern**, similar to a high-end wine magazine.

- Serif or serif-adjacent font for headings and wine notes
- Clean sans-serif for body text, UI labels, metadata
- Clear hierarchy with generous spacing
- Comfortable line height for reading tasting notes

Avoid:
- Tech-heavy monospace fonts for primary UI
- Decorative or novelty fonts

---

### 4. Layout & Spacing Principles

Apply these rules consistently across the app:

- Increase whitespace and breathing room
- Favor floating cards over boxed panels
- Subtle rounded corners (not playful)
- Light elevation via soft shadows
- Reduce visual clutter: fewer lines, dividers, and borders

Pages should feel:
- Calm
- Scannable
- Inviting to linger and read

---

### 5. Dynamic & Interactive Elements

Introduce **subtle, tasteful motion**:

- Gentle hover states
- Soft transitions between views
- Micro-animations for:
  - Wine score reveals
  - Tag selection
  - Save / submit actions

Motion should feel:
- Organic
- Confident and unhurried
- Optional to disable for accessibility preferences

Avoid aggressive, bouncy, or attention-seeking animations.

---

### 6. Wine-Specific UI Enhancements

Where wine data is displayed:

- Make tasting notes feel like reading, not data entry
- Structure text blocks with visual rhythm
- Scores should feel considered and reflective, not gamified
- Tags should resemble elegant labels rather than generic pills

Icons (if used):
- Minimal, outline-based
- Wine-appropriate (glass, leaf, soil, sun, barrel)
- Never cartoonish

---

### 7. Scope & Constraints (Critical)

**Do NOT change:**
- Application logic
- Data schemas
- Scoring algorithms
- Feature behavior

**ONLY change:**
- Styling
- Layout
- UI components
- Theme or design tokens
- Animations and transitions

If a design change risks breaking functionality, do not implement it.

---

### 8. Deliverables

Complete the following in one pass:

1. Updated styles or theme definitions
2. Modified UI components reflecting the new aesthetic
3. Any necessary layout refactors
4. A short summary (comments or README note) explaining:
   - Design system choices
   - How to extend the style consistently going forward

Proceed confidently and make design decisions without asking follow-up questions.

---

## Notes

This prompt is intentionally detailed to enable a **single-pass execution** by Claude Code with minimal iteration.  
It is optimized for clarity, aesthetic coherence, and preservation of existing functionality.
