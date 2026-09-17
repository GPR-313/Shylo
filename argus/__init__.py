"""ARGUS — trend-intelligence agent.

Four append-only stores and the analysis built over them. All stdlib, so the
spine keeps working when `requirements.txt` rots; `argus.sources` is the only
part that needs `requests`.

    argus.store       append-only event store -- the substrate under all four
    argus.ledger      predictions; the only writer to data/ledger/predictions.jsonl
    argus.theses      thesis registry; mechanism, kill criteria, lifecycle stage
    argus.catalysts   dated catalyst calendar; anchors every resolve-by date
    argus.edge        expected value, Kelly sizing, the ruin guard
    argus.graph       the relation graph -- concentration, cut points, bridges
    argus.regime      macro regime classifier with stated invalidation
    argus.sources     cached, rate-limited REST clients for the OBSERVE layer

Front door: `python -m argus status | doctor | agenda`.
"""

__version__ = "0.3.0"
