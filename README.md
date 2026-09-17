# ARGUS

**An always-on trend intelligence agent that observes, comprehends, and predicts across every domain of human activity — and converts that edge into financial positioning.**

> Named for Argus Panoptes, the hundred-eyed watchman of Greek myth who never fully slept. Rename at will — the architecture doesn't care what you call it.

---

## Mission

ARGUS exists to build — and relentlessly upgrade — a working model of where the world is going, then translate that model into financial advantage. The stock market is the primary arena. Everything else is the sensor network that feeds it.

The core premise: **every domain of human activity is a leading indicator for every other domain.** A shift in religious demographics is a consumer-spending signal. A meme's velocity curve is a retail-flow signal. A preprint server is an earnings surprise eighteen months early. A defense appropriations markup is a supply-chain re-rating waiting to happen. The edge lives in connections nobody else is drawing yet — pre-consensus, cross-domain, second- and third-order.

Two mandates define this agent:

1. **See the future earlier than consensus.** Observe → Comprehend → Predict → Navigate.
2. **Never be satisfied.** Every week, ARGUS must be measurably better than the week before. Every output must aim to impress. Restating consensus is failure.

---

## Prime Directives

1. **Observe everything.** No domain is beneath attention. Markets, social platforms, pop culture, politics, tech, science, geopolitics, religion, demographics — all of it is signal-bearing.
2. **Comprehend before predicting.** A trend spotted is worthless without a causal model of *why* it's happening and *what it forces next*.
3. **Predict in probabilities, with expiration dates.** Every forecast carries a probability, a time horizon, and explicit resolution criteria. Vague vibes don't count as predictions.
4. **Benchmark against the crowd.** Where a market prices the question, ARGUS records that price and is scored against it. Beating the market is the only evidence of edge; failing to beat it is a finding, not an embarrassment.
5. **Every thesis ships with kill criteria.** ARGUS must state, in advance, what evidence would prove it wrong — and say so loudly when it happens.
6. **Convert insight into positioning, never into orders.** ARGUS recommends; the human decides and executes. No autonomous trading. Ever.
7. **Hunger is the default state.** ARGUS treats its current self as a rough draft. "Good enough" is a bug, not a state.
8. **Impress or iterate.** Each output should contain at least one insight the user could not have gotten from a headline. If it doesn't, it isn't done.

---

## The design principle: rules are code, not prose

The thing that separates this repo from a well-written prompt is that its rules are **enforced at write time by a validator, not remembered by an agent mid-task.**

You cannot log an unfalsifiable prediction. You cannot register a thesis that isn't attached to a falsifiable call. You cannot publish a position size without a computed breakeven. You cannot hand-edit the record of what you believed. Each of these is a `ValidationError`, not a paragraph.

| Discipline | The prose version | What actually enforces it |
|---|---|---|
| Falsifiability | "state resolution criteria" | `ledger add` rejects weasel words and undated claims |
| Kill criteria | "say what would prove you wrong" | `theses open` requires `--kill` |
| Causal reasoning | "a trend without a mechanism is noise" | `theses open` rejects a `--mechanism` with no causal verb |
| Beliefs stay falsifiable | "don't let a thesis outlive the evidence" | a thesis requires ≥1 live ledger prediction |
| Dates mean something | "anchor to a catalyst" (EP-000b) | `catalysts orphans` lists every unanchored call |
| Honest scoring | "no memory-holing" | append-only stores; `argus doctor` catches edits |
| Real edge | "beat the market or say so" | `ledger score` runs the head-to-head |
| Ruin is forbidden | "size speculatively" | `edge size` caps, `size_cluster` caps correlated groups |

---

## Architecture: five cortical layers

### Layer 1 — OBSERVE (Sensory Cortex)

Continuous multi-domain ingestion. Breadth is the point. Seventeen clients in `argus/sources/`, all behind one `Source` base that supplies caching, retry, rate limiting, and stale-cache fallback.

| Domain | Example Signals | Module | Why It Pays |
|---|---|---|---|
| **Equities positioning** | Market-wide Form 4 / 13D sweep, insider clusters, activist stakes | `positioning.py` | Cluster buying is observable the day it files |
| **Macro & Rates** | Fed plumbing, Treasury issuance, credit spreads, SOFR–IORB | `macro.py` | The tide that moves all boats |
| **Crypto & Tokenization** | Stablecoin supply, RWA issuance by category | `tokenization.py` | The rails being rebuilt |
| **Social & attention** | GDELT news velocity, Reddit mentions, Wikipedia pageviews | `narrative.py` | Retail flow and curiosity, in real time |
| **Politics & Policy** | Federal Register rules and deadlines, bill stage transitions | `policy.py` | Governments pick winners; front-run the pick |
| **Science** | Phase 3 readout dates, publication velocity, preprints | `science.py` | Earnings surprises before they're earnings |
| **Calibration benchmark** | Polymarket, Kalshi implied probabilities | `prediction_markets.py` | The crowd you have to beat to claim edge |

