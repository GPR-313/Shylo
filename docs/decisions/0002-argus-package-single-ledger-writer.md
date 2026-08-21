# ADR 0002 — The `argus` package, and one writer for the ledger

**Date:** 2026-08-21 · **Status:** accepted · **Supersedes parts of:** ADR 0001

## Context

ARGUS arrived at Phase 1 with a working ledger (`scripts/ledger.py`, 20 seeded
predictions) and no ingestion. Phase 1 landed as a package — `argus/ledger.py`
plus `argus/sources/` — carrying its own ledger implementation, a
`scripts/check_sources.py` status board, `scripts/setup.sh`, and a scheduled
GitHub Actions run.

That created a direct conflict. Two ledger implementations, both able to write
`data/ledger/predictions.jsonl`, disagreed on the record schema:

| | `scripts/ledger.py` (0.1) | `argus/ledger.py` (0.2) |
|---|---|---|
| discriminator | `type` | `kind` |
| id | slug (`2026-08-21-spy-770-eoy`) | `uuid4().hex[:12]` |
| reasoning snapshot | `thesis` | `reasoning` (`thesis` is now a grouping tag) |
| written at | `logged_at` | `created_at` |
| resolution points at | `id` | `prediction_id` |
| outcome | `"yes"` / `"no"` / `"unresolvable"` | `bool` |
| note field | `notes` | `note` |
| domains | `policy`, `other` | `politics`, `meta` |

The failure was silent, which is the dangerous kind. `argus.ledger` folds state
with `rec.get("kind") == "prediction"`; every seeded record carries `type`
instead. Verified before changing anything:

```
$ python3 -m argus.ledger list --open
(empty)
```

Twenty open predictions, reported as none. `score` would likewise have graded an
empty ledger forever, and the Actions job would have committed that silence
every weekday morning. This is precisely the memory-holing the Ledger Contract
exists to prevent — arriving by schema drift rather than by intent.

## Decision

1. **`argus/ledger.py` is the only writer.** `scripts/ledger.py` is deleted, not
   deprecated. Two writers appending to one append-only file is a split brain:
   each writes records the other cannot see, and neither is wrong about it.

2. **Read both schemas; write only the new one.** `normalize()` maps legacy
   records onto current field names at read time, and `record_kind()` accepts
   `type` or `kind`. The 20 seeded records are **not rewritten** — rewriting the
   append-only file to fit new code would trade the audit trail for tidiness,
   and the audit trail is the product. The adapter is lossless: legacy keys
   survive alongside canonical ones.

3. **`unresolvable` survives as a first-class outcome.** The 0.2 ledger typed
   `outcome` as `bool`, which cannot express it. Ledger Contract rule 2 —
   "a mistaken entry gets resolved as `unresolvable` with a note, never
   deleted" — depends on it existing, so `outcome` is now `True | False |
   "unresolvable"`. Unresolvables are excluded from Brier scoring and counted
   separately: they are failures of the *criteria*, not of the forecast, and
   ADR 0001 made that rate the audit metric on the falsifiability gate.

4. **The domain vocabulary is the union of both.** `policy`/`politics` and
   `other`/`meta` are accepted spellings of the same domains. Two seeded
   predictions use `policy`; narrowing the set would have made them
   unloggable and unlistable. `policy` and `other` are preferred going forward.

5. **`scripts/calibration.py` reads through `argus.ledger`.** It keeps its
   markdown report, ASCII calibration curve, and overdue queue — capability the
   0.2 `score` command does not have — but no longer parses the ledger itself.
   `show` and `audit` were ported into `argus/ledger.py` so retiring the old CLI
   cost nothing.

6. **`resolve --note` is mandatory, minimum 10 characters.** Carried forward
   from 0.1, which enforced it; 0.2 had made it optional. A resolution is final,
   and the post-mortem needs to know how it was adjudicated.

## Consequences

- `python -m argus.ledger` is the documented entry point everywhere:
  `CLAUDE.md`, `README.md`, both skills, both prompts, and the Actions workflow.
- The ledger file is now mixed-schema, permanently. That is the intended cost:
  `audit` validates both shapes, and every record is still exactly one line of
  git history.
- Legacy slug ids keep working — `resolve 2026-08-21-dems-take-house` grades
  correctly — so nothing in the seeded set is stranded.
- `data/briefs/2026-08-21.md` still cites the old command. Shipped briefs are
  dated artifacts and are not retroactively edited; ADR 0001 is likewise left
  as written.

## Also settled here

- **A latent bug in `Source.get()`:** joining an empty path produced a trailing
  slash, so GDELT was called as `/api/v2/doc/doc/`. Its documented endpoint has
  none, and that shape is a plausible 404. An empty path now hits `base_url`
  unchanged. Not verified against the live API — outbound calls were blocked in
  the environment where this was written.
- **No MCP wrapper for prediction markets or Treasury data.** `argus/sources/`
  already reaches both over plain REST; a second path to the same numbers is a
  way to get two answers and no way to choose. `.mcp.json` declares `edgar` and
  `sqlite` only.
