---
name: frontend-design-system
description: Use when designing or refining the Chokobot Next.js admin frontend, including visual system, component consistency, dashboard/admin UX, responsive layouts, accessibility, and production-minded UI polish without breaking the current visual direction.
---

# Frontend Design System

Use this skill for work on the modern admin frontend in `frontend/` when the task is visual refinement, UI consistency, component polish, dashboard usability, or stronger design-system decisions.

## Focus Areas

- `frontend/src/app/`
- `frontend/src/components/`
- `frontend/src/app/globals.css`
- `frontend/tailwind.config.ts`
- snapshot consumers in `frontend/src/lib/`

## Current Product Context

- The admin is a modern replacement for the old FastAPI + Jinja panel.
- Main operational surfaces today include:
  - dashboard
  - operações
  - clientes
  - encomendas
- The current visual language already uses warm paper tones, sand/blush accents, rounded panels, and dense operational cards.

## Design Goals

- Preserve the established admin language instead of resetting the interface.
- Improve hierarchy and scanability for operators first.
- Favor data-dense clarity over decorative complexity.
- Keep mobile behavior acceptable even for admin tables and card boards.
- Add polish only when it does not hurt performance or readability.

## Workflow

1. Identify the surface:
   - dashboard summary
   - operational cards
   - tables/forms
   - navigation/session flows

2. Review consistency across:
   - spacing
   - typography scale
   - badge/status styling
   - empty states
   - action priority
   - responsive collapse behavior

3. Prefer improvements in this order:
   - hierarchy and information density
   - consistent reusable patterns
   - accessibility and focus states
   - motion/loading polish

4. Reuse or extract shared patterns when duplication appears in multiple pages.

## Project Rules

- Do not regress the current warm visual direction unless the user explicitly wants a redesign.
- Avoid generic SaaS styling.
- Avoid adding client-side state just for cosmetic UI if a server component is enough.
- Keep links, filters, and operational actions obvious and fast to scan.
- If a page is list-heavy, prioritize filtering, row clarity, and responsive overflow handling.

## Validation

Use whichever checks are available:

- `cd frontend && npm run build`
- inspect affected routes for type errors
- keep server/client boundaries valid in Next.js

If styling changes are broad, mention which pages/components were visually normalized.

## Output Expectations

When using this skill, report:

- which admin surfaces were improved
- what design-system inconsistency was removed
- any accessibility or responsive gain
- build/test result
