"""Regime classification — pure, so testable without a network."""

from __future__ import annotations

import unittest

from argus import regime as R


class Classify(unittest.TestCase):
    CALM = dict(sofr=4.30, iorb=4.40, rrp_bn=400.0, hy_oas_bp=300.0, curve_10y2y=0.80)

    def test_a_benign_tape_reads_risk_on_at_full_size(self):
        v = R.classify(self.CALM)
        self.assertEqual(v["composite"], "risk_on")
        self.assertEqual(v["sizing_multiplier"], 1.0)
        self.assertEqual(v["liquidity"]["state"], "abundant")
        self.assertEqual(v["credit"]["state"], "calm")
        self.assertEqual(v["confidence"], "high")

    def test_stressed_credit_forces_crisis_regardless_of_the_rest(self):
        v = R.classify({**self.CALM, "hy_oas_bp": 620.0})
        self.assertEqual(v["composite"], "crisis")
        self.assertEqual(v["sizing_multiplier"], 0.25)

    def test_sofr_above_iorb_reads_as_reserve_scarcity(self):
        v = R.classify({**self.CALM, "sofr": 4.48, "iorb": 4.40})
        self.assertEqual(v["liquidity"]["state"], "scarce")
        self.assertIn("above IORB", v["liquidity"]["reading"])

    def test_a_drained_rrp_downgrades_liquidity_even_below_the_floor(self):
        v = R.classify({**self.CALM, "rrp_bn": 10.0})
        self.assertEqual(v["liquidity"]["state"], "draining")

    def test_fast_widening_counts_even_from_a_low_level(self):
        v = R.classify({**self.CALM, "hy_oas_bp": 330.0, "hy_oas_change_bp": 70.0})
        self.assertEqual(v["credit"]["state"], "widening")
        self.assertIn("rate of change", v["credit"]["reading"])

    def test_an_inverted_curve_is_labelled_and_its_break_is_stated(self):
        v = R.classify({**self.CALM, "curve_10y2y": -0.35})
        self.assertEqual(v["curve"]["state"], "inverted")
        self.assertTrue(any("turns positive" in b for b in v["breaks_if"]))

    def test_every_regime_states_what_would_break_it(self):
        for override in [{}, {"hy_oas_bp": 620.0}, {"sofr": 4.5},
                         {"curve_10y2y": -0.2}, {"rrp_bn": 5.0}]:
            v = R.classify({**self.CALM, **override})
            self.assertTrue(v["breaks_if"], f"no invalidation stated for {override}")

    def test_missing_inputs_lower_confidence_rather_than_being_hidden(self):
        v = R.classify({"curve_10y2y": 0.5})
        self.assertEqual(v["confidence"], "low")
        self.assertIn("sofr", v["missing_inputs"])
        self.assertIn("hy_oas_bp", v["missing_inputs"])

    def test_an_empty_reading_set_does_not_raise(self):
        v = R.classify({})
        self.assertIn(v["composite"], R.COMPOSITES)
        self.assertEqual(v["confidence"], "low")

    def test_sizing_multipliers_are_monotonic_in_severity(self):
        order = ["risk_on", "neutral", "risk_off", "crisis"]
        values = [R.REGIME_SIZING[k] for k in order]
        self.assertEqual(values, sorted(values, reverse=True))
