"""The falsifiability gate, the legacy-schema fold, and the scoring math.

The most important test in this file is `test_legacy_schema_records_are_read`.
ADR 0002 documents the day two ledger implementations disagreed on a field name
and twenty open predictions reported as zero — silently, every weekday morning,
in an automated commit. That is the failure this whole project exists to
prevent, and it arrived through a refactor, not through malice. It gets a test.
"""

from __future__ import annotations

from argus.store import ValidationError
from tests.support import StoreCase, future, past


class ValidationGate(StoreCase):
    def test_accepts_a_well_formed_prediction(self):
        p = self.add_prediction()
        self.assertEqual(len(self.L.load_state()), 1)
        self.assertIsNone(self.L.load_state()[p.id]["outcome"])

    def test_rejects_certainty(self):
        for prob in (0.0, 1.0, -0.1, 1.2):
            with self.assertRaises(ValidationError, msg=f"P={prob} accepted"):
                self.add_prediction(probability=prob)

    def test_rejects_a_past_resolve_by_date(self):
        with self.assertRaises(ValidationError):
            self.add_prediction(resolve_by=past(1))

    def test_rejects_non_iso_dates(self):
        with self.assertRaises(ValidationError):
            self.add_prediction(resolve_by="end of next year")

    def test_rejects_weasel_words_in_criteria(self):
        with self.assertRaises(ValidationError) as ctx:
            self.add_prediction(
                resolution_criteria="SPY performs significantly better than 700 by then"
            )
        self.assertIn("unadjudicable language", str(ctx.exception))

    def test_rejects_criteria_with_no_threshold_or_event(self):
        with self.assertRaises(ValidationError) as ctx:
            self.add_prediction(
                resolution_criteria="whether the index ends the year where I think it will"
            )
        self.assertIn("not adjudicable", str(ctx.exception))

    def test_rejects_a_missing_reasoning_snapshot(self):
        with self.assertRaises(ValidationError):
            self.add_prediction(reasoning="   ")

    def test_rejects_an_unknown_domain(self):
        with self.assertRaises(ValidationError):
            self.add_prediction(domain="astrology")

    def test_rejects_an_out_of_range_market_probability(self):
        with self.assertRaises(ValidationError):
            self.add_prediction(market_prob=1.0)

    def test_accepts_an_in_range_market_probability(self):
        p = self.add_prediction(market_prob=0.42)
        self.assertAlmostEqual(self.L.load_state()[p.id]["market_prob"], 0.42)


class LegacySchema(StoreCase):
    """ADR 0002's regression, pinned."""

    LEGACY = {
        "type": "prediction",
        "id": "2026-08-21-spy-770-eoy",
        "claim": "SPY closes at or above 770.00 on the final session of 2026",
        "probability": 0.55,
        "resolve_by": "2027-01-05",
        "resolution_criteria": "SPY official close >= 770.00 on the final 2026 session",
        "domain": "equities",
        "thesis": "Breadth narrow, revisions positive.",
        "logged_at": "2026-08-21T14:00:00+00:00",
        "status": "open",
    }

    def test_legacy_schema_records_are_read(self):
        """`type` instead of `kind` must not make a prediction disappear."""
        self.write_raw(self.ledger_path, self.LEGACY)
        state = self.L.load_state()
        self.assertIn("2026-08-21-spy-770-eoy", state,
                      "legacy `type` record vanished from the fold — ADR 0002 regression")
        self.assertIsNone(state["2026-08-21-spy-770-eoy"]["outcome"])

    def test_legacy_thesis_field_becomes_the_reasoning_snapshot(self):
        self.write_raw(self.ledger_path, self.LEGACY)
        rec = self.L.load_state()["2026-08-21-spy-770-eoy"]
        self.assertEqual(rec["reasoning"], "Breadth narrow, revisions positive.")

    def test_legacy_resolution_keyed_by_id_still_grades(self):
        self.write_raw(
            self.ledger_path,
            self.LEGACY,
            {"type": "resolution", "id": "2026-08-21-spy-770-eoy",
             "outcome": "yes", "notes": "closed at 781.20 per Nasdaq"},
        )
        rec = self.L.load_state()["2026-08-21-spy-770-eoy"]
        self.assertIs(rec["outcome"], True)
        self.assertEqual(rec["note"], "closed at 781.20 per Nasdaq")

    def test_new_fields_default_on_legacy_records(self):
        self.write_raw(self.ledger_path, self.LEGACY)
        rec = self.L.load_state()["2026-08-21-spy-770-eoy"]
        self.assertIsNone(rec["market_prob"])
        self.assertEqual(rec["catalyst"], "")

    def test_outcome_spellings_all_normalise(self):
        for spelling, expected in [("yes", True), ("true", True), ("hit", True),
                                   ("no", False), ("false", False), ("miss", False),
                                   ("unresolvable", "unresolvable")]:
            self.assertEqual(self.L.coerce_outcome(spelling), expected)


