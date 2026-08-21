"""Cached, rate-limited clients for the OBSERVE layer.

Every client subclasses `Source` (see `base.py`), which supplies polite rate
limiting, retry-with-backoff, and an on-disk cache. Import the clients from
this package rather than reaching into the modules directly, so the module
layout stays free to change:

    from argus.sources import DefiLlama, Fred

Keyless: DeFiLlama, TreasuryFiscal, NyFedMarkets, Gdelt, ApeWisdom, Tradestie,
Polymarket, Kalshi (public reads).
Keyed: Fred (FRED_API_KEY), RwaXyz (RWA_XYZ_API_KEY).
"""

from .base import Source, SourceError
from .macro import Fred, NyFedMarkets, TreasuryFiscal
from .narrative import ApeWisdom, Gdelt, Tradestie
from .prediction_markets import Kalshi, Polymarket
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
    # prediction markets
    "Kalshi",
    "Polymarket",
    # tokenization
    "DefiLlama",
    "RwaXyz",
]
