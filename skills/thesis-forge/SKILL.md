---
name: thesis-forge
description: Turn an observation into a positioned thesis — mechanism, falsifiable calls with market benchmarks, dated catalysts, correlation check, and a computed size. Use whenever an idea is worth keeping: a finding from a sweep or dossier, a bottleneck-hunt result, a news item that seems mispriced, or any "this is interesting" that would otherwise evaporate. This is the path from noticed to positioned.
---

# Thesis Forge

Most edge is lost between noticing and positioning. Someone sees the thing,
writes it down, and nothing happens — `python -m argus.graph orphans` has a
category for exactly this (`memory_ideas_never_converted`) because it is the
most common way an idea dies.

This workflow closes that gap in seven steps. Each step has a command, and the
gates reject work that skips one.

Read `CLAUDE.md` first if you haven't this session — the four contracts and the
pre-publication gates apply in full.

## 0. Is this worth forging?

A thesis is expensive: it needs a mechanism, kill criteria, at least one logged
prediction, and ongoing maintenance. Forge one when **all** of these hold:

- There is a *mechanism*, not just a correlation. You can say what forces what.
- There is a *dated event* within roughly 18 months that would settle it.
- There is a *position* expressible in something the user could actually own.
- Consensus has not already priced it, or you can say specifically why it hasn't.

If any fails, capture it to memory (`argus-capture`) and move on. An idea in
memory with an honest "not yet" beats a thesis that cannot be graded.

## 1. State the mechanism before anything else

Write the causal chain in one paragraph, in the form *A forces B, which forces
C, and C is what reprices D*. Not a description of the world — an assertion
about what causes what.

Two tests, both cheap:

- **The reversal test.** If the mechanism ran backwards, would you notice? A
  mechanism that explains any outcome explains none.
- **The next-link test.** Name the observable that sits one link *before* the
  repricing. That observable is your leading indicator and usually your
  catalyst; if you cannot name it, you have a story, not a mechanism.

The registry enforces the floor mechanically: `theses open` rejects a
`--mechanism` under 60 characters or containing no causal connective. Passing
that check is not the same as passing the two tests above.

## 2. Stage it honestly

Where is this narrative *now*?

| Stage | What it looks like | Sizing |
|---|---|---|
| `fringe` | Practitioners only. No coverage, no ETF, no consensus name. | 25% |
| `early_adopter` | First coverage initiated, mechanism plausible but unproven. | 50% |
| `acceleration` | Mechanism confirmed by data, crowd not yet arrived. | 100% |
| `consensus` | It is the pitch everyone makes. You are paying for it. | 40% |
| `exhaustion` | The rerate is behind you; flows are the only argument left. | 15% |
| `reversal` | The constraint cleared. The trade, if any, is the other way. | 0% |

Stage is a **sizing input**, not a label — the multiplier above is applied by
`argus.edge`. The most expensive error in this workflow is staging something
`acceleration` because you like it, when the honest read is `consensus`.

Cross-check the stage against an attention series rather than intuition:
`Gdelt.velocity()`, `WikipediaPageviews.velocity()`, and `OpenAlex.velocity()`
all return the same z-score shape. A z-score above 2 with a flat operating
metric is late-stage consensus, not acceleration (EP-000a).

## 3. Write the falsifiable calls — and check the market first

For each call, **before** logging:

```bash
python -c "
from argus.sources import Polymarket, Kalshi
for m in Polymarket().search('<your keyword>', limit=10):
    print(round(Polymarket().implied_probability(m) or -1, 3), m.get('question'))
"
```

Then log it, with the market price if one exists:

```bash
python -m argus.ledger add \
  --claim "..." --prob 0.NN --by YYYY-MM-DD \
  --criteria "<the test a stranger runs, with a threshold and a named source>" \
  --domain <domain> --reasoning "<why you believe this, right now>" \
  --kill "<what ends the parent thesis>" \
  --market-prob 0.NN \
  --tickers ... --sources ...
```

Rules, all of them non-negotiable:

- **If a market prices it, record the price.** Under five points of
  disagreement is agreement with the crowd — say so rather than dressing it up
  (EP-000f).
- **If nothing prices it, say so explicitly** in the output, and name where you
  looked. "No market prices this" is a finding; silence is not.
