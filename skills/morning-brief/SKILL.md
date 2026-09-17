---
name: morning-brief
description: Run the ARGUS Morning Brief — the daily Observe→Comprehend→Predict→Navigate loop. Opens on the whole-system status, pulls fresh data, reconciles the book against the graph, surfaces one non-obvious cross-domain connection, logs every prediction with its market benchmark, and ships sized positioning options.
---

# Morning Brief

**Scope (deliberate):** equities and the macro/rates/crypto context that bears
on them, plus whatever the graph says is connected to the live book. Widening
to all ten domains is a roadmap decision, not a morning decision — but the
graph's `bridges` output reaches across domains for free, and reading it is
mandatory below.

Read `CLAUDE.md` first if you haven't this session. The four contracts and the
pre-publication gates apply in full.

## 1. Open on the whole book

```bash
python -m argus status
python -m argus agenda --days 21
```

This is the first command of the day, before any data pull. It tells you:
overdue predictions, theses whose latest evidence undercuts them, catalysts
past their date, concentration warnings, and a ranked "what to do next."

**Anything `status` lists as overdue gets handled today, not "later."** An
overdue prediction is memory-holing on a delay.

## 2. Observe — fetch, don't recall

Pull fresh data and timestamp everything. Minimum set:

- **Index complex:** SPY, QQQ, RSP, IWM — last close and pre-market. RSP-vs-SPY
  is the standing concentration gauge.
- **Rates:** the curve (1M, 3M, 1Y, 2Y, 10Y, 30Y). The front end against
  effective fed funds is the market's Fed call.
- **Regime:** `python -m argus.regime`. Liquidity, credit, curve, and the
  composite sizing multiplier. Read `breaks_if` — a regime call with no stated
  invalidation is a label, not an analysis.
- **Crypto context:** BTC spot and 7-day path — risk appetite and the
  tokenization thesis in one series.
- **Positioning:** `EdgarDailyIndex.insider_clusters(days=5)` and
  `.activist_stakes(days=5)`. Cluster buying and fresh 13Ds are same-day
  observable. The index records *that* a Form 4 filed, not whether it was a buy
  — read the document via the `edgar` connector before it becomes a claim.
- **Single names:** anything within 7 days of a catalyst you track.
- **Calendar:** `python -m argus.catalysts list --days 21`, plus earnings and
  scheduled macro (FOMC, CPI) in the next 14 days.

If a source is unavailable, **say so in the brief**. Several clients in
`argus/sources/` have never been exercised live (their docstrings say which);
`python3 scripts/check_sources.py` is the acceptance test. A number from an
unverified client is a number you have not verified.

## 3. Orient against the book and the error library

```bash
python -m argus.ledger list --open
python -m argus.graph concentration
python -m argus.graph bridges
python -m argus.theses list --open
```

- Which open calls does today's data support, weaken, or resolve early?
- Does anything today hit a live thesis's **kill criteria**? If yes, that is the
  headline, not a footnote — `python -m argus.theses show <id>` to read them
  verbatim before deciding.
- Read `docs/error-patterns.md`. Every new call gets checked against it.

## 4. Comprehend

- What actually changed overnight, and *why*? Causal model, not headline echo.
- Where is each active narrative in its lifecycle, and did anything move a
  stage? A stage change needs evidence and a command, not a sentence:
  `python -m argus.theses stage <id> --to X --evidence "..."`.
- **The non-obvious connection of the day** — mandatory; a brief without it is
  not done. Start from `argus.graph bridges`: a node spanning two domains is a
  propagation path already half-drawn in your own book. If the graph offers
  nothing new, run Part 2 of `skills/connection-hunt/SKILL.md` — one domain
  pair, one traced chain. State the chain with its leading indicator and a
  falsifiable implication.

## 5. Predict and log — BEFORE writing the brief

For each new call, check the market first, then log with the price attached:

```bash
python -m argus.ledger add --claim "..." --prob 0.NN --by YYYY-MM-DD \
    --criteria "..." --domain ... --reasoning "..." --kill "..." \
    --market-prob 0.NN --catalyst <catalyst-id> --tickers ...
python -m argus.catalysts orphans   # your new call must not appear here
```

- Where a market prices the question, quote it and state whether you differ and
  why. **Under five points of disagreement is agreement** — publish that
  finding rather than dressing it up (EP-000f).
- Where nothing prices it, say so and name where you looked.
- If the validator rejects a call, sharpen it until it passes.
- The brief may reference predictions **only by ledger id**. An unlogged
  prediction in a shipped brief is a bug.

## 6. Navigate — size before you suggest

```bash
python -m argus.graph concentration          # correlation BEFORE sizing
python -m argus.edge rank
python -m argus.edge size --prob 0.NN --win W --loss L --stage <stage>
```

Positions sharing a catalyst are one bet: size the group with
`argus.edge.size_cluster`, not each leg against the per-position cap (EP-000d).
Apply the regime multiplier from step 2. Never invent `--win`/`--loss`; unpriced
is the honest state.

## 7. Write the brief

Output: `data/briefs/YYYY-MM-DD.md`.

```markdown
# Morning Brief — YYYY-MM-DD

*Data as of <UTC timestamp>. Sources: <list>. Unverified sources flagged inline.
Research, not financial advice.*

## Book status
<overdue calls handled, theses undercut, catalysts closed — from `argus status`>

## Tape
<index complex, rates, BTC — levels, deltas, what stands out>
<regime: composite, sizing multiplier, and what would break it>

## What changed and why
<2-4 developments with causal read, and lifecycle stage where relevant>

## Non-obvious connection of the day
<the cross-domain chain: signal -> mechanism -> constraint -> instrument,
with the leading indicator and a falsifiable implication>

## Catalyst countdown
<dated table: event, date, precision, which ledger ids and theses it resolves>

## Ledger actions
<new calls (id, claim, P, market P, resolve-by); open calls strengthened or
weakened by today's data; anything resolved; anything staged>

## Positioning notes
<options with conditions: entry, exit, invalidation level. Computed size with
its binding constraint; cluster scaling where correlated. Counter-case attached
to each. Never instructions to execute.>
```

## 8. Gate, then ship

```bash
python -m argus doctor          # all four stores consistent
python -m argus.ledger score    # read the market head-to-head before publishing
```

Then the rest of the CLAUDE.md gates: error-pattern check, counter-case, impress
test, precision sweep. **If the impress test fails, dig deeper — do not ship a
headline-restating brief.** Commit the brief and every store change together.
