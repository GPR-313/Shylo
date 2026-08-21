"""
ARGUS prediction ledger.

Append-only JSONL. Every prediction is a line; every resolution and revision is
another line. Nothing is ever mutated in place, so `git log` becomes the
tamper-evident record of what ARGUS believed and when. Prime Directive #4
("every thesis ships with kill criteria") is enforced mechanically here: a
prediction that cannot be adjudicated by a stranger is rejected at write time.

CLI:
    python -m argus.ledger add --claim "..." --prob 0.65 --by 2026-12-31 \
        --criteria "..." --domain equities
    python -m argus.ledger resolve <id> --outcome true --note "..."
    python -m argus.ledger list [--open|--resolved] [--domain X]
    python -m argus.ledger score [--domain X]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent

# Anchored to the repo, not the cwd, so `python -m argus.ledger` grades the same
# ledger from a subdirectory, a cron job, or a CI runner.
LEDGER_PATH = Path(
    os.getenv("ARGUS_LEDGER_PATH", REPO_ROOT / "data" / "ledger" / "predictions.jsonl")
)

# Union of the vocabulary this repo has used. `policy` and `politics` mean the
# same thing, as do `other` and `meta`; both spellings stay accepted so no
# already-logged prediction becomes unreadable. Prefer `policy` and `other` --
# that is what the seeded ledger uses.
DOMAINS = {
    "equities", "macro", "crypto", "tokenization", "social", "culture",
    "policy", "politics", "tech", "science", "geopolitics", "demographics",
    "other", "meta",
}

# Outcomes. `unresolvable` is not a cop-out: it is how a mistaken or
# ill-posed entry leaves the open queue without being deleted (CLAUDE.md,
# Ledger Contract rule 2). It is excluded from scoring rather than graded.
UNRESOLVABLE = "unresolvable"

# --------------------------------------------------------------------------
# Validation: the falsifiability gate
# --------------------------------------------------------------------------

# Words that signal a criterion is a vibe rather than an adjudicable test.
_WEASEL = re.compile(
    r"\b(soon|likely|probably|significant(ly)?|substantial(ly)?|meaningful(ly)?|"
    r"strong(ly)?|weak(ly)?|better|worse|improve|deteriorate|a lot|somewhat|"
    r"materially|notably|considerably)\b",
    re.IGNORECASE,
)

# A resolvable criterion almost always contains a number, a date, a comparison,
# or a named binary event. This is a heuristic, not a proof -- but it catches
# the common failure of writing "criteria" that restate the claim.
_ADJUDICABLE = re.compile(
    r"(\d|>=|<=|>|<|=|%|\$|announce|file|filing|report|publish|approve|reject|"
    r"vote|pass|settle|launch|resolve|close above|close below|exceed|fall below)",
    re.IGNORECASE,
)


class ValidationError(ValueError):
    """Raised when a prediction fails the falsifiability gate."""


def _validate(p: "Prediction") -> None:
    errs: list[str] = []

    if not 0.0 < p.probability < 1.0:
        errs.append(
            f"probability must be strictly between 0 and 1 (got {p.probability}); "
            "0 and 1 are not forecasts, they are assertions"
        )

    if not p.claim or len(p.claim.strip()) < 15:
        errs.append("claim is missing or too short to be a real forecast")

    try:
        resolve_by = date.fromisoformat(p.resolve_by)
    except (ValueError, TypeError):
        errs.append(f"resolve_by must be an ISO date (YYYY-MM-DD), got {p.resolve_by!r}")
    else:
        if resolve_by <= date.today():
            errs.append(f"resolve_by {p.resolve_by} is not in the future")

    crit = (p.resolution_criteria or "").strip()
    if len(crit) < 25:
        errs.append(
            "resolution_criteria is missing or too vague -- write the test a "
            "stranger would run to grade this without asking you a question"
        )
    else:
        if not _ADJUDICABLE.search(crit):
            errs.append(
                "resolution_criteria contains no number, threshold, or named "
                "event -- it is not adjudicable as written"
            )
        weasels = sorted({m.group(0).lower() for m in _WEASEL.finditer(crit)})
        if weasels:
            errs.append(
                f"resolution_criteria contains unadjudicable language {weasels}; "
                "replace with a threshold, a source, and a date"
            )

    if p.domain not in DOMAINS:
        errs.append(f"domain {p.domain!r} not in {sorted(DOMAINS)}")

    if not (p.reasoning or "").strip():
        errs.append(
            "reasoning snapshot is required -- post-mortems need to know what "
            "you believed at write time, not what you remember believing"
        )

    if errs:
        raise ValidationError(
            "prediction rejected:\n  - " + "\n  - ".join(errs)
        )


# --------------------------------------------------------------------------
# Records
# --------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Prediction:
    claim: str
    probability: float
    resolve_by: str            # ISO date
    resolution_criteria: str
    domain: str
    reasoning: str
    kill_criteria: str = ""    # what would falsify the parent thesis
    thesis: str = ""           # free-text thesis tag, groups related calls
    tickers: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: str = field(default_factory=_now)
    kind: str = "prediction"

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


@dataclass
class Resolution:
    prediction_id: str
    outcome: bool | str        # True | False | "unresolvable"
    note: str = ""
    resolved_at: str = field(default_factory=_now)
    kind: str = "resolution"

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


# --------------------------------------------------------------------------
# Storage
# --------------------------------------------------------------------------


def _append(record: Prediction | Resolution, path: Path = LEDGER_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(record.to_json() + "\n")


def read_all(path: Path = LEDGER_PATH) -> Iterator[dict[str, Any]]:
    if not path.exists():
        return
    with path.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"warn: bad JSON at line {lineno}: {exc}", file=sys.stderr)


def record_kind(rec: dict[str, Any]) -> str | None:
    """Discriminator, tolerant of the pre-0.2 schema.

    Records written by the retired `scripts/ledger.py` used `type`; records
    written by this module use `kind`. Reading both is what keeps the twenty
    seeded predictions from silently vanishing at the schema change.
    """
    return rec.get("kind") or rec.get("type")


def coerce_outcome(value: Any) -> bool | str | None:
    """Normalise every outcome spelling the ledger has ever used to True/False/
    "unresolvable". Unrecognised values pass through for `audit` to flag."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        low = value.strip().lower()
        if low in {"yes", "true", "y", "1", "hit"}:
            return True
        if low in {"no", "false", "n", "0", "miss"}:
            return False
        if low == UNRESOLVABLE:
            return UNRESOLVABLE
    return value


