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

---

## Patterns

*(None yet — the ledger was seeded 2026-08-21; first resolutions land from
late September 2026. Until real autopsies exist, the known-risk below stands
in as the only standing check.)*

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
