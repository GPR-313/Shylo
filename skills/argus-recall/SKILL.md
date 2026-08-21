---
name: argus-recall
description: The read path out of Project Argus, the user's persistent second brain. Searches the project's accumulated memory, synthesizes an answer with memory-ID citations, and surfaces connected threads, contradictions, and stale information alongside the direct answer. Use whenever the user asks what do I know about X, what did I decide about, have I looked into, did I already research, what was my thinking on, ask Argus, check my brain / my memory / my notes — or references anything they may have captured before, even without naming Argus. Prefer this over answering from scratch whenever the question touches the user's own history, decisions, portfolio thinking, or past research.
---

# argus-recall — the read path

Memory that cannot be retrieved might as well not exist. This skill answers questions from what the brain already knows — with citations, so every claim is traceable to an entry — and does the two things raw search cannot: it notices what else in memory is *connected* to the question, and it warns when the stored answer may have gone stale.

## The Argus protocol (shared by all argus-* skills)

All memory lives in the attached Claude Project via the Projects tool — never on the local filesystem, which is discarded when the session ends.

- `argus/ARGUS.md` — the constitution: memory map, entry format, rules. Read it first, every run. It wins over this skill on any conflict.
- `argus/INDEX.md` — master index: active threads, entities & watch list, open questions, doc registry.
- `argus/core.md` — distilled durable memory: identity, standing preferences, working theses, principles.
- `argus/memory/YYYY-MM.md` — monthly journal, newest entries first.
- `argus/dossiers/<slug>.md`, `argus/sweeps/YYYY-MM.md`, `argus/archive/...` — dossiers, sweep briefs, retired material.

Entries look like `### M20260821a — Title`, carry tags, source, confidence, and an optional `review` date, and reference related entries by ID.

If `argus/ARGUS.md` or `argus/INDEX.md` is missing, the brain has not been bootstrapped (or was moved): recreate both from the protocol described in this section before proceeding, and tell the user you did.

## Procedure

1. **Sync.** `project_read` `argus/ARGUS.md`, `argus/INDEX.md`, and `argus/core.md`. Core and the index alone answer many questions ("what are my standing rules?") without any search.

2. **Search wide, then read deep.** Run `project_search` with two to four different phrasings — the entity's name, synonyms, the tag that would have been used, adjacent concepts. Search hits are snippets; read the actual docs they point into so entries are seen whole, and follow related-entry IDs one hop out. Check whether a dossier exists on the subject — it outranks scattered entries.

3. **Answer first, then annotate.** Lead with the direct answer to what was asked. Cite entry IDs inline — "You capped positions at 8% in August [M20260821b]" — and keep the distinction sharp between what memory *says* and what you are *inferring* from it. Then, briefly: connections worth knowing (related threads, a dossier that touches this), and anything adjacent the user probably wants surfaced.

4. **Freshness check.** Flag any load-bearing entry that is past its `review` date or older than its domain's shelf life — prices and positions decay in days, company facts in months, principles almost never. Say plainly: "this is from May and predates their Q2 earnings — want me to refresh it?" Offer a web check, an argus-sweep, or an argus-dossier depending on the size of the gap. For present-day facts (current prices, current officeholders, anything with a date attached), memory is a starting point, never the final word — verify with live tools before asserting.

5. **Contradiction check.** When memory disagrees with itself, or with what live tools show, surface it explicitly rather than quietly picking a side — and append it to the open questions in `argus/INDEX.md`. Contradictions are the most valuable thing this skill can find.

6. **Name the gaps.** If the brain has little or nothing, say so honestly — never improvise a memory that isn't there. Offer the fix: "Nothing in Argus on this yet. Want a dossier?"

## Judgment calls

- Recall is **read-mostly**: the only writes permitted are appending open questions to INDEX. Never edit or rewrite memory entries during recall — corrections go through argus-capture (as a dated addendum) or argus-synthesis.
- **Weight by confidence and provenance.** A high-confidence decision entry from Graham outranks a low-confidence idea captured from a random article. Read the metadata, not just the text.
- **Small questions get small answers.** "What's my position cap?" deserves one sentence and a citation, not a memory tour. Save the connections-and-caveats treatment for questions with real surface area.
- **Unattended mode**: answer from what exists, state assumptions, log gaps as open questions — never block on a clarifying question.

## Example

"What do I know about my position sizing rules?"

> Your standing rule is a hard 8% cap per position, set in August after the NVDA concentration episode [M20260821b] — it's promoted in core, so it's current policy. Related: your July note on small-cap liquidity [M20260714b] argued for smaller caps in illiquid names; the two haven't been reconciled, so I've logged that as an open question. Nothing in memory yet on rebalancing frequency — want me to research and capture a policy for that?
