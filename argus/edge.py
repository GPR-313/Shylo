"""ARGUS edge engine — expected value, Kelly sizing, and the ruin guard.

Being calibrated and being paid are different things. A book of perfectly
calibrated 80% calls at 5:1 *against* loses money forever, and the ledger --
which grades only whether ARGUS was right -- would report that book as
excellent. This module is the missing half: it prices the bet, not the belief.

Three ideas do all the work here.

**Breakeven probability.** Every payoff structure implies the probability you
need just to break even. If your P is not above it, there is no trade however
good the story. Stating breakeven next to P is the fastest way to kill a
thesis that survives on narrative alone.

**Kelly, fractionalised and capped.** Full Kelly maximises long-run growth and
is far too violent for a book built on subjective probabilities -- a 10-point
overestimate of P does real damage at full Kelly. ARGUS sizes at a fraction of
Kelly, multiplies by a lifecycle-stage factor (`theses.STAGE_SIZING`), and then
applies a hard per-position cap. The output names which of the three bound, so
a suspiciously large number is always traceable.

**The ruin guard.** Positions that share a catalyst are one bet wearing several
tickers. `size_cluster` scales a correlated group so their *joint* worst case
respects a single drawdown limit. `argus.graph` finds the groups; this sizes
them.

Everything here is pure arithmetic on explicit inputs -- no network, no
hidden state, fully testable. Sizing output is a research option with
conditions attached, never an instruction to execute.

CLI:
    python -m argus.edge size --prob 0.62 --win 1.8 --loss 0.6 --stage acceleration
    python -m argus.edge compare --prob 0.62 --market 0.45
    python -m argus.edge rank [--bankroll 1.0] [--cap 0.05] [--kelly 0.25]
    python -m argus.edge book
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from .theses import STAGE_SIZING

# Quarter-Kelly. The literature's argument for fractional Kelly is that Kelly
# is optimal only if your probabilities are right; ARGUS's are estimates, and
# the penalty for overbetting is asymmetric and permanent.
DEFAULT_KELLY_FRACTION = 0.25

# No single thesis gets more than this share of the bankroll, whatever the
# arithmetic says. "Ruin is forbidden" is only a rule if something enforces it.
DEFAULT_POSITION_CAP = 0.05

# Joint worst-case loss allowed across one correlated cluster -- positions that
# resolve off the same catalyst. Five names on one catalyst chain are one bet.
DEFAULT_CLUSTER_CAP = 0.08


class SizingError(ValueError):
    """Raised on inputs that cannot be sized rather than silently coerced."""


# --------------------------------------------------------------------------
# Core arithmetic
# --------------------------------------------------------------------------


def _check(p: float, win: float, loss: float) -> None:
    if not 0.0 < p < 1.0:
        raise SizingError(f"probability must be strictly between 0 and 1 (got {p})")
    if win <= 0:
        raise SizingError(f"win must be a positive gain per unit exposure (got {win})")
    if loss <= 0:
        raise SizingError(f"loss must be a positive loss per unit exposure (got {loss})")


def expected_value(p: float, win: float, loss: float) -> float:
    """EV per unit of exposure. `win` and `loss` are fractions of the position."""
    _check(p, win, loss)
    return p * win - (1.0 - p) * loss


def breakeven_probability(win: float, loss: float) -> float:
    """The P at which this payoff is a coin flip. Below it, the trade is a donation."""
    if win <= 0 or loss <= 0:
        raise SizingError("win and loss must both be positive")
    return loss / (win + loss)


def edge(p: float, win: float, loss: float) -> float:
    """Probability points of edge over breakeven. Negative means no trade."""
    return p - breakeven_probability(win, loss)


def payoff_ratio(win: float, loss: float) -> float:
    return win / loss


def ev_per_risk(p: float, win: float, loss: float) -> float:
    """EV per unit *at risk* -- the right cross-thesis ranking metric.

    Raw EV flatters big-loss positions: a bet risking 1.0 to make 0.3 at P=0.9
    and one risking 0.1 to make 0.03 at P=0.9 have the same shape but very
    different EVs. Dividing by the downside makes them comparable.
    """
    return expected_value(p, win, loss) / loss


def kelly_fraction(p: float, win: float, loss: float) -> float:
    """Full-Kelly stake as a fraction of bankroll, floored at 0.

    For a bet gaining `win` and losing `loss` per unit staked, maximising
    E[log wealth] gives f* = (p*win - q*loss) / (win*loss). With loss = 1
    (total loss of stake) this reduces to the familiar (p*b - q)/b.
    """
    _check(p, win, loss)
    f = (p * win - (1.0 - p) * loss) / (win * loss)
    return max(0.0, f)


def market_edge(p_argus: float, p_market: float) -> dict[str, float | str]:
    """Take ARGUS's side of a binary the market prices at `p_market`.

    Buying YES at `p_market` pays (1 - p_market) / p_market on a win and costs
    the stake on a loss. If ARGUS's P is below the market's, the trade is the
    NO side and the payoff inverts. Returns whichever side ARGUS's view implies.
    """
    if not 0.0 < p_argus < 1.0:
        raise SizingError(f"p_argus must be strictly between 0 and 1 (got {p_argus})")
    if not 0.0 < p_market < 1.0:
        raise SizingError(f"p_market must be strictly between 0 and 1 (got {p_market})")

    if p_argus >= p_market:
        side, price, p_side = "yes", p_market, p_argus
    else:
        side, price, p_side = "no", 1.0 - p_market, 1.0 - p_argus

    win = (1.0 - price) / price
    ev = expected_value(p_side, win, 1.0)
    return {
        "side": side,
        "price": round(price, 4),
        "argus_p_on_side": round(p_side, 4),
        "payoff_if_right": round(win, 4),
        "ev_per_unit_staked": round(ev, 4),
        "kelly": round(kelly_fraction(p_side, win, 1.0), 4),
        "disagreement_pts": round(abs(p_argus - p_market), 4),
    }


# --------------------------------------------------------------------------
# Sizing
# --------------------------------------------------------------------------


def size(
    p: float,
    win: float,
    loss: float,
    *,
    stage: str = "acceleration",
    kelly_frac: float = DEFAULT_KELLY_FRACTION,
    cap: float = DEFAULT_POSITION_CAP,
    bankroll: float = 1.0,
) -> dict[str, Any]:
    """Stage-adjusted, fractional-Kelly, hard-capped position size.

    Returns every intermediate number and names the binding constraint, because
    a size you cannot explain is a size you will not hold through a drawdown.
    """
    if stage not in STAGE_SIZING:
        raise SizingError(f"unknown lifecycle stage {stage!r}")
    if not 0 < kelly_frac <= 1:
        raise SizingError("kelly_frac must be in (0, 1]")

    ev = expected_value(p, win, loss)
    full = kelly_fraction(p, win, loss)
    mult = STAGE_SIZING[stage]

    fractional = full * kelly_frac
    staged = fractional * mult
    final = min(staged, cap)

    if ev <= 0:
        final, binding = 0.0, "negative expected value -- no trade"
    elif stage == "reversal":
        final, binding = 0.0, "stage is reversal -- no long exposure"
    elif final == cap and staged > cap:
        binding = f"position cap ({cap:.1%})"
    elif mult < 1.0:
        binding = f"lifecycle stage '{stage}' ({mult:.0%} of Kelly)"
    else:
        binding = f"fractional Kelly ({kelly_frac:.0%} of full)"

    return {
        "probability": p,
        "win": win,
        "loss": loss,
        "stage": stage,
        "expected_value": round(ev, 4),
        "ev_per_risk": round(ev / loss, 4),
        "breakeven_p": round(breakeven_probability(win, loss), 4),
        "edge_pts": round(edge(p, win, loss), 4),
        "payoff_ratio": round(payoff_ratio(win, loss), 3),
        "full_kelly": round(full, 6),
        "fractional_kelly": round(fractional, 6),
        "stage_multiplier": mult,
        "size_fraction": round(final, 6),
        "size_notional": round(final * bankroll, 6),
        "worst_case_loss": round(final * loss * bankroll, 6),
        "binding_constraint": binding,
    }


def size_cluster(
    positions: list[dict[str, Any]],
    *,
    cluster_cap: float = DEFAULT_CLUSTER_CAP,
) -> dict[str, Any]:
    """Scale a correlated group so its *joint* worst case respects one limit.

    Positions sharing a catalyst do not diversify -- they resolve together. The
    memory brain already recorded this by hand ("one bet expressed five ways,
    not diversification"); this computes it. Each position is scaled by the same
    factor, so relative conviction inside the cluster is preserved.

    `positions` are `size()` outputs. Returns them with `cluster_size_fraction`
    added, plus the scale factor applied.
    """
    joint = sum(p["worst_case_loss"] for p in positions)
    scale = 1.0 if joint <= cluster_cap or joint == 0 else cluster_cap / joint
    scaled = []
    for pos in positions:
        row = dict(pos)
        row["cluster_scale"] = round(scale, 6)
        row["cluster_size_fraction"] = round(pos["size_fraction"] * scale, 6)
        row["cluster_worst_case"] = round(pos["worst_case_loss"] * scale, 6)
        scaled.append(row)
    return {
        "joint_worst_case_before": round(joint, 6),
        "joint_worst_case_after": round(joint * scale, 6),
        "cluster_cap": cluster_cap,
        "scale": round(scale, 4),
        "binding": scale < 1.0,
        "positions": scaled,
    }


# --------------------------------------------------------------------------
# Ranking the live book
# --------------------------------------------------------------------------


def rank_theses(
    *,
    bankroll: float = 1.0,
    cap: float = DEFAULT_POSITION_CAP,
    kelly_frac: float = DEFAULT_KELLY_FRACTION,
) -> dict[str, Any]:
    """Rank every live, priced thesis by EV per unit of risk.

    A thesis's probability is taken as the mean of its open ledger predictions:
    those are the calls that actually falsify it, so they are the honest
    estimate of whether it is working. A thesis with no open call, or with no
    --win/--loss, cannot be ranked and is reported as such rather than guessed.
    """
    from . import ledger as L
    from . import theses as T

    preds = L.load_state()
    ranked: list[dict[str, Any]] = []
    unpriced: list[dict[str, str]] = []

    for t in T.live():
        open_calls = [preds[pid] for pid in t.get("prediction_ids", [])
                      if pid in preds and preds[pid]["outcome"] is None]
        if t.get("win") is None or t.get("loss") is None:
            unpriced.append({"id": t["id"], "why": "no --win/--loss on the thesis"})
            continue
        if not open_calls:
            unpriced.append({"id": t["id"], "why": "no open prediction to price it from"})
            continue
        p = sum(c["probability"] for c in open_calls) / len(open_calls)
        row = size(p, float(t["win"]), float(t["loss"]), stage=t["stage"],
                   kelly_frac=kelly_frac, cap=cap, bankroll=bankroll)
        row.update(
            id=t["id"], title=t["title"], domain=t["domain"],
            direction=t["direction"], tickers=t.get("tickers") or [],
            n_open_calls=len(open_calls),
            catalyst_ids=t.get("catalyst_ids") or [],
        )
        ranked.append(row)

    ranked.sort(key=lambda r: -r["ev_per_risk"])
    return {
        "ranked": ranked,
        "unpriced": unpriced,
        "gross_exposure": round(sum(r["size_fraction"] for r in ranked), 6),
        "aggregate_worst_case": round(sum(r["worst_case_loss"] for r in ranked), 6),
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

_DISCLAIMER = ("Research, not financial advice. Sizing output is an option with "
               "conditions, never an instruction to execute.")


def _cmd_size(args: argparse.Namespace) -> int:
    try:
        row = size(args.prob, args.win, args.loss, stage=args.stage,
                   kelly_frac=args.kelly, cap=args.cap, bankroll=args.bankroll)
    except SizingError as exc:
        print(f"REJECTED. {exc}")
        return 1
    print(json.dumps(row, indent=2))
    if row["edge_pts"] <= 0:
        print(f"\nP={args.prob:.0%} is at or below the {row['breakeven_p']:.0%} "
              "breakeven for this payoff. No trade.")
    if args.market is not None:
        print("\nvs market:")
        print(json.dumps(market_edge(args.prob, args.market), indent=2))
    print(f"\n{_DISCLAIMER}")
    return 0


def _cmd_compare(args: argparse.Namespace) -> int:
    try:
        row = market_edge(args.prob, args.market)
    except SizingError as exc:
        print(f"REJECTED. {exc}")
        return 1
    print(json.dumps(row, indent=2))
    if row["disagreement_pts"] < 0.05:
        print("\nUnder 5 points of disagreement. That is agreement with the crowd,")
        print("not an edge -- say so in the output rather than dressing it up.")
    elif row["ev_per_unit_staked"] <= 0:
        print("\nNo positive EV at this price even on ARGUS's own number.")
    print(f"\n{_DISCLAIMER}")
    return 0


def _cmd_rank(args: argparse.Namespace) -> int:
    out = rank_theses(bankroll=args.bankroll, cap=args.cap, kelly_frac=args.kelly)
    if args.json:
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0
    if not out["ranked"] and not out["unpriced"]:
        print("no live theses -- `python -m argus.theses open --help`")
        return 0
    if out["ranked"]:
        print(f"{'thesis':<34} {'stage':<14} {'P':>5} {'BE':>5} {'EV/risk':>8} {'size':>7}")
        print("-" * 80)
        for r in out["ranked"]:
            print(f"{r['id'][:33]:<34} {r['stage']:<14} {r['probability']:>5.0%} "
                  f"{r['breakeven_p']:>5.0%} {r['ev_per_risk']:>8.3f} "
                  f"{r['size_fraction']:>7.2%}")
        print("-" * 80)
        print(f"gross exposure {out['gross_exposure']:.1%}  |  "
              f"aggregate worst case {out['aggregate_worst_case']:.1%}")
        print("\nCorrelation is NOT priced in above. Run `python -m argus.graph "
              "concentration`\nfirst -- positions sharing a catalyst must be sized "
              "as one bet (size_cluster).")
    if out["unpriced"]:
        print("\nunpriced (cannot be ranked):")
        for u in out["unpriced"]:
            print(f"  {u['id']}: {u['why']}")
    print(f"\n{_DISCLAIMER}")
    return 0


def _cmd_book(args: argparse.Namespace) -> int:
    out = rank_theses(bankroll=args.bankroll)
    by_domain: dict[str, float] = {}
    by_ticker: dict[str, float] = {}
    for r in out["ranked"]:
        by_domain[r["domain"]] = by_domain.get(r["domain"], 0) + r["size_fraction"]
        for tk in r["tickers"]:
            by_ticker[tk] = by_ticker.get(tk, 0) + r["size_fraction"]
    print(json.dumps({
        "gross_exposure": out["gross_exposure"],
        "aggregate_worst_case": out["aggregate_worst_case"],
        "by_domain": {k: round(v, 6) for k, v in sorted(by_domain.items(), key=lambda x: -x[1])},
        "by_ticker": {k: round(v, 6) for k, v in sorted(by_ticker.items(), key=lambda x: -x[1])},
        "unpriced": out["unpriced"],
    }, indent=2))
    print(f"\n{_DISCLAIMER}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="argus.edge", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("size", help="size one position")
    s.add_argument("--prob", type=float, required=True)
    s.add_argument("--win", type=float, required=True, help="gain per unit exposure")
    s.add_argument("--loss", type=float, required=True, help="loss per unit exposure")
    s.add_argument("--stage", default="acceleration", choices=list(STAGE_SIZING))
    s.add_argument("--kelly", type=float, default=DEFAULT_KELLY_FRACTION)
    s.add_argument("--cap", type=float, default=DEFAULT_POSITION_CAP)
    s.add_argument("--bankroll", type=float, default=1.0)
    s.add_argument("--market", type=float, help="market-implied P for the same question")
    s.set_defaults(func=_cmd_size)

    c = sub.add_parser("compare", help="ARGUS's P against a market price")
    c.add_argument("--prob", type=float, required=True)
    c.add_argument("--market", type=float, required=True)
    c.set_defaults(func=_cmd_compare)

    r = sub.add_parser("rank", help="rank the live book by EV per unit of risk")
    r.add_argument("--bankroll", type=float, default=1.0)
    r.add_argument("--cap", type=float, default=DEFAULT_POSITION_CAP)
    r.add_argument("--kelly", type=float, default=DEFAULT_KELLY_FRACTION)
    r.add_argument("--json", action="store_true")
    r.set_defaults(func=_cmd_rank)

    b = sub.add_parser("book", help="aggregate exposure by domain and ticker")
    b.add_argument("--bankroll", type=float, default=1.0)
    b.set_defaults(func=_cmd_book)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
