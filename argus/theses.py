"""ARGUS thesis registry — the weld between the memory brain and the ledger.

Before this module the repo had two halves that did not touch. The ledger knew
what ARGUS *predicted* and whether it came true. The memory brain under
`argus/` knew what ARGUS *believed* and why. Nothing connected a belief to the
falsifiable calls that would kill it, so a thesis could quietly outlive the
evidence against it -- the exact failure the kill-criteria rule exists to
prevent.

A thesis here carries three things the registry refuses to store without:

1. **A mechanism.** Not "AI is big" -- the causal chain, stated so the next
   link is checkable. A trend without a mechanism is noise.
2. **Kill criteria.** The evidence that ends this, written before the
   evidence exists.
3. **At least one live ledger prediction.** A thesis with nothing falsifiable
   attached is a vibe with a ticker next to it, and the gate rejects it.

Lifecycle stage is first-class because stage drives sizing more than conviction
does (see `argus/edge.py`, which reads `STAGE_SIZING` from here). Every stage
change is an event with evidence attached, so the *history* of how a narrative
matured is queryable later -- that record is what post-mortems actually need.

CLI:
    python -m argus.theses open --id tokenization-collateral \
        --title "..." --mechanism "..." --kill "..." --domain tokenization \
        --stage acceleration --direction long --predictions id1,id2 \
        [--tickers BK,CPU] [--catalysts slug] [--memory M20260821c] \
        [--win 1.8 --loss 0.6]
    python -m argus.theses stage <id> --to consensus --evidence "..."
    python -m argus.theses link <id> --catalysts slug [--predictions id] [--note "..."]
    python -m argus.theses evidence <id> --note "..." [--supports|--undercuts]
    python -m argus.theses close <id> --outcome played_out|killed|abandoned --note "..."
    python -m argus.theses list [--stage X] [--domain X] [--open] [--json]
    python -m argus.theses show <id>
    python -m argus.theses orphans
    python -m argus.theses audit
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import store
from .store import ValidationError, slugify, split_csv, utc_now

THESES_PATH = Path(store.DATA_DIR / "theses.jsonl")

# The narrative lifecycle. Direction and sizing depend on where a trend sits
# far more than on how good the story is -- a correct thesis bought at
# `consensus` still loses money.
STAGES = ("fringe", "early_adopter", "acceleration", "consensus",
          "exhaustion", "reversal")

# Stage-conditioned sizing multiplier, applied to the Kelly fraction in
# `argus/edge.py`. These are priors, not measurements: they encode "pay up for
# asymmetry early, refuse to pay for consensus", and the weekly review is
# supposed to recalibrate them once enough theses have run their course.
#
#   fringe         max asymmetry, minimum evidence -- small, survivable bets
#   early_adopter  thesis is working but unproven; scale in
#   acceleration   the sweet spot: mechanism confirmed, crowd not yet arrived
#   consensus      edge is mostly priced; you are paying for other people's work
#   exhaustion     the rerate is behind you; this is where positions go to die
#   reversal       no long exposure; the trade, if any, is the other way
STAGE_SIZING = {
    "fringe": 0.25,
    "early_adopter": 0.50,
    "acceleration": 1.00,
    "consensus": 0.40,
    "exhaustion": 0.15,
    "reversal": 0.00,
}

DIRECTIONS = ("long", "short", "pair", "flat")
CLOSE_OUTCOMES = ("played_out", "killed", "abandoned", "superseded")

# A mechanism has to assert that something *causes* something else. This is a
# crude test and it is meant to be: it catches the common failure of writing a
# description where a causal chain belongs.
_CAUSAL = (
    "because", "drives", "forces", "leads to", "causes", "so that", "which means",
    "results in", "requires", "constrains", "->", "→", "therefore", "compels",
    "pushes", "squeezes", "shifts", "transfers", "reprices", "displaces",
)


@dataclass
class Thesis:
    title: str
    mechanism: str               # the causal chain, not a description
    kill: str                    # what ends this, written in advance
    domain: str
    stage: str
    direction: str = "long"
    prediction_ids: list[str] = field(default_factory=list)
    catalyst_ids: list[str] = field(default_factory=list)
    memory_ids: list[str] = field(default_factory=list)   # brain entry IDs
    tickers: list[str] = field(default_factory=list)
    # Payoff estimates per unit of exposure, for `argus.edge`. `win` is the
    # gain if the thesis plays out, `loss` the loss if the kill criteria hit.
    # Both are fractions of the position, not dollars.
    win: float | None = None
    loss: float | None = None
    id: str = ""
    created_at: str = field(default_factory=utc_now)
    kind: str = "thesis"


@dataclass
class StageChange:
    thesis_id: str
    to_stage: str
    evidence: str
    from_stage: str = ""
    changed_at: str = field(default_factory=utc_now)
    kind: str = "stage_change"


@dataclass
class Evidence:
    thesis_id: str
    note: str
    direction: str = "supports"  # supports | undercuts | neutral
    source: str = ""
    logged_at: str = field(default_factory=utc_now)
    kind: str = "evidence"


@dataclass
class ThesisLink:
    """Additive only, by design.

    Catalysts get discovered after a thesis is opened -- that is normal, and a
    thesis that cannot absorb one goes stale. But a link that can be *removed*
    would let an inconvenient dependency be quietly detached, which is the
    memory-holing this store exists to prevent. Links accumulate; a wrong one
    is answered in a `close` post-mortem, never deleted.
    """

    thesis_id: str
    catalyst_ids: list[str] = field(default_factory=list)
    prediction_ids: list[str] = field(default_factory=list)
    memory_ids: list[str] = field(default_factory=list)
    tickers: list[str] = field(default_factory=list)
    note: str = ""
    linked_at: str = field(default_factory=utc_now)
    kind: str = "thesis_link"


@dataclass
class ThesisClose:
    thesis_id: str
    outcome: str                 # played_out | killed | abandoned | superseded
    note: str
    closed_at: str = field(default_factory=utc_now)
    kind: str = "thesis_close"


# --------------------------------------------------------------------------
# Validation -- the gate that makes a thesis more than an opinion
# --------------------------------------------------------------------------


def _validate(t: Thesis, *, ledger_path: Path | None = None) -> None:
    from . import ledger as L

    errs: list[str] = []

    if len((t.title or "").strip()) < 10:
        errs.append("title is missing or too short")

    mech = (t.mechanism or "").strip()
    if len(mech) < 60:
        errs.append(
            "mechanism is missing or too short -- state the causal chain: what "
            "forces what, in what order. A trend without a mechanism is noise."
        )
    elif not any(word in mech.lower() for word in _CAUSAL):
        errs.append(
            "mechanism reads as a description, not a causal chain. Say why one "
            f"thing forces the next (e.g. {', '.join(_CAUSAL[:5])})."
        )

    if len((t.kill or "").strip()) < 25:
        errs.append(
            "kill criteria are missing or too vague -- name the observable "
            "evidence that ends this thesis, before it exists"
        )

    if t.stage not in STAGES:
        errs.append(f"stage {t.stage!r} not in {list(STAGES)}")

    if t.direction not in DIRECTIONS:
        errs.append(f"direction {t.direction!r} not in {list(DIRECTIONS)}")

    if t.domain not in L.DOMAINS:
        errs.append(f"domain {t.domain!r} not in {sorted(L.DOMAINS)}")

    # The weld. A thesis with no falsifiable call attached cannot be graded,
    # cannot be killed on schedule, and will quietly outlive its evidence.
    if not t.prediction_ids:
        errs.append(
            "no prediction_ids -- every thesis carries at least one logged, "
            "falsifiable call. Log it with `python -m argus.ledger add` first, "
            "then attach it here with --predictions."
        )
    else:
        known = L.load_state(ledger_path or L.LEDGER_PATH)
        missing = [pid for pid in t.prediction_ids if pid not in known]
        if missing:
            errs.append(f"prediction_ids not in the ledger: {missing}")

    if t.catalyst_ids:
        from . import catalysts as C
        unknown = [c for c in t.catalyst_ids if c not in C.load_state()]
        if unknown:
            errs.append(
                f"catalyst_ids not in the calendar: {unknown}. Log the catalyst "
                "first, or attach it later with `python -m argus.theses link`."
            )

    for name, value in (("win", t.win), ("loss", t.loss)):
        if value is not None and not (0 < float(value) <= 10):
            errs.append(f"{name} must be a positive fraction of the position (got {value})")
    if (t.win is None) != (t.loss is None):
        errs.append("give both --win and --loss, or neither; one alone cannot be sized")

    if errs:
        raise ValidationError("thesis rejected:\n  - " + "\n  - ".join(errs))


# --------------------------------------------------------------------------
# Storage
# --------------------------------------------------------------------------


def _apply_stage(entity: dict[str, Any], event: dict[str, Any]) -> None:
    entity.setdefault("stage_history", []).append({
        "from": event.get("from_stage") or entity.get("stage"),
        "to": event.get("to_stage"),
        "evidence": event.get("evidence", ""),
        "at": event.get("changed_at"),
    })
    entity["stage"] = event.get("to_stage", entity.get("stage"))


def _apply_evidence(entity: dict[str, Any], event: dict[str, Any]) -> None:
    entity.setdefault("evidence_log", []).append({
        "note": event.get("note", ""),
        "direction": event.get("direction", "supports"),
        "source": event.get("source", ""),
        "at": event.get("logged_at"),
    })


def _apply_link(entity: dict[str, Any], event: dict[str, Any]) -> None:
    for field_name in ("catalyst_ids", "prediction_ids", "memory_ids", "tickers"):
        added = event.get(field_name) or []
        if not added:
            continue
        current = list(entity.get(field_name) or [])
        entity[field_name] = current + [x for x in added if x not in current]
    entity.setdefault("link_log", []).append({
        "note": event.get("note", ""), "at": event.get("linked_at")})


def _apply_close(entity: dict[str, Any], event: dict[str, Any]) -> None:
    entity.update(
        closed=event.get("outcome"),
        close_note=event.get("note", ""),
        closed_at=event.get("closed_at"),
    )


def load_state(path: Path | None = None) -> dict[str, dict[str, Any]]:
    return store.fold(
        path or THESES_PATH,
        base_kind="thesis",
        apply_events={
            "stage_change": _apply_stage,
            "evidence": _apply_evidence,
            "thesis_link": _apply_link,
            "thesis_close": _apply_close,
        },
        initial={"closed": None, "close_note": "", "closed_at": None,
                 "stage_history": [], "evidence_log": [], "link_log": []},
    )


def open_thesis(**kwargs: Any) -> Thesis:
    t = Thesis(**kwargs)
    if not t.id:
        t.id = slugify(t.title)
    _validate(t)
    if t.id in load_state():
        raise ValidationError(
            f"thesis {t.id!r} already exists -- theses are not edited. Log a "
            "stage change, add evidence, or close it and open a successor."
        )
    store.append_record(THESES_PATH, t)
    return t


def set_stage(thesis_id: str, to_stage: str, evidence: str) -> StageChange:
    state = load_state()
    if thesis_id not in state:
        raise KeyError(f"no thesis with id {thesis_id}")
    if to_stage not in STAGES:
        raise ValidationError(f"stage {to_stage!r} not in {list(STAGES)}")
    if state[thesis_id]["closed"]:
        raise ValidationError(f"{thesis_id} is closed; open a successor thesis instead")
    if len((evidence or "").strip()) < 15:
        raise ValidationError(
            "--evidence must name what you observed that moved the stage; a "
            "stage change with no evidence is a mood swing"
        )
    current = state[thesis_id]["stage"]
    if current == to_stage:
        raise ValidationError(f"{thesis_id} is already at stage {to_stage!r}")
    sc = StageChange(thesis_id=thesis_id, to_stage=to_stage,
                     evidence=evidence, from_stage=current)
    store.append_record(THESES_PATH, sc)
    return sc


def add_evidence(thesis_id: str, note: str, direction: str = "supports",
                 source: str = "") -> Evidence:
    state = load_state()
    if thesis_id not in state:
        raise KeyError(f"no thesis with id {thesis_id}")
    if direction not in ("supports", "undercuts", "neutral"):
        raise ValidationError("direction must be supports, undercuts, or neutral")
    if len((note or "").strip()) < 15:
        raise ValidationError("--note must carry the observation, not just a pointer")
    e = Evidence(thesis_id=thesis_id, note=note, direction=direction, source=source)
    store.append_record(THESES_PATH, e)
    return e


def link(thesis_id: str, *, catalyst_ids: list[str] | None = None,
         prediction_ids: list[str] | None = None,
         memory_ids: list[str] | None = None,
         tickers: list[str] | None = None, note: str = "") -> ThesisLink:
    """Attach newly-discovered dependencies to an existing thesis."""
    from . import catalysts as C
    from . import ledger as L

    state = load_state()
    if thesis_id not in state:
        raise KeyError(f"no thesis with id {thesis_id}")

    catalyst_ids = catalyst_ids or []
    prediction_ids = prediction_ids or []
    if not any([catalyst_ids, prediction_ids, memory_ids, tickers]):
        raise ValidationError("nothing to link")

    # Validate at write time, not at audit time: a dangling link that is only
    # caught by a later audit has already polluted every graph query in between.
    missing_c = [c for c in catalyst_ids if c not in C.load_state()]
    missing_p = [p for p in prediction_ids if p not in L.load_state()]
    if missing_c or missing_p:
        problems = []
        if missing_c:
            problems.append(f"unknown catalysts {missing_c}")
        if missing_p:
            problems.append(f"unknown predictions {missing_p}")
        raise ValidationError("link rejected: " + "; ".join(problems))

    ln = ThesisLink(thesis_id=thesis_id, catalyst_ids=catalyst_ids,
                    prediction_ids=prediction_ids, memory_ids=memory_ids or [],
                    tickers=[t.upper() for t in (tickers or [])], note=note)
    store.append_record(THESES_PATH, ln)
    return ln


def close(thesis_id: str, outcome: str, note: str) -> ThesisClose:
    state = load_state()
    if thesis_id not in state:
        raise KeyError(f"no thesis with id {thesis_id}")
    if state[thesis_id]["closed"]:
        raise ValidationError(f"{thesis_id} is already closed")
    if outcome not in CLOSE_OUTCOMES:
        raise ValidationError(f"outcome must be one of {list(CLOSE_OUTCOMES)}")
    if len((note or "").strip()) < 20:
        raise ValidationError(
            "--note must be the post-mortem: what the mechanism got right, what "
            "it got wrong, and what you would watch earlier next time"
        )
    c = ThesisClose(thesis_id=thesis_id, outcome=outcome, note=note)
    store.append_record(THESES_PATH, c)
    return c


# --------------------------------------------------------------------------
# Queries
# --------------------------------------------------------------------------


def live(path: Path | None = None) -> list[dict[str, Any]]:
    return [t for t in load_state(path).values() if not t["closed"]]


def undercut(path: Path | None = None) -> list[dict[str, Any]]:
    """Live theses whose most recent evidence undercuts them.

    The quiet failure mode this catches: evidence against a thesis gets logged
    honestly, and then nothing happens. A thesis whose latest evidence cuts
    against it is either about to be staged down or about to be killed -- it
    should not simply sit there at its old size.
    """
    out = []
    for t in live(path):
        log = t.get("evidence_log") or []
        if log and log[-1]["direction"] == "undercuts":
            out.append(t)
    return out


def orphans(path: Path | None = None, ledger_path: Path | None = None) -> dict[str, list]:
    """Broken links in both directions -- the registry's own hygiene check."""
    from . import ledger as L

    lp = ledger_path or L.LEDGER_PATH
    preds = L.load_state(lp)
    theses = load_state(path)

    claimed: set[str] = set()
    for t in theses.values():
        claimed.update(t.get("prediction_ids", []))

    # A thesis all of whose predictions have resolved is unfalsifiable *now*:
    # nothing open can kill it, so it needs a fresh call or a close-out.
    no_live_call = [
        t["id"] for t in theses.values()
        if not t["closed"]
        and t.get("prediction_ids")
        and all(preds.get(pid, {}).get("outcome") is not None
                for pid in t["prediction_ids"])
    ]
    unattached = [
        p["id"] for p in preds.values()
        if p["outcome"] is None and p["id"] not in claimed
    ]
    return {"theses_with_no_live_call": no_live_call,
            "predictions_with_no_thesis": unattached}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _cmd_open(args: argparse.Namespace) -> int:
    try:
        t = open_thesis(
            title=args.title,
            mechanism=args.mechanism,
            kill=args.kill,
            domain=args.domain,
            stage=args.stage,
            direction=args.direction,
            prediction_ids=split_csv(args.predictions),
            catalyst_ids=split_csv(args.catalysts),
            memory_ids=split_csv(args.memory),
            tickers=split_csv(args.tickers),
            win=args.win,
            loss=args.loss,
            id=args.id or "",
        )
    except ValidationError as exc:
        print(f"REJECTED. {exc}", file=sys.stderr)
        return 1
    mult = STAGE_SIZING[t.stage]
    print(f"opened thesis {t.id}  [{t.domain}] stage={t.stage} "
          f"({mult:.0%} sizing) direction={t.direction}")
    print(f"  {len(t.prediction_ids)} prediction(s), {len(t.catalyst_ids)} catalyst(s)")
    if t.win is None:
        print("  no --win/--loss: `python -m argus.edge rank` cannot size this yet.")
    return 0


