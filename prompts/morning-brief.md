Run the Morning Brief.

Follow `skills/morning-brief/SKILL.md` exactly. Open with `python -m argus
status` before any data pull and handle everything it lists as overdue today.
Fetch fresh data (no recall-only numbers) and flag any source you could not
reach. Read `python -m argus.graph bridges` for the mandatory non-obvious
connection. Check the prediction markets and log every new call through
`python -m argus.ledger add` with `--market-prob` BEFORE writing anything. Run
`python -m argus.graph concentration` before publishing any size. Check
`docs/error-patterns.md`. Then write `data/briefs/<today>.md` and commit the
brief together with every store change.

Apply all CLAUDE.md pre-publication gates, starting with `python -m argus
doctor`. If the impress test fails, dig deeper before shipping.
