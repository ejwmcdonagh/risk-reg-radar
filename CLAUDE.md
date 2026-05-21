# Pulse - CLAUDE.md

Project-specific instructions for Claude Code in this repository.

## What this project is

Pulse is a live risk intelligence platform for CISOs. It pulls threat data from 13 built-in sources, clusters related signals, scores them by real-world risk, and generates 5-layer intelligence cards using Claude.

Risk is the primary lens. Regulatory context is supporting evidence, not the headline.

## Tech stack

- Python 3.11 + FastAPI backend
- Next.js 15 (App Router) + Tailwind frontend
- Supabase (local dev via `supabase start --exclude edge-runtime`)
- Claude Haiku by default, Opus commented out in services

## Writing style

Never use em dashes anywhere. In code comments, docs, UI copy - nowhere.

Keep all writing plain and direct. A 10-year-old should be able to follow the README.

## Comment style

Comment the WHY, not the WHAT. Only add a comment when a future reader would not understand why the code is written that way - a hidden constraint, a workaround, a non-obvious invariant.

Never write multi-line comment blocks. One short line max.

## AI models

Both service files (`clustering.py` and `card_generator.py`) use this pattern:

```python
model="claude-haiku-4-5-20251001",
# model="claude-opus-4-7",
# thinking={"type": "adaptive"},
```

Haiku is the default. To switch to Opus: comment the Haiku line, uncomment the two Opus lines. Thinking only works on Opus - do not uncomment it for Haiku.

## Built-in sources (13 total)

Official feeds: CISA KEV, CISA Advisories, NCSC, NVD, GitHub Advisory

Threat news: SANS Internet Storm Center (`exploit_db` enum), Bleeping Computer, FCA News (`ico_enforcement` enum)

Research blogs: Recorded Future, Google Threat Intel, Horizon3, Dark Reading, CrowdStrike

The `exploit_db` and `ico_enforcement` enum names are historical - the actual ingesters pull SANS ISC and FCA News respectively. Display names in `profile.py` BUILTIN_SOURCES are correct.

## Source toggling

`org_profile.disabled_sources TEXT[]` stores paused sources. `_guarded_run` in `scheduler.py` checks this before each ingester job.

## Scoring

Additive model: +2 per signal, +10 Critical / +5 High / +2 Medium severity, +3 per signal in last 7 days, +5 per unique source, +10 if spans multiple domains. Cards generated for clusters scoring >= 30.

## Database

Local Supabase only. Migrations in `supabase/migrations/`. Run `supabase migration up --local` to apply.

## Cost reference

Based on actual runs with ~1000 signals across all sources:
- Clustering: Haiku ~$0.06, Opus ~$0.30
- Card generation: Haiku ~$0.10, Opus ~$0.50
- Daily incremental runs are much cheaper - first run processes the full backlog
