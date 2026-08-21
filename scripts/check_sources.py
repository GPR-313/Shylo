#!/usr/bin/env python3
"""Verify every configured source is reachable. Run after setup or key changes.

Exits 0 even when optional sources fail -- the point is a status board, not a
gate. Sources that need a key you have not set are reported as SKIP, not FAIL.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from argus.sources import (  # noqa: E402
    ApeWisdom, DefiLlama, Fred, Gdelt, Kalshi, NyFedMarkets,
    Polymarket, RwaXyz, Tradestie, TreasuryFiscal,
)

GREEN, YELLOW, RED, RESET = "\033[92m", "\033[93m", "\033[91m", "\033[0m"


def check(label: str, fn, needs_key: str | None = None) -> str:
    if needs_key and not os.getenv(needs_key):
        print(f"  {YELLOW}SKIP{RESET} {label:<22} ({needs_key} not set)")
        return "skip"
    try:
        result = fn()
        detail = result if isinstance(result, str) else "ok"
        print(f"  {GREEN}OK  {RESET} {label:<22} {detail}")
        return "ok"
    except Exception as exc:  # noqa: BLE001 -- status board, report everything
        msg = str(exc).split("\n")[0][:70]
        print(f"  {RED}FAIL{RESET} {label:<22} {msg}")
        return "fail"


def main() -> int:
    print("\nchecking ARGUS sources\n")
    results = []

    # --- keyless ---------------------------------------------------------
    def _defillama() -> str:
        rows = DefiLlama().stablecoin_dominance()
        total = sum(r["circulating"] for r in rows)
        return f"{len(rows)} stablecoins, ${total/1e9:.1f}B total supply"

    results.append(check("DeFiLlama", _defillama))

    def _treasury() -> str:
        rows = TreasuryFiscal().debt_to_the_penny(days=1)
        return f"debt {rows[0]['record_date']}" if rows else "ok"

    results.append(check("Treasury FiscalData", _treasury))

    def _nyfed() -> str:
        NyFedMarkets().reverse_repo(n=1)
        return "repo ops reachable"

    results.append(check("NY Fed markets", _nyfed))

    def _gdelt() -> str:
        v = Gdelt().velocity("tokenization")
        return f"'tokenization' z={v.get('z')}"

    results.append(check("GDELT", _gdelt))

    def _apewisdom() -> str:
        return f"{len(ApeWisdom().trending())} tickers trending"

    results.append(check("ApeWisdom", _apewisdom))

    def _tradestie() -> str:
        return f"{len(Tradestie().wsb())} WSB names"

    results.append(check("Tradestie", _tradestie))

    def _polymarket() -> str:
        return f"{len(Polymarket().markets(limit=20))} active markets"

    results.append(check("Polymarket", _polymarket))

    def _kalshi() -> str:
        return f"{len(Kalshi().markets(limit=20))} open markets"

    results.append(check("Kalshi (public)", _kalshi))

    # --- keyed -----------------------------------------------------------
    def _fred() -> str:
        snap = Fred().latest("rrp")
        return f"RRP {snap['value']:,.0f} on {snap['date']}" if snap else "ok"

    results.append(check("FRED", _fred, "FRED_API_KEY"))

    def _rwa() -> str:
        return f"{len(RwaXyz().tokenized_treasuries())} tokenized treasuries"

    results.append(check("RWA.xyz", _rwa, "RWA_XYZ_API_KEY"))

    ok = results.count("ok")
    print(
        f"\n{ok}/{len(results)} live, "
        f"{results.count('skip')} skipped, {results.count('fail')} failed\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
