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

---

## Observed patterns

*(None yet — the ledger was seeded 2026-08-21; first resolutions land from
late September 2026. Until real autopsies exist, the seeded priors above are
the only standing checks.)*