def _cmd_stage(args: argparse.Namespace) -> int:
    try:
        sc = set_stage(args.id, args.to, args.evidence)
    except (KeyError, ValidationError) as exc:
        print(f"REJECTED. {exc}", file=sys.stderr)
        return 1
    before, after = STAGE_SIZING[sc.from_stage], STAGE_SIZING[sc.to_stage]
    print(f"{args.id}: {sc.from_stage} -> {sc.to_stage}   "
          f"sizing multiplier {before:.0%} -> {after:.0%}")
    if after < before:
        print("  Size down. Re-run `python -m argus.edge rank` before any new entry.")
    return 0


def _cmd_evidence(args: argparse.Namespace) -> int:
    direction = "undercuts" if args.undercuts else ("neutral" if args.neutral else "supports")
    try:
        add_evidence(args.id, args.note, direction, args.source or "")
    except (KeyError, ValidationError) as exc:
        print(f"REJECTED. {exc}", file=sys.stderr)
        return 1
    print(f"logged {direction} evidence on {args.id}")
    if direction == "undercuts":
        print("  Does this hit the kill criteria? If yes, say so loudly and close it.")
        print(f"  `python -m argus.theses show {args.id}` to re-read them.")
    return 0


def _cmd_link(args: argparse.Namespace) -> int:
    try:
        link(args.id,
             catalyst_ids=split_csv(args.catalysts),
             prediction_ids=split_csv(args.predictions),
             memory_ids=split_csv(args.memory),
             tickers=split_csv(args.tickers),
             note=args.note or "")
    except (KeyError, ValidationError) as exc:
        print(f"REJECTED. {exc}", file=sys.stderr)
        return 1
    print(f"linked {args.id}. Re-run `python -m argus.graph concentration` -- a new "
          "shared catalyst\n  may have just turned two positions into one bet.")
    return 0


