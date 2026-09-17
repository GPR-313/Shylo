"""The thesis gate — mechanism, kill criteria, and the weld to the ledger.

The weld is the point of this module: a thesis that is not attached to a live,
falsifiable prediction cannot be killed on schedule, and will quietly outlive
the evidence against it. `RequiresALivePrediction` pins that.
"""

from __future__ import annotations

from argus.store import ValidationError
from tests.support import StoreCase


class MechanismGate(StoreCase):
    def test_accepts_a_real_causal_chain(self):
        p = self.add_prediction()
        t = self.add_thesis([p.id])
        self.assertEqual(self.T.load_state()[t.id]["stage"], "acceleration")

    def test_rejects_a_mechanism_that_is_merely_a_description(self):
        p = self.add_prediction()
        with self.assertRaises(ValidationError) as ctx:
            self.add_thesis(
                [p.id],
                mechanism=("Tokenization is a large and growing market with many "
                           "institutional participants and significant momentum behind it."),
            )
        self.assertIn("causal chain", str(ctx.exception))

    def test_rejects_a_mechanism_too_short_to_be_a_chain(self):
        p = self.add_prediction()
        with self.assertRaises(ValidationError):
            self.add_thesis([p.id], mechanism="Rates drive it.")

    def test_rejects_missing_kill_criteria(self):
        p = self.add_prediction()
        with self.assertRaises(ValidationError) as ctx:
            self.add_thesis([p.id], kill="it fails")
        self.assertIn("kill criteria", str(ctx.exception))

    def test_rejects_an_unknown_stage(self):
        p = self.add_prediction()
        with self.assertRaises(ValidationError):
            self.add_thesis([p.id], stage="hype")


class RequiresALivePrediction(StoreCase):
    def test_rejects_a_thesis_with_no_prediction_attached(self):
        with self.assertRaises(ValidationError) as ctx:
            self.add_thesis([])
        self.assertIn("no prediction_ids", str(ctx.exception))

    def test_rejects_a_prediction_id_that_is_not_in_the_ledger(self):
        with self.assertRaises(ValidationError) as ctx:
            self.add_thesis(["does-not-exist"])
        self.assertIn("not in the ledger", str(ctx.exception))

    def test_a_thesis_whose_calls_have_all_resolved_shows_as_orphaned(self):
        p = self.add_prediction()
        t = self.add_thesis([p.id])
        self.assertEqual(self.T.orphans()["theses_with_no_live_call"], [])
        self.L.resolve(p.id, True, "adjudicated against the named source")
        self.assertIn(t.id, self.T.orphans()["theses_with_no_live_call"])

    def test_open_predictions_with_no_thesis_are_reported(self):
        loose = self.add_prediction()
        self.assertIn(loose.id, self.T.orphans()["predictions_with_no_thesis"])


class PayoffFields(StoreCase):
    def test_win_without_loss_is_rejected(self):
        p = self.add_prediction()
        with self.assertRaises(ValidationError) as ctx:
            self.add_thesis([p.id], win=1.8)
        self.assertIn("both", str(ctx.exception))

    def test_negative_payoffs_are_rejected(self):
        p = self.add_prediction()
        with self.assertRaises(ValidationError):
            self.add_thesis([p.id], win=1.8, loss=-0.6)


