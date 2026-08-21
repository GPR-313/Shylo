#!/usr/bin/env python3
"""ARGUS calibration report.

Reads the prediction ledger and renders a markdown calibration report:
status counts, overdue queue, Brier by domain, a calibration table, and an
ASCII calibration curve. Prints to stdout; use --out to also write a file
(the weekly self-review writes it into the memo).

Stdlib only, like ledger.py — the ledger stack must run anywhere Python does.

Usage:
    python3 scripts/calibration.py [--ledger PATH] [--out FILE]
"""

import argparse
from datetime import datetime, timezone
from pathlib import Path

import ledger as ledger_mod  # sibling module: reuse loading/merging/status logic

BUCKETS = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)]
CURVE_WIDTH = 50  # characters representing 0%..100%


def build_report(ledger_path: Path) -> str:
    merged = ledger_mod.merge(ledger_mod.load_records(ledger_path))
    today = datetime.now(timezone.utc).date()
    preds = [v for v in merged.values() if "claim" in v]

    lines = [f"# Calibration report — {today.isoformat()}", ""]
    if not preds:
        lines.append("Ledger is empty. Log predictions with `scripts/ledger.py add`.")
        return "\n".join(lines) + "\n"

    statuses: dict[str, list[dict]] = {}
    for v in preds:
        statuses.setdefault(ledger_mod.derived_status(v, today), []).append(v)

    lines.append(f"**{len(preds)} predictions** — " + ", ".join(
        f"{len(vs)} {k}" for k, vs in sorted(statuses.items())))
    lines.append("")

    overdue = statuses.get("overdue", [])
    if overdue:
        lines.append("## Overdue — resolve these first")
        lines.append("")
        for v in sorted(overdue, key=lambda v: v["resolve_by"]):
            lines.append(f"- `{v['id']}` (was due {v['resolve_by']}): {v['claim']}")
        lines.append("")

    scored = [(v["domain"], v["probability"],
               v["resolution"]["outcome"] == "yes", v["resolution"]["brier"])
              for v in preds
              if v.get("resolution", {}).get("outcome") in ("yes", "no")]
    if not scored:
        lines.append("No scoreable resolutions yet. The curve appears once "
                     "resolve-by dates start passing and outcomes are logged.")
        return "\n".join(lines) + "\n"

    overall = sum(s[3] for s in scored) / len(scored)
    lines.append(f"## Brier: {overall:.4f} overall (n={len(scored)})")
    lines.append("")
    lines.append("0 = perfect, 0.25 = always guessing 50%. Lower is better.")
    lines.append("")
    lines.append("| Domain | Brier | n |")
    lines.append("|---|---|---|")
    by_domain: dict[str, list[float]] = {}
    for domain, _, _, b in scored:
        by_domain.setdefault(domain, []).append(b)
    for domain in sorted(by_domain, key=lambda d: sum(by_domain[d]) / len(by_domain[d])):
        vals = by_domain[domain]
        lines.append(f"| {domain} | {sum(vals) / len(vals):.4f} | {len(vals)} |")
    lines.append("")

    lines.append("## Calibration curve")
    lines.append("")
    lines.append("Perfect calibration: `x` (realized) sits on `.` (predicted).")
    lines.append("")
    lines.append("```")
    lines.append("bucket      n   predicted -> realized")
    for lo, hi in BUCKETS:
        members = [(p, yes) for _, p, yes, _ in scored if lo <= p < hi]
        if not members:
            continue
        avg_p = sum(p for p, _ in members) / len(members)
        realized = sum(1 for _, yes in members if yes) / len(members)
        row = [" "] * (CURVE_WIDTH + 1)
        row[round(avg_p * CURVE_WIDTH)] = "."
        row[round(realized * CURVE_WIDTH)] = "x"
        lines.append(f"{lo:>3.0%}-{min(hi, 1.0):<4.0%} {len(members):>3}   "
                     f"{avg_p:>4.0%} -> {realized:>4.0%}  |{''.join(row)}|")
    lines.append("      0%" + " " * (CURVE_WIDTH - 8) + "100%")
    lines.append("```")
    lines.append("")
    lines.append("Read: `x` left of `.` in high buckets = overconfident on yes-calls; "
                 "`x` right of `.` in low buckets = too timid.")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ledger", default=str(ledger_mod.DEFAULT_LEDGER))
    parser.add_argument("--out", help="also write the report to this file")
    args = parser.parse_args()

    report = build_report(Path(args.ledger))
    print(report, end="")
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report)
        print(f"\n[written to {out}]")


if __name__ == "__main__":
    main()