def _cmd_close(args: argparse.Namespace) -> int:
    try:
        close(args.id, args.outcome, args.note)
    except (KeyError, ValidationError) as exc:
        print(f"REJECTED. {exc}", file=sys.stderr)
        return 1
    print(f"closed {args.id} -> {args.outcome}")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    rows = list(load_state().values())
    if args.open:
        rows = [t for t in rows if not t["closed"]]
    if args.stage:
        rows = [t for t in rows if t["stage"] == args.stage]
    if args.domain:
        rows = [t for t in rows if t["domain"] == args.domain]
    rows.sort(key=lambda t: (STAGES.index(t["stage"]) if t["stage"] in STAGES else 9, t["id"]))
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return 0
    if not rows:
        print("(no theses -- `python -m argus.theses open --help`)")
        return 0
    for t in rows:
        state = f"CLOSED:{t['closed']}" if t["closed"] else t["stage"].upper()
        ev = t.get("evidence_log") or []
        against = sum(1 for e in ev if e["direction"] == "undercuts")
        flag = f"  {against} undercutting" if against else ""
        print(f"{state:<16} {t['id'][:38]:<38} [{t['domain']}] "
              f"{t['direction']} {','.join(t.get('tickers') or []) or '-'}{flag}")
        print(f"       {t['title'][:92]}")
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    t = load_state().get(args.id)
    if t is None:
        print(f"no thesis with id {args.id}", file=sys.stderr)
        return 1
    print(json.dumps(t, indent=2, ensure_ascii=False))
    return 0


