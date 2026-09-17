"""ARGUS front door — whole-system situational awareness in one command.

    python -m argus status     what needs attention right now
    python -m argus doctor     integrity-check every store at once
    python -m argus agenda     the dated queue: catalysts and resolve-by dates

Before this existed, knowing the state of ARGUS meant running six commands and
holding the answers in your head. The daily loop begins here.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

RED, YELLOW, GREEN, DIM, RESET = (
    "\033[91m", "\033[93m", "\033[92m", "\033[2m", "\033[0m")


def _h(text: str) -> None:
    print(f"\n{text}\n{'-' * len(text)}")


def _cmd_status(args: argparse.Namespace) -> int:
    from . import catalysts as C
    from . import edge as E
    from . import graph as G
    from . import ledger as L
    from . import theses as T

    today = date.today()
    todo: list[str] = []

    preds = L.load_state()
    open_preds = [p for p in preds.values() if p["outcome"] is None]
    overdue = [p for p in open_preds if date.fromisoformat(p["resolve_by"]) < today]
    soon = [p for p in open_preds
            if today <= date.fromisoformat(p["resolve_by"]) <= today + timedelta(days=14)]
    cov = L.market_coverage()

    _h("LEDGER")
    print(f"  {len(preds)} logged · {len(open_preds)} open · "
          f"{len(preds) - len(open_preds)} resolved")
    if overdue:
        print(f"  {RED}{len(overdue)} OVERDUE{RESET} — resolutions are prompt or they are "
              "memory-holing:")
        for p in sorted(overdue, key=lambda p: p["resolve_by"]):
            print(f"    {p['id']}  was due {p['resolve_by']}  {p['claim'][:64]}")
        todo.append(f"resolve {len(overdue)} overdue prediction(s) — "
                    "`python -m argus.ledger resolve <id> --outcome ... --note ...`")
    if soon:
        print(f"  {YELLOW}{len(soon)} resolving within 14 days{RESET}")
        for p in sorted(soon, key=lambda p: p["resolve_by"])[:6]:
            print(f"    {p['id']}  by {p['resolve_by']}  P={p['probability']:.0%}")
    print(f"  market benchmark on {cov['with_market']}/{cov['n']} calls "
          f"({cov['coverage']:.0%})")
    if cov["coverage"] < 0.3:
        todo.append("log --market-prob where a market prices the question; below ~30% "
                    "coverage the edge claim cannot be tested")

    scored = L.score()
    if scored["n"]:
        flag = f" {RED}EMERGENCY{RESET}" if scored["brier"] > 0.25 else ""
        print(f"  Brier {scored['brier']:.4f} on n={scored['n']}{flag}")
        if scored.get("vs_market"):
            vm = scored["vs_market"]
            print(f"  vs market: {vm['verdict']} ({vm['argus_brier']:.4f} "
                  f"vs {vm['market_brier']:.4f}, n={vm['n']})")

    _h("THESES")
    live = T.live()
    if not live:
        print(f"  {DIM}none registered{RESET} — predictions with no causal model behind "
              "them are bets, not theses")
        todo.append("register at least one thesis — `python -m argus.theses open --help`")
    else:
        by_stage: dict[str, int] = {}
        for t in live:
            by_stage[t["stage"]] = by_stage.get(t["stage"], 0) + 1
        print("  " + " · ".join(f"{v} {k}" for k, v in sorted(by_stage.items())))
        cut = T.undercut()
        if cut:
            print(f"  {YELLOW}{len(cut)} whose latest evidence UNDERCUTS them{RESET}:")
            for t in cut:
                print(f"    {t['id']} — re-read the kill criteria and act or argue")
            todo.append(f"act on {len(cut)} undercut thesis/theses: stage down, or kill")

    _h("CATALYSTS")
    up = C.upcoming(days=args.days)
    late = C.overdue()
    if late:
        print(f"  {YELLOW}{len(late)} past their date with no outcome logged{RESET}")
        for c in late[:5]:
            print(f"    {c['id']}  was {c['date']}")
        todo.append(f"close {len(late)} past-due catalyst(s) — "
                    "`python -m argus.catalysts resolve <id> --what-happened ...`")
    if up:
        print(f"  next {args.days} days:")
        for c in up[:10]:
            dd = (date.fromisoformat(c["date"]) - today).days
            print(f"    T-{dd:<3} {c['date']}  {c['title'][:62]}")
    else:
        print(f"  {DIM}nothing scheduled in the next {args.days} days{RESET}")

    _h("GRAPH")
    g = G.build()
    s = G.stats(g)
    print(f"  {s['nodes']} nodes / {s['edges']} edges · {s['components']} components")
    conc = G.concentration(g)
    if conc:
        print(f"  {YELLOW}concentration:{RESET} {len(conc)} catalyst(s) carry more than "
              "one position — size each group as ONE bet")
        for row in conc[:4]:
            print(f"    {row['catalyst']} ({row['date']}): {row['dependents']} dependents, "
                  f"tickers {row['tickers'] or '—'}")
    br = G.bridges(g)
    print(f"  {len(br)} cross-domain bridge(s)"
          + (f" — top: {br[0]['node']} spans {br[0]['domains']}" if br else
             f" {DIM}(the cross-domain premise is unexercised){RESET}"))
    orph = G.orphans()
    dangling = sum(len(v) for v in orph.values())
    if dangling:
        print(f"  {dangling} dangling link(s) — `python -m argus.graph orphans`")

    _h("BOOK")
    ranked = E.rank_theses()
    if ranked["ranked"]:
        for r in ranked["ranked"][:5]:
            print(f"  {r['ev_per_risk']:>6.2f} EV/risk  {r['size_fraction']:>6.2%}  "
                  f"{r['id'][:44]}  [{r['stage']}]")
        print(f"  gross {ranked['gross_exposure']:.1%} · worst case "
              f"{ranked['aggregate_worst_case']:.1%}")
    else:
        print(f"  {DIM}nothing priced — theses need --win/--loss to be ranked{RESET}")

    _h("WHAT TO DO NEXT")
    if todo:
        for i, item in enumerate(todo, 1):
            print(f"  {i}. {item}")
    else:
        print(f"  {GREEN}nothing overdue.{RESET} Go find something nobody else has seen.")
    print("\nResearch, not financial advice.\n")
    return 1 if overdue else 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    from . import catalysts as C
    from . import ledger as L
    from . import theses as T

    failures = 0
    for label, fn in [("ledger", L._cmd_audit), ("catalysts", C._cmd_audit),
                      ("theses", T._cmd_audit)]:
        print(f"\n[{label}]")
        rc = fn(argparse.Namespace())
        failures += rc
    print(f"\n{'ALL STORES CONSISTENT' if not failures else f'{failures} STORE(S) FAILED AUDIT'}")
    return 1 if failures else 0


def _cmd_agenda(args: argparse.Namespace) -> int:
    from . import catalysts as C
    from . import ledger as L

    today = date.today()
    horizon = today + timedelta(days=args.days)
    rows: list[tuple[str, str, str]] = []
    for p in L.load_state().values():
        if p["outcome"] is None and date.fromisoformat(p["resolve_by"]) <= horizon:
            rows.append((p["resolve_by"], "prediction",
                         f"{p['id']}  P={p['probability']:.0%}  {p['claim'][:62]}"))
    for c in C.load_state().values():
        if c["what_happened"] is None and date.fromisoformat(c["date"]) <= horizon:
            rows.append((c["date"], "catalyst", f"{c['id']}  {c['title'][:62]}"))
    if not rows:
        print(f"nothing dated in the next {args.days} days")
        return 0
    for when, kind, label in sorted(rows):
        dd = (date.fromisoformat(when) - today).days
        mark = f"{RED}LATE{RESET}" if dd < 0 else f"T-{dd:<3}"
        print(f"{when}  {mark}  {kind:<10} {label}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="argus", description=__doc__)
    sub = ap.add_subparsers(dest="cmd")

    st = sub.add_parser("status", help="what needs attention right now")
    st.add_argument("--days", type=int, default=21, help="catalyst horizon")
    st.set_defaults(func=_cmd_status)

    dc = sub.add_parser("doctor", help="integrity-check every store")
    dc.set_defaults(func=_cmd_doctor)

    ag = sub.add_parser("agenda", help="the dated queue")
    ag.add_argument("--days", type=int, default=45)
    ag.set_defaults(func=_cmd_agenda)

    args = ap.parse_args(argv)
    if not getattr(args, "func", None):
        ap.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
