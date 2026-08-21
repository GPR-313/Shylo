"""Macro and Fed plumbing: FRED, Treasury FiscalData, NY Fed.

FRED needs a free key (FRED_API_KEY). Treasury FiscalData and the NY Fed
markets endpoints need nothing at all.
"""

from __future__ import annotations

import os
from typing import Any

from .base import Source


class Fred(Source):
    """St. Louis Fed. The series IDs below are the plumbing ARGUS watches."""

    name = "fred"
    base_url = "https://api.stlouisfed.org/fred"
    min_interval = 0.2
    ttl = 3600
    requires_key = "FRED_API_KEY"

    # Curated series for the monetary-system module. Extend freely.
    SERIES = {
        "rrp": "RRPONTSYD",        # overnight reverse repo volume
        "reserves": "WRESBAL",     # reserve balances at Fed banks
        "sofr": "SOFR",
        "effr": "EFFR",
        "fed_balance_sheet": "WALCL",
        "iorb": "IORB",
        "cpi": "CPIAUCSL",
        "core_pce": "PCEPILFE",
        "unemployment": "UNRATE",
        "gdp": "GDPC1",
        "2y": "DGS2",
        "10y": "DGS10",
        "30y": "DGS30",
        "curve_10y2y": "T10Y2Y",
        "hy_spread": "BAMLH0A0HYM2",   # high-yield OAS, credit stress
        "ig_spread": "BAMLC0A0CM",
        "m2": "M2SL",
        "bank_credit": "TOTBKCR",
        "dollar_index": "DTWEXBGS",
    }

    def observations(
        self, series_id: str, start: str | None = None, limit: int = 500
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "series_id": series_id,
            "api_key": os.environ["FRED_API_KEY"],
            "file_type": "json",
            "sort_order": "desc",
            "limit": limit,
        }
        if start:
            params["observation_start"] = start
        return self.get("/series/observations", params).get("observations", [])

    def latest(self, key_or_id: str) -> dict[str, Any] | None:
        """Most recent non-missing observation. Accepts a friendly key or raw ID."""
        series_id = self.SERIES.get(key_or_id, key_or_id)
        for obs in self.observations(series_id, limit=10):
            if obs.get("value") not in (".", None, ""):
                return {
                    "series": series_id,
                    "date": obs["date"],
                    "value": float(obs["value"]),
                }
        return None

    def plumbing_snapshot(self) -> dict[str, Any]:
        """One call site for the Fed-plumbing dashboard in the morning brief."""
        keys = ["rrp", "reserves", "sofr", "effr", "iorb", "fed_balance_sheet",
                "curve_10y2y", "hy_spread"]
        out: dict[str, Any] = {}
        for k in keys:
            try:
                out[k] = self.latest(k)
            except Exception as exc:  # one dead series must not kill the brief
                out[k] = {"error": str(exc)}
        return out


class TreasuryFiscal(Source):
    """Treasury FiscalData. No key, no auth, generous limits."""

    name = "treasury"
    base_url = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
    min_interval = 0.3
    ttl = 7200

    def dataset(
        self,
        endpoint: str,
        *,
        fields: str | None = None,
        filter: str | None = None,
        sort: str = "-record_date",
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"sort": sort, "page[size]": page_size}
        if fields:
            params["fields"] = fields
        if filter:
            params["filter"] = filter
        return self.get(endpoint, params).get("data", [])

    def debt_to_the_penny(self, days: int = 30) -> list[dict[str, Any]]:
        return self.dataset("/v2/accounting/od/debt_to_penny", page_size=days)

    def auction_results(self, page_size: int = 50) -> list[dict[str, Any]]:
        """Recent auctions -- bid-to-cover is the demand signal that matters."""
        return self.dataset("/v1/accounting/od/auctions_query", page_size=page_size)

    def daily_cash_balance(self, days: int = 30) -> list[dict[str, Any]]:
        """TGA balance. Drains and rebuilds move liquidity."""
        return self.dataset(
            "/v1/accounting/dts/operating_cash_balance", page_size=days
        )


class NyFedMarkets(Source):
    """NY Fed markets data: SOMA holdings, repo/reverse-repo operations."""

    name = "nyfed"
    base_url = "https://markets.newyorkfed.org/api"
    min_interval = 0.5
    ttl = 7200

    def repo_operations(self, n: int = 10) -> Any:
        return self.get(f"/rp/all/results/last/{n}.json")

    def reverse_repo(self, n: int = 10) -> Any:
        return self.get(f"/rp/reverserepo/all/results/last/{n}.json")

    def soma_holdings(self) -> Any:
        return self.get("/soma/summary.json")