def _cmd_orphans(args: argparse.Namespace) -> int:
    o = orphans()
    clean = True
    if o["theses_with_no_live_call"]:
        clean = False
        print("Theses with no OPEN prediction left -- nothing can kill these now:")
        for tid in o["theses_with_no_live_call"]:
            print(f"  {tid}")
        print("  Log a fresh call, or close the thesis with a post-mortem.\n")
    if o["predictions_with_no_thesis"]:
        clean = False
        print("Open predictions attached to no thesis -- calls with no causal model:")
        for pid in o["predictions_with_no_thesis"]:
            print(f"  {pid}")
        print("  Either attach them to a thesis or accept they are standalone bets.")
    if clean:
        print("every live thesis has a live call, and every open call has a thesis.")
    return 0


def _cmd_audit(args: argparse.Namespace) -> int:
    from . import catalysts as C
    from . import ledger as L

    problems: list[str] = []
    preds, cats = L.load_state(), C.load_state()
    for tid, t in load_state().items():
        if t["stage"] not in STAGES:
            problems.append(f"{tid}: unknown stage {t['stage']!r}")
        for pid in t.get("prediction_ids", []):
            if pid not in preds:
                problems.append(f"{tid}: unknown prediction {pid!r}")
        for cid in t.get("catalyst_ids", []):
            if cid not in cats:
                problems.append(f"{tid}: unknown catalyst {cid!r}")
    if problems:
        print(f"AUDIT FAILED ({len(problems)} problem(s)):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"AUDIT OK: {len(load_state())} theses, all links resolve")
    return 0


def main(argv: list[str] | None = None) -> int:
    from .ledger import DOMAINS

    ap = argparse.ArgumentParser(prog="argus.theses", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    o = sub.add_parser("open", help="register a thesis (needs a live prediction)")
    o.add_argument("--title", required=True)
    o.add_argument("--mechanism", required=True, help="the causal chain, not a description")
    o.add_argument("--kill", required=True, help="what ends this, written in advance")
    o.add_argument("--domain", required=True, choices=sorted(DOMAINS))
    o.add_argument("--stage", required=True, choices=list(STAGES))
    o.add_argument("--direction", default="long", choices=list(DIRECTIONS))
    o.add_argument("--predictions", required=True, help="comma-separated ledger ids")
    o.add_argument("--catalysts", help="comma-separated catalyst ids")
    o.add_argument("--memory", help="comma-separated brain entry IDs (M20260821c)")
    o.add_argument("--tickers", help="comma-separated")
    o.add_argument("--win", type=float, help="gain per unit exposure if it plays out")
    o.add_argument("--loss", type=float, help="loss per unit exposure if killed")
    o.add_argument("--id", help="explicit slug; derived from the title otherwise")
    o.set_defaults(func=_cmd_open)

    s = sub.add_parser("stage", help="move a thesis along the lifecycle")
    s.add_argument("id")
    s.add_argument("--to", required=True, choices=list(STAGES))
    s.add_argument("--evidence", required=True)
    s.set_defaults(func=_cmd_stage)

    e = sub.add_parser("evidence", help="log an observation for or against")
    e.add_argument("id")
    e.add_argument("--note", required=True)
    e.add_argument("--source")
    g = e.add_mutually_exclusive_group()
    g.add_argument("--undercuts", action="store_true")
    g.add_argument("--neutral", action="store_true")
    e.set_defaults(func=_cmd_evidence)

    ln = sub.add_parser("link", help="attach a catalyst, prediction, memory id, or ticker")
    ln.add_argument("id")
    ln.add_argument("--catalysts", help="comma-separated catalyst ids")
    ln.add_argument("--predictions", help="comma-separated ledger ids")
    ln.add_argument("--memory", help="comma-separated brain entry IDs")
    ln.add_argument("--tickers", help="comma-separated")
    ln.add_argument("--note", help="why this link exists")
    ln.set_defaults(func=_cmd_link)

    c = sub.add_parser("close", help="retire a thesis with a post-mortem")
    c.add_argument("id")
    c.add_argument("--outcome", required=True, choices=list(CLOSE_OUTCOMES))
    c.add_argument("--note", required=True)
    c.set_defaults(func=_cmd_close)

    l = sub.add_parser("list")
    l.add_argument("--stage", choices=list(STAGES))
    l.add_argument("--domain", choices=sorted(DOMAINS))
    l.add_argument("--open", action="store_true")
    l.add_argument("--json", action="store_true")
    l.set_defaults(func=_cmd_list)

    sh = sub.add_parser("show")
    sh.add_argument("id")
    sh.set_defaults(func=_cmd_show)

    orp = sub.add_parser("orphans", help="theses with no live call, calls with no thesis")
    orp.set_defaults(func=_cmd_orphans)

    au = sub.add_parser("audit")
    au.set_defaults(func=_cmd_audit)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
