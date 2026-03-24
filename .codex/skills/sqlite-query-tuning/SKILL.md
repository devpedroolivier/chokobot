---
name: sqlite-query-tuning
description: Use when improving SQLite performance in the Chokobot backend, especially query shape, indexes, joins, ordering, lookup hot paths, panel reads, and safe schema-level tuning without changing business behavior.
---

# SQLite Query Tuning

Use this skill when a Chokobot bottleneck is likely inside SQLite queries, schema support for reads, or unnecessary database work in repositories and panel endpoints.

## Focus Areas

- `app/infrastructure/repositories/sqlite_*.py`
- `app/db/`
- `app/models/`
- panel and snapshot endpoints
- tests covering repository behavior

## What To Look For

- repeated lookups by the same key in one request
- N+1 query patterns
- `JOIN` paths missing useful indexes
- `ORDER BY` on unindexed columns
- broad `SELECT *` where only a few fields are needed
- duplicate reads to derive data already available in the first query
- expensive Python-side shaping caused by weak SQL shaping

## Workflow

1. Identify the hot query path first.
2. Read repository code before proposing indexes.
3. Match index proposals to real predicates:
   - `WHERE`
   - `JOIN`
   - `ORDER BY`
   - unique lookup keys
4. Prefer these fixes:
   - reduce query count
   - narrow selected columns
   - add targeted indexes
   - shape rows closer to the query
   - avoid extra round-trips for derived status/labels

## Project Rules

- Do not change business behavior for the sake of a “cleaner” query.
- Avoid speculative index proliferation.
- Keep SQLite compatibility intact unless the user explicitly wants a migration step.
- If a migration or schema change is needed, make it small and explain why it supports a real hot path.

## Validation

Use focused checks first:

- repository unit tests
- panel snapshot tests
- `python3 -m compileall app tests`

If the environment supports it, you may also compare query count or inspect query plans.

## Output Expectations

When using this skill, report:

- which query path was tuned
- whether the gain came from fewer queries, better indexes, or narrower reads
- any schema/index change applied
- validation result
