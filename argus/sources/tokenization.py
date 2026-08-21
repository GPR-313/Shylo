"""Tokenization module data sources: DeFiLlama (free, keyless) and RWA.xyz.

This is the pair that feeds ARGUS's specialty module. DeFiLlama gives the
stablecoin supply curve -- the denominator of the whole tokenized-dollar
thesis -- and RWA.xyz gives tokenized-Treasury AUM by issuer, which is the
cleanest available proxy for institutional adoption.

DeFiLlama needs no key. RWA.xyz needs RWA_XYZ_API_KEY.
"""

from __future__ import annotations

from typing import Any

from .base import Source, SourceError


class DefiLlama(Source):
    """Free, keyless. Stablecoins, TVL, DEX volume, protocol fees.

    Note the stablecoin endpoints live on a different subdomain than TVL, so
    several methods pass absolute URLs rather than using base_url.
    """

    name = "defillama"
    base_url = "https://api.llama.fi"
    min_interval = 0.3
    ttl = 1800

    STABLECOINS = "https://stablecoins.llama.fi"

    def stablecoin_supply(self, include_prices: bool = True) -> list[dict[str, Any]]:
        """Circulating supply for every tracked stablecoin, current snapshot."""
        data = self.get(
            f"{self.STABLECOINS}/stablecoins",
            {"includePrices": str(include_prices).lower()},
        )
        return data.get("peggedAssets", [])

    def stablecoin_history(self, chain: str | None = None) -> list[dict[str, Any]]:
        """Aggregate stablecoin market cap over time, optionally per chain.

        This is the series to watch for post-GENIUS-Act issuance inflections.
        """
        url = (
            f"{self.STABLECOINS}/stablecoincharts/{chain}"
            if chain
            else f"{self.STABLECOINS}/stablecoincharts/all"
        )
        return self.get(url)

    def stablecoin_dominance(self) -> list[dict[str, str | float]]:
        """Supply share by issuer -- concentration risk in one glance."""
        assets = self.stablecoin_supply()
        rows = []
        for a in assets:
            circ = (a.get("circulating") or {}).get("peggedUSD")
            if circ:
                rows.append({"symbol": a.get("symbol"), "name": a.get("name"), "circulating": circ})
        total = sum(r["circulating"] for r in rows) or 1
        for r in rows:
            r["share"] = round(r["circulating"] / total, 4)
        return sorted(rows, key=lambda r: -r["circulating"])

    def protocol_tvl(self, slug: str) -> dict[str, Any]:
        """TVL history for one protocol, e.g. 'ondo-finance'."""
        return self.get(f"/protocol/{slug}")

    def chains(self) -> list[dict[str, Any]]:
        return self.get("/v2/chains")


class RwaXyz(Source):
    """Tokenized real-world assets: BUIDL, BENJI, USYC, OUSG, USDY and peers.

    Verify your tier and the exact base path against current docs at signup --
    this client targets the v4 REST shape. If the response schema has moved,
    `raw()` lets you inspect without editing the module.
    """

    name = "rwa_xyz"
    base_url = "https://api.rwa.xyz/v4"
    min_interval = 1.0
    ttl = 21600  # 6h; this data updates daily at best
    requires_key = "RWA_XYZ_API_KEY"

    # Tokenized Treasury funds worth tracking as the adoption curve.
    TREASURY_FUNDS = ["BUIDL", "BENJI", "USYC", "OUSG", "USDY", "TBILL"]

    def _auth(self) -> dict[str, str]:
        import os
        return {"Authorization": f"Bearer {os.environ['RWA_XYZ_API_KEY']}"}

    def assets(self, **params: Any) -> Any:
        return self.get("/assets", params or None, headers=self._auth())

    def raw(self, path: str, **params: Any) -> Any:
        """Escape hatch for schema drift -- hit any path with auth attached."""
        return self.get(path, params or None, headers=self._auth())

    def tokenized_treasuries(self) -> list[dict[str, Any]]:
        """Filter the asset list down to tokenized Treasury products."""
        payload = self.assets()
        items = payload.get("data", payload) if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            raise SourceError("unexpected RWA.xyz payload shape; call raw() to inspect")
        return [
            a for a in items
            if str(a.get("symbol", "")).upper() in self.TREASURY_FUNDS
            or "treasury" in str(a.get("asset_class", "")).lower()
        ]
