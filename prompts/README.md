# Prompts

Invocation prompts for each workflow — the exact text a human (today) or a
scheduler (Phase 2+, e.g. a GitHub Actions cron invoking the agent) sends to
kick off a run. Keeping them versioned here means hand-triggered runs and
future automated runs execute the identical instruction, so output quality is
comparable across the transition.

| File | Workflow | Cadence |
|---|---|---|
| `morning-brief.md` | `skills/morning-brief/SKILL.md` | Daily (market days) |
| `weekly-self-review.md` | `skills/weekly-self-review/SKILL.md` | Weekly (Sunday) |

These are triggers, not instructions: the procedure itself lives in the
skill; the standing rules live in `CLAUDE.md`. Keep it that way — a prompt
that starts accumulating its own rules is a fork waiting to happen.
