"""ARGUS catalyst calendar — dated events that actually resolve open questions.

Why this exists as data rather than prose: `docs/error-patterns.md` EP-000b
says resolve-by dates get set by convenience (year-end, quarter-end) instead of
by a catalyst that settles the question. That was a written rule nothing could
enforce. With the calendar as a store, `orphans` mechanically finds every open
prediction whose date is anchored to nothing, and the weekly review has to
answer for it.

Append-only JSONL, folded at read time, same contract as the ledger: nothing is
edited, a wrong entry is closed with an outcome and a note.

CLI:
    python -m argus.catalysts add --title "..." --date 2026-10-31 \
        --resolves "..." --domain tokenization [--predictions id1,id2] \
        [--theses slug] [--precision day|week|month|quarter] [--source "..."]
    python -m argus.catalysts list [--days 30] [--domain X] [--past] [--json]
    python -m argus.catalysts resolve <id> --what-happened "..." [--on DATE]
    python -m argus.catalysts orphans [--window 21]
    python -m argus.catalysts show <id>
    python -m argus.catalysts audit
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from . import store
from .store import ValidationError, slugify, split_csv, utc_now

CATALYSTS_PATH = Path(
    store.DATA_DIR / "catalysts.jsonl"
)

# How precisely the date is known. A Q4 guess and a scheduled FOMC date are not
# the same object, and pretending otherwise is how a thesis gets graded against
# a date nobody ever promised.
PRECISIONS = ("day", "week", "month", "quarter")

# Days of slack allowed per precision when matching a catalyst to a resolve-by
# date. A "quarter" catalyst legitimately anchors a date up to ~45 days out; a
# "day" catalyst does not.
PRECISION_SLACK = {"day": 7, "week": 14, "month": 30, "quarter": 50}

DEFAULT_ORPHAN_WINDOW = 21


@dataclass
class Catalyst:
    title: str
    date: str                    # ISO date the event is expected to land
    resolves: str                # the question this settles, in plain words
    domain: str
    precision: str = "day"
    prediction_ids: list[str] = field(default_factory=list)
    thesis_ids: list[str] = field(default_factory=list)
    source: str = ""             # where the date came from -- a date with no
                                 # source is a guess wearing a calendar entry
    id: str = ""
    created_at: str = field(default_factory=utc_now)
    kind: str = "catalyst"


@dataclass
class CatalystOutcome:
    catalyst_id: str
    what_happened: str
    occurred_on: str = ""        # ISO; blank means "as scheduled"
    resolved_at: str = field(default_factory=utc_now)
    kind: str = "catalyst_outcome"


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------


def _validate(c: Catalyst) -> None:
    from .ledger import DOMAINS

    errs: list[str] = []

    if len((c.title or "").strip()) < 8:
        errs.append("title is missing or too short to identify the event")

    try:
        date.fromisoformat(c.date)
    except (ValueError, TypeError):
        errs.append(f"date must be an ISO date (YYYY-MM-DD), got {c.date!r}")

    if c.precision not in PRECISIONS:
        errs.append(f"precision {c.precision!r} not in {list(PRECISIONS)}")

    resolves = (c.resolves or "").strip()
    if len(resolves) < 20:
        errs.append(
            "resolves is missing or too vague -- name the question this event "
            "settles. A catalyst that settles nothing is a diary entry."
        )

    if c.domain not in DOMAINS:
        errs.append(f"domain {c.domain!r} not in {sorted(DOMAINS)}")

    if errs:
        raise ValidationError("catalyst rejected:\n  - " + "\n  - ".join(errs))


# --------------------------------------------------------------------------
# Storage
# --------------------------------------------------------------------------


def _apply_outcome(entity: dict[str, Any], event: dict[str, Any]) -> None:
    entity.update(
        what_happened=event.get("what_happened", ""),
        occurred_on=event.get("occurred_on") or entity.get("date"),
        resolved_at=event.get("resolved_at"),
    )


def load_state(path: Path | None = None) -> dict[str, dict[str, Any]]:
    return store.fold(
        path or CATALYSTS_PATH,
        base_kind="catalyst",
        apply_events={"catalyst_outcome": _apply_outcome},
        initial={"what_happened": None, "occurred_on": None, "resolved_at": None},
    )


def add(**kwargs: Any) -> Catalyst:
    c = Catalyst(**kwargs)
    if not c.id:
        c.id = slugify(f"{c.date}-{c.title}")
    _validate(c)
    if c.id in load_state():
        raise ValidationError(
            f"catalyst id {c.id!r} already exists -- catalysts are not edited; "
            "log a new one and close the old with `resolve` if the date moved"
        )
    store.append_record(CATALYSTS_PATH, c)
    return c


def resolve(catalyst_id: str, what_happened: str, occurred_on: str = "") -> CatalystOutcome:
    state = load_state()
    if catalyst_id not in state:
        raise KeyError(f"no catalyst with id {catalyst_id}")
    if state[catalyst_id]["what_happened"] is not None:
        raise ValidationError(f"{catalyst_id} already has an outcome; append a new catalyst instead")
    if len((what_happened or "").strip()) < 10:
        raise ValidationError("--what-happened must say what actually occurred")
    o = CatalystOutcome(catalyst_id=catalyst_id, what_happened=what_happened,
                        occurred_on=occurred_on)
    store.append_record(CATALYSTS_PATH, o)
    return o


# --------------------------------------------------------------------------
# Queries
# --------------------------------------------------------------------------


def upcoming(days: int = 30, domain: str | None = None,
             path: Path | None = None, today: date | None = None) -> list[dict[str, Any]]:
    today = today or date.today()
    horizon = today + timedelta(days=days)
    rows = [
        c for c in load_state(path).values()
        if c["what_happened"] is None
        and today <= date.fromisoformat(c["date"]) <= horizon
        and (domain is None or c["domain"] == domain)
    ]
    return sorted(rows, key=lambda c: c["date"])


def overdue(path: Path | None = None, today: date | None = None) -> list[dict[str, Any]]:
    """Catalysts whose date has passed with no outcome logged. A calendar that
    is never closed out stops being a calendar and becomes a wish list."""
    today = today or date.today()
    rows = [
        c for c in load_state(path).values()
        if c["what_happened"] is None and date.fromisoformat(c["date"]) < today
    ]
    return sorted(rows, key=lambda c: c["date"])


def anchors_for(resolve_by: str, *, window: int = DEFAULT_ORPHAN_WINDOW,
                path: Path | None = None) -> list[dict[str, Any]]:
    """Catalysts close enough to a resolve-by date to plausibly have set it.

    Slack scales with the catalyst's own date precision, so a quarter-precision
    event anchors a wider window than a scheduled FOMC meeting does.
    """
    try:
        target = date.fromisoformat(resolve_by)
    except (ValueError, TypeError):
        return []
    out = []
    for c in load_state(path).values():
        try:
            when = date.fromisoformat(c["date"])
        except (ValueError, TypeError):
            continue
        slack = max(window, PRECISION_SLACK.get(c.get("precision", "day"), window))
        # A catalyst anchors a date it precedes or lands on, not one it follows:
        # an event after the resolve-by cannot have resolved the question.
        if -slack <= (target - when).days <= slack and when <= target + timedelta(days=slack):
            out.append(c)
    return sorted(out, key=lambda c: abs((date.fromisoformat(c["date"]) - target).days))


def orphans(window: int = DEFAULT_ORPHAN_WINDOW,
            ledger_path: Path | None = None,
            path: Path | None = None) -> list[dict[str, Any]]:
    """Open predictions whose resolve-by date is anchored to nothing.

    This is EP-000b ("horizon set by convenience") made mechanical. An entry
    here is not automatically wrong -- some questions genuinely resolve on a
    calendar boundary -- but each one owes the weekly review an answer.
    """
    from . import ledger as L

    lp = ledger_path or L.LEDGER_PATH
    out = []
    for p in L.load_state(lp).values():
        if p["outcome"] is not None:
            continue
        linked = p.get("catalyst")
        if linked and linked in load_state(path):
            continue
        near = anchors_for(p["resolve_by"], window=window, path=path)
        if near:
            continue
        out.append({
            "id": p["id"],
            "resolve_by": p["resolve_by"],
            "domain": p["domain"],
            "claim": p["claim"],
            # A date on a round boundary with no catalyst is the textbook
            # EP-000b shape; flagged separately so the worst cases sort first.
            "round_date": p["resolve_by"].endswith(("-12-31", "-03-31", "-06-30",
                                                    "-09-30", "-01-01")),
        })
    return sorted(out, key=lambda r: (not r["round_date"], r["resolve_by"]))


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _cmd_add(args: argparse.Namespace) -> int:
    try:
        c = add(
            title=args.title,
            date=args.date,
            resolves=args.resolves,
            domain=args.domain,
            precision=args.precision,
            prediction_ids=split_csv(args.predictions),
            thesis_ids=split_csv(args.theses),
            source=args.source or "",
        )
    except ValidationError as exc:
        print(f"REJECTED. {exc}", file=sys.stderr)
        return 1
    print(f"logged catalyst {c.id}  {c.date} ({c.precision})  [{c.domain}]")
    if not c.prediction_ids and not c.thesis_ids:
        print("  nothing depends on this yet -- link it with "
              "`ledger add --catalyst " + c.id + "` or it is just a date.")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    today = date.today()
    if args.past:
        rows = sorted(load_state().values(), key=lambda c: c["date"])
    else:
        rows = upcoming(days=args.days, domain=args.domain)
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return 0
    if not rows:
        print("(no catalysts in window)")
        return 0
    for c in rows:
        when = date.fromisoformat(c["date"])
        dd = (when - today).days
        state = "DONE " if c["what_happened"] is not None else (
            "LATE " if dd < 0 else f"T-{dd:<3}")
        deps = len(c["prediction_ids"]) + len(c["thesis_ids"])
        print(f"{state} {c['date']}  {c['id'][:40]:<40} [{c['domain']}] "
              f"{deps} linked\n       {c['title'][:90]}")
    return 0


def _cmd_resolve(args: argparse.Namespace) -> int:
    try:
        resolve(args.id, args.what_happened, args.on or "")
    except (KeyError, ValidationError) as exc:
        print(f"REJECTED. {exc}", file=sys.stderr)
        return 1
    print(f"closed catalyst {args.id}")
    print("  now grade every prediction it was supposed to resolve: "
          "`python -m argus.ledger list --open`")
    return 0


def _cmd_orphans(args: argparse.Namespace) -> int:
    rows = orphans(window=args.window)
    if not rows:
        print("every open prediction is anchored to a catalyst. EP-000b clear.")
        return 0
    print(f"{len(rows)} open prediction(s) with no catalyst within "
          f"+/-{args.window}d of the resolve-by date (EP-000b):\n")
    for r in rows:
        tag = "  <-- round-number date, no catalyst" if r["round_date"] else ""
        print(f"  {r['id']}  by {r['resolve_by']}  [{r['domain']}]{tag}")
        print(f"      {r['claim'][:92]}")
    print("\nFix by logging the catalyst that actually settles each question, or")
    print("by moving the resolve-by date onto one that exists.")
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    c = load_state().get(args.id)
    if c is None:
        print(f"no catalyst with id {args.id}", file=sys.stderr)
        return 1
    print(json.dumps(c, indent=2, ensure_ascii=False))
    return 0


def _cmd_audit(args: argparse.Namespace) -> int:
    from . import ledger as L

    problems: list[str] = []
    state = load_state()
    known_preds = set(L.load_state().keys())
    for cid, c in state.items():
        try:
            date.fromisoformat(c["date"])
        except (ValueError, TypeError, KeyError):
            problems.append(f"{cid}: bad or missing date {c.get('date')!r}")
        if c.get("precision") not in PRECISIONS:
            problems.append(f"{cid}: bad precision {c.get('precision')!r}")
        for pid in c.get("prediction_ids", []):
            if pid not in known_preds:
                problems.append(f"{cid}: links unknown prediction {pid!r}")
    if problems:
        print(f"AUDIT FAILED ({len(problems)} problem(s)):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"AUDIT OK: {len(state)} catalysts, all links resolve")
    return 0


def main(argv: list[str] | None = None) -> int:
    from .ledger import DOMAINS

    ap = argparse.ArgumentParser(prog="argus.catalysts", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="log a dated catalyst")
    a.add_argument("--title", required=True)
    a.add_argument("--date", required=True, help="YYYY-MM-DD")
    a.add_argument("--resolves", required=True, help="the question this settles")
    a.add_argument("--domain", required=True, choices=sorted(DOMAINS))
    a.add_argument("--precision", default="day", choices=list(PRECISIONS))
    a.add_argument("--predictions", help="comma-separated ledger ids")
    a.add_argument("--theses", help="comma-separated thesis ids")
    a.add_argument("--source", help="where the date came from")
    a.set_defaults(func=_cmd_add)

    l = sub.add_parser("list", help="the calendar")
    l.add_argument("--days", type=int, default=30)
    l.add_argument("--domain", choices=sorted(DOMAINS))
    l.add_argument("--past", action="store_true", help="include everything, dated order")
    l.add_argument("--json", action="store_true")
    l.set_defaults(func=_cmd_list)

    r = sub.add_parser("resolve", help="close a catalyst with what happened")
    r.add_argument("id")
    r.add_argument("--what-happened", dest="what_happened", required=True)
    r.add_argument("--on", help="actual date, if it moved")
    r.set_defaults(func=_cmd_resolve)

    o = sub.add_parser("orphans", help="open predictions anchored to no catalyst")
    o.add_argument("--window", type=int, default=DEFAULT_ORPHAN_WINDOW)
    o.set_defaults(func=_cmd_orphans)

    sh = sub.add_parser("show")
    sh.add_argument("id")
    sh.set_defaults(func=_cmd_show)

    au = sub.add_parser("audit", help="integrity-check the calendar")
    au.set_defaults(func=_cmd_audit)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
