---
name: weekly-self-review
description: Run the ARGUS weekly self-review — resolve due predictions, score calibration AND the market head-to-head, autopsy every miss into the error-pattern library, audit the relation graph for dangling and correlated positions, and propose one concrete process upgrade. The mechanism behind "never be satisfied."
---

# Weekly Self-Review

The improvement loop's heartbeat. Runs weekly (suggested: Sunday), and
immediately after any thesis hits its kill criteria.

## 1. Resolve everything that's due

```bash
python -m argus status
python -m argus.ledger list --open | grep OVERDUE
python -m argus.catalysts list --past
```

For each overdue prediction: research the actual outcome **against the
prediction's own `resolution_criteria`** — fetch the named source, do not
adjudicate from memory — then:

```bash
python -m argus.ledger resolve <id> --outcome true|false|unresolvable \
    --note "<source consulted + what happened>"
```

Close every catalyst whose date has passed:

```bash
python -m argus.catalysts resolve <id> --what-happened "..." [--on YYYY-MM-DD]
```

`unresolvable` is for genuinely unadjudicable outcomes (source vanished, event
redefined) — not for calls you'd rather not grade. Also resolve early any open
prediction whose outcome is already locked in.

## 2. Score — both scoreboards

```bash
python -m argus.ledger score
python3 scripts/calibration.py
```

Two numbers matter, and they answer different questions:

**Brier and the calibration curve** answer *was ARGUS right?* Note overall
Brier, best and worst domain, and curve shape. Compare against last week's memo:
**a flat or worsening curve two weeks running is an emergency** — escalate it to
the top of the memo and propose a structural fix, not a tweak.

**The market head-to-head** answers *did ARGUS beat deferring to the crowd?*
This is the harder and more important question. If `vs_market` reports "no
edge," that is not a bad week — it is a finding, and the correct response is to
say so in the memo, stop publishing differentiated probabilities on those
questions, and name the mechanism that would justify resuming. If `vs_market`
is `null`, coverage is the problem: check `market_coverage()` and fix the
process, because an edge claim with no benchmark is unfalsifiable (EP-000f).

`score` also reports the `unresolvable` count. That rate audits the
falsifiability gate itself — unresolvables are criteria failures, not
forecasting failures. Above ~10% of everything closed, fix the criteria
template before logging more calls.

## 3. Autopsy every miss

For each prediction resolved `false` that carried P > 0.5 (and each `true` that
carried P < 0.5 — misses run both ways), classify the failure:

- **Bad data** — the input was wrong or stale at logging time.
- **Bad model** — the causal story was wrong; the world worked differently.
- **Bad timing** — right direction, wrong resolve-by window.
- **Unknowable** — no better version of me sees this coming. Use sparingly;
  this is the excuse bucket and it is audited.

Then the harder question: *what would a better version of me have seen at
logging time?* Name the observable signal that was available and ignored. If it
was available through a source in `argus/sources/`, name the module — that is
how a miss becomes a check rather than a regret.

## 4. Audit the graph

```bash
python -m argus.graph report
python -m argus.theses orphans
python -m argus.catalysts orphans
```

Five things to act on, not just read:

1. **Concentration.** Any catalyst carrying more than one position is one bet.
   Was it sized as one? If not, that is EP-000d and it goes in the memo.
2. **Cut points.** Which single event holds the most of the book together? Is
   that exposure intentional?
3. **Theses with no live call.** Nothing can falsify these now. Log a fresh
   prediction or close the thesis with a post-mortem — those are the only two
   options.
4. **Unanchored resolve-by dates.** EP-000b. Either log the catalyst that
   settles each, or justify the calendar boundary in the memo.
5. **Memory ideas never converted.** Your own past insights, already
   researched, unused. Pick at least one per review and run
   `skills/thesis-forge/SKILL.md` on it, or archive it with a reason.

## 5. Review every live thesis

```bash
python -m argus.theses list --open
```

For each:

- **Does the latest evidence undercut it?** `argus status` flags this. Stage
  down, close it, or argue in the memo why the evidence does not meet the kill
  criteria as written. Continuing at the old size without doing one of those is
  EP-000e.
- **Is the stage still honest?** A thesis that has been `acceleration` for six
  months while coverage initiated and the multiple expanded is `consensus`, and
  saying otherwise is how sizing discipline quietly dies.
- **Do the kill criteria still discriminate?** Criteria that nothing could
  trigger are decoration. Rewrite them by closing the thesis and opening a
  successor — never by editing.

## 6. Feed the error-pattern library

Append findings to `docs/error-patterns.md` in its entry format. If a pattern
recurs (2+ hits), promote it: sharpen the detection rule until a pre-publication
gate can mechanically apply it. **The best outcome of a review is a written rule
becoming a command** — that is how EP-000b became `catalysts orphans`.

## 7. Propose upgrades

At least one concrete, implementable process upgrade per review. "Keep doing
what we're doing" is not an acceptable finding. Good candidates:

- A stated prior that the data now contradicts — `theses.STAGE_SIZING` and
  `regime` thresholds are named constants precisely so this is a one-line diff.
- A source that would have caught a miss, added to `argus/sources/`.
- A gate that would have caught a bad call, added to a validator **with a test**.

Significant changes get an ADR in `docs/decisions/`. Anything touching
validation, scoring, or sizing ships with a test:
`python3 -m unittest discover -s tests`.

## 8. Write the memo

Output: `data/reviews/YYYY-Www.md` (e.g. `2026-W38.md`).

```markdown
# Weekly Self-Review — week Www, YYYY

## Scoreboard
<resolutions this week; Brier trend; calibration curve summary; best/worst
domain; THE MARKET HEAD-TO-HEAD and what it says about edge; unresolvable rate>

## Autopsies
<per miss: what I said, what happened, failure class, what a better version of
me would have seen, and which source would have shown it>

## Graph audit
<concentration, cut points, orphans, memory ideas converted or archived>

## Thesis review
<per live thesis: stage honest? evidence undercutting? kill criteria still
discriminating? actions taken, with commands>

## What I missed this week
<events I should have had a prediction on, but didn't — the silent misses>

## Process upgrades
<the concrete upgrade(s) proposed, what was adopted, and the test that pins it>
```

Commit the memo, the resolutions, the store changes, and the error-pattern
updates together.