def normalize(rec: dict[str, Any]) -> dict[str, Any]:
    """Map a legacy record onto the current field names. Lossless: legacy keys
    are kept alongside the canonical ones."""
    out = dict(rec)
    kind = record_kind(rec)
    out["kind"] = kind
    if kind == "prediction":
        # Legacy called the reasoning snapshot `thesis`; `thesis` is now a
        # grouping tag, so copy it across only when reasoning is absent.
        out.setdefault("reasoning", "")
        if not out["reasoning"]:
            out["reasoning"] = rec.get("thesis", "")
        out.setdefault("created_at", rec.get("logged_at", ""))
        out.setdefault("kill_criteria", "")
        out.setdefault("tickers", [])
        out.setdefault("sources", [])
    elif kind == "resolution":
        # Legacy keyed the resolution by `id` and spelled the note `notes`.
        out["prediction_id"] = rec.get("prediction_id") or rec.get("id")
        out["outcome"] = coerce_outcome(rec.get("outcome"))
        out.setdefault("note", rec.get("notes", ""))
    return out


def is_graded(outcome: Any) -> bool:
    """True only for outcomes that carry a Brier score. `unresolvable` does not."""
    return isinstance(outcome, bool)


def load_state(path: Path = LEDGER_PATH) -> dict[str, dict[str, Any]]:
    """Fold the append-only log into current state, keyed by prediction id."""
    preds: dict[str, dict[str, Any]] = {}
    for raw in read_all(path):
        rec = normalize(raw)
        if rec["kind"] == "prediction":
            preds[rec["id"]] = {**rec, "outcome": None, "resolved_at": None, "note": ""}
        elif rec["kind"] == "resolution":
            pid = rec.get("prediction_id")
            if pid in preds:
                preds[pid].update(
                    outcome=rec["outcome"],
                    resolved_at=rec.get("resolved_at"),
                    note=rec.get("note", ""),
                )
            else:
                print(f"warn: resolution for unknown id {pid}", file=sys.stderr)
    return preds


