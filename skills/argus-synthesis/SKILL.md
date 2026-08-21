---
name: argus-synthesis
description: The consolidation pass of Project Argus, the user's persistent second brain — the step that turns stored notes into intelligence, the way sleep turns a day into memory. Reviews everything captured since the last pass against the whole brain - promotes durable insights into core memory, surfaces patterns and contradictions across entries, refreshes or archives stale items, closes dead threads, grooms the index, and poses the sharpest next questions. Use for weekly review, synthesize, consolidate, clean up Argus, tidy my brain, what has Argus learned, Argus maintenance — and as the skill behind any scheduled weekly run, attended or unattended. Also use when the index or memory files have grown messy or contradictory.
---

# argus-synthesis — consolidation

Capture without consolidation is a junk drawer. This skill is why Argus compounds instead of accumulating: on each pass it re-reads recent memory against the whole brain, keeps what proved durable, connects what rhymes, confronts what conflicts, and retires what died. It is the only skill allowed to write `argus/core.md`, and the only one allowed to archive — powers that come with the obligation to leave an audit trail.

## The Argus protocol (shared by all argus-* skills)

All memory lives in the attached Claude Project via the Projects tool — never on the local filesystem, which is discarded when the session ends.

- `argus/ARGUS.md` — the constitution: memory map, entry format, rules. Read it first, every run. It wins over this skill on any conflict.
- `argus/INDEX.md` — master index: active threads, entities & watch list, open questions, doc registry, last-synthesis stamp.
- `argus/core.md` — distilled durable memory. This skill is its sole author; every promotion carries provenance entry IDs.
- `argus/memory/YYYY-MM.md` — monthly journal, newest entries first.
- `argus/dossiers/<slug>.md`, `argus/sweeps/YYYY-MM.md` — dossiers and sweep briefs.
- `argus/archive/...` — retired material. Nothing in Argus is ever deleted; it is archived with a pointer left behind.

Entries look like `### M20260821a — Title`, carry tags, source, confidence, and an optional `review` date.

If `argus/ARGUS.md` or `argus/INDEX.md` is missing, the brain has not been bootstrapped (or was moved): recreate both from the protocol described in this section before proceeding, and tell the user you did.

## Procedure

1. **Sync.** Read `argus/ARGUS.md`, `argus/INDEX.md`, `argus/core.md`, every memory entry since the last-synthesis stamp (all of it, if never), and skim recent sweep briefs for anything that never got captured but should have been.

2. **Promote.** Gather entries tagged `#core-candidate` plus anything recall or sweeps kept leaning on. Promotion into `core.md` means *compression*: merge into an existing belief where one exists, write one tight line with provenance IDs where none does — never paste entries in wholesale. Core stays under ~150 lines; if a promotion would breach that, something weaker in core gets compressed or demoted first. A brain whose core grows without bound has merely moved the junk drawer.

3. **Find the patterns.** Read across the period's entries looking for rhymes: the same theme arriving from three directions, a thesis quietly accumulating support or damage, a behavioral pattern in the decisions themselves ("third capture this month about position sizing regret"). Write the one to three real patterns as memory entries tagged `#synthesis` — these are often the most valuable entries in the whole brain, because no single day could have produced them.

4. **Hunt contradictions.** Deliberately, not incidentally: core versus recent entries, dossier verdicts versus later sweeps, stated preferences versus captured decisions. Every contradiction found becomes an open question in INDEX and a line in the report. Never resolve one silently — flag it, and resolve it only where the evidence clearly settles it, recording the resolution as a memory entry.

5. **Hygiene.** Entries past their `review` date: quickly re-verify (live tools where cheap), then re-date, revise with a dated addendum, or archive. Threads silent past ~30 days: close with a one-line outcome or explicitly mark dormant. Move superseded or dead material to `argus/archive/YYYY-MM-<topic>.md`, leaving a one-line pointer where it lived. Rebuild any INDEX section that has drifted from reality — the index is derived data; memory files are the truth.

6. **Report and stamp.** Write the synthesis report as a memory entry (tagged `#synthesis`), update the last-synthesis stamp, then deliver the short version: what was promoted, patterns found, contradictions open, what was archived, and the **top three questions most worth a dossier next**. Attended: in chat. Unattended: written to the project, with a concise message sent if the run produced anything that matters — a quiet week honestly reported as quiet builds more trust than manufactured insight.

## Judgment calls

- **Editing `argus/ARGUS.md` itself** (the constitution) is allowed only for additive clarifications, and only with the user's explicit approval in an attended session. Never unattended.
- **Provenance is non-negotiable.** Every line in core must trace to entry IDs. A core belief that cannot say where it came from gets demoted to an open question.
- **Archive, never delete** — including during hygiene. The audit trail is the brain's ability to explain itself later.
- **Re-verification stays read-only toward the world**: live tools may be queried to refresh a stale entry, but synthesis never trades, sends, or shares anything outward.
- **Cadence**: weekly is the natural rhythm; monthly is the minimum before the backlog makes passes shallow. If the backlog is huge, do the most recent month well rather than everything badly, and say so in the report.

## Report format

```
# Synthesis — 2026-08-23
Promoted to core: 2 (M20260821b → position sizing; M20260822a → …)
Patterns: 1 — recurring interest in energy-storage names across 4 entries; captured as M20260823a
Contradictions open: 1 — 8% cap [M20260821b] vs. July small-cap liquidity note [M20260714b] → Q3
Hygiene: 3 refreshed, 1 archived (dead thread T2), index rebuilt
Worth a dossier next: (1) …, (2) …, (3) …
```
