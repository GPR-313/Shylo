"""Narrative velocity: GDELT for global news, ApeWisdom/Tradestie for retail.

All three are free and keyless. GDELT is the closest thing to a global nervous
system that a solo operator can query; the retail feeds are mention *counts*,
which is an attention signal, not a sentiment signal -- do not confuse them.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .base import Source


class Gdelt(Source):
    """GDELT 2.0 DOC API. Updated every 15 minutes.

    Gotchas that bite everyone: the API caps at 250 articles per request, and
    compound boolean queries parse unreliably. Window the queries tightly and
    dedup on the client side.
    """

    name = "gdelt"
    base_url = "https://api.gdeltproject.org/api/v2/doc/doc"
    min_interval = 1.0
    ttl = 900

    MAX_RECORDS = 250

    def _query(self, query: str, mode: str, **extra: Any) -> Any:
        params = {
            "query": query,
            "mode": mode,
            "format": "json",
            "maxrecords": self.MAX_RECORDS,
            **extra,
        }
        return self.get("", params)

    def articles(self, query: str, hours: int = 24) -> list[dict[str, Any]]:
        """Recent coverage matching a query. Keep queries simple."""
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=hours)
        payload = self._query(
            query,
            "ArtList",
            startdatetime=start.strftime("%Y%m%d%H%M%S"),
            enddatetime=end.strftime("%Y%m%d%H%M%S"),
        )
        seen, out = set(), []
        for a in payload.get("articles", []):
            if a.get("url") in seen:
                continue
            seen.add(a.get("url"))
            out.append(a)
        return out

    def volume_timeline(self, query: str, months: int = 3) -> list[dict[str, Any]]:
        """Coverage volume over time -- the raw material for lifecycle staging.

        A narrative moving fringe -> acceleration shows up here before it shows
        up in price.
        """
        payload = self._query(query, "TimelineVol", timespan=f"{months}m")
        series = payload.get("timeline", [])
        return series[0].get("data", []) if series else []

    def tone_timeline(self, query: str, months: int = 3) -> list[dict[str, Any]]:
        payload = self._query(query, "TimelineTone", timespan=f"{months}m")
        series = payload.get("timeline", [])
        return series[0].get("data", []) if series else []

    def velocity(self, query: str, months: int = 3) -> dict[str, Any]:
        """Crude but useful: latest volume vs. trailing mean, in std devs.

        A z-score above ~2 means the narrative is accelerating, not merely alive.
        """
        data = self.volume_timeline(query, months)
        values = [d.get("value", 0) for d in data if isinstance(d.get("value"), (int, float))]
        if len(values) < 8:
            return {"query": query, "n": len(values), "z": None}
        latest = values[-1]
        prior = values[:-1]
        mean = sum(prior) / len(prior)
        var = sum((v - mean) ** 2 for v in prior) / len(prior)
        sd = var ** 0.5
        return {
            "query": query,
            "n": len(values),
            "latest": latest,
            "mean": round(mean, 4),
            "z": round((latest - mean) / sd, 2) if sd else None,
        }


class ApeWisdom(Source):
    """Free, keyless retail mention counts across ~15 subreddits.

    Returns mentions and 24h change -- attention velocity, not sentiment.
    """

    name = "apewisdom"
    base_url = "https://apewisdom.io/api/v1.0"
    min_interval = 1.0
    ttl = 1800

    def trending(self, filter: str = "all-stocks", page: int = 1) -> list[dict[str, Any]]:
        """filter: all-stocks | all-crypto | wallstreetbets | stocks | ..."""
        return self.get(f"/filter/{filter}/page/{page}").get("results", [])

    def movers(self, filter: str = "all-stocks", min_mentions: int = 20) -> list[dict[str, Any]]:
        """Names whose mention count is accelerating fastest."""
        rows = []
        for r in self.trending(filter):
            mentions = int(r.get("mentions") or 0)
            prior = int(r.get("mentions_24h_ago") or 0)
            if mentions < min_mentions or prior <= 0:
                continue
            rows.append({
                "ticker": r.get("ticker"),
                "name": r.get("name"),
                "mentions": mentions,
                "prior": prior,
                "change": round((mentions - prior) / prior, 3),
                "rank": r.get("rank"),
            })
        return sorted(rows, key=lambda r: -r["change"])


class Tradestie(Source):
    """Free keyless top-50 WallStreetBets snapshot, with a sentiment field."""

    name = "tradestie"
    base_url = "https://tradestie.com/api/v1/apps"
    min_interval = 1.0
    ttl = 3600

    def wsb(self, date: str | None = None) -> list[dict[str, Any]]:
        return self.get("/reddit", {"date": date} if date else None)


class WikipediaPageviews(Source):
    """Wikimedia pageviews — attention with far less gaming than social counts.

    Reddit mention counts are trivially manipulated and skew to whatever the
    retail crowd is already trading. Wikipedia lookups measure something
    different and harder to fake: people encountering a term and going to find
    out what it means. That is the *fringe-to-early-adopter* transition in its
    purest observable form, and it leads the social feeds rather than echoing
    them.

    Keyless. EP-000a still applies in full -- this is an attention series, not
    an adoption series, and it needs a fundamental confirmation series before
    it sizes anything.
    """

    name = "wikipedia"
    base_url = "https://wikimedia.org/api/rest_v1/metrics/pageviews"
    min_interval = 0.3
    ttl = 21600

    def daily(self, article: str, *, days: int = 90, project: str = "en.wikipedia",
              access: str = "all-access", agent: str = "user") -> list[dict[str, Any]]:
        """Daily views for one article title. Spaces become underscores.

        `agent=user` strips bots and spiders, which otherwise dominate the
        series for any article a scraper happens to like.
        """
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=days)
        title = article.replace(" ", "_")
        payload = self.get(
            f"/per-article/{project}/{access}/{agent}/{title}/daily/"
            f"{start.strftime('%Y%m%d')}/{end.strftime('%Y%m%d')}"
        )
        return [
            {"date": item["timestamp"][:8], "views": item["views"]}
            for item in payload.get("items", [])
        ]

    def velocity(self, article: str, *, days: int = 90, baseline: int = 28) -> dict[str, Any]:
        """Trailing-week mean against the prior baseline, in standard deviations.

        Same z-score shape as `Gdelt.velocity` and `OpenAlex.velocity` on
        purpose: news, literature, and curiosity read on one scale, so a
        cross-domain comparison is an arithmetic one rather than a vibe.
        """
        series = self.daily(article, days=days)
        if len(series) < baseline + 7:
            return {"article": article, "n": len(series), "z": None}
        values = [row["views"] for row in series]
        recent = values[-7:]
        prior = values[-(baseline + 7):-7]
        latest = sum(recent) / len(recent)
        mean = sum(prior) / len(prior)
        sd = (sum((v - mean) ** 2 for v in prior) / len(prior)) ** 0.5
        return {
            "article": article,
            "n": len(series),
            "latest_7d_mean": round(latest, 1),
            "baseline_mean": round(mean, 1),
            "z": round((latest - mean) / sd, 2) if sd else None,
            "signal": "attention, not adoption (EP-000a)",
        }
