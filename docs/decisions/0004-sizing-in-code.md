# ADR 0004 — Sizing belongs in code, not in adjectives

**Date:** 2026-09-17 · **Status:** accepted

## Context

CLAUDE.md has always said "speculative theses get speculative sizing" and
"ruin is forbidden." Those are the right rules and they were unenforceable. An
agent writing a brief under time pressure, having just talked itself into a
thesis, is the worst possible judge of what "speculative" means — and there was
nothing to check its answer against.

Worse, the ledger measured the wrong thing on its own. Brier score grades
whether ARGUS was *right*. A book of perfectly calibrated 80% calls at 5:1
against loses money forever, and the ledger would report that book as excellent.
Calibration is necessary and nowhere near sufficient.

## Decision

`argus/edge.py`, pure arithmetic on explicit inputs, no network, no hidden
state. Every positioning suggestion goes through it.

1. **Breakeven probability is published next to P.** Every payoff structure
   implies the probability needed to break even. Stating it is the fastest way
   to kill a thesis surviving on narrative alone, and it takes one line.

2. **Quarter-Kelly by default.** Full Kelly maximises long-run growth *if your
   probabilities are right*. ARGUS's are subjective estimates, and the penalty
   for overbetting is asymmetric and permanent. `DEFAULT_KELLY_FRACTION = 0.25`.

3. **Three constraints, and the binding one is named.** Fractional Kelly, then
   the lifecycle-stage multiplier from `theses.STAGE_SIZING`, then a hard
   per-position cap (5%). The output says which one bound, because a size you
   cannot explain is a size you will not hold through a drawdown.

4. **The ruin guard is a cluster cap.** `size_cluster` scales a correlated
   group — positions sharing a catalyst, as found by `argus.graph
   concentration` — so their *joint* worst case respects one drawdown limit
   (8%). Scaling is proportional, so relative conviction inside the cluster
   survives. This is the mechanical version of "five names on one catalyst
   chain are one bet, not diversification."

5. **Negative EV sizes to zero, and `reversal` stage sizes to zero.** Not a
   warning. Zero.

6. **Payoffs are never invented.** A thesis without `--win` and `--loss` is
   reported by `edge rank` as unpriced. Unpriced is the correct state for a
   thesis nobody has estimated a payoff for; a fabricated payoff flows straight
   into a position size.

7. **`market_prob` is stored on every benchmarked prediction,** and
   `ledger score` reports ARGUS's Brier against the market's on the overlapping
   subset only. Scoring ARGUS's whole book against the market's subset would
   flatter ARGUS by construction. This head-to-head, not calibration, is the
   evidence that the project beats deferring to the crowd.

## Consequences

- Sizing tests pin **hand-computed** values, not captured output. A sizing bug
  loses real money quietly, so the expected numbers are derived independently
  of the implementation.
- Sizes round to six decimal places, not four: a fringe-stage quarter-Kelly
  stake is legitimately ~60bp, and four decimals threw away half its
  significant figures and broke proportionality inside a cluster.
- The stage and regime multipliers are **priors, not measurements.** They are
  named constants so the weekly self-review can argue with them cheaply. Once
  enough theses have run their course, they should be fitted; until then,
  pretending they are anything but assumptions would be the same error the
  ledger exists to prevent.
- Everything `edge` prints carries a disclaimer line. Sizing output is an
  option with conditions, never an instruction to execute, and the tool that
  produces numbers is the most likely place for that distinction to erode.
