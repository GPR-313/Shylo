# ADR 0003 — Connective tissue: theses, catalysts, and a graph over everything

**Date:** 2026-09-17 · **Status:** accepted · **Extends:** ADR 0001, ADR 0002

## Context

By September 2026 ARGUS had two working halves that did not touch.

The **ledger** knew what ARGUS predicted and whether it came true. The **memory
brain** under `argus/` knew what ARGUS believed and why. Nothing connected a
belief to the falsifiable calls that would kill it. Three consequences, all
visible in the repo as it stood:

1. **A thesis could outlive its evidence.** `argus/memory/2026-08.md` M20260821f
   records a contradiction — an issuer's CFO saying AUM-based revenue is
   immaterial, against an earlier claim that tokenization economics accrue
   through AUM fees. The contradiction was logged honestly. Nothing then
   happened, because nothing was structurally obliged to happen.

2. **Predictions existed only in memory.** M20260821d states four probabilistic
   calls with resolution criteria. Three of the four were never logged to the
   ledger, in direct violation of Ledger Contract rule 1 — not through
   carelessness, but because the memory path and the ledger path were separate
   and neither knew the other's contents.

3. **The README's signature claim had no code.** "Cross-domain correlation —
   the signature move" had been in the architecture document since the first
   commit. Nothing computed it. Correlation was something the agent was
   supposed to notice, which means it was noticed exactly as often as the agent
   happened to be clever that day.

A fourth problem was structural rather than conceptual: the same memory entry
that seeded the watch list also observed that five names "share one catalyst
chain, so they are one bet expressed five ways, not diversification." That is
the single most valuable risk observation in the whole repo, and it was made by
hand, once, and never re-checked.

## Decision

1. **Two new stores, same contract as the ledger.** `data/theses.jsonl` and
   `data/catalysts.jsonl` are append-only, event-sourced JSONL folded at read
   time, with write-time validation gates. `argus/store.py` holds the shared
   primitives so the pattern is implemented once rather than three times with
   three subtly different bugs. `argus/ledger.py` was refactored onto it; the
   ADR 0002 regression is now pinned by `tests/test_ledger.py`.

2. **A thesis cannot exist without a live ledger prediction.** `theses open`
   validates `--predictions` against the ledger at write time and rejects an
   empty list. This is the weld. A thesis with nothing falsifiable attached is
   unfalsifiable by construction, and `theses orphans` reports a thesis whose
   calls have *all* resolved as needing a fresh call or a close-out.

3. **A mechanism is required and is checked.** `--mechanism` must be at least
   60 characters and must contain a causal connective. The check is crude on
   purpose: it catches the common failure of writing a description where a
   causal chain belongs, and a crude check that fires is worth more than a
   sophisticated one that is never run.

4. **Lifecycle stage is a sizing input, not a label.** `STAGE_SIZING` in
   `theses.py` is read by `argus/edge.py`. "Stage determines sizing more than
   the thesis does" was already in CLAUDE.md; now the multiplication happens.
   Stage changes require evidence and are recorded as events, so *how* a
   narrative matured is queryable in post-mortems.

5. **Links are additive only.** Catalysts get discovered after a thesis opens;
   a thesis that cannot absorb one goes stale. But a *removable* link would let
   an inconvenient dependency be quietly detached, which is memory-holing by
   another name. `theses link` adds; nothing removes. A wrong link is answered
   in the close post-mortem.

6. **`argus/graph.py` computes the connections.** One graph over predictions,
   theses, catalysts, tickers, domains, and the memory journals (parsed
   read-only). Four queries: `concentration` (what is actually one bet),
   `cutpoints` (Hopcroft-Tarjan articulation points — what single event
   disconnects the most), `bridges` (nodes spanning two or more domains), and
   `orphans` (every dangling link, including memory ideas never converted into
   a thesis).

7. **The memory brain stays where it is,** at `argus/ARGUS.md` and siblings,
   despite being markdown inside a Python package. The five `argus-*` skills
   are synced to the user's account and hardcode those paths; moving the store
   to satisfy a layout instinct would break a live, working setup that this
   repo does not control. Recorded here so the smell is documented rather than
   rediscovered. `argus/README.md` and `argus/CLAUDE.md` were deleted — those
   were strict duplicates of the root files, which is a different problem with
   no such excuse.

## Alternatives considered

- **A graph database.** Rejected for the same reason ADR 0001 rejected a SQL
  ledger: the whole repo is four files of JSONL and an in-memory graph built
  in milliseconds. Revisit alongside the ledger's own database question.
- **Inferring links from free text.** Rejected. `graph.py` links a prediction
  to a thesis only when its `thesis` tag names a *registered* thesis, and only
  extracts a ticker from memory prose when the symbol is followed by a named
  exchange. Manufactured edges are worse than missing ones: they make the
  concentration report confidently wrong, and concentration drives sizing.
- **Making stage multipliers empirical.** Rejected for now — there are zero
  resolved theses to fit against. The constants are stated priors, written as
  named constants so the weekly review can argue with them in a one-line diff.

## Consequences

- Seeding the stores from the memory brain immediately produced findings the
  repo could not previously have generated: two catalysts each carrying more
  than one position, three cross-domain bridges, and one thesis whose most
  recent evidence undercuts it — all surfaced by `python -m argus status`.
- The audit caught a real error during that seeding: slug truncation produced
  catalyst ids that did not match what the thesis referenced. The gate worked
  before the data was committed, which is the entire argument for having it.
- `theses.py` and `catalysts.py` import `ledger.DOMAINS` at call time rather
  than module scope, to avoid an import cycle. Slightly ugly; documented here.
- Four stores means four audits. `python -m argus doctor` runs all of them.
