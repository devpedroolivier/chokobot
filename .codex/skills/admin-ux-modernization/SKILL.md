---
name: admin-ux-modernization
description: Use when improving the Chokobot admin operational flow, especially dashboard usability, process tracking, handoff clarity, table-to-detail journeys, action priority, and operator-facing workflow design in the modern Next.js admin.
---

# Admin UX Modernization

Use this skill for work on the Chokobot admin when the problem is not only visual design, but operational usability: how operators scan, decide, and act across dashboard, operações, clientes, and encomendas.

## Focus Areas

- `frontend/src/app/`
- `frontend/src/components/`
- snapshot-driven admin routes
- process cards, kanban, tables, filters, empty states, quick actions

## Core Goals

- reduce operator friction
- improve scanability of urgent work
- clarify what needs human action versus bot follow-up
- shorten the path from signal to action
- preserve current business flow while improving the interface

## Workflow

1. Identify the operational surface:
   - dashboard overview
   - operações follow-up
   - clientes lookup
   - encomendas management

2. Inspect these questions:
   - what is the most important action on this screen?
   - is urgency visually obvious?
   - can the operator tell bot, humano, and logística states apart quickly?
   - are filters and quick actions placed near the decision point?
   - are detail pages reachable in one obvious step?
   - are empty/error/loading states operationally useful?

3. Prioritize fixes in this order:
   - information hierarchy
   - urgent versus routine work separation
   - navigation/action clarity
   - consistency across cards, tables, badges, and forms
   - polish and motion

4. Prefer reusable patterns when the same operational idea appears in multiple screens.

## Project Rules

- Do not redesign away from the current warm admin language without explicit request.
- Keep operators as the primary user, not stakeholders reviewing mockups.
- Prefer clarity and density over decorative spacing.
- Avoid flows that add clicks without improving confidence or speed.

## Validation

Primary check:

- `cd frontend && npm run build`

Also verify:

- key admin journeys still exist in one or two obvious actions
- status/handoff distinctions remain clear
- mobile and narrow-width behavior still works for dense screens

## Output Expectations

When using this skill, report:

- which operational surface was improved
- what friction or ambiguity was reduced
- whether action hierarchy or follow-up flow became clearer
- build/test result
