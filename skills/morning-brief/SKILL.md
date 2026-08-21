---
name: morning-brief
description: Run the ARGUS Morning Brief — the equities vertical slice of the Observe→Comprehend→Predict→Log loop. Pulls market data, synthesizes overnight developments and catalysts, surfaces one non-obvious cross-domain connection, and logs every prediction to the ledger before the brief ships.
---

# Morning Brief

**Scope (deliberate, Phase 0):** equities and the macro/rates/crypto context that
directly bears on them. Do not widen to the full ten-domain sensory table until
this slice consistently passes the impress test — that widening is a roadmap
decision, not a morning decision.

Read `CLAUDE.md` first if you haven't this session. The pre-publication gates
there apply in full.

## Procedure

### 1. Observe (fetch, don't recall)

Pull fresh data; timestamp everything. Minimum set:

- **Index complex:** SPY, QQQ, RSP, IWM — last close, overnight/pre-market
  level if available. RSP-vs-SPY is the standing concentration gauge.
- **Rates:** the Treasury curve (1M, 3M, 1Y, 2Y, 10Y, 30Y). Watch the front
  end vs the effective fed funds rate — that spread is the market's Fed call.
- **Crypto context:** BTC spot and 7-day path (regime thermometer for risk
  appetite and the tokenization thesis).
- **Single names:** anything within 7 days of a catalyst you're tracking.
- **Calendar:** earnings in the next 14 days (large caps), scheduled macro
  events (FOMC, CPI), and every open ledger prediction's resolve-by date.

Data sources available today: FMP MCP tools (treasury rates, historical
prices, sector snapshots, statements), Robinhood MCP tools (real-time equity
quotes, earnings calendar). If a source is unavailable, say so in the brief
rather than filling the gap from memory.

### 2. Orient against the ledger and the error library

- `python -m argus.ledger list --open` — which open calls does today's data
  support, weaken, or resolve early?
- `python -m argus.ledger list --open | grep OVERDUE` — anything overdue gets
  resolved today, not "later".
- Read `docs/error-patterns.md`. Every new call you're about to make gets
  checked against it.

### 3. Comprehend

- What actually changed overnight, and *why* (causal model, not headline echo)?
- Where is each active narrative in its lifecycle
  (fringe → early adopter → acceleration → consensus → exhaustion → reversal)?
- **The non-obvious connection of the day** — the signature move. One
  cross-domain propagation nobody's drawing yet, stated with a falsifiable
  implication. This section is mandatory; a brief without it isn't done.

### 4. Predict and log — BEFORE writing the brief

Formulate at least one new falsifiable call (more when the data offers them).
Log each via:

```bash
python -m argus.ledger add --claim "..." --prob 0.NN --by YYYY-MM-DD \
    --criteria "..." --domain ... --reasoning "..." --kill "..."
```

Where a prediction market prices the same question, quote its implied
probability (`argus/sources/prediction_markets.py`) and state whether you are
differing from it and why. No edge over the market is a valid finding — say it.

If the validator rejects a call, sharpen it until it passes. The brief may
only reference predictions by their ledger id — an unlogged prediction in a
shipped brief is a bug.

### 5. Write the brief

Output file: `data/briefs/YYYY-MM-DD.md`. Template:

```markdown
# Morning Brief — YYYY-MM-DD

*Data as of <UTC timestamp>. Sources: <list>. Research, not financial advice.*

## Tape
<index complex, rates, BTC — levels, deltas, and what stands out>

## What changed and why
<2-4 developments with causal read, narrative-lifecycle stage where relevant>

## Non-obvious connection of the day
<the cross-domain insight + its falsifiable implication>

## Catalyst countdown
<dated table: event, date, which ledger ids it resolves or informs>

## Ledger actions
<new predictions logged today (id, claim, P, resolve-by); open calls
strengthened/weakened by today's data; anything resolved>

## Positioning notes
<options with conditions and sizing discipline, each with its counter-case
and invalidation level. Never instructions to execute.>
```

### 6. Gate, then ship

Run the CLAUDE.md pre-publication gates (error-pattern check, falsifiability,
counter-case, impress test, precision sweep). If the impress test fails, dig
deeper — do not ship a headline-restating brief. Then commit the brief and the
ledger change together.
