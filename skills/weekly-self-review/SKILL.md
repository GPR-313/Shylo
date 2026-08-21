---
name: weekly-self-review
description: Run the ARGUS weekly self-review — resolve due predictions, score calibration, autopsy every miss into the error-pattern library, and propose one concrete process upgrade. The mechanism behind "never be satisfied."
---

# Weekly Self-Review

The improvement loop's heartbeat. Runs weekly (suggested: Sunday), and
immediately after any thesis hits its kill criteria.

## Procedure

### 1. Resolve everything that's due

```bash
python3 scripts/ledger.py list --status overdue
```

For each overdue prediction: research the actual outcome against the
prediction's own `resolution_criteria` (fetch the named source — do not
adjudicate from memory), then:

```bash
python3 scripts/ledger.py resolve <id> --outcome yes|no|unresolvable \
    --notes "<source consulted + what happened>"
```

`unresolvable` is for genuinely unadjudicable outcomes (source vanished,
event redefined) — not for calls you'd rather not grade. Also resolve early
any open prediction whose outcome is already locked in.

### 2. Score

```bash
python3 scripts/ledger.py score
python3 scripts/calibration.py
```

Note overall Brier, best/worst domain, and calibration-curve shape. Compare
against last week's memo: **a flat or worsening curve two weeks running is an
emergency** — escalate it to the top of the memo and propose a structural fix,
not a tweak.

### 3. Autopsy every miss

For each prediction resolved `no` that carried P > 0.5 (and each `yes` that
carried P < 0.5 — misses in both directions), classify the failure:

- **Bad data** — the input was wrong or stale at logging time.
- **Bad model** — the causal story was wrong; the world worked differently.
- **Bad timing** — right direction, wrong resolve-by window.
- **Unknowable** — no better version of me sees this coming (use sparingly;
  this is the excuse bucket, and it's audited).

Then ask the harder question: *what would a better version of me have seen at
logging time?* Name the observable signal that was available and ignored.

### 4. Feed the error-pattern library

Append findings to `docs/error-patterns.md` using its entry format. If a
pattern recurs (2+ hits), promote it: sharpen its detection rule so the
pre-publication gate in CLAUDE.md can actually catch it next time.

### 5. Propose upgrades

At least one concrete, implementable process upgrade per review — a new gate,
a data source, a sizing rule, a domain to start logging. "Keep doing what
we're doing" is not an acceptable finding. Significant changes get an ADR in
`docs/decisions/`.

### 6. Write the memo

Output: `data/reviews/YYYY-Www.md` (e.g. `2026-W34.md`):

```markdown
# Weekly Self-Review — week Www, YYYY

## Scoreboard
<resolutions this week, overall Brier trend, calibration curve summary,
best/worst domain>

## Autopsies
<per miss: what I said, what happened, failure class, what a better version
of me would have seen>

## Error-pattern updates
<entries added or promoted in docs/error-patterns.md>

## What I missed this week
<events I should have had a prediction on, but didn't — the silent misses>

## Process upgrades
<the concrete upgrade(s) proposed, and what was adopted>
```

Commit the memo, the ledger resolutions, and the error-pattern updates
together.
