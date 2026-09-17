"""Policy pipeline: Federal Register and Congress.gov.

"Governments pick winners; front-run the pick" was in the README from day one
with no code behind it. This is that domain's OBSERVE layer.

The asymmetry worth exploiting here is procedural, not political. A proposed
rule publishes a comment deadline, a final rule publishes an effective date,
and a bill's committee action is public the day it happens -- all of it dated,
all of it weeks to months before the trade press turns it into a narrative.
Those dates are catalysts in the `argus.catalysts` sense: they settle questions
on a schedule somebody else already published.

Federal Register is keyless. Congress.gov needs a free CONGRESS_API_KEY -- it
has been in `.env.example` since the beginning and nothing read it until now.

VERIFICATION STATUS: written against the published API shapes; outbound HTTPS
was blocked by egress policy in the session that wrote it, so no call here has
been exercised live. Run `python3 scripts/check_sources.py` before trusting any
number these return, and treat a schema surprise as expected rather than novel.
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any

from .base import Source


class FederalRegister(Source):
    """federalregister.gov public API. No key, no auth, generous limits.

    The document types that matter, in rough order of tradability:
      RULE          -- final; carries an effective date, so the clock is real
      PRORULE       -- proposed; carries a comment deadline, the earlier signal
      NOTICE        -- includes export-control listings and agency determinations
      PRESDOCU      -- executive orders and proclamations
    """

    name = "federal_register"
    base_url = "https://www.federalregister.gov/api/v1"
    min_interval = 0.5
    ttl = 3600

    DOC_TYPES = ("RULE", "PRORULE", "NOTICE", "PRESDOCU")

    def documents(
        self,
        term: str | None = None,
        *,
        agencies: list[str] | None = None,
        doc_types: list[str] | None = None,
        since: str | None = None,
        per_page: int = 50,
    ) -> list[dict[str, Any]]:
        """Search published documents. `agencies` takes slugs, e.g.
        'securities-and-exchange-commission', 'industry-and-security-bureau'."""
        params: dict[str, Any] = {
            "per_page": min(per_page, 1000),
            "order": "newest",
            "fields[]": [
                "document_number", "title", "type", "abstract", "publication_date",
                "effective_on", "comments_close_on", "agencies", "html_url",
                "docket_ids", "significant",
            ],
        }
        if term:
            params["conditions[term]"] = term
        if agencies:
            params["conditions[agencies][]"] = agencies
        if doc_types:
            params["conditions[type][]"] = doc_types
        params["conditions[publication_date][gte]"] = (
            since or (date.today() - timedelta(days=30)).isoformat()
        )
        return self.get("/documents.json", params).get("results", [])

    def dated_deadlines(self, term: str, *, since: str | None = None) -> list[dict[str, Any]]:
        """Documents carrying a real forward date — the catalyst harvest.

        Everything returned here can be logged straight into the catalyst
        calendar: the date is the agency's own, not an estimate.
        """
        out = []
        for doc in self.documents(term, since=since):
            for field, kind in (("effective_on", "effective"),
                                ("comments_close_on", "comment_deadline")):
                when = doc.get(field)
                if not when:
                    continue
                out.append({
                    "date": when,
                    "kind": kind,
                    "title": doc.get("title"),
                    "type": doc.get("type"),
                    "agencies": [a.get("name") for a in doc.get("agencies") or []],
                    "url": doc.get("html_url"),
                    "document_number": doc.get("document_number"),
                    "significant": doc.get("significant"),
                })
        return sorted(out, key=lambda d: d["date"])

    def export_controls(self, *, since: str | None = None) -> list[dict[str, Any]]:
        """BIS actions — the geopolitics domain's most mechanical feed.

        Entity-list additions and rule tightenings land here on the day they
        publish, typically before the supply-chain read-through is drawn.
        """
        return self.documents(
            "export administration regulations",
            agencies=["industry-and-security-bureau"],
            doc_types=["RULE", "PRORULE", "NOTICE"],
            since=since,
        )


class Congress(Source):
    """api.congress.gov v3. Free key, instant signup.

    Bills are a slow-moving pipeline with public stage transitions. The useful
    read is not "will it pass" -- prediction markets price that better -- but
    *which committee touched it when*, because that is the dated event a market
    is usually not pricing at all.
    """

    name = "congress"
    base_url = "https://api.congress.gov/v3"
    min_interval = 0.5
    ttl = 3600
    requires_key = "CONGRESS_API_KEY"

    def _params(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"api_key": os.environ["CONGRESS_API_KEY"], "format": "json",
                **(extra or {})}

    def bills(self, congress: int = 119, *, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        return self.get(f"/bill/{congress}",
                        self._params({"limit": limit, "offset": offset})).get("bills", [])

    def bill(self, congress: int, bill_type: str, number: int) -> dict[str, Any]:
        return self.get(f"/bill/{congress}/{bill_type.lower()}/{number}",
                        self._params()).get("bill", {})

    def bill_actions(self, congress: int, bill_type: str, number: int,
                     limit: int = 100) -> list[dict[str, Any]]:
        """The stage-transition log. Each action is dated and attributable."""
        return self.get(f"/bill/{congress}/{bill_type.lower()}/{number}/actions",
                        self._params({"limit": limit})).get("actions", [])

    def search_bills(self, congress: int = 119, *, limit: int = 250) -> list[dict[str, Any]]:
        """Recent bills, newest first. The v3 API has no free-text bill search,
        so filter client-side on `title` rather than pretending otherwise."""
        return self.bills(congress, limit=min(limit, 250))
