---
name: argus-dossier
description: The investigation arm of Project Argus, the user's persistent second brain. Runs a deep, multi-source investigation — web research, plus FMP fundamentals and Bigdata.com content for financial targets — and files a durable, structured dossier in the project, cross-linked to existing memory, with explicit confidence levels and open questions. Use for deep dive, build a dossier, full workup, research X properly, look into this company / stock / person / technology / decision and save it — any time research should outlive the conversation instead of evaporating with it. Also use when argus-recall or argus-sweep finds a gap big enough to be worth closing properly.
---

# argus-dossier — investigation

A sweep glances; a dossier stares. This skill exists because real research is expensive, and research that evaporates when the conversation ends has to be paid for twice. Every dossier is written to be read cold, months later: verdict first, facts dated and sourced, reasoning separated from evidence, and an honest account of what would change the conclusion.

## The Argus protocol (shared by all argus-* skills)

All memory lives in the attached Claude Project via the Projects tool — never on the local filesystem, which is discarded when the session ends.

- `argus/ARGUS.md` — the constitution: memory map, entry format, rules. Read it first, every run. It wins over this skill on any conflict.
- `argus/INDEX.md` — master index: active threads, entities & watch list, open questions, doc registry.
- `argus/core.md` — distilled durable memory (existing theses the dossier may support or challenge).
- `argus/memory/YYYY-MM.md` — monthly journal, newest entries first.
- `argus/dossiers/<slug>.md` — where dossiers live, one per subject, slug lowercase-hyphenated.
- `argus/sweeps/YYYY-MM.md`, `argus/archive/...` — sweep briefs, retired material.

Entries look like `### M20260821a — Title`, carry tags, source, confidence, and an optional `review` date.

If `argus/ARGUS.md` or `argus/INDEX.md` is missing, the brain has not been bootstrapped (or was moved): recreate both from the protocol described in this section before proceeding, and tell the user you did.

## Procedure

1. **Sync and check prior art.** Read `argus/ARGUS.md` and `argus/INDEX.md`; `project_search` the subject. If a dossier already exists, this run is an **update**: add a dated `## Update — YYYY-MM-DD` section on top of its body and revise the verdict, keeping the old material below. Never fork a duplicate dossier on the same subject. Related memory entries found now become the "relation to memory" section later.

2. **Scope in one sentence.** "Dossier on Palantir: is the valuation defensible at current growth rates" beats "research Palantir". Attended and genuinely ambiguous: confirm the angle first. Unattended: state the assumed angle in the dossier header and proceed.

3. **Investigate from multiple angles.** Web search is mandatory for anything present-day — training knowledge is stale by definition. For companies and tickers: what the business actually does and for whom; financials from FMP (statements, quotes, key ratios) with figures dated; recent developments and management moves (news, Bigdata.com); the bull case and bear case as their strongest proponents would make them; valuation context against peers. For people, technologies, themes, or decisions: the landscape, the mechanism, the live disagreements, the options and their tradeoffs, and who is credible on the subject. Throughout: note where sources disagree instead of smoothing disagreement over — the disagreements are usually the finding.

4. **Write the dossier** to `argus/dossiers/<slug>.md`, in exactly this structure:

```
# Dossier — <Subject>
as-of: YYYY-MM-DD · confidence: high/med/low · review: YYYY-MM-DD

## Verdict
Three sentences maximum. The answer, the strength of the answer, the biggest caveat.

## Key facts
Each fact with its source and as-of date. Facts only — no interpretation here.

## Analysis
The reasoning. Bull and bear where applicable. Inference clearly labeled as inference.

## What would change my mind
The specific observations that would flip the verdict.

## Open questions
What remains unknown and would be worth finding out.

## Relation to memory
Which existing entries/theses this supports, contradicts, or extends — by ID.

## Sources
```

5. **File it.** Write one memory entry summarizing the verdict and pointing at the dossier. Update `argus/INDEX.md`: doc registry, the subject's entity line, any new open questions. If the dossier contradicts an existing thesis in core, log that as an open question — argus-synthesis reconciles core; this skill does not edit it.

6. **Deliver.** Present the verdict and the two or three most decision-relevant findings in chat, and say where the dossier lives. The dossier is the deliverable; the chat message is the trailer.

## Judgment calls

- **Set the `review` date by volatility of the subject.** An earnings-driven thesis: next earnings date. A technology landscape: a quarter. A biography: a year.
- **Confidence is per-dossier and earned.** High means multiple independent credible sources agree. One blog post is `low`, whatever it claims.
- **Financial subjects**: figures carry dates, always. Market and broker tools are read-only for research — and the constitution's rule 7 applies: the dossier informs a decision; it never instructs or places a trade.
- **Time-box honestly.** A dossier is a deep pass, not an infinite one. When diminishing returns hit, write down what was not investigated in Open questions rather than pretending completeness.

## Example triggers

"Do a deep dive on ASML and save it" · "Build me a dossier on solid-state batteries" · "Research whether I should move my LLC to Wyoming — properly, I want to keep it" · "Recall says we know nothing about my new landlord's company — fix that"