Company fundamentals and filing *contents* are deliberately **not** here — the `edgar` and FMP connectors serve those, and a second path to the same number is a way to get two answers and no way to choose (ADR 0002).

### Layer 2 — COMPREHEND (Synthesis Cortex)

- **Narrative lifecycle tracking** — every thesis carries a stage: *fringe → early adopter → acceleration → consensus → exhaustion → reversal*. Stage is a **sizing input**, not a label: `argus.edge` multiplies position size by it, so a correct thesis bought at consensus is sized like the late arrival it is.
- **Regime detection** — `argus/regime.py` classifies liquidity (SOFR–IORB, RRP), credit (HY OAS level and rate of change), and curve into a composite that discounts sizing. Every regime call states what would break it.
- **Choke-point analysis** — Theory-of-Constraints: when a trend goes mainstream, who *owns the constraint* and collects the rent? See `skills/ai-bottleneck-hunter/`.
- **Signal vs. engagement bait** — attention series (news volume, mentions, pageviews, publication counts) are explicitly labelled as attention, never as adoption. EP-000a exists to keep those apart.

### Layer 3 — CONNECT (Association Cortex)

The layer that makes cross-domain correlation a computation rather than an aspiration. `argus/graph.py` builds one graph over predictions, theses, catalysts, tickers, domains, and the memory brain, then answers four questions:

- **`concentration`** — which positions are actually *one bet*? Anything sharing a catalyst resolves together. The brain once noted by hand that five tokenization names were "one bet expressed five ways, not diversification"; this finds that shape every time, and `edge.size_cluster` sizes the group as the single bet it is.
- **`cutpoints`** — Hopcroft-Tarjan articulation points. Which single event, if it goes the other way, disconnects the most of the book?
- **`bridges`** — nodes whose neighbourhood spans two or more domains. A ticker reachable from both `macro` and `tokenization` is a propagation path someone has already half-drawn. **This is the signature move, found by structure instead of by inspiration.**
- **`orphans`** — every dangling link across all four stores: calls with no thesis, theses nothing can falsify, dates anchored to nothing, and memory ideas that were noticed and then dropped.

### Layer 4 — PREDICT (Prefrontal Cortex)

- **Probabilistic forecasts** — `P(event) = X% by DATE`, with stranger-adjudicable criteria, logged before publication.
- **The market head-to-head** — every call that a market prices stores that price. `ledger score` reports ARGUS's Brier against the market's on the overlapping subset. That number, not calibration alone, is the case for this project existing.
- **Catalyst calendar** — `data/catalysts.jsonl`: dated events that settle open questions, with what each one resolves and what depends on it.

### Layer 5 — NAVIGATE (Motor Cortex)

`argus/edge.py` turns a probability into a number:

- **Breakeven probability** next to your P. Below it there is no trade, however good the story.
- **Fractional Kelly** (quarter by default — Kelly is optimal only if your probabilities are right, and these are estimates), multiplied by lifecycle stage, then hard-capped.
- **The ruin guard** — correlated clusters scaled so their *joint* worst case respects one drawdown limit.
- Every size reports its **binding constraint**, because a size you can't explain is a size you won't hold through a drawdown.

Output is always options with conditions attached, never instructions to execute.

---

## The Drive: Continuous Improvement Loop

1. **Prediction Ledger.** Every forecast logged: claim, probability, horizon, resolution criteria, market benchmark, reasoning snapshot.
2. **Scoring.** Brier scores, calibration curves, per-domain breakdowns — and the head-to-head against prediction markets.
3. **Post-mortems.** Every miss gets an autopsy: bad data, bad model, bad timing, or unknowable? Findings feed `docs/error-patterns.md`, checked before new calls ship.
4. **Weekly self-review.** *What did I miss? What would a better version of me have seen? What blind spot cost the most?* — plus at least one concrete process upgrade.
5. **The impress test.** Non-obvious, actionable, defensible — or dig deeper.

A flat calibration curve is an emergency. So is a persistent loss in the market head-to-head.

---

## Quick start

```bash
git clone <this-repo> && cd Shylo
./scripts/setup.sh                  # venv, deps, .env, source health check
python3 -m unittest discover -s tests   # 146 tests in under a second
python3 -m argus status             # what needs attention right now
```

Nothing but the standard library is needed to run the stores, the scoring, the graph, or the sizing engine — 140 of the 146 tests pass on a bare interpreter, and the 6 that need `requests` (the source-layer parsers) skip rather than error. CI runs the suite both ways so that stays true. Keys only gate the OBSERVE layer.

### The commands

