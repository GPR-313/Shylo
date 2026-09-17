"""Source-layer parsing that can be tested without a network.

Most of `argus/sources/` is thin REST plumbing whose correctness depends on a
live endpoint. The parsing that does *not* — the EDGAR fixed-width daily index,
which breaks on company names with spaces and form types like `SC 13D/A` — is
exactly where a silent bug would go unnoticed, so it is pinned here.

These are the only tests in the suite that need `requests`, because importing
any source client pulls in `argus/sources/base.py`. They skip rather than error
when it is absent, so `python3 -m unittest discover -s tests` still passes on a
bare interpreter — the spine's stores, scoring, sizing, and graph are stdlib
only, and that property is worth keeping testable rather than merely claimed.
CI runs the suite both ways for exactly that reason.
"""

from __future__ import annotations

import unittest

try:
    from argus.sources.base import SourceError
    from argus.sources.positioning import EdgarDailyIndex

    HAS_REQUESTS = True
except ImportError:                      # pragma: no cover - dependency-free run
    HAS_REQUESTS = False
    SourceError = Exception
    EdgarDailyIndex = None

INDEX = """Description:           Daily Index of EDGAR Dissemination Feed by Form Type
Last Data Received:    September 17, 2026

Form Type   Company Name                                                  CIK         Date Filed  File Name
---------------------------------------------------------------------------------------------------------
4           NVIDIA CORP                                                   1045810     20260917    edgar/data/1045810/0001.txt
4           NVIDIA CORP                                                   1045810     20260917    edgar/data/1045810/0004.txt
SC 13D/A    ELLIOTT INVESTMENT MANAGEMENT L.P.                            1791786     20260917    edgar/data/1791786/0002.txt
8-K         Berkshire Hathaway Inc                                        1067983     20260917    edgar/data/1067983/0003.txt
"""


@unittest.skipUnless(HAS_REQUESTS, "requests not installed; argus.sources needs it")
class DailyIndexParsing(unittest.TestCase):
    def test_parses_every_data_row(self):
        self.assertEqual(len(EdgarDailyIndex._parse(INDEX)), 4)

    def test_company_names_with_spaces_survive(self):
        rows = EdgarDailyIndex._parse(INDEX)
        self.assertEqual(rows[3]["company"], "Berkshire Hathaway Inc")

    def test_form_types_containing_spaces_survive(self):
        rows = EdgarDailyIndex._parse(INDEX)
        self.assertEqual(rows[2]["form_type"], "SC 13D/A")
        self.assertEqual(rows[2]["company"], "ELLIOTT INVESTMENT MANAGEMENT L.P.")

    def test_the_separator_rule_is_not_treated_as_data(self):
        self.assertTrue(all(r["cik"].isdigit() for r in EdgarDailyIndex._parse(INDEX)))

    def test_a_missing_header_raises_rather_than_returning_garbage(self):
        with self.assertRaises(SourceError):
            EdgarDailyIndex._parse("just some text\nwith no header at all\n")

    def test_quarter_maths(self):
        from datetime import date
        for month, quarter in [(1, 1), (3, 1), (4, 2), (6, 2), (7, 3), (9, 3),
                               (10, 4), (12, 4)]:
            self.assertEqual(EdgarDailyIndex._quarter(date(2026, month, 1)), quarter)