def add(**kwargs: Any) -> Prediction:
    p = Prediction(**kwargs)
    _validate(p)
    _append(p)
    return p


def resolve(prediction_id: str, outcome: bool | str, note: str = "") -> Resolution:
    if not (isinstance(outcome, bool) or outcome == UNRESOLVABLE):
        raise ValueError(f"outcome must be True, False, or {UNRESOLVABLE!r}")
    state = load_state()
    if prediction_id not in state:
        raise KeyError(f"no prediction with id {prediction_id}")
    if state[prediction_id]["outcome"] is not None:
        raise ValueError(
            f"{prediction_id} already resolved -- append a post-mortem note "
            "instead of re-resolving"
        )
    r = Resolution(prediction_id=prediction_id, outcome=outcome, note=note)
    _append(r)
    return r


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------


def brier(probability: float, outcome: bool) -> float:
    """Brier score for a single binary forecast. Lower is better; 0 is perfect.

    0.25 is the score of always saying 50%. Anything above that is worse than
    admitting you have no idea, which is a useful humiliation to keep visible.
    """
    return (probability - (1.0 if outcome else 0.0)) ** 2


def score(domain: str | None = None, path: Path = LEDGER_PATH) -> dict[str, Any]:
    resolved = [
        p for p in load_state(path).values()
        if is_graded(p["outcome"]) and (domain is None or p["domain"] == domain)
    ]
    if not resolved:
        return {"n": 0}

    scores = [brier(p["probability"], p["outcome"]) for p in resolved]
    mean_brier = sum(scores) / len(scores)
    base_rate = sum(1 for p in resolved if p["outcome"]) / len(resolved)
    # Brier score of always predicting the base rate -- the benchmark to beat.
    reference = base_rate * (1 - base_rate)
    skill = (1 - mean_brier / reference) if reference > 0 else float("nan")

    by_domain: dict[str, list[float]] = {}
    for p, s in zip(resolved, scores):
        by_domain.setdefault(p["domain"], []).append(s)

    # ADR 0001 makes the unresolvable rate the audit metric on the
    # falsifiability gate: a rising count means calls are being written
    # unadjudicably, not that the world got harder.
    ungraded = sum(
        1 for q in load_state(path).values()
        if q["outcome"] == UNRESOLVABLE and (domain is None or q["domain"] == domain)
    )

    return {
        "n": len(resolved),
        "unresolvable": ungraded,
        "brier": round(mean_brier, 4),
        "base_rate": round(base_rate, 4),
        "reference_brier": round(reference, 4),
        "skill_score": round(skill, 4) if skill == skill else None,
        "by_domain": {
            d: {"n": len(v), "brier": round(sum(v) / len(v), 4)}
            for d, v in sorted(by_domain.items())
        },
    }


