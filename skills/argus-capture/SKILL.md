---
name: argus-capture
description: The write path into Project Argus, the user's persistent second brain. Files anything into permanent, indexed memory — thoughts, decisions, articles, links, emails, trade ideas, meeting takeaways, preferences, lessons learned. Classifies and tags the item, assigns a memory ID, checks for duplicates and connections, appends it to the monthly journal, and updates the master index. Use whenever the user says remember this, capture this, log this, note this, save this to Argus / to my brain / to memory / to the project, add this for later, or shares information and clearly wants it kept — even if they never say the word "Argus" or "capture". Also use at the end of any conversation where a durable decision, preference, or finding emerged and the user asks to keep it.
---

# argus-capture — the write path

A brain that cannot write reliably cannot think. This skill turns anything Graham hands over — a stray thought, a pasted article, a decision made mid-conversation — into a permanent, findable, connected memory entry in Project Argus. The value is not the storage; it is the classification, deduplication, and indexing that make the memory retrievable months later by argus-recall.

## The Argus protocol (shared by all argus-* skills)

All memory lives in the attached Claude Project via the Projects tool — never on the local filesystem, which is discarded when the session ends.

- `argus/ARGUS.md` — the constitution: memory map, entry format, rules. Read it first, every run. It wins over this skill on any conflict.
- `argus/INDEX.md` — master index: active threads, entities & watch list, open questions, doc registry. Updated after every memory write.
- `argus/core.md` — distilled durable memory. Written only by argus-synthesis; this skill flags candidates with `#core-candidate`.
- `argus/memory/YYYY-MM.md` — monthly journal, newest entries first.
- `argus/dossiers/<slug>.md`, `argus/sweeps/YYYY-MM.md`, `argus/archive/...` — dossiers, sweep briefs, retired material.

Entry format:

```
### M20260821a — Title in eight words or fewer
tags: #tag1 #tag2 | source: where it came from | confidence: high/med/low | review: 2026-11-21
One to six sentences. Reference related entries by ID.
```

IDs are `M` + `YYYYMMDD` + a per-day letter (a, b, c…) and are permanent. `review` is optional — set it for anything that decays (prices in days, company facts in months, principles almost never).

If `argus/ARGUS.md` or `argus/INDEX.md` is missing, the brain has not been bootstrapped (or was moved): recreate both from the protocol described in this section before proceeding, and tell the user you did.

## Procedure

1. **Sync.** `project_read` `argus/ARGUS.md` and `argus/INDEX.md`. Note the tag glossary, active threads, and the next entry ID hint.

2. **Understand the input.** It may be a conversational statement ("remember that I…"), pasted text, a URL (fetch it and capture the substance plus the link — not the whole article), an attached file (read it), or an email the user references (retrieve it via Gmail if connected). One message can contain several distinct memories — split them; an entry should be one idea.

3. **Classify and tag.** Decide what kind of memory it is: fact, idea, decision, preference, reference, lesson, or watch-item. Pick tags from the glossary; invent a new tag only when nothing fits, and define it in INDEX.md when you do. An item the daily sweep should track (a ticker, a theme, a situation to monitor) gets `#watch` and a line in the INDEX watch list.

4. **Dedupe and connect.** `project_search` one or two phrasings of the item before writing. If an existing entry already covers it, update that entry with a dated addendum instead of creating a near-duplicate. Either way, note related entry IDs — connections are what make this a brain rather than a pile.

5. **Draft the entry.** Next ID in today's sequence, tight title, honest source, honest confidence. Set `review` when the item can go stale. Durable identity facts, standing preferences, and stated theses ("I never let one position exceed 8%") also get `#core-candidate` so argus-synthesis can promote them.

6. **Write.** Read the current `argus/memory/YYYY-MM.md`, insert the entry at the top (below the header), and `project_write` the full doc back. Create the month's doc if it doesn't exist.

7. **Index.** Update `argus/INDEX.md`: bump the next-ID hint, touch any thread the entry advances, add entities or watch-list items, log any open question the item raises.

8. **Confirm in one line.** Report the ID and anything interesting found on the way: "Filed as M20260821c (#idea #watch) — connects to your July note on small-cap liquidity, M20260714b." If nothing connects, just the ID. No essay.

## Judgment calls

- **Compress, don't transcribe.** The entry is the distilled point plus a pointer to the source, not a mirror of the source. Six sentences is the ceiling for a reason: retrieval reads dozens of entries at once.
- **Capture the decision, not the debate.** When a conversation ends in a choice, record the choice, the one-line why, and what would reverse it.
- **Sensitive material.** Never store credentials, account numbers, or government IDs — strip them and say so. If the item is emotionally sensitive personal context the user explicitly wants remembered, store it plainly and respectfully.
- **Unattended mode** (scheduled or clearly away): never block on a clarifying question — classify with best judgment, note the assumption inside the entry, and proceed.
- Argus observes; it does not act. Capturing a trade idea never means acting on it — broker tools are read-only, always.

## Example

Input: "remember this: I'm capping any single position at 8% of the portfolio, learned that the hard way with the NVDA run-up"

Written to `argus/memory/2026-08.md`:

```
### M20260821b — Position size cap: 8% per name
tags: #decision #portfolio #lesson #core-candidate | source: Graham, stated 2026-08-21 | confidence: high
Hard cap of 8% of portfolio per single position. Motivated by concentration pain during the NVDA run-up. Standing rule until revised — argus-sweep should flag any position drifting above it.
```

Plus: INDEX next-ID hint bumped, and a watch-list note that sweeps should check position concentration. Confirmation: "Filed as M20260821b — flagged for core, and the daily sweep will now watch for positions drifting past 8%."