class Resolution(StoreCase):
    def test_resolve_records_the_outcome(self):
        p = self.add_prediction()
        self.L.resolve(p.id, True, "adjudicated against the named source")
        self.assertIs(self.L.load_state()[p.id]["outcome"], True)

    def test_a_resolved_prediction_cannot_be_re_resolved(self):
        p = self.add_prediction()
        self.L.resolve(p.id, True, "adjudicated against the named source")
        with self.assertRaises(ValueError):
            self.L.resolve(p.id, False, "changed my mind about this one")

    def test_resolving_an_unknown_id_raises(self):
        with self.assertRaises(KeyError):
            self.L.resolve("nope", True, "adjudicated against the named source")

    def test_outcome_must_be_true_false_or_unresolvable(self):
        p = self.add_prediction()
        with self.assertRaises(ValueError):
            self.L.resolve(p.id, "maybe", "adjudicated against the named source")

    def test_the_file_is_append_only(self):
        p = self.add_prediction()
        self.L.resolve(p.id, False, "adjudicated against the named source")
        lines = self.ledger_path.read_text().strip().split("\n")
        self.assertEqual(len(lines), 2, "resolution must append, never rewrite")


class Scoring(StoreCase):
    def test_brier_endpoints(self):
        self.assertAlmostEqual(self.L.brier(1.0, True), 0.0)
        self.assertAlmostEqual(self.L.brier(0.0, True), 1.0)
        self.assertAlmostEqual(self.L.brier(0.5, True), 0.25)
        self.assertAlmostEqual(self.L.brier(0.5, False), 0.25)
        self.assertAlmostEqual(self.L.brier(0.8, True), 0.04)

    def test_unresolvable_is_excluded_from_brier_and_counted_separately(self):
        hit = self.add_prediction(probability=0.9)
        bad = self.add_prediction(probability=0.6, claim="A claim that cannot be graded at all")
        self.L.resolve(hit.id, True, "adjudicated against the named source")
        self.L.resolve(bad.id, "unresolvable", "source retired the series mid-window")
        s = self.L.score()
        self.assertEqual(s["n"], 1, "unresolvable must not be graded")
        self.assertEqual(s["unresolvable"], 1)
        self.assertAlmostEqual(s["brier"], 0.01)

    def test_score_is_empty_before_any_resolution(self):
        self.add_prediction()
        self.assertEqual(self.L.score()["n"], 0)

    def test_vs_market_compares_only_the_overlapping_subset(self):
        # ARGUS right and confident where the market was wrong.
        a = self.add_prediction(probability=0.9, market_prob=0.4)
        # No market benchmark: must not enter the head-to-head at all.
        b = self.add_prediction(probability=0.1, claim="An unpriced question with no market")
        self.L.resolve(a.id, True, "adjudicated against the named source")
        self.L.resolve(b.id, True, "adjudicated against the named source")
        vm = self.L.score()["vs_market"]
        self.assertEqual(vm["n"], 1, "only benchmarked calls belong in the head-to-head")
        self.assertAlmostEqual(vm["argus_brier"], 0.01)
        self.assertAlmostEqual(vm["market_brier"], 0.36)
        self.assertLess(vm["delta"], 0)
        self.assertEqual(vm["verdict"], "edge")

    def test_vs_market_reports_no_edge_honestly(self):
        p = self.add_prediction(probability=0.3, market_prob=0.8)
        self.L.resolve(p.id, True, "adjudicated against the named source")
        vm = self.L.score()["vs_market"]
        self.assertEqual(vm["verdict"], "no edge")
        self.assertGreater(vm["delta"], 0)

    def test_vs_market_is_none_without_benchmarks(self):
        p = self.add_prediction()
        self.L.resolve(p.id, True, "adjudicated against the named source")
        self.assertIsNone(self.L.score()["vs_market"])

    def test_market_coverage_ranks_by_disagreement(self):
        self.add_prediction(probability=0.9, market_prob=0.4)
        self.add_prediction(probability=0.5, market_prob=0.48,
                            claim="A question where ARGUS agrees with the crowd")
        cov = self.L.market_coverage()
        self.assertEqual(cov["with_market"], 2)
        self.assertAlmostEqual(cov["coverage"], 1.0)
        self.assertAlmostEqual(abs(cov["disagreements"][0]["delta"]), 0.5)

    def test_calibration_buckets_stated_against_observed(self):
        for _ in range(4):
            p = self.add_prediction(probability=0.9)
            self.L.resolve(p.id, True, "adjudicated against the named source")
        miss = self.add_prediction(probability=0.9)
        self.L.resolve(miss.id, False, "adjudicated against the named source")
        row = [r for r in self.L.calibration() if r["n"] == 5][0]
        self.assertAlmostEqual(row["stated"], 0.9)
        self.assertAlmostEqual(row["observed"], 0.8)


class Audit(StoreCase):
    def _audit(self) -> int:
        """Run the audit command, swallowing its diagnostics.

        These tests assert a failing audit, so "AUDIT FAILED" on stdout is the
        expected behaviour -- but printed into a passing CI log it reads as a
        real failure to anyone scanning, which is its own small kind of
        dishonesty.
        """
        import argparse
        import contextlib
        import io

        with contextlib.redirect_stdout(io.StringIO()):
            return self.L._cmd_audit(argparse.Namespace())

    def test_audit_catches_a_hand_edited_probability(self):
        self.write_raw(self.ledger_path, {**LegacySchema.LEGACY, "probability": 1.0})
        self.assertEqual(self._audit(), 1)

    def test_audit_catches_a_resolution_with_no_prediction(self):
        self.write_raw(self.ledger_path,
                       {"kind": "resolution", "prediction_id": "ghost", "outcome": True})
        self.assertEqual(self._audit(), 1)

    def test_audit_passes_on_a_clean_ledger(self):
        self.add_prediction()
        self.assertEqual(self._audit(), 0)