class Lifecycle(StoreCase):
    def test_stage_change_is_recorded_with_its_evidence(self):
        p = self.add_prediction()
        t = self.add_thesis([p.id], stage="early_adopter")
        self.T.set_stage(t.id, "acceleration",
                         "DTCC named 40+ live production counterparties on 2026-07-15")
        rec = self.T.load_state()[t.id]
        self.assertEqual(rec["stage"], "acceleration")
        self.assertEqual(len(rec["stage_history"]), 1)
        self.assertEqual(rec["stage_history"][0]["from"], "early_adopter")

    def test_a_stage_change_without_evidence_is_rejected(self):
        p = self.add_prediction()
        t = self.add_thesis([p.id])
        with self.assertRaises(ValidationError):
            self.T.set_stage(t.id, "consensus", "felt right")

    def test_restaging_to_the_current_stage_is_rejected(self):
        p = self.add_prediction()
        t = self.add_thesis([p.id], stage="consensus")
        with self.assertRaises(ValidationError):
            self.T.set_stage(t.id, "consensus", "nothing changed but logging it anyway")

    def test_undercutting_evidence_surfaces_the_thesis(self):
        p = self.add_prediction()
        t = self.add_thesis([p.id])
        self.assertEqual(self.T.undercut(), [])
        self.T.add_evidence(t.id, "Issuer CFO said AUM-based revenue is not material",
                            direction="undercuts")
        self.assertEqual([x["id"] for x in self.T.undercut()], [t.id])

    def test_later_supporting_evidence_clears_the_flag(self):
        p = self.add_prediction()
        t = self.add_thesis([p.id])
        self.T.add_evidence(t.id, "Issuer CFO said AUM revenue is not material", "undercuts")
        self.T.add_evidence(t.id, "Follow-up 8-K restated the fee line upward", "supports")
        self.assertEqual(self.T.undercut(), [])

    def test_closing_requires_a_post_mortem(self):
        p = self.add_prediction()
        t = self.add_thesis([p.id])
        with self.assertRaises(ValidationError):
            self.T.close(t.id, "killed", "wrong")
        self.T.close(t.id, "killed",
                     "Mechanism was right, the revenue link was not; watch the fee "
                     "line rather than AUM next time.")
        self.assertEqual(self.T.load_state()[t.id]["closed"], "killed")

    def test_a_closed_thesis_cannot_be_restaged(self):
        p = self.add_prediction()
        t = self.add_thesis([p.id])
        self.T.close(t.id, "played_out",
                     "Rerate happened on the collateral ruling; exited into consensus.")
        with self.assertRaises(ValidationError):
            self.T.set_stage(t.id, "exhaustion", "it kept running after we closed it")

    def test_duplicate_ids_are_refused_rather_than_overwritten(self):
        p = self.add_prediction()
        t = self.add_thesis([p.id])
        with self.assertRaises(ValidationError):
            self.add_thesis([p.id], id=t.id)

    def test_the_store_is_append_only(self):
        p = self.add_prediction()
        t = self.add_thesis([p.id])
        self.T.set_stage(t.id, "consensus", "Coverage initiated at three bulge brackets")
        self.T.add_evidence(t.id, "Short interest halved over the quarter")
        self.assertEqual(len(self.theses_path.read_text().strip().split("\n")), 3)


class Linking(StoreCase):
    def test_a_catalyst_can_be_attached_after_the_thesis_is_opened(self):
        p = self.add_prediction()
        t = self.add_thesis([p.id])
        c = self.add_catalyst()
        self.T.link(t.id, catalyst_ids=[c.id], note="discovered after opening")
        self.assertIn(c.id, self.T.load_state()[t.id]["catalyst_ids"])

    def test_linking_an_unknown_catalyst_is_refused_at_write_time(self):
        p = self.add_prediction()
        t = self.add_thesis([p.id])
        with self.assertRaises(ValidationError) as ctx:
            self.T.link(t.id, catalyst_ids=["no-such-catalyst"])
        self.assertIn("unknown catalysts", str(ctx.exception))

    def test_opening_with_an_unknown_catalyst_is_refused(self):
        p = self.add_prediction()
        with self.assertRaises(ValidationError) as ctx:
            self.add_thesis([p.id], catalyst_ids=["no-such-catalyst"])
        self.assertIn("not in the calendar", str(ctx.exception))

    def test_links_accumulate_without_duplicating(self):
        p = self.add_prediction()
        t = self.add_thesis([p.id], tickers=["BK"])
        self.T.link(t.id, tickers=["BK", "CPU"])
        self.assertEqual(self.T.load_state()[t.id]["tickers"], ["BK", "CPU"])

    def test_an_empty_link_is_refused(self):
        p = self.add_prediction()
        t = self.add_thesis([p.id])
        with self.assertRaises(ValidationError):
            self.T.link(t.id)

    def test_linking_an_unknown_thesis_raises(self):
        with self.assertRaises(KeyError):
            self.T.link("ghost", tickers=["BK"])
