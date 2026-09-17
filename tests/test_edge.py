"""Sizing arithmetic, pinned against hand-computed values.

Every number in this file was derived by hand from the formula in the
docstring, not captured from a run. A sizing bug is the kind that loses real
money quietly, so the expected values are independent of the implementation.
"""

from __future__ import annotations

import unittest

from argus import edge as E


class Arithmetic(unittest.TestCase):
    def test_expected_value(self):
        # 0.6 * 2.0 - 0.4 * 1.0 = 0.8
        self.assertAlmostEqual(E.expected_value(0.6, 2.0, 1.0), 0.8)
        # A fair coin on even money is worth exactly nothing.
        self.assertAlmostEqual(E.expected_value(0.5, 1.0, 1.0), 0.0)

    def test_breakeven_probability(self):
        # 2:1 payoff needs one win in three.
        self.assertAlmostEqual(E.breakeven_probability(2.0, 1.0), 1 / 3)
        self.assertAlmostEqual(E.breakeven_probability(1.0, 1.0), 0.5)
        # Risking 0.6 to make 1.8 -> 0.6 / 2.4
        self.assertAlmostEqual(E.breakeven_probability(1.8, 0.6), 0.25)

    def test_edge_is_probability_points_over_breakeven(self):
        self.assertAlmostEqual(E.edge(0.5, 2.0, 1.0), 0.5 - 1 / 3)
        self.assertLess(E.edge(0.3, 2.0, 1.0), 0)

    def test_kelly_matches_the_classic_form(self):
        # loss = 1 reduces f* = (p*b - q) / b. p=0.6, b=2 -> (1.2-0.4)/2 = 0.4
        self.assertAlmostEqual(E.kelly_fraction(0.6, 2.0, 1.0), 0.4)
        # f* = (0.62*1.8 - 0.38*0.6) / (1.8*0.6) = 0.888 / 1.08
        self.assertAlmostEqual(E.kelly_fraction(0.62, 1.8, 0.6), 0.888 / 1.08)

    def test_kelly_floors_at_zero_on_a_negative_edge(self):
        self.assertEqual(E.kelly_fraction(0.2, 1.0, 1.0), 0.0)

    def test_ev_per_risk_normalises_by_the_downside(self):
        # Same shape, ten times the stake: identical EV per unit at risk.
        self.assertAlmostEqual(E.ev_per_risk(0.6, 2.0, 1.0),
                               E.ev_per_risk(0.6, 20.0, 10.0))

    def test_rejects_impossible_inputs(self):
        for args in [(0.0, 1.0, 1.0), (1.0, 1.0, 1.0), (0.5, 0.0, 1.0), (0.5, 1.0, -1.0)]:
            with self.assertRaises(E.SizingError):
                E.expected_value(*args)


class MarketEdge(unittest.TestCase):
    def test_takes_the_yes_side_when_argus_is_above_the_market(self):
        row = E.market_edge(0.62, 0.45)
        self.assertEqual(row["side"], "yes")
        # Buying at 0.45 pays (1 - 0.45)/0.45
        self.assertAlmostEqual(row["payoff_if_right"], 0.55 / 0.45, places=4)
        # EV = 0.62 * 1.2222 - 0.38
        self.assertAlmostEqual(row["ev_per_unit_staked"], 0.62 * (0.55 / 0.45) - 0.38,
                               places=3)

    def test_flips_to_the_no_side_when_argus_is_below_the_market(self):
        row = E.market_edge(0.30, 0.80)
        self.assertEqual(row["side"], "no")
        self.assertAlmostEqual(row["price"], 0.20)
        self.assertAlmostEqual(row["argus_p_on_side"], 0.70)
        self.assertGreater(row["ev_per_unit_staked"], 0)

    def test_agreement_with_the_market_yields_no_ev(self):
        row = E.market_edge(0.50, 0.50)
        self.assertAlmostEqual(row["ev_per_unit_staked"], 0.0, places=6)
        self.assertAlmostEqual(row["disagreement_pts"], 0.0)

    def test_disagreement_is_symmetric(self):
        self.assertAlmostEqual(E.market_edge(0.7, 0.4)["disagreement_pts"],
                               E.market_edge(0.4, 0.7)["disagreement_pts"])


