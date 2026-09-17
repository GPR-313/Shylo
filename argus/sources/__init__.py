"""Cached, rate-limited clients for the OBSERVE layer.

Every client subclasses `Source` (see `base.py`), which supplies polite rate
limiting, retry-with-backoff, an on-disk cache, and stale-cache fallback so a
scheduled run degrades instead of dying. Import from this package rather than
reaching into the modules, so the layout stays free to change:

    from argus.sources import DefiLlama, Fred, FederalRegister

Coverage against the ten-domain table in `README.md`:

| Domain              | Module                | Key needed            |
|---------------------|-----------------------|-----------------------|
| macro & rates       | `macro`               | FRED_API_KEY (1 of 3) |
| crypto/tokenization | `tokenization`        | RWA_XYZ_API_KEY (1/2) |
| social & culture    | `narrative`           | none                  |
| policy & geopolitics| `policy`              | CONGRESS_API_KEY (1/2)|
| science             | `science`             | none                  |
| equities positioning| `positioning`         | none (UA required)    |
| calibration bench   | `prediction_markets`  | none for public reads |

Not covered here on purpose: company fundamentals and filing *contents*, which
the `edgar` and FMP connectors already serve. ADR 0002 -- a second path to the
same numbers is a way to get two answers and no way to choose.
"""

from .base import Source, SourceError
from .macro import Fred, NyFedMarkets, TreasuryFiscal
from .narrative import ApeWisdom, Gdelt, Tradestie, WikipediaPageviews
from .policy import Congress, FederalRegister
from .positioning import EdgarDailyIndex
from .prediction_markets import Kalshi, Polymarket
from .science import ArXiv, ClinicalTrials, OpenAlex
from .tokenization import DefiLlama, RwaXyz

__all__ = [
    "Source",
    "SourceError",
    # macro
    "Fred",
    "NyFedMarkets",
    "TreasuryFiscal",
    # narrative
    "ApeWisdom",
    "Gdelt",
    "Tradestie",
    "WikipediaPageviews",
    # policy
    "Congress",
    "FederalRegister",
    # positioning
    "EdgarDailyIndex",
    # prediction markets
    "Kalshi",
    "Polymarket",
    # science
    "ArXiv",
    "ClinicalTrials",
    "OpenAlex",
    # tokenization
    "DefiLlama",
    "RwaXyz",
]