- **If the validator rejects the call, sharpen the claim.** Never soften the
  tooling, never bypass the CLI, never drop the prediction quietly.
- At least one call must be resolvable within roughly six months. A thesis whose
  earliest test is two years out cannot be managed, only held.

## 4. Anchor to catalysts

Every resolve-by date needs a dated event that actually settles the question.

```bash
python -m argus.catalysts add --title "..." --date YYYY-MM-DD \
  --resolves "<the question this settles>" --domain <domain> \
  --precision day|week|month|quarter \
  --predictions <ledger-id>,<ledger-id> --source "<where the date came from>"

python -m argus.catalysts orphans     # must not list your new calls
```

Where to find real dates rather than guessing:

- **Regulatory:** `FederalRegister.dated_deadlines()` — comment deadlines and
  effective dates are the agency's own, not an estimate.
- **Clinical:** `ClinicalTrials.upcoming_readouts()` — a registered Phase 3
  primary completion date is among the most reliable forward dates anywhere.
- **Legislative:** `Congress.bill_actions()` — committee action is dated and
  attributable the day it happens.
- **Corporate:** earnings dates via the FMP or Robinhood connectors.

Use `--precision` honestly. A scheduled FOMC meeting is `day`; "sometime in
Q4" is `quarter`, and the calendar treats the two differently when it decides
whether a catalyst could have anchored a date.

## 5. Register the thesis

```bash
python -m argus.theses open \
  --title "..." --mechanism "..." --kill "..." \
  --domain <domain> --stage <stage> --direction long|short|pair|flat \
  --predictions <ledger-id>,... --catalysts <catalyst-id>,... \
  --memory M2026MMDDx --tickers ... \
  [--win 1.8 --loss 0.6]
```

`--win` and `--loss` are the gain and loss per unit of exposure if the thesis
plays out or hits its kill criteria. **Estimate them or omit them — never
invent them.** A thesis with no payoff estimate shows as `unpriced` in
`edge rank`, which is the correct and honest state. A fabricated payoff flows
directly into a position size.

Link `--memory` to the brain entries this came from. That link is what lets
`graph orphans` stop reporting the idea as unconverted, and what lets a future
post-mortem find what you were reading when you formed the view.

## 6. Check correlation BEFORE sizing

```bash
python -m argus.graph concentration
python -m argus.graph cutpoints
```

If your new thesis shares a catalyst with an existing one, **they are one bet.**
Two theses, two tickers, two domains — one dated event, one drawdown. Size the
group, not the legs:

```python
from argus.edge import size, size_cluster
group = [size(p, win, loss, stage=stage) for ... ]
print(size_cluster(group, cluster_cap=0.08))
```

This step is not optional and it is not a formality. Skipping it is EP-000d,
and EP-000d is how a book with a 5% per-position cap takes a 15% drawdown.

## 7. Size, then write it up

```bash
python -m argus.edge size --prob 0.NN --win W --loss L --stage <stage> --market 0.NN
python -m argus.edge rank
python -m argus.regime          # does the backdrop discount this further?
```

Then publish, with every one of these present:

- **The mechanism**, in the causal form, one paragraph.
- **The stage**, and the observable that justifies it.
- **The calls**, by ledger id, with P, resolve-by, and the market price or an
  explicit "nothing prices this."
- **The catalysts**, dated, with what each resolves.
- **The counter-case** — the strongest argument against, stated properly rather
  than strawmanned. If you cannot make it well, you do not understand the
  thesis well enough to size it.
- **The kill criteria**, quoted verbatim from the registry.
- **The size**, with its binding constraint and the cluster scaling if any.
- **The disclaimer.** Options with conditions, never instructions to execute.
  Research, not financial advice.

## Maintenance — the part that gets skipped

A forged thesis is a standing obligation:

```bash
python -m argus.theses evidence <id> --note "..." --undercuts   # log it against
python -m argus.theses stage <id> --to <stage> --evidence "..." # move it
python -m argus.theses close <id> --outcome killed --note "<post-mortem>"
```

`python -m argus status` surfaces any thesis whose latest evidence undercuts it,
every single run, until you act. Logging a contradiction and then continuing to
publish the thesis at its old size is EP-000e — and it is the failure mode this
whole registry was built to make impossible to ignore.
