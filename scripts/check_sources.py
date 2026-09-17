#!/usr/bin/env python3
"""Verify every configured source is reachable. Run after setup or key changes.

Exits 0 even when optional sources fail -- the point is a status board, not a
gate. Sources that need a key you have not set are reported as SKIP, not FAIL.

This is also the acceptance test for anything in `argus/sources/`. Several
clients were written against published API shapes in an environment with no
outbound network (see the VERIFICATION STATUS note in each module); a green
line here is the first evidence any of them actually works. Treat a red line
on a new client as "schema drifted or the shape was wrong", not as an outage.
"""

from __future__ import annotations

import argparse
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
    ApeWisdom, ArXiv, ClinicalTrials, Congress, DefiLlama, EdgarDailyIndex,
    FederalRegister, Fred, Gdelt, Kalshi, NyFedMarkets, OpenAlex, Polymarket,
    RwaXyz, Tradestie, TreasuryFiscal, WikipediaPageviews,
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
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--retries", type=int, default=1,
                    help="attempts per source (default 1 -- a status board should "
                         "fail fast; raise it when diagnosing a flaky endpoint)")
    ap.add_argument("--timeout", type=int, default=10, help="seconds per request")
    args = ap.parse_args()
    # Read by argus.sources.base at request time.
    os.environ.setdefault("ARGUS_RETRIES", str(args.retries))
    os.environ.setdefault("ARGUS_TIMEOUT", str(args.timeout))

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

    def _wikipedia() -> str:
        v = WikipediaPageviews().velocity("Tokenization (finance)")
        return f"'Tokenization (finance)' z={v.get('z')}"

    results.append(check("Wikipedia pageviews", _wikipedia))

    def _fedreg() -> str:
        docs = FederalRegister().documents("tokenized securities", per_page=5)
        return f"{len(docs)} recent documents"

    results.append(check("Federal Register", _fedreg))

    def _trials() -> str:
        rows = ClinicalTrials().studies("GLP-1", page_size=5)
        return f"{len(rows)} studies"

    results.append(check("ClinicalTrials.gov", _trials))

    def _openalex() -> str:
        v = OpenAlex().velocity("tokenized securities settlement")
        return f"z={v.get('z')} over {v.get('n')} years"

    results.append(check("OpenAlex", _openalex))

    def _arxiv() -> str:
        return f"{len(ArXiv().search('cat:q-fin.TR', max_results=5))} preprints"

    results.append(check("arXiv", _arxiv))

    def _edgar_index() -> str:
        # Probe reachability with the ticker map, which exists every day of the
        # year. `filings()` deliberately swallows a missing index so a Saturday
        # sweep does not crash -- which means an empty result cannot tell a
        # holiday apart from an outage, and reporting OK on it would be exactly
        # the "confident guess dressed as knowledge" this repo forbids.
        from datetime import date, timedelta
        client = EdgarDailyIndex()
        mapped = len(client.ticker_map())      # raises if SEC is unreachable
        for back in range(5):
            day = date.today() - timedelta(days=back)
            rows = client.filings(day)
            if rows:
                return f"{len(rows)} filings on {day}, {mapped} tickers mapped"
        return f"{mapped} tickers mapped; no daily index in 5 days (holiday window?)"

    results.append(check("EDGAR daily index", _edgar_index))

    # --- keyed -----------------------------------------------------------
    def _fred() -> str:
        snap = Fred().latest("rrp")
        return f"RRP {snap['value']:,.0f} on {snap['date']}" if snap else "ok"

    results.append(check("FRED", _fred, "FRED_API_KEY"))

    def _rwa() -> str:
        return f"{len(RwaXyz().tokenized_treasuries())} tokenized treasuries"

    results.append(check("RWA.xyz", _rwa, "RWA_XYZ_API_KEY"))

    def _congress() -> str:
        return f"{len(Congress().bills(limit=5))} recent bills"

    results.append(check("Congress.gov", _congress, "CONGRESS_API_KEY"))

    ok = results.count("ok")
    print(
        f"\n{ok}/{len(results)} live, "
        f"{results.count('skip')} skipped, {results.count('fail')} failed\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
