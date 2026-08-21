"""Prediction markets as a calibration benchmark.

The point is not to trade these. It is to have a market-implied probability to
score ARGUS against. If ARGUS cannot beat Polymarket on questions Polymarket
already prices, it has no edge on those questions and should say so.

Polymarket read endpoints are public and keyless. Kalshi needs a key for
authenticated endpoints; public market data is largely open.
"""

from __future__ import annotations

from typing import Any

from .base import Source


class Polymarket(Source):
    """Gamma API -- public, keyless reads. US trading is geo-restricted; reads are not."""

    name = "polymarket"
    base_url = "https://gamma-api.polymarket.com"
    min_interval = 0.5
    ttl = 600

    def markets(self, limit: int = 100, active: bool = True, **extra: Any) -> list[dict[str, Any]]:
        params = {"limit": limit, "active": str(active).lower(), "closed": "false", **extra}
        data = self.get("/markets", params)
        return data if isinstance(data, list) else data.get("data", [])

    def search(self, term: str, limit: int = 50) -> list[dict[str, Any]]:
        term_l = term.lower()
        return [
            m for m in self.markets(limit=limit * 4)
            if term_l in str(m.get("question", "")).lower()
        ][:limit]

    def implied_probability(self, market: dict[str, Any]) -> float | None:
        """Best-effort extraction of the YES price as a probability."""
        import json as _json

        prices = market.get("outcomePrices")
        if isinstance(prices, str):
            try:
                prices = _json.loads(prices)
            except _json.JSONDecodeError:
                return None
        if isinstance(prices, list) and prices:
            try:
                return float(prices[0])
            except (TypeError, ValueError):
                return None
        return None


class Kalshi(Source):
    """Kalshi public market data. Set KALSHI_API_KEY for authenticated endpoints."""

    name = "kalshi"
    base_url = "https://api.elections.kalshi.com/trade-api/v2"
    min_interval = 0.5
    ttl = 600

    def markets(self, limit: int = 100, status: str = "open", **extra: Any) -> list[dict[str, Any]]:
        return self.get("/markets", {"limit": limit, "status": status, **extra}).get("markets", [])

    def market(self, ticker: str) -> dict[str, Any]:
        return self.get(f"/markets/{ticker}").get("market", {})

    @staticmethod
    def implied_probability(market: dict[str, Any]) -> float | None:
        """Kalshi quotes cents; midpoint of bid/ask is the implied probability."""
        bid, ask = market.get("yes_bid"), market.get("yes_ask")
        if bid is None or ask is None:
            last = market.get("last_price")
            return last / 100 if last is not None else None
        return (bid + ask) / 200
