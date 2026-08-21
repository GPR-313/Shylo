#!/usr/bin/env python3
"""ARGUS prediction ledger CLI.

The ledger is append-only JSONL: every line is either a "prediction" record or
a "resolution" record referencing a prediction id. This file is the ONLY
writer — the ledger must never be edited by hand (see CLAUDE.md, Ledger
Contract). Mistaken entries are resolved as `unresolvable`, never deleted.

Commands:
    add      log a new prediction (falsifiability is validated here)
    resolve  record the outcome of an open prediction
    list     tabulate predictions by status
    show     dump one prediction (and its resolution) in full
    score    Brier scores, calibration buckets, status counts
    audit    integrity-check the ledger file

Prime Directive #4 is enforced mechanically in `add`: a prediction without a
future resolve-by date and stranger-adjudicable resolution criteria is
rejected at write time. Sharpen the claim until it passes; do not bypass.
"""

import argparse
import contextlib
import json
import re
import signal
import sys
from datetime import date, datetime, timezone
from pathlib import Path

# Piping into `head` must not traceback.
with contextlib.suppress(AttributeError, ValueError):  # non-POSIX / non-main thread
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LEDGER = REPO_ROOT / "data" / "ledger" / "predictions.jsonl"

DOMAINS = [
    "equities", "macro", "crypto", "tokenization", "social", "culture",
    "policy", "tech", "science", "geopolitics", "demographics", "other",
]

OUTCOMES = ["yes", "no", "unresolvable"]

# Words that mark resolution criteria as non-adjudicable. A stranger cannot
# grade "significant" or "soon"; they can grade a number and a date.
VAGUE_WORDS = [
    "significant", "significantly", "meaningful", "meaningfully",
    "substantial", "substantially", "considerable", "considerably",
    "noticeable", "noticeably", "roughly", "approximately", "around",
    "probably", "likely", "soon", "eventually", "in the near future",
    "a lot", "many", "several", "some extent",
]
VAGUE_RE = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in VAGUE_WORDS) + r")\b", re.IGNORECASE
)

