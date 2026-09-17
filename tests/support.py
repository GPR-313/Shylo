"""Shared fixtures — every test runs against a throwaway store, never the book.

The real `data/ledger/predictions.jsonl` is append-only and its git history is
the audit trail. A test that writes to it would corrupt the product it exists
to protect, so `StoreCase` repoints every module path at a temp directory.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path


def future(days: int = 90) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def past(days: int = 5) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


class StoreCase(unittest.TestCase):
    """Repoints ledger, theses, and catalyst stores into a temp dir."""

    def setUp(self) -> None:
        from argus import catalysts as C
        from argus import ledger as L
        from argus import theses as T

        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

        self.ledger_path = self.tmp / "predictions.jsonl"
        self.theses_path = self.tmp / "theses.jsonl"
        self.catalysts_path = self.tmp / "catalysts.jsonl"

        for module, attr, value in (
            (L, "LEDGER_PATH", self.ledger_path),
            (T, "THESES_PATH", self.theses_path),
            (C, "CATALYSTS_PATH", self.catalysts_path),
        ):
            original = getattr(module, attr)
            setattr(module, attr, value)
            self.addCleanup(setattr, module, attr, original)

        self.L, self.T, self.C = L, T, C

    # -- convenience builders ---------------------------------------------

    def add_prediction(self, **over):
        kwargs = dict(
            claim="SPY closes at or above 700.00 on the final session of the year",
            probability=0.55,
            resolve_by=future(120),
            resolution_criteria="SPY official closing price >= 700.00 per Nasdaq on that date",
            domain="equities",
            reasoning="Breadth is narrow but earnings revisions are still positive.",
        )
        kwargs.update(over)
        return self.L.add(**kwargs)

    def add_thesis(self, prediction_ids, **over):
        kwargs = dict(
            title="Tokenized collateral relief reprices the custody layer",
            mechanism=(
                "DTC granting tokenized entitlements collateral value forces dealers to "
                "post them against Net Debit Caps, which drives real balance-sheet "
                "demand for regulated custody rather than pilot volume."
            ),
            kill="DTC defers or denies collateral-value relief past 2027-12-31",
            domain="tokenization",
            stage="acceleration",
            prediction_ids=prediction_ids,
        )
        kwargs.update(over)
        return self.T.open_thesis(**kwargs)

    def add_catalyst(self, **over):
        kwargs = dict(
            title="DTC tokenization service general availability",
            date=future(30),
            resolves="Whether DTC ships general availability or extends the pilot again",
            domain="tokenization",
        )
        kwargs.update(over)
        return self.C.add(**kwargs)

    def write_raw(self, path: Path, *records: dict) -> None:
        with path.open("a", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec) + "\n")
