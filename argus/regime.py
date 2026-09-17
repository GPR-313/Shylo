"""Macro regime classifier — and, more usefully, what would break the regime.

The README has claimed regime detection since the first commit with no code
behind it. The gap mattered: the same thesis at the same probability deserves a
different size depending on whether credit is calm or widening, and "stage
determines sizing" applies to the macro backdrop exactly as it applies to a
narrative.

Everything here is a **stated prior, not a measurement.** The thresholds below
encode conventional readings of each series; they have not been fitted to
anything, and the weekly self-review is supposed to argue with them. They are
written as named constants so that argument is a one-line diff rather than an
archaeology expedition.

The output that matters most is not the regime label -- it is `breaks_if`. A
regime call with no stated invalidation is the macro equivalent of a thesis
with no kill criteria, and gets treated the same way.

`classify()` is pure: it takes readings and returns a verdict, so it is
testable without a network. `snapshot()` is the thin FRED-fetching wrapper.

CLI:
    python -m argus.regime                       # fetch from FRED and classify
    python -m argus.regime --sofr 4.32 --iorb 4.40 --hy-oas 312 --curve 0.45
"""

from __future__ import annotations

import argparse
import json
from typing import Any

# -- Thresholds. Priors, argued with in the weekly review, not fitted. -------

# SOFR above IORB means overnight cash is bidding above the rate the Fed pays
# banks to hold reserves: the classic sign reserves have stopped being
# abundant. Measured in basis points of spread.
SOFR_IORB_SCARCE = 5.0        # bp above IORB -- funding pressure is real
SOFR_IORB_TIGHTENING = 0.0    # at or above IORB -- the buffer is thinning

# High-yield OAS, basis points. Sub-350 is a market not pricing default risk;
# 500+ has historically coincided with the funding channel actually closing.
HY_CALM = 350.0
HY_WIDENING = 500.0

# 10y-2y in percentage points.
CURVE_INVERTED = 0.0
CURVE_FLAT = 0.50

# Overnight RRP in $bn. The facility is the shock absorber between Treasury
# issuance and bank reserves; near zero, issuance drains reserves directly.
RRP_DRAINED = 50.0

LIQUIDITY_STATES = ("abundant", "adequate", "draining", "scarce")
CREDIT_STATES = ("calm", "widening", "stressed")
CURVE_STATES = ("inverted", "flat", "normal")
COMPOSITES = ("risk_on", "neutral", "risk_off", "crisis")

# How much the composite discounts position sizes. Multiplies the stage factor
# in `argus.edge`, so a good thesis in a stressed tape is sized like a
# speculative one -- which is the whole point of noticing the regime.
REGIME_SIZING = {"risk_on": 1.00, "neutral": 0.80, "risk_off": 0.50, "crisis": 0.25}


def _liquidity(sofr: float | None, iorb: float | None,
               rrp_bn: float | None) -> tuple[str, str]:
    if sofr is None or iorb is None:
        return "adequate", "SOFR or IORB unavailable — liquidity read is a guess"
    spread_bp = (sofr - iorb) * 100
    drained = rrp_bn is not None and rrp_bn < RRP_DRAINED
    if spread_bp >= SOFR_IORB_SCARCE:
        state = "scarce"
        why = (f"SOFR is {spread_bp:.0f}bp above IORB — cash is bidding above the "
               "administered floor, which is what reserve scarcity looks like")
    elif spread_bp >= SOFR_IORB_TIGHTENING:
        state = "draining" if drained else "adequate"
        why = (f"SOFR is {spread_bp:+.0f}bp vs IORB"
               + (f", and RRP at ${rrp_bn:.0f}bn is effectively drained — issuance "
                  "now comes straight out of reserves" if drained else ""))
    else:
        state = "draining" if drained else "abundant"
        why = (f"SOFR is {spread_bp:+.0f}bp below IORB"
               + (f" but RRP at ${rrp_bn:.0f}bn is drained, so the buffer is gone"
                  if drained else " — the floor system is holding"))
    return state, why


def _credit(hy_oas_bp: float | None, hy_change_bp: float | None) -> tuple[str, str]:
    if hy_oas_bp is None:
        return "calm", "HY OAS unavailable — credit read is a guess"
    widening_fast = hy_change_bp is not None and hy_change_bp >= 50
    if hy_oas_bp >= HY_WIDENING:
        return "stressed", (f"HY OAS at {hy_oas_bp:.0f}bp — above {HY_WIDENING:.0f}bp the "
                            "funding channel has historically closed, not merely repriced")
    if hy_oas_bp >= HY_CALM or widening_fast:
        detail = f"HY OAS at {hy_oas_bp:.0f}bp"
        if widening_fast:
            detail += f", {hy_change_bp:+.0f}bp over the window — the rate of change is the signal"
        return "widening", detail
    return "calm", f"HY OAS at {hy_oas_bp:.0f}bp — default risk is not being priced"


def _curve(curve_10y2y: float | None) -> tuple[str, str]:
    if curve_10y2y is None:
        return "flat", "10y-2y unavailable — curve read is a guess"
    if curve_10y2y < CURVE_INVERTED:
        return "inverted", (f"10y-2y at {curve_10y2y:+.2f}pp — inversion is a recession "
                            "signal with a long and variable lag, not a timing tool")
    if curve_10y2y < CURVE_FLAT:
        return "flat", f"10y-2y at {curve_10y2y:+.2f}pp"
    return "normal", (f"10y-2y at {curve_10y2y:+.2f}pp — a steepening curve out of "
                      "inversion has historically been the nearer warning")