MIN_CLAIM_LEN = 15
MIN_CRITERIA_LEN = 40
MIN_THESIS_LEN = 20
PROB_MIN, PROB_MAX = 0.01, 0.99


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso_date(s: str, field: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError:
        die(f"{field} must be an ISO date (YYYY-MM-DD), got: {s!r}")


def die(msg: str) -> None:
    print(f"REJECTED: {msg}", file=sys.stderr)
    sys.exit(1)


def load_records(ledger: Path) -> list[dict]:
    if not ledger.exists():
        return []
    records = []
    with ledger.open() as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                die(f"{ledger}:{lineno} is not valid JSON ({e}). "
                    "Run `ledger.py audit` — do not hand-edit.")
    return records


def append_record(ledger: Path, record: dict) -> None:
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def merge(records: list[dict]) -> dict[str, dict]:
    """Fold prediction + resolution events into {id: merged_view}."""
    merged: dict[str, dict] = {}
    for r in records:
        if r.get("type") == "prediction":
            merged[r["id"]] = dict(r)
        elif r.get("type") == "resolution":
            merged.setdefault(r["id"], {})["resolution"] = r
    return merged


def derived_status(view: dict, today: date) -> str:
    res = view.get("resolution")
    if res:
        return f"resolved:{res['outcome']}"
    if date.fromisoformat(view["resolve_by"]) < today:
        return "overdue"
    return "open"


def slugify(text: str, max_words: int = 5) -> str:
    words = re.findall(r"[a-z0-9]+", text.lower())
    stop = {"the", "a", "an", "of", "on", "in", "at", "by", "to", "is", "its",
            "for", "and", "or", "with", "any", "least", "before", "after"}
    kept = [w for w in words if w not in stop][:max_words]
    return "-".join(kept) or "prediction"


def brier(p: float, outcome_yes: bool) -> float:
    return round((p - (1.0 if outcome_yes else 0.0)) ** 2, 4)


# ---------------------------------------------------------------- commands


def cmd_add(args: argparse.Namespace) -> None:
    claim = args.claim.strip()
    criteria = args.criteria.strip()
    thesis = args.thesis.strip()
    today = utc_now().date()

    # --- the falsifiability gate (Prime Directive #4, in code) ---
    problems = []
    if len(claim) < MIN_CLAIM_LEN:
        problems.append(f"claim is too short (<{MIN_CLAIM_LEN} chars) to be a real claim")
    if not (PROB_MIN <= args.p <= PROB_MAX):
        problems.append(
            f"probability must be in [{PROB_MIN}, {PROB_MAX}] — certainty is "
            "conviction theater, and 0/1 breaks calibration math")
    resolve_by = parse_iso_date(args.resolve_by, "--resolve-by")
    if resolve_by <= today:
        problems.append(f"resolve-by {resolve_by} is not in the future (today is {today})")
    if len(criteria) < MIN_CRITERIA_LEN:
        problems.append(
            f"resolution criteria too thin (<{MIN_CRITERIA_LEN} chars). State what a "
            "stranger would check, where, and the exact threshold")
    vague = sorted({m.group(0).lower() for m in VAGUE_RE.finditer(criteria)})
    if vague:
        problems.append(
            f"resolution criteria contain non-adjudicable words: {', '.join(vague)}. "
            "Replace with numbers, dates, and named sources")
    if args.domain not in DOMAINS:
        problems.append(f"domain must be one of: {', '.join(DOMAINS)}")
    if len(thesis) < MIN_THESIS_LEN:
        problems.append("thesis (reasoning snapshot) is required — future-you needs "
                        "to know why present-you believed this")
    if problems:
        die("prediction is not falsifiable enough to log:\n  - " + "\n  - ".join(problems))

    ledger = Path(args.ledger)
    existing = merge(load_records(ledger))
    base_id = f"{today:%Y-%m-%d}-{args.slug or slugify(claim)}"
    pid, n = base_id, 2
    while pid in existing:
        pid, n = f"{base_id}-{n}", n + 1

    record = {
        "type": "prediction",
        "id": pid,
        "logged_at": utc_now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "claim": claim,
        "probability": args.p,
        "resolve_by": resolve_by.isoformat(),
        "resolution_criteria": criteria,
        "domain": args.domain,
        "thesis": thesis,
        "status": "open",
    }
    if args.tags:
        record["tags"] = sorted(set(args.tags))
    append_record(ledger, record)
    print(f"LOGGED {pid}")
    print(f"  P(yes) = {args.p:.0%}  resolve by {resolve_by}  [{args.domain}]")
    print(f"  {claim}")


def cmd_resolve(args: argparse.Namespace) -> None:
    ledger = Path(args.ledger)
    merged = merge(load_records(ledger))
    view = merged.get(args.id)
    if view is None or "claim" not in view:
        die(f"no prediction with id {args.id!r}. Use `ledger.py list` to find ids.")
    if view.get("resolution"):
        die(f"{args.id} is already resolved "
            f"({view['resolution']['outcome']} on {view['resolution']['resolved_at']}). "
            "Resolutions are final.")
    notes = args.notes.strip()
    if len(notes) < 10:
        die("--notes must say how the outcome was adjudicated (source + what happened)")

    record = {
        "type": "resolution",
        "id": args.id,
        "resolved_at": utc_now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "outcome": args.outcome,
        "notes": notes,
    }
    if args.outcome in ("yes", "no"):
        record["brier"] = brier(view["probability"], args.outcome == "yes")
    append_record(ledger, record)
    print(f"RESOLVED {args.id} -> {args.outcome}")
    if "brier" in record:
        print(f"  P was {view['probability']:.0%}  Brier {record['brier']:.4f} "
              "(0 = perfect, 0.25 = coin-flip guessing)")


def cmd_list(args: argparse.Namespace) -> None:
    merged = merge(load_records(Path(args.ledger)))
    today = utc_now().date()
    rows = []
    for pid, view in merged.items():
        if "claim" not in view:
            continue
        status = derived_status(view, today)
        if args.status != "all":
            if args.status == "resolved" and not status.startswith("resolved"):
                continue
            if args.status in ("open", "overdue") and status != args.status:
                continue
        rows.append((view["resolve_by"], pid, status, view))
    rows.sort()
    if not rows:
        print(f"no predictions with status={args.status}")
        return
    for resolve_by, pid, status, view in rows:
        b = view.get("resolution", {}).get("brier")
        btxt = f"  brier={b:.4f}" if b is not None else ""
        print(f"{pid}")
        print(f"  [{status}] P={view['probability']:.0%} by {resolve_by} "
              f"({view['domain']}){btxt}")
        print(f"  {view['claim']}")


def cmd_show(args: argparse.Namespace) -> None:
    merged = merge(load_records(Path(args.ledger)))
    view = merged.get(args.id)
    if view is None or "claim" not in view:
        die(f"no prediction with id {args.id!r}")
    view = dict(view)
    view["status"] = derived_status(view, utc_now().date())
    print(json.dumps(view, indent=2, ensure_ascii=False))


def cmd_score(args: argparse.Namespace) -> None:
    merged = merge(load_records(Path(args.ledger)))
    today = utc_now().date()
    preds = [v for v in merged.values() if "claim" in v]
    if not preds:
        print("ledger is empty")
        return

    counts = {"open": 0, "overdue": 0, "resolved:yes": 0, "resolved:no": 0,
              "resolved:unresolvable": 0}
    scored = []  # (domain, probability, outcome_yes, brier)
    for v in preds:
        status = derived_status(v, today)
        counts[status] = counts.get(status, 0) + 1
        res = v.get("resolution")
        if res and res["outcome"] in ("yes", "no"):
            scored.append((v["domain"], v["probability"],
                           res["outcome"] == "yes", res["brier"]))

    print(f"PREDICTIONS: {len(preds)} total")
    for k in ("open", "overdue", "resolved:yes", "resolved:no", "resolved:unresolvable"):
        if counts.get(k):
            print(f"  {k:<24} {counts[k]}")
    if counts.get("overdue"):
        print("  !! overdue predictions need resolving — run the weekly self-review")

    if not scored:
        print("\nNo scoreable resolutions yet — Brier and calibration will appear "
              "once resolve-by dates start passing.")
        return

    overall = sum(s[3] for s in scored) / len(scored)
    print(f"\nBRIER (overall): {overall:.4f} on {len(scored)} resolved "
          "(0 = perfect, 0.25 = coin-flip guessing, lower is better)")

    by_domain: dict[str, list[float]] = {}
    for domain, _, _, b in scored:
        by_domain.setdefault(domain, []).append(b)
    print("BRIER by domain:")
    for domain in sorted(by_domain, key=lambda d: sum(by_domain[d]) / len(by_domain[d])):
        vals = by_domain[domain]
        print(f"  {domain:<14} {sum(vals) / len(vals):.4f}  (n={len(vals)})")

    print("CALIBRATION (predicted vs realized):")
    buckets = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)]
    for lo, hi in buckets:
        members = [(p, yes) for _, p, yes, _ in scored if lo <= p < hi]
        if not members:
            continue
        avg_p = sum(p for p, _ in members) / len(members)
        realized = sum(1 for _, yes in members if yes) / len(members)
        print(f"  {lo:.0%}-{min(hi, 1.0):.0%}: predicted {avg_p:.0%}, "
              f"realized {realized:.0%}  (n={len(members)})")