```bash
python -m argus status              # overdue calls, undercut theses, concentration, next actions
python -m argus agenda --days 45    # the dated queue
python -m argus doctor              # integrity-check all four stores

python -m argus.ledger add --claim "..." --prob 0.62 --by 2027-03-31 \
    --criteria "RWA.xyz tokenized Treasury AUM above \$50B before 2027-03-31" \
    --domain tokenization --reasoning "..." --kill "..." \
    --market-prob 0.45 --catalyst 2027-01-18-genius-act-...
python -m argus.ledger list --open  # OVERDUE flagged automatically
python -m argus.ledger score        # Brier, calibration, and the market head-to-head

python -m argus.theses open --title "..." --mechanism "..." --kill "..." \
    --domain tokenization --stage acceleration --predictions <id>
python -m argus.theses stage <id> --to consensus --evidence "..."
python -m argus.theses evidence <id> --note "..." --undercuts

python -m argus.catalysts add --title "..." --date 2026-10-31 --resolves "..." --domain X
python -m argus.catalysts orphans   # calls anchored to nothing (EP-000b)

python -m argus.edge size --prob 0.62 --win 1.8 --loss 0.6 --stage acceleration
python -m argus.edge compare --prob 0.62 --market 0.45
python -m argus.edge rank           # the live book by EV per unit of risk

python -m argus.graph report        # concentration, cut points, bridges, orphans
python -m argus.regime              # macro backdrop and what would break it
python3 scripts/calibration.py      # full markdown calibration report
python3 scripts/check_sources.py    # is every source reachable?
```

---

## Repository Layout

| Path | What lives there |
|---|---|
| `CLAUDE.md` | Standing operating instructions — the four contracts and the pre-publication gates |
| `argus/store.py` | Append-only event store: the substrate under every record type |
| `argus/ledger.py` | Predictions — `add`, `resolve`, `list`, `score`, `show`, `audit`; falsifiability enforced at write time |
| `argus/theses.py` | Thesis registry — mechanism, kill criteria, lifecycle stage, and the weld to the ledger |
| `argus/catalysts.py` | Dated catalyst calendar, and the `orphans` check that anchors resolve-by dates |
| `argus/edge.py` | EV, breakeven, fractional Kelly, stage multipliers, position and cluster caps |
| `argus/graph.py` | The relation graph — concentration, cut points, cross-domain bridges, orphans |
| `argus/regime.py` | Macro regime classifier with stated invalidation conditions |
| `argus/__main__.py` | `python -m argus status / doctor / agenda` |
| `argus/sources/` | Seventeen cached, rate-limited REST clients for the OBSERVE layer |
| `tests/` | 146 tests; the spine's regression suite, 140 of them dependency-free |
| `data/ledger/predictions.jsonl` | The prediction ledger |
| `data/theses.jsonl`, `data/catalysts.jsonl` | Thesis registry and catalyst calendar |
| `data/briefs/`, `data/reviews/` | Dated Morning Briefs and weekly self-review memos |
| `docs/error-patterns.md` | The error-pattern library — checked before new calls ship |
| `docs/decisions/` | Architecture decision records |
| `scripts/` | `calibration.py`, `check_sources.py`, `setup.sh` |
| `skills/` | Agent workflows (see below) |
| `prompts/` | Versioned invocation prompts, so hand-triggered and scheduled runs are identical |
| `argus/ARGUS.md`, `INDEX.md`, `core.md`, `memory/`, `dossiers/`, `sweeps/`, `archive/` | The memory brain (see below) |

### Skills

| Skill | Role |
|---|---|
| `thesis-forge` | Observation → mechanism → falsifiable calls → catalysts → size. The path from "interesting" to "positioned" |
| `connection-hunt` | The cross-domain propagation search, run deliberately rather than hoped for |
| `morning-brief` | Daily loop: observe, orient against the book, predict, log, publish |
| `weekly-self-review` | Resolve, score, autopsy, audit the graph, propose an upgrade |
| `ai-bottleneck-hunter` | Choke-point research in the AI buildout; files findings into the thesis registry |
| `argus-capture` / `argus-recall` / `argus-sweep` / `argus-dossier` / `argus-synthesis` | The memory brain's five-skill loop |

---

## The Memory Brain

The ledger enforces honesty about the future; the memory brain enforces continuity across sessions. Memory is plain Markdown under `argus/`, governed by `argus/ARGUS.md`, with permanent entry IDs (`M` + `YYYYMMDD` + a letter), tags, source, confidence, and review dates. Nothing is deleted; superseded material moves to `argus/archive/` with a pointer.

The two halves are now welded. A thesis carries `--memory` IDs, `argus/graph.py` parses the journals read-only and links entries into the same graph as predictions and catalysts, and `graph orphans` reports **memory ideas that were noticed and never converted into a thesis** — historically the most common place an edge goes to die.

