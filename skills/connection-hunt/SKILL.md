---
name: connection-hunt
description: The cross-domain propagation search, run deliberately instead of hoped for. Pairs domains, traces a signal in one into a forced consequence in another, and converts the survivors into falsifiable calls. Use weekly, whenever a brief fails the impress test, or whenever the answer to "what am I missing?" is a shrug.
---

# Connection Hunt

ARGUS's stated differentiator is finding connections nobody else is drawing.
That was, for a long time, a hope: the agent would notice something clever, or
it wouldn't, and there was no procedure either way.

This is the procedure. It runs in two halves — the graph tells you where
connections **already exist in your own book** and are under-exploited; then a
deliberate domain sweep looks for the ones that aren't there yet.

Read `CLAUDE.md` first if you haven't this session.

## Part 1 — Mine the graph you already have

```bash
python -m argus.graph report
```

Four reads, in order of how often they pay:

**Bridges.** Nodes whose neighbourhood spans two or more domains. Each one is a
propagation path you have already half-drawn without following it through. For
each bridge, ask the only question that matters: *does a move in one domain
force a move in the other, and is that forcing already priced?* If yes and yes,
there is no trade. If yes and no, that is the brief.

**Cut points.** Articulation points — remove the node and the book splits. A
*catalyst* appearing here means one dated event decides several apparently
separate positions. That is a risk finding and often also an idea: whatever
sits on the other side of that event is the most leveraged expression of it.

**Concentration.** Catalysts carrying more than one position. Risk first — size
the group as one bet — but read it the other way too: if three theses converge
on one event, you have a conviction you have not stated explicitly, and stating
it may be the sharper thesis.

**Orphans.** Specifically `memory_ideas_never_converted`: entries tagged
`#idea` or `#watch` that never became a thesis. These are your own past
insights, already researched, sitting unused. Cheapest edge in the repo.

## Part 2 — The deliberate domain sweep

Pick **two domains you have not paired this month.** Do not pick the pair you
find interesting — pick the pair you have been avoiding, because the interesting
pairs are the ones already priced.

The ten domains: `equities` `macro` `crypto` `tokenization` `social` `culture`
`policy` `tech` `science` `geopolitics` `demographics`.

For the pair, pull one live, dated, primary-source signal from each side:

| Domain | Where to pull from | What counts as a signal |
|---|---|---|
| macro | `Fred.plumbing_snapshot()`, `TreasuryFiscal` | a level crossing a threshold, an issuance shift |
| policy | `FederalRegister.dated_deadlines()`, `Congress.bill_actions()` | a comment deadline, a committee action |
| geopolitics | `FederalRegister.export_controls()` | an entity listing, a rule tightening |
| science | `ClinicalTrials.upcoming_readouts()`, `OpenAlex.velocity()` | a dated readout, a publication z-score |
| social | `Gdelt.velocity()`, `WikipediaPageviews.velocity()`, `ApeWisdom.movers()` | an attention inflection |
| tokenization | `DefiLlama`, `RwaXyz` | a supply or category-share inflection |
| equities | `EdgarDailyIndex.insider_clusters()`, `.activist_stakes()` | cluster filings, a fresh 13D |
| tech / culture | connectors, plus the above | capex guides, launch dates, release calendars |

Then trace, out loud, in this shape:

> Signal in domain A (dated, sourced)
> → forces mechanism M (say *why*, not *that*)
> → which binds constraint C (who owns it?)
> → which reprices instrument D (is it listed? liquid? pure-play?)
> → observable first at leading indicator L, before the repricing.

**L is the whole point.** A propagation chain with no observable ahead of the
repricing is a story you can tell afterwards, not a trade you can take
beforehand. If you cannot name L, the chain fails and you move on.

## Part 3 — Kill most of them

Four filters. A chain must survive all four. Expect most to die here; that is
the filter working, not a bad session.

1. **Mechanism, not correlation.** Can you state what forces what, and would
   you notice if it ran backwards?
2. **Not already priced.** Where a market prices any link in the chain, quote
   it. Under five points of disagreement is agreement — there is no edge and
   saying so is the honest output (EP-000f).
3. **Attention is not adoption.** If the only evidence is a velocity z-score,
   the chain is unconfirmed. Require a fundamental series — revenue, units,
   capacity, filings — before it sizes anything (EP-000a).
4. **Expressible.** Name the instrument. "Long the theme" is not a position. If
   the pure-play is private or illiquid, say so — a real constraint honestly
   stated beats a listed proxy that does not actually capture the rent.

## Part 4 — Convert or discard, explicitly

For each survivor, run `skills/thesis-forge/SKILL.md` end to end.

For each casualty, say why it died in one line. The discards are the more
valuable half of the output over time: they are what stops the same dead chain
being rediscovered every quarter, and they are the raw material for new entries
in `docs/error-patterns.md`.

Capture both to memory (`argus-capture`), tagged `#idea`, with the domain pair
in the entry so the next hunt knows which pairs are already worked.

## Output

Append to the day's brief, or write standalone to `data/briefs/`:

```markdown
## Connection hunt — YYYY-MM-DD

**Graph reading:** <bridges / cut points / concentration worth acting on, or
"nothing new" — which is a legitimate finding on a small book>

**Domains paired:** A x B  *(last paired: DATE, or never)*

**Chains traced:** N. Survived: M.

### <surviving chain>
Signal (dated, sourced) -> mechanism -> constraint -> instrument -> leading indicator L
- Market price on the nearest priced link: X% (source), vs ARGUS at Y%
- Falsifiable call: <ledger id>
- Counter-case: <the strongest argument against>

### Discarded
- <chain>: died at filter N because ...

**Ideas resurrected from memory:** <M-ids converted, or none>
```

## The standard

One defensible connection beats six speculative ones. A hunt that finds nothing
and says so honestly is a successful hunt; a hunt that manufactures a chain to
avoid an empty output has poisoned the graph, the ledger, and eventually the
sizing. Restating consensus is failure — but so is inventing non-consensus.
