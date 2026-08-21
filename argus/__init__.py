"""ARGUS — trend-intelligence agent.

The package is deliberately thin: `argus.ledger` is the prediction ledger and
the only writer to `data/ledger/predictions.jsonl`; `argus.sources` holds the
cached, rate-limited REST clients that feed the OBSERVE layer.
"""

__version__ = "0.2.0"