The five `argus-*` skills in `skills/` are vendored mirrors of the account-synced copies. The synced copies are canonical; these are here so the repo is self-describing.

---

## Monetary System & Tokenization Module

ARGUS's deepest domain expertise, and the module the financial-path mission rests on.

**Baseline fluency:** Fed plumbing (reserves, RRP, QT/QE, the rate corridor, standing facilities); Treasury dynamics (issuance composition, auction demand, fiscal dominance); money creation through bank lending and where Basel/SLR binds; the dollar system (eurodollars, swap lines, de-dollarization rhetoric vs. reality); the digital-dollar landscape (stablecoins under the post-GENIUS framework, tokenized deposits, tokenized money-market funds, CBDC).

**The working assumption — tokenization reaches full adoption.** Under it: markets run 24/7/365 with atomic T+0 settlement and the settlement float evaporates; cash pays yield by default, compressing deposit franchises; everything fractionalizes; collateral becomes mobile and programmatic; and **the choke points move** — value migrates from legacy settlement toll-collectors to issuance platforms, regulated custody, on/off-ramps, oracles, compliance rails, and the venues where tokenized assets actually trade.

ARGUS tracks the adoption curve itself as a first-class prediction target. The live thesis, `tokenized-rails-outrun-economics`, is that the rails went live *ahead of the economics that justify them*: dollars rotating from non-yielding float into yield-bearing claims force the rails to get built but do not yet force revenue, because issuers are paid for integration work rather than basis points on assets. Its kill criteria and four catalysts are in the stores; `python -m argus.theses show tokenized-rails-outrun-economics` has the current state.

**The Financial Path Engine** (Phase 3): exposure audit against the tokenized-future winners/losers matrix, a ranked picks-and-shovels map, milestone-sequenced positioning, personal rails (custody, counterparty risk, where cash lives when cash yields), and standing kill criteria for the full-adoption assumption.

---

## Outputs

| Cadence | Deliverable |
|---|---|
| Daily | **Morning Brief** — overnight developments, narrative-velocity movers, catalyst countdowns, one non-obvious connection |
| Real-time | **Signal Alerts** — a stage transition, a thesis hitting kill criteria, a catalyst resolving |
| Weekly | **Synthesis Memo** — cross-domain trend map, graph audit, self-review, calibration report |
| Monthly | **Trend Dossiers** — deep dives with choke-point analysis |
| Quarterly | **Financial Path Review** — tokenization roadmap and exposure audit |
| Continuous | **The stores** — ledger, theses, catalysts, and the graph over them |

---

## Guardrails

- **Probabilistic, not prophetic.** Markets are complex adaptive systems; nothing here is certainty.
- **Human in the loop, always.** ARGUS produces research and options. It does not execute trades, move funds, or act on accounts.
- **Sizing discipline is enforced in code.** High-conviction language never overrides a position cap.
- **Not financial, legal, or tax advice.** ARGUS is a research instrument. Decisions with real money deserve independent judgment and, where appropriate, licensed professionals.

---

## Roadmap

- **Phase 0 — Prototype.** ✅ Ledger seeded, Morning Brief run end-to-end, synthesis quality proven before automation.
- **Phase 1 — Ingestion & Ledger.** ✅ Seventeen source clients; ledger with falsifiability enforced in code.
- **Phase 2 — Scoring & Self-Improvement.** ✅ Brier, calibration, market head-to-head, error-pattern library, weekly review.
- **Phase 2.5 — Connective tissue.** ✅ Thesis registry, catalyst calendar, relation graph, EV/Kelly sizing, regime classifier, 146-test suite.
- **Phase 3 — Tokenization Path Engine.** Exposure audit and milestone-triggered positioning as a standing module.
- **Phase 4 — Full Cortex.** Continuous cross-domain correlation, real-time alerting, improvement loop closed end-to-end.

---

## Configuration

Keys live in `.env` (gitignored), documented in `.env.example`. `FRED_API_KEY` and `CONGRESS_API_KEY` are free and instant; `EDGAR_IDENTITY` just needs a real email or the SEC blocks you.

Local MCP servers are declared in `.mcp.json` and picked up by Claude Code automatically — currently `edgar` (`uvx sec-edgar-mcp`), verified live at 21 tools. Hosted MCPs authenticate via OAuth and are added in claude.ai Settings → Connectors, or with `claude mcp add --transport http <name> <url>`:

| Server | URL |
|---|---|
| Blockscout | `https://mcp.blockscout.com/mcp` (free, no auth) |
| Unusual Whales | `https://unusualwhales.com/public-api/mcp` |
| Token Terminal | `https://mcp.tokenterminal.com` |
| Dune | see `dune.com/blog/dune-mcp` |

---

*ARGUS watches so you can act. It is never finished, and that's the feature.*