def cmd_audit(args: argparse.Namespace) -> None:
    ledger = Path(args.ledger)
    records = load_records(ledger)  # dies on unparseable lines
    seen_ids, problems = set(), []
    for i, r in enumerate(records, 1):
        rtype = r.get("type")
        if rtype == "prediction":
            missing = [k for k in ("id", "logged_at", "claim", "probability",
                                   "resolve_by", "resolution_criteria", "domain",
                                   "thesis") if k not in r]
            if missing:
                problems.append(f"record {i}: prediction missing fields {missing}")
            elif r["id"] in seen_ids:
                problems.append(f"record {i}: duplicate prediction id {r['id']!r}")
            else:
                seen_ids.add(r["id"])
        elif rtype == "resolution":
            if r.get("id") not in seen_ids:
                problems.append(f"record {i}: resolution for unknown id {r.get('id')!r}")
            if r.get("outcome") not in OUTCOMES:
                problems.append(f"record {i}: bad outcome {r.get('outcome')!r}")
        else:
            problems.append(f"record {i}: unknown type {rtype!r}")
    if problems:
        print(f"AUDIT FAILED ({len(problems)} problem(s)):")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)
    print(f"AUDIT OK: {len(records)} records, {len(seen_ids)} predictions, ledger is consistent")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER),
                        help="ledger file (default: data/ledger/predictions.jsonl)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("add", help="log a new prediction")
    p.add_argument("--claim", required=True, help="what will happen, stated plainly")
    p.add_argument("--p", "--probability", dest="p", type=float, required=True,
                   help=f"P(claim resolves yes), in [{PROB_MIN}, {PROB_MAX}]")
    p.add_argument("--resolve-by", required=True, help="ISO date the claim expires")
    p.add_argument("--criteria", required=True,
                   help="how a stranger adjudicates yes/no: source + exact threshold")
    p.add_argument("--domain", required=True, choices=DOMAINS)
    p.add_argument("--thesis", required=True,
                   help="reasoning snapshot: why present-you believes this")
    p.add_argument("--slug", help="short id suffix (default: derived from claim)")
    p.add_argument("--tags", nargs="*", help="optional free-form tags")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("resolve", help="record an outcome")
    p.add_argument("id")
    p.add_argument("--outcome", required=True, choices=OUTCOMES)
    p.add_argument("--notes", required=True,
                   help="how it was adjudicated: source + what happened")
    p.set_defaults(func=cmd_resolve)

    p = sub.add_parser("list", help="tabulate predictions")
    p.add_argument("--status", default="open",
                   choices=["open", "overdue", "resolved", "all"])
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("show", help="dump one prediction in full")
    p.add_argument("id")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("score", help="Brier + calibration summary")
    p.set_defaults(func=cmd_score)

    p = sub.add_parser("audit", help="integrity-check the ledger file")
    p.set_defaults(func=cmd_audit)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