def calibration(bins: int = 5, path: Path = LEDGER_PATH) -> list[dict[str, Any]]:
    """Bucket forecasts by stated probability and compare to observed frequency.

    The gap between `stated` and `observed` is where the agent is fooling itself.
    """
    resolved = [p for p in load_state(path).values() if is_graded(p["outcome"])]
    out = []
    for i in range(bins):
        lo, hi = i / bins, (i + 1) / bins
        group = [
            p for p in resolved
            if lo <= p["probability"] < hi or (i == bins - 1 and p["probability"] == hi)
        ]
        if not group:
            continue
        out.append({
            "bucket": f"{lo:.0%}-{hi:.0%}",
            "n": len(group),
            "stated": round(sum(p["probability"] for p in group) / len(group), 3),
            "observed": round(sum(1 for p in group if p["outcome"]) / len(group), 3),
        })
    return out


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _cmd_add(args: argparse.Namespace) -> int:
    try:
        p = add(
            claim=args.claim,
            probability=args.prob,
            resolve_by=args.by,
            resolution_criteria=args.criteria,
            domain=args.domain,
            reasoning=args.reasoning,
            kill_criteria=args.kill or "",
            thesis=args.thesis or "",
            tickers=args.tickers.split(",") if args.tickers else [],
            sources=args.sources.split(",") if args.sources else [],
        )
    except ValidationError as exc:
        print(f"REJECTED. {exc}", file=sys.stderr)
        return 1
    print(f"logged {p.id}  P={p.probability:.0%} by {p.resolve_by}  [{p.domain}]")
    return 0


def _cmd_resolve(args: argparse.Namespace) -> int:
    outcome = coerce_outcome(args.outcome)
    note = (args.note or "").strip()
    if len(note) < 10:
        print(
            "REJECTED. --note must say how this was adjudicated (source + what "
            "happened); resolutions are final and the post-mortem needs it.",
            file=sys.stderr,
        )
        return 1
    try:
        resolve(args.id, outcome, note)
    except (KeyError, ValueError) as exc:
        print(f"REJECTED. {exc}", file=sys.stderr)
        return 1

    if not is_graded(outcome):
        print(f"resolved {args.id} -> {UNRESOLVABLE} (not scored)")
        print("  counted against the falsifiability gate in `score`; the weekly")
        print("  self-review audits this rate -- see docs/decisions/0001.")
        return 0

    state = load_state()[args.id]
    b = brier(state["probability"], outcome)
    verdict = "well-calibrated" if b < 0.25 else "worse than a coin flip"
    print(f"resolved {args.id} -> {outcome}  brier={b:.3f} ({verdict})")
    if b >= 0.25:
        print("  write the post-mortem: bad data, bad model, bad timing, or unknowable?")
        print("  novel failure modes belong in docs/error-patterns.md")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    rows = sorted(load_state().values(), key=lambda p: p["resolve_by"])
    if args.open:
        rows = [p for p in rows if p["outcome"] is None]
    if args.resolved:
        rows = [p for p in rows if p["outcome"] is not None]
    if args.domain:
        rows = [p for p in rows if p["domain"] == args.domain]
    if not rows:
        print("(empty)")
        return 0
    for p in rows:
        if p["outcome"] is None:
            status = "OPEN "
        elif not is_graded(p["outcome"]):
            status = "N/A  "
        else:
            status = "HIT  " if p["outcome"] else "MISS "
        overdue = (
            " OVERDUE" if p["outcome"] is None
            and date.fromisoformat(p["resolve_by"]) < date.today() else ""
        )
        print(
            f"{status} {p['id']}  P={p['probability']:.0%}  by {p['resolve_by']}"
            f"  [{p['domain']}]{overdue}\n       {p['claim'][:96]}"
        )
    return 0


def _cmd_score(args: argparse.Namespace) -> int:
    s = score(args.domain)
    if s["n"] == 0:
        print("no resolved predictions yet -- nothing to grade")
        state = load_state()
        opens = sum(1 for p in state.values() if p["outcome"] is None)
        if opens:
            nxt = min(
                (p["resolve_by"] for p in state.values() if p["outcome"] is None),
                default=None,
            )
            print(f"  {opens} open, {len(state)} logged; first resolves {nxt}")
        return 0
    print(json.dumps(s, indent=2))
    print("\ncalibration:")
    for row in calibration():
        drift = row["observed"] - row["stated"]
        flag = "  <-- overconfident" if drift < -0.15 else ("  <-- underconfident" if drift > 0.15 else "")
        print(
            f"  {row['bucket']:>9}  n={row['n']:<3} stated={row['stated']:.0%} "
            f"observed={row['observed']:.0%}{flag}"
        )
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    state = load_state()
    p = state.get(args.id)
    if p is None:
        print(f"no prediction with id {args.id}", file=sys.stderr)
        return 1
    print(json.dumps(p, indent=2, ensure_ascii=False))
    return 0


