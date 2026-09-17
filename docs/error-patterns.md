# Error-Pattern Library

Every miss gets an autopsy (see `skills/weekly-self-review/SKILL.md`); every
autopsy that generalizes lands here. **CLAUDE.md requires checking this file
before any new call ships** — that check is only as good as the entries, so
write detection rules a future run can mechanically apply, not vibes.

## Entry format

```markdown
### EP-NNN: <short pattern name>
- **First observed:** YYYY-MM-DD (ledger ids: ...)
- **Hits:** N (update when the pattern recurs)
- **Failure class:** bad data | bad model | bad timing | unknowable
- **Pattern:** what keeps going wrong, stated generally
- **Detection rule:** the question to ask a new call to catch this before
  logging (make it answerable yes/no)
- **Prescription:** what to do instead
```

Patterns with 2+ hits are *load-bearing*: a new call matching one must either
be fixed or explicitly argue why the pattern doesn't apply.

## Failure classes

- **bad data** — the input was wrong, stale, or misread. Fixable by sourcing.
- **bad model** — the causal story was wrong. The expensive kind; update priors.
- **bad timing** — right thesis, wrong horizon. Usually means the resolve-by
  date was set by optimism rather than by a catalyst.
- **unknowable** — genuinely irreducible. Rare. Do not use as an excuse; if
  more than ~20% of misses land here, the classification is being abused.

Note the distinction between a *miss* and an `unresolvable` resolution: a miss
is a forecasting failure and belongs in this library; an `unresolvable` is a
gate failure — the criteria could not be adjudicated as written — and is
audited via `python -m argus.ledger score` in the weekly review.

---

## Seeded priors

Known failure modes for this kind of agent, entered before any miss so ARGUS
starts with something to check against. These carry 0 hits by construction;
they are not evidence, they are hypotheses about how this agent will fail.

### EP-000: Stale-anchor risk (standing check, logged pre-emptively)
- **First observed:** 2026-08-21 (at seeding — not from a resolved miss)
- **Hits:** 0
- **Failure class:** bad data
- **Pattern:** the agent's training knowledge lags reality by months; thresholds
  or base rates anchored on recalled (not fetched) numbers embed that lag.
  Discovered at seeding: recalled Fed expectations implied cuts, while the
  fetched bill curve (EFFR 3.63% vs 1Y at 4.00%) priced hikes.
- **Detection rule:** does every number in the claim, criteria, and thesis
  trace to data fetched this session? If any number is recalled, is it labeled
  as recalled?
- **Prescription:** fetch before logging; when a number can't be fetched, say
  so in the thesis and widen the uncertainty (pull P toward 50%).

### EP-000a: Narrative velocity mistaken for adoption
- **First observed:** 2026-08-21 (seeded prior)
- **Hits:** 0
- **Failure class:** bad model
- **Pattern:** GDELT volume and Reddit mention counts measure *attention*, not
  adoption or fundamentals. A spike often marks late-stage consensus — the
  point of maximum coverage is frequently the point of minimum remaining edge.
- **Detection rule:** is the volume z-score above 2 while the underlying
  operating metric is flat? (`Gdelt.velocity()` returns the z-score;
  `ApeWisdom.movers()` returns mention deltas.)
- **Prescription:** require a fundamental confirmation series before acting on
  any attention signal. Stage the narrative explicitly.

### EP-000b: Horizon set by convenience
- **First observed:** 2026-08-21 (seeded prior)
- **Hits:** 0
- **Failure class:** bad timing
- **Pattern:** resolve-by dates chosen as round numbers (year-end,
  quarter-end) rather than anchored to a dated catalyst that actually resolves
  the question.
- **Detection rule:** do the resolution criteria name an event, filing, or
  scheduled release? If the date is 12-31 or a quarter boundary, is that
  because a catalyst lands there, or because it was tidy?
- **Prescription:** anchor every date to a catalyst on the calendar.

### EP-000c: Extrapolating an adoption curve linearly
- **First observed:** 2026-08-21 (seeded prior)
- **Hits:** 0
- **Failure class:** bad model
- **Pattern:** tokenization and stablecoin AUM curves are lumpy — driven by
  discrete issuer launches and allocation decisions, not smooth accretion.
  Linear or exponential fits over-predict in quiet months and under-predict on
  launch news.
- **Detection rule:** does the reasoning contain "run rate", "extrapolating",
  or an implied constant growth rate?
- **Prescription:** decompose into known scheduled catalysts plus a residual.

### EP-000d: Correlated bets counted as diversification
- **First observed:** 2026-08-21 (seeded prior; the shape was noticed by hand in
  memory entry M20260821e before any tooling existed to find it)
- **Hits:** 0
- **Failure class:** bad model
- **Pattern:** several positions with different tickers, sectors, or even
  domains resolve off one dated event. The book looks diversified and is one
  bet, so the drawdown arrives all at once and is several times the size the
  per-position cap implied.
- **Detection rule:** does `python -m argus.graph concentration` list a catalyst
  carrying more than one position? Does `python -m argus.graph cutpoints` return
  an articulation point with degree above 2? Either is a yes.
- **Prescription:** size the group as one bet through
  `argus.edge.size_cluster`, not each leg against the per-position cap. State
  the shared catalyst explicitly in the output so the reader sees the
  correlation rather than inferring diversification from the ticker list.

### EP-000e: Thesis outlives its own evidence
- **First observed:** 2026-08-21 (seeded prior; M20260821f is a real instance —
  the contradiction was logged honestly and then nothing happened)
- **Hits:** 0
- **Failure class:** bad model
- **Pattern:** evidence against a thesis is observed and recorded, and the
  thesis keeps its stage, its size, and its place in the brief. Honest logging
  substitutes for acting on what was logged.
- **Detection rule:** does `python -m argus status` list this thesis under
  "latest evidence UNDERCUTS them"? Does the undercutting evidence satisfy the
  thesis's own `kill` field as written?
- **Prescription:** stage down, or close with a post-mortem. Argue explicitly
  why the evidence does not meet the kill criteria, in the output, or act on
  it. Continuing to publish the thesis at its old size without doing either is
  the failure.

### EP-000f: Differentiated probability with no benchmark
- **First observed:** 2026-09-17 (seeded prior, at the point market_prob was
  added to the ledger)
- **Hits:** 0
- **Failure class:** bad model
- **Pattern:** a probability is published as though it carries edge, on a
  question a liquid market already prices, without checking or recording that
  price. The claim to edge is then unfalsifiable: nothing afterwards can show
  whether ARGUS beat the crowd or merely restated it with more words.
- **Detection rule:** does the call carry `--market-prob`? If not, has the
  output stated explicitly that no market prices this question, and named where
  it looked? Is `python -m argus.ledger score`'s head-to-head verdict "edge"?
- **Prescription:** search Polymarket and Kalshi
  (`argus/sources/prediction_markets.py`) before logging; record the price;
  state the disagreement in points and the mechanism that justifies it. Under
  five points of disagreement is agreement with the crowd, and should be
  published as such. No edge over the market is a valid finding.

---

## Observed patterns

*(None yet — the ledger was seeded 2026-08-21; first resolutions land from
late September 2026. Until real autopsies exist, the seeded priors above are
the only standing checks.)*
