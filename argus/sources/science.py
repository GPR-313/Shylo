"""Science pipeline: ClinicalTrials.gov, OpenAlex, arXiv.

"A preprint server is an earnings surprise eighteen months early" is the
README's line; this module is the part that makes it checkable.

Each source answers a different question:

- **ClinicalTrials.gov** gives *dated* readouts. A Phase 3 primary completion
  date is a catalyst with a registry entry behind it -- among the most reliable
  forward dates available anywhere, and one most equity coverage reads late.
- **OpenAlex** gives publication and citation *velocity* per concept. Velocity
  is a lifecycle-stage signal: an idea accelerating in the literature two years
  before it appears in a capex line is the fringe-to-early-adopter transition.
- **arXiv** gives raw preprints, the earliest layer of all, at the cost of
  being noisy and XML.

All three are keyless. OpenAlex asks for a contact address in `mailto` for its
polite pool -- `ARGUS_USER_AGENT` carries one.

Note the standing trap, EP-000a: publication counts measure *attention within a
field*, not adoption. A citation spike is evidence about researchers, not about
revenue, and needs a fundamental confirmation series before it sizes anything.

VERIFICATION STATUS: written against the published API shapes; outbound HTTPS
was blocked by egress policy in the session that wrote it. Run
`python3 scripts/check_sources.py` before trusting any number these return.
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from typing import Any

from .base import Source


class ClinicalTrials(Source):
    """ClinicalTrials.gov API v2. Keyless.

    The field of interest is `primaryCompletionDateStruct`: a dated, registered
    commitment to produce a result. `ACTUAL` means it already happened;
    `ESTIMATED` means it is a forward catalyst.
    """

    name = "clinicaltrials"
    base_url = "https://clinicaltrials.gov/api/v2"
    min_interval = 0.5
    ttl = 21600

    def studies(
        self,
        query: str,
        *,
        phase: str | None = None,
        status: str | None = "RECRUITING",
        page_size: int = 50,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "query.term": query,
            "pageSize": min(page_size, 1000),
            "fields": ",".join([
                "NCTId", "BriefTitle", "OverallStatus", "Phase",
                "PrimaryCompletionDate", "CompletionDate", "LeadSponsorName",
                "InterventionName", "Condition", "EnrollmentCount",
            ]),
        }
        if phase:
            params["filter.advanced"] = f"AREA[Phase]{phase}"
        if status:
            params["filter.overallStatus"] = status
        return self.get("/studies", params).get("studies", [])

    def upcoming_readouts(self, query: str, *, within_days: int = 365,
                          phase: str = "PHASE3") -> list[dict[str, Any]]:
        """Phase 3 primary completions inside a window — catalysts, dated.

        Returns rows shaped for `python -m argus.catalysts add`.
        """
        horizon = date.today() + timedelta(days=within_days)
        out = []
        for s in self.studies(query, phase=phase, status=None, page_size=200):
            protocol = s.get("protocolSection", s)
            ident = protocol.get("identificationModule", {})
            status = protocol.get("statusModule", {})
            pcd = (status.get("primaryCompletionDateStruct") or {}).get("date")
            if not pcd:
                continue
            # The registry sometimes gives YYYY-MM; normalise to the month end
            # rather than silently inventing a day-of-month precision.
            precision = "day" if len(pcd) == 10 else "month"
            when = pcd if len(pcd) == 10 else f"{pcd}-28"
            try:
                parsed = date.fromisoformat(when)
            except ValueError:
                continue
            if not (date.today() <= parsed <= horizon):
                continue
            out.append({
                "nct_id": ident.get("nctId"),
                "title": ident.get("briefTitle"),
                "date": when,
                "precision": precision,
                "status": status.get("overallStatus"),
                "sponsor": (protocol.get("sponsorCollaboratorsModule", {})
                            .get("leadSponsor", {}).get("name")),
            })
        return sorted(out, key=lambda r: r["date"])


class OpenAlex(Source):
    """OpenAlex. Keyless; a contact address buys the faster polite pool.

    Indexes arXiv, PubMed, Crossref and more in one JSON API, which makes it
    the practical way to measure a *concept's* publication velocity rather than
    one repository's.
    """

    name = "openalex"
    base_url = "https://api.openalex.org"
    min_interval = 0.3
    ttl = 21600

    @staticmethod
    def _mailto() -> str:
        """Pull a contact address out of ARGUS_USER_AGENT for the polite pool."""
        ua = os.getenv("ARGUS_USER_AGENT", "")
        match = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", ua)
        return match.group(0) if match else ""

    def _params(self, extra: dict[str, Any]) -> dict[str, Any]:
        mail = self._mailto()
        return {**extra, **({"mailto": mail} if mail else {})}

    def works(self, search: str, *, since: str | None = None,
              per_page: int = 50) -> list[dict[str, Any]]:
        filters = [f"from_publication_date:{since}"] if since else []
        params = self._params({"search": search, "per-page": min(per_page, 200)})
        if filters:
            params["filter"] = ",".join(filters)
        return self.get("/works", params).get("results", [])

    def yearly_counts(self, search: str) -> list[dict[str, Any]]:
        """Works per year for a search — the raw velocity series.

        `group_by` returns counts without paging through the works themselves,
        which is the difference between one request and two hundred.
        """
        params = self._params({"search": search, "group_by": "publication_year"})
        rows = self.get("/works", params).get("group_by", [])
        return sorted(
            ({"year": int(r["key"]), "count": r["count"]}
             for r in rows if str(r.get("key", "")).isdigit()),
            key=lambda r: r["year"],
        )

    def velocity(self, search: str, *, years: int = 6) -> dict[str, Any]:
        """Latest complete year against the trailing mean, in standard deviations.

        Mirrors `Gdelt.velocity` deliberately: the same z-score shape, so a
        narrative in the news and an idea in the literature are read on one
        scale. The current year is dropped -- it is always partial, and
        including it manufactures a fake deceleration every January.
        """
        series = [r for r in self.yearly_counts(search) if r["year"] < date.today().year]
        series = series[-years:]
        if len(series) < 4:
            return {"query": search, "n": len(series), "z": None}
        values = [r["count"] for r in series]
        latest, prior = values[-1], values[:-1]
        mean = sum(prior) / len(prior)
        sd = (sum((v - mean) ** 2 for v in prior) / len(prior)) ** 0.5
        return {
            "query": search,
            "n": len(series),
            "years": [r["year"] for r in series],
            "counts": values,
            "latest": latest,
            "mean": round(mean, 2),
            "z": round((latest - mean) / sd, 2) if sd else None,
        }


class ArXiv(Source):
    """arXiv Atom API. Keyless, XML, rate-limited to roughly one call every 3s.

    The earliest layer in the stack and the noisiest. Use it to read what a
    named group is actually publishing; use OpenAlex to measure a field.
    """

    name = "arxiv"
    base_url = "http://export.arxiv.org/api/query"
    min_interval = 3.0
    ttl = 21600

    _NS = {"a": "http://www.w3.org/2005/Atom"}

    def search(self, query: str, *, max_results: int = 50,
               sort_by: str = "submittedDate") -> list[dict[str, Any]]:
        raw = self.get_text("", {
            "search_query": query,
            "max_results": min(max_results, 200),
            "sortBy": sort_by,
            "sortOrder": "descending",
        })
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return []
        out = []
        for entry in root.findall("a:entry", self._NS):
            def text(tag: str) -> str:
                node = entry.find(f"a:{tag}", self._NS)
                return (node.text or "").strip() if node is not None else ""

            out.append({
                "id": text("id"),
                "title": " ".join(text("title").split()),
                "published": text("published")[:10],
                "updated": text("updated")[:10],
                "summary": " ".join(text("summary").split())[:600],
                "authors": [
                    (a.find("a:name", self._NS).text or "")
                    for a in entry.findall("a:author", self._NS)
                    if a.find("a:name", self._NS) is not None
                ],
            })
        return out
