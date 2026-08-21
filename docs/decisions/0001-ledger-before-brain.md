# ADR 0001 — Ledger before brain

**Date:** 2026-08-21 · **Status:** accepted

## Context

The obvious build order for a trend-intelligence agent is ingestion-first: wire
up the ten-domain sensory table, then bolt on synthesis, then eventually keep
score. But ARGUS's actual differentiator is the improvement loop — calibration
that visibly improves — and that loop depends entirely on a ledger schema and
a stream of resolved predictions. The calibration flywheel has a 30–90 day
feedback delay *minimum*: a ledger that starts in "Phase 2" starves the
scoring machinery for months.

## Decision

1. **Build and seed the prediction ledger first**, before any automated
   ingestion. Day one ships the ledger CLI plus ~20 hand-logged real
   predictions so scoreable resolutions start landing from late September 2026.
2. **Append-only JSONL, not a database.** `data/ledger/predictions.jsonl` is
   event-sourced: `prediction` records and `resolution` records, folded at
   read time. Rationale: git-diffable (every prediction and resolution is a
   one-line diff with full history), zero infrastructure, trivially portable
   to a DB in Phase 1 if scale demands it. The file is written only through
   `scripts/ledger.py` — hand edits are forbidden, and mistakes are resolved
   as `unresolvable` rather than deleted, so the "no memory-holing" guarantee
   is structural.
3. **Falsifiability is enforced in code, not vibes.** `ledger.py add` rejects
   any prediction lacking: a strictly future resolve-by date, ≥40 chars of
   resolution criteria, criteria free of a vague-word blacklist
   ("significant", "soon", "likely", …), a probability in [0.01, 0.99], a
   known domain, and a reasoning-snapshot thesis. This turns Prime
   Directive #4 into a mechanical gate: the agent literally cannot log an
   unfalsifiable call. The gate is a proxy — code can't fully judge "a
   stranger could adjudicate this" — so the weekly self-review audits
   `unresolvable` outcomes as the gate's escape-valve metric.
4. **One vertical slice, not ten stubs.** The Morning Brief runs end-to-end
   for equities only (observe → comprehend → predict → log), proving synthesis
   quality — the Phase 0 exit criterion — before the aperture widens.

## Deferred (deliberately, revisit dates attached)

- **GitHub Actions cron** for scheduled briefs: only after hand-triggered
  briefs pass the impress test consistently (~2 weeks of dailies). The
  invocation prompts in `prompts/` are already written so automation is a
  scheduler change, not a behavior change.
- **Vector memory, dashboards, real-time alerting:** Phase 3–4 problems.
  Premature infrastructure is how these projects die with a beautiful
  architecture and zero resolved predictions. Revisit only once ≥30 resolved
  predictions exist and calibration reporting is routine.
- **Database migration for the ledger:** revisit at ~1,000 records or when
  concurrent writers appear, whichever comes first.

## Consequences

- Scoring output is meaningfully populated by late 2026 instead of mid-2027.
- Everything is reviewable in `git log`; the audit trail is the repo itself.
- The JSONL fold is O(file) per command — fine for years at this volume.
- Seed predictions carry a known stale-anchor risk (see EP-000 in
  `docs/error-patterns.md`); numbers were fetched live at seeding to
  mitigate.
