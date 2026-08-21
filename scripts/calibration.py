#!/usr/bin/env python3
"""ARGUS calibration report.

Renders a markdown calibration report from the prediction ledger: status
counts, the overdue queue, Brier by domain, a calibration table, and an ASCII
calibration curve. Prints to stdout; use --out to also write a file (the
weekly self-review writes it into the memo).

Reads through `argus.ledger` so there is exactly one interpretation of the
ledger file. This script never writes to the ledger.

Usage:
    python3 scripts/calibration.py [--ledger PATH] [--out FILE]
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from argus import ledger as L  # noqa: E402

BUCKETS = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)]
CURVE_WIDTH = 50  # characters representing 0%..100%


def status_of(p: dict, today: date) -> str:
    outcome = p["outcome"]
    if outcome is None:
        return "overdue" if date.fromisoformat(p["resolve_by"]) < today else "open"
    if not L.is_graded(outcome):
        return "unresolvable"
    return "resolved:hit" if outcome else "resolved:miss"


def build_report(ledger_path: Path) -> str:
    preds = list(L.load_state(ledger_path).values())
    today = datetime.now(timezone.utc).date()

    lines = [f"# Calibration report — {today.isoformat()}", ""]
    if not preds:
        lines.append("Ledger is empty. Log predictions with `python -m argus.ledger add`.")
        return "\n".join(lines) + "\n"

    statuses: dict[str, list[dict]] = {}
    for p in preds:
        statuses.setdefault(status_of(p, today), []).append(p)

    lines.append(
        f"**{len(preds)} predictions** — "
        + ", ".join(f"{len(v)} {k}" for k, v in sorted(statuses.items()))
    )
    lines.append("")

    overdue = statuses.get("overdue", [])
    if overdue:
        lines.append("## Overdue — resolve these first")
        lines.append("")
        for p in sorted(overdue, key=lambda p: p["resolve_by"]):
            lines.append(f"- `{p['id']}` (was due {p['resolve_by']}): {p['claim']}")
        lines.append("")

    # The unresolvable rate audits the falsifiability gate itself (ADR 0001):
    # calls that could not be graded were written badly, not merely missed.
    ungraded = statuses.get("unresolvable", [])
    if ungraded:
        graded_n = len(statuses.get("resolved:hit", [])) + len(statuses.get("resolved:miss", []))
        denom = graded_n + len(ungraded)
        lines.append(
            f"## Unresolvable: {len(ungraded)}/{denom} "
            f"({len(ungraded) / denom:.0%} of everything closed)"
        )
        lines.append("")
        lines.append(
            "These are gate failures, not forecasting failures — the criteria "
            "could not be adjudicated as written. Above ~10%, sharpen the "
            "criteria template before logging more calls."
        )
        lines.append("")
        for p in ungraded:
            lines.append(f"- `{p['id']}`: {p['note'] or '(no note)'}")
        lines.append("")

    scored = [p for p in preds if L.is_graded(p["outcome"])]
    if not scored:
        lines.append(
            "No scoreable resolutions yet. The curve appears once resolve-by "
            "dates start passing and outcomes are logged."
        )
        return "\n".join(lines) + "\n"

    briers = {p["id"]: L.brier(p["probability"], p["outcome"]) for p in scored}
    overall = sum(briers.values()) / len(scored)
    lines.append(f"## Brier: {overall:.4f} overall (n={len(scored)})")
    lines.append("")
    lines.append("0 = perfect, 0.25 = always guessing 50%. Lower is better.")
    if overall > 0.25:
        lines.append("")
        lines.append(
            "> **Above 0.25 — worse than saying 50% every time.** CLAUDE.md "
            "treats this as an emergency, not a data point."
        )
    lines.append("")
    lines.append("| Domain | Brier | n |")
    lines.append("|---|---|---|")
    by_domain: dict[str, list[float]] = {}
    for p in scored:
        by_domain.setdefault(p["domain"], []).append(briers[p["id"]])
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
        members = [p for p in scored if lo <= p["probability"] < hi]
        if not members:
            continue
        avg_p = sum(p["probability"] for p in members) / len(members)
        realized = sum(1 for p in members if p["outcome"]) / len(members)
        row = [" "] * (CURVE_WIDTH + 1)
        row[round(avg_p * CURVE_WIDTH)] = "."
        row[round(realized * CURVE_WIDTH)] = "x"
        lines.append(
            f"{lo:>3.0%}-{min(hi, 1.0):<4.0%} {len(members):>3}   "
            f"{avg_p:>4.0%} -> {realized:>4.0%}  |{''.join(row)}|"
        )
    lines.append("      0%" + " " * (CURVE_WIDTH - 8) + "100%")
    lines.append("```")
    lines.append("")
    lines.append(
        "Read: `x` left of `.` in high buckets = overconfident on yes-calls; "
        "`x` right of `.` in low buckets = too timid."
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ledger", default=str(L.LEDGER_PATH))
    parser.add_argument("--out", help="also write the report to this file")
    args = parser.parse_args()

    report = build_report(Path(args.ledger))
    print(report, end="")
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
        print(f"\n[written to {out}]")


if __name__ == "__main__":
    main()
