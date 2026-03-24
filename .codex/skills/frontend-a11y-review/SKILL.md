---
name: frontend-a11y-review
description: Use when reviewing or improving accessibility of the Chokobot admin frontend, especially keyboard navigation, contrast, form semantics, table usability, focus states, status messaging, and accessible patterns in the Next.js back-office UI.
---

# Frontend A11y Review

Use this skill for accessibility work in the Chokobot modern admin when the goal is to make the UI easier to use with keyboard, assistive tech, and stronger visual clarity.

## Focus Areas

- `frontend/src/app/`
- `frontend/src/components/`
- forms, tables, nav, dialogs, action buttons, filters, badges, alerts
- global styles affecting focus and contrast

## Audit Checklist

- are interactive elements keyboard reachable in a sensible order?
- are links and buttons visually distinct and consistently styled?
- do inputs have clear labels or accessible names?
- are focus states visible without relying on browser defaults alone?
- is contrast acceptable for text, badges, and status indicators?
- do tables remain understandable on narrow screens?
- are alerts, warnings, and errors readable and semantically clear?
- is status conveyed by more than color alone?

## Workflow

1. Start from the affected route or component.
2. Audit semantics first:
   - heading order
   - button versus link usage
   - form labels
   - table headers
   - landmark/nav structure
3. Then audit usability:
   - focus visibility
   - contrast
   - target size
   - keyboard flow
   - empty/loading/error communication
4. Fix the highest-impact blockers before cosmetic improvements.

## Project Rules

- Preserve the existing admin look while making it more accessible.
- Do not hide focus rings without replacing them with a stronger visible treatment.
- Avoid accessibility changes that make dense operational UI slower to use.
- Prefer accessible defaults in shared components when possible.

## Validation

Primary check:

- `cd frontend && npm run build`

Also verify manually in code review terms:

- keyboard path through nav, tables, filters, and primary actions
- labels and semantics for forms
- visible focus treatment on key controls

## Output Expectations

When using this skill, report:

- which accessibility issues were addressed
- whether fixes were semantic, visual, or interaction-related
- any shared component improvements
- build/test result