def classify(readings: dict[str, float | None]) -> dict[str, Any]:
    """Classify the macro backdrop from explicit readings.

    Recognised keys (all optional; missing ones degrade the read and say so):
        sofr, iorb, rrp_bn, hy_oas_bp, hy_oas_change_bp, curve_10y2y
    """
    liq, liq_why = _liquidity(readings.get("sofr"), readings.get("iorb"),
                              readings.get("rrp_bn"))
    cred, cred_why = _credit(readings.get("hy_oas_bp"), readings.get("hy_oas_change_bp"))
    crv, crv_why = _curve(readings.get("curve_10y2y"))

    # Composite. Credit carries the most weight because it is the channel that
    # actually transmits stress into prices; the curve carries the least
    # because its lead time is measured in quarters.
    score = 0
    score += {"abundant": 0, "adequate": 1, "draining": 2, "scarce": 3}[liq]
    score += {"calm": 0, "widening": 2, "stressed": 4}[cred]
    score += {"normal": 0, "flat": 1, "inverted": 1}[crv]

    if cred == "stressed" or score >= 6:
        composite = "crisis"
    elif score >= 4:
        composite = "risk_off"
    elif score >= 2:
        composite = "neutral"
    else:
        composite = "risk_on"

    missing = [k for k in ("sofr", "iorb", "hy_oas_bp", "curve_10y2y")
               if readings.get(k) is None]

    breaks_if = []
    if liq in ("abundant", "adequate"):
        breaks_if.append(f"SOFR prints {SOFR_IORB_SCARCE:.0f}bp or more above IORB "
                         "for three consecutive sessions")
    else:
        breaks_if.append("SOFR falls back below IORB and the RRP balance rebuilds")
    if cred == "calm":
        breaks_if.append(f"HY OAS closes above {HY_CALM:.0f}bp, or widens 50bp in a month")
    elif cred == "widening":
        breaks_if.append(f"HY OAS closes above {HY_WIDENING:.0f}bp (escalation) or back "
                         f"below {HY_CALM:.0f}bp (all clear)")
    else:
        breaks_if.append(f"HY OAS closes back below {HY_WIDENING:.0f}bp")
    if crv == "inverted":
        breaks_if.append("10y-2y turns positive — the steepening, not the inversion, "
                         "is what has marked the turn")

    return {
        "composite": composite,
        "sizing_multiplier": REGIME_SIZING[composite],
        "liquidity": {"state": liq, "reading": liq_why},
        "credit": {"state": cred, "reading": cred_why},
        "curve": {"state": crv, "reading": crv_why},
        "score": score,
        "breaks_if": breaks_if,
        "missing_inputs": missing,
        "confidence": "low" if len(missing) >= 2 else ("medium" if missing else "high"),
    }


def snapshot() -> dict[str, Any]:
    """Fetch the inputs from FRED and classify. Needs FRED_API_KEY.

    Every reading carries its own observation date: FRED series update on
    different schedules, and a regime call built from a three-week-old credit
    print and a same-day SOFR is not the snapshot it looks like.
    """
    try:
        from .sources import Fred
        from .sources.base import SourceError
    except ImportError as exc:  # `requests` absent -- the rest of ARGUS still works
        raise SystemExit(
            f"argus.regime snapshot needs the OBSERVE layer ({exc}). Install with "
            "`pip install -r requirements.txt`, or pass the readings directly:\n"
            "  python -m argus.regime --sofr 4.30 --iorb 4.40 --hy-oas 312 --curve 0.45"
        ) from exc

    fred = Fred()
    readings: dict[str, float | None] = {}
    asof: dict[str, str] = {}

    for key, series in (("sofr", "sofr"), ("iorb", "iorb"), ("rrp_bn", "rrp"),
                        ("hy_oas_bp", "hy_spread"), ("curve_10y2y", "curve_10y2y")):
        try:
            obs = fred.latest(series)
        except (SourceError, KeyError, OSError):
            obs = None
        if obs is None:
            readings[key] = None
            continue
        value = obs["value"]
        # FRED publishes HY OAS in percentage points and RRP in $bn already.
        if key == "hy_oas_bp":
            value *= 100
        readings[key] = value
        asof[key] = obs["date"]

    verdict = classify(readings)
    verdict["readings"] = readings
    verdict["as_of"] = asof
    return verdict


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="argus.regime", description=__doc__)
    ap.add_argument("--sofr", type=float)
    ap.add_argument("--iorb", type=float)
    ap.add_argument("--rrp-bn", dest="rrp_bn", type=float)
    ap.add_argument("--hy-oas", dest="hy_oas_bp", type=float, help="basis points")
    ap.add_argument("--hy-change", dest="hy_oas_change_bp", type=float, help="bp over window")
    ap.add_argument("--curve", dest="curve_10y2y", type=float, help="10y-2y, pp")
    args = ap.parse_args(argv)

    manual = {k: v for k, v in vars(args).items() if v is not None}
    verdict = classify(manual) if manual else snapshot()
    print(json.dumps(verdict, indent=2))
    if verdict["confidence"] == "low":
        print("\nConfidence is low: too many inputs are missing for this to steer "
              "sizing.\nSay so in the brief rather than quoting the label.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