def _cmd_audit(args: argparse.Namespace) -> int:
    """Integrity check. The ledger is hand-edit-forbidden, so this is how a
    hand edit gets caught."""
    required = ("id", "claim", "probability", "resolve_by",
                "resolution_criteria", "domain")
    seen: set[str] = set()
    problems: list[str] = []
    n = 0

    for i, raw in enumerate(read_all(LEDGER_PATH), 1):
        n += 1
        rec = normalize(raw)
        kind = rec["kind"]
        if kind == "prediction":
            missing = [k for k in required if not rec.get(k)]
            if missing:
                problems.append(f"record {i}: prediction missing {missing}")
            if not (rec.get("reasoning") or "").strip():
                problems.append(f"record {i}: prediction has no reasoning snapshot")
            if rec.get("id") in seen:
                problems.append(f"record {i}: duplicate prediction id {rec.get('id')!r}")
            else:
                seen.add(rec.get("id"))
            if rec.get("domain") not in DOMAINS:
                problems.append(f"record {i}: unknown domain {rec.get('domain')!r}")
            prob = rec.get("probability")
            if not isinstance(prob, (int, float)) or not 0.0 < float(prob) < 1.0:
                problems.append(f"record {i}: probability {prob!r} not strictly in (0,1)")
        elif kind == "resolution":
            pid = rec.get("prediction_id")
            if pid not in seen:
                problems.append(f"record {i}: resolution for unknown id {pid!r}")
            out = rec.get("outcome")
            if not (isinstance(out, bool) or out == UNRESOLVABLE):
                problems.append(f"record {i}: bad outcome {raw.get('outcome')!r}")
        else:
            problems.append(f"record {i}: unknown record kind {kind!r}")

    if problems:
        print(f"AUDIT FAILED ({len(problems)} problem(s)):")
        for prob in problems:
            print(f"  - {prob}")
        return 1
    print(f"AUDIT OK: {n} records, {len(seen)} predictions, ledger is consistent")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="argus.ledger", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="log a new prediction")
    a.add_argument("--claim", required=True)
    a.add_argument("--prob", type=float, required=True, help="0 < p < 1")
    a.add_argument("--by", required=True, help="resolve-by date, YYYY-MM-DD")
    a.add_argument("--criteria", required=True, help="how a stranger grades this")
    a.add_argument("--domain", required=True, choices=sorted(DOMAINS))
    a.add_argument("--reasoning", required=True, help="why you believe this, now")
    a.add_argument("--kill", help="what would falsify the parent thesis")
    a.add_argument("--thesis")
    a.add_argument("--tickers", help="comma-separated")
    a.add_argument("--sources", help="comma-separated")
    a.set_defaults(func=_cmd_add)

    r = sub.add_parser("resolve", help="grade a prediction")
    r.add_argument("id")
    r.add_argument(
        "--outcome", required=True,
        choices=["true", "false", "yes", "no", UNRESOLVABLE],
        help="true/false grade the call; unresolvable retires it unscored",
    )
    r.add_argument("--note", required=True,
                   help="how it was adjudicated -- source and what happened")
    r.set_defaults(func=_cmd_resolve)

    l = sub.add_parser("list", help="show the ledger")
    l.add_argument("--open", action="store_true")
    l.add_argument("--resolved", action="store_true")
    l.add_argument("--domain", choices=sorted(DOMAINS))
    l.set_defaults(func=_cmd_list)

    s = sub.add_parser("score", help="Brier score and calibration")
    s.add_argument("--domain", choices=sorted(DOMAINS))
    s.set_defaults(func=_cmd_score)

    sh = sub.add_parser("show", help="dump one prediction in full")
    sh.add_argument("id")
    sh.set_defaults(func=_cmd_show)

    au = sub.add_parser("audit", help="integrity-check the ledger file")
    au.set_defaults(func=_cmd_audit)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