class Sizing(unittest.TestCase):
    def test_the_position_cap_binds_and_says_so(self):
        row = E.size(0.62, 1.8, 0.6, stage="acceleration", cap=0.05)
        self.assertAlmostEqual(row["size_fraction"], 0.05)
        self.assertIn("position cap", row["binding_constraint"])

    def test_fractional_kelly_binds_when_the_cap_is_generous(self):
        row = E.size(0.55, 1.0, 1.0, stage="acceleration", cap=0.50, kelly_frac=0.25)
        # full kelly (0.55*1 - 0.45*1)/1 = 0.10 -> quarter = 0.025
        self.assertAlmostEqual(row["full_kelly"], 0.10)
        self.assertAlmostEqual(row["size_fraction"], 0.025)
        self.assertIn("fractional Kelly", row["binding_constraint"])

    def test_stage_scales_the_same_bet(self):
        kwargs = dict(cap=0.50, kelly_frac=0.25)
        accel = E.size(0.55, 1.0, 1.0, stage="acceleration", **kwargs)["size_fraction"]
        consensus = E.size(0.55, 1.0, 1.0, stage="consensus", **kwargs)["size_fraction"]
        fringe = E.size(0.55, 1.0, 1.0, stage="fringe", **kwargs)["size_fraction"]
        self.assertAlmostEqual(consensus, accel * 0.40)
        self.assertAlmostEqual(fringe, accel * 0.25)
        self.assertLess(consensus, accel)

    def test_reversal_stage_takes_no_long_exposure(self):
        row = E.size(0.9, 5.0, 1.0, stage="reversal", cap=0.5)
        self.assertEqual(row["size_fraction"], 0.0)
        self.assertIn("reversal", row["binding_constraint"])

    def test_negative_expected_value_sizes_to_zero(self):
        row = E.size(0.20, 1.0, 1.0, stage="acceleration", cap=0.5)
        self.assertEqual(row["size_fraction"], 0.0)
        self.assertIn("negative expected value", row["binding_constraint"])

    def test_worst_case_loss_is_reported_in_bankroll_terms(self):
        row = E.size(0.62, 1.8, 0.6, cap=0.05, bankroll=100_000)
        # 5% of bankroll, losing 0.6 of the position
        self.assertAlmostEqual(row["worst_case_loss"], 0.05 * 0.6 * 100_000)

    def test_unknown_stage_is_rejected_not_defaulted(self):
        with self.assertRaises(E.SizingError):
            E.size(0.6, 2.0, 1.0, stage="vibes")


class ClusterRuinGuard(unittest.TestCase):
    """Five names on one catalyst chain are one bet, and get sized as one."""

    def _five(self):
        return [E.size(0.62, 1.8, 0.6, cap=0.05) for _ in range(5)]

    def test_a_correlated_group_is_scaled_to_the_joint_cap(self):
        out = E.size_cluster(self._five(), cluster_cap=0.08)
        # 5 positions * 5% * 0.6 loss = 15% joint worst case, over an 8% limit.
        self.assertAlmostEqual(out["joint_worst_case_before"], 0.15)
        self.assertAlmostEqual(out["joint_worst_case_after"], 0.08, places=4)
        self.assertTrue(out["binding"])

    def test_scaling_preserves_relative_conviction(self):
        positions = [E.size(0.62, 1.8, 0.6, cap=0.05),
                     E.size(0.55, 1.0, 1.0, cap=0.05, kelly_frac=0.25)]
        before = positions[0]["size_fraction"] / positions[1]["size_fraction"]
        out = E.size_cluster(positions, cluster_cap=0.01)
        after = (out["positions"][0]["cluster_size_fraction"]
                 / out["positions"][1]["cluster_size_fraction"])
        self.assertAlmostEqual(before, after, places=3)

    def test_an_uncorrelated_group_inside_the_cap_is_left_alone(self):
        out = E.size_cluster([E.size(0.62, 1.8, 0.6, cap=0.05)], cluster_cap=0.50)
        self.assertEqual(out["scale"], 1.0)
        self.assertFalse(out["binding"])

    def test_an_empty_cluster_does_not_divide_by_zero(self):
        out = E.size_cluster([], cluster_cap=0.08)
        self.assertEqual(out["scale"], 1.0)
        self.assertEqual(out["positions"], [])
