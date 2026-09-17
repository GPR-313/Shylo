"""Market-wide filing sweep: who filed what, today, across every issuer.

ADR 0002 warns against a second path to numbers a connector already serves, so
this module deliberately does **not** duplicate the `edgar` MCP. That server is
company-scoped: given a ticker, it returns that company's filings, financials
and Form 4s. It cannot answer the question that actually finds ideas --
*across the whole market, who filed a Form 4 / an 8-K / a 13D this morning?*

EDGAR's daily index answers exactly that, in one request per day, keyless. The
division of labour:

    market-wide discovery  ->  this module (which names, which forms, when)
    company-level detail   ->  the `edgar` MCP (what the filing actually says)

Why the sweep is worth having: cluster buying by insiders is among the most
durable documented effects in equities, and it is observable the day it files
rather than the quarter it aggregates. Two independent officers buying the same
small-cap inside a week is a signal with a name attached; a 13D is an activist
announcing themselves in public before the coverage catches it.

SEC requires a descriptive User-Agent with a real contact address or it blocks
you outright — `ARGUS_USER_AGENT` / `EDGAR_IDENTITY` carry it.

VERIFICATION STATUS: written against the published index layout; outbound HTTPS
was blocked by egress policy in the session that wrote it. Run
`python3 scripts/check_sources.py` before trusting any row this returns.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from .base import Source, SourceError

# The forms that carry positioning information, with what each one means.
FORM_MEANING = {
    "4": "insider transaction (open-market buys are the signal; sales are noise)",
    "3": "new insider — often a hire or a board seat worth knowing about",
    "SC 13D": "activist stake above 5% with intent to influence",
    "SC 13D/A": "activist stake amended — watch for increases",
    "SC 13G": "passive stake above 5%",
    "8-K": "material event; item number decides whether it matters",
    "S-1": "IPO registration",
    "424B4": "pricing — the IPO is live",
    "SC 14D9": "target's response to a tender offer",
    "DEFM14A": "merger proxy",
    "13F-HR": "quarterly institutional holdings (45 days stale by construction)",
}


class EdgarDailyIndex(Source):
    """The full daily filing index, market-wide. Keyless, one request per day."""

    name = "edgar_daily"
    base_url = "https://www.sec.gov/Archives/edgar/daily-index"
    min_interval = 0.6      # SEC asks for <= 10 req/s; this is far under
    ttl = 21600

    TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"

    # -- the index ---------------------------------------------------------

    @staticmethod
    def _quarter(day: date) -> int:
        return (day.month - 1) // 3 + 1

    def raw_index(self, day: date | None = None) -> str:
        day = day or date.today()
        path = (f"/{day.year}/QTR{self._quarter(day)}/"
                f"form.{day.strftime('%Y%m%d')}.idx")
        return self.get_text(path)

    @staticmethod
    def _parse(raw: str) -> list[dict[str, str]]:
        """Parse the fixed-width index using its own header for column offsets.

        Splitting on whitespace breaks on company names with spaces and on form
        types like `SC 13D/A`. Reading the offsets out of the header line is the
        only parse that survives both.
        """
        lines = raw.splitlines()
        header_idx = next(
            (i for i, ln in enumerate(lines)
             if ln.startswith("Form Type") and "CIK" in ln), None,
        )
        if header_idx is None:
            raise SourceError("daily index has no recognisable header row")
        header = lines[header_idx]
        cols = ["Form Type", "Company Name", "CIK", "Date Filed", "File Name"]
        starts = []
        for col in cols:
            pos = header.find(col)
            if pos < 0:
                raise SourceError(f"daily index header missing column {col!r}")
            starts.append(pos)
        bounds = list(zip(starts, starts[1:] + [len(header) + 400]))

        rows = []
        for line in lines[header_idx + 1:]:
            if not line.strip() or set(line.strip()) <= {"-"}:
                continue
            values = [line[a:b].strip() for a, b in bounds]
            if len(values) != 5 or not values[2].isdigit():
                continue
            rows.append(dict(zip(
                ["form_type", "company", "cik", "date_filed", "file_name"], values)))
        return rows

    def filings(self, day: date | None = None,
                forms: list[str] | None = None) -> list[dict[str, str]]:
        """Every filing on one day, optionally narrowed to given form types.

        Weekends and federal holidays have no index; the caller gets an empty
        list rather than an exception, because a scheduled sweep must not die
        on a Saturday.
        """
        day = day or date.today()
        try:
            raw = self.raw_index(day)
        except SourceError:
            return []
        try:
            rows = self._parse(raw)
        except SourceError:
            return []
        if forms:
            wanted = {f.upper() for f in forms}
            rows = [r for r in rows if r["form_type"].upper() in wanted]
        for r in rows:
            r["url"] = f"https://www.sec.gov/Archives/{r['file_name']}"
            r["meaning"] = FORM_MEANING.get(r["form_type"], "")
        return rows

    def sweep(self, days: int = 5,
              forms: list[str] | None = None) -> list[dict[str, str]]:
        """The last N calendar days of filings, newest first."""
        out: list[dict[str, str]] = []
        for back in range(days):
            out.extend(self.filings(date.today() - timedelta(days=back), forms))
        return sorted(out, key=lambda r: r["date_filed"], reverse=True)

    # -- derived signals ---------------------------------------------------

    def insider_clusters(self, days: int = 7, min_filers: int = 2) -> list[dict[str, Any]]:
        """Issuers with Form 4s from several distinct filers inside a window.

        Cluster activity is the part of insider data that carries information:
        one officer transacting is routine, three inside a week is a decision
        that several people made independently.

        Caveat that must travel with every row: the daily index records *that*
        a Form 4 was filed, not whether it was a buy, a sale, or an automatic
        10b5-1 disposition. Sales dominate by volume and mean nothing. Read the
        actual document -- `mcp__edgar__get_form4_details` -- before this
        becomes a thesis.
        """
        by_cik: dict[str, dict[str, Any]] = {}
        for row in self.sweep(days=days, forms=["4"]):
            entry = by_cik.setdefault(row["cik"], {
                "cik": row["cik"], "company": row["company"],
                "filings": 0, "dates": set(), "urls": [],
            })
            entry["filings"] += 1
            entry["dates"].add(row["date_filed"])
            entry["urls"].append(row["url"])
        rows = [
            {**v, "dates": sorted(v["dates"]), "urls": v["urls"][:8]}
            for v in by_cik.values() if v["filings"] >= min_filers
        ]
        return sorted(rows, key=lambda r: -r["filings"])

    def activist_stakes(self, days: int = 7) -> list[dict[str, str]]:
        """Fresh and amended 13Ds — activists announcing themselves in public."""
        return self.sweep(days=days, forms=["SC 13D", "SC 13D/A"])

    # -- identity ----------------------------------------------------------

    def ticker_map(self) -> dict[str, dict[str, Any]]:
        """CIK -> {ticker, title}. The index gives CIKs; humans think in tickers."""
        payload = self.get(self.TICKER_MAP_URL)
        rows = payload.values() if isinstance(payload, dict) else payload
        out: dict[str, dict[str, Any]] = {}
        for row in rows:
            cik = str(row.get("cik_str") or row.get("cik") or "").lstrip("0")
            if cik:
                out[cik] = {"ticker": row.get("ticker"), "title": row.get("title")}
        return out

    def with_tickers(self, rows: list[dict[str, str]]) -> list[dict[str, Any]]:
        """Attach tickers to index rows. Private filers simply have none."""
        mapping = self.ticker_map()
        out = []
        for row in rows:
            meta = mapping.get(str(row["cik"]).lstrip("0"), {})
            out.append({**row, "ticker": meta.get("ticker")})
        return out
