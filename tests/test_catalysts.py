"""The catalyst calendar and the EP-000b enforcement it exists to provide."""

from __future__ import annotations

from datetime import date, timedelta

from argus.store import ValidationError
from tests.support import StoreCase, future, past


class Gate(StoreCase):
    def test_accepts_a_dated_catalyst_that_settles_something(self):
        c = self.add_catalyst()
        self.assertIn(c.id, self.C.load_state())

    def test_rejects_a_catalyst_that_settles_nothing(self):
        with self.assertRaises(ValidationError) as ctx:
            self.add_catalyst(resolves="big day")
        self.assertIn("resolves", str(ctx.exception))

    def test_rejects_a_bad_date(self):
        with self.assertRaises(ValidationError):
            self.add_catalyst(date="October-ish")

    def test_rejects_an_unknown_precision(self):
        with self.assertRaises(ValidationError):
            self.add_catalyst(precision="vague")

    def test_the_id_is_derived_from_date_and_title(self):
        c = self.add_catalyst(date="2026-10-31", title="DTC general availability launch")
        self.assertTrue(c.id.startswith("2026-10-31-dtc"))

    def test_duplicates_are_refused(self):
        c = self.add_catalyst()
        with self.assertRaises(ValidationError):
            self.add_catalyst(date=c.date, title=c.title)


class Anchoring(StoreCase):
    """A resolve-by date should be set by an event, not by tidiness."""

    def test_a_day_precision_catalyst_anchors_a_nearby_date(self):
        target = date.today() + timedelta(days=60)
        self.add_catalyst(date=target.isoformat())
        hits = self.C.anchors_for(target.isoformat(), window=21)
        self.assertEqual(len(hits), 1)

    def test_a_distant_catalyst_does_not_anchor(self):
        self.add_catalyst(date=future(10))
        self.assertEqual(self.C.anchors_for(future(200), window=21), [])

    def test_quarter_precision_gets_more_slack_than_a_scheduled_day(self):
        target = date.today() + timedelta(days=90)
        loose = (target - timedelta(days=40)).isoformat()
        self.add_catalyst(date=loose, precision="quarter",
                          title="Tokenized private credit share crosses the category line")
        self.assertEqual(len(self.C.anchors_for(target.isoformat(), window=21)), 1)
        # The same date at day precision is too far away to have set it.
        self.C.CATALYSTS_PATH.unlink()
        self.add_catalyst(date=loose, precision="day",
                          title="Tokenized private credit share crosses the category line")
        self.assertEqual(self.C.anchors_for(target.isoformat(), window=21), [])


class Orphans(StoreCase):
    def test_an_unanchored_prediction_is_flagged(self):
        p = self.add_prediction(resolve_by=future(200))
        self.assertEqual([r["id"] for r in self.C.orphans()], [p.id])

    def test_an_explicit_catalyst_link_clears_the_flag(self):
        c = self.add_catalyst()
        p = self.add_prediction(resolve_by=future(200), catalyst=c.id)
        self.assertEqual(self.C.orphans(), [])

    def test_a_nearby_catalyst_clears_the_flag_without_an_explicit_link(self):
        target = date.today() + timedelta(days=100)
        self.add_catalyst(date=target.isoformat())
        self.add_prediction(resolve_by=target.isoformat())
        self.assertEqual(self.C.orphans(), [])

    def test_round_number_dates_sort_first(self):
        year_end = f"{date.today().year + 1}-12-31"
        self.add_prediction(resolve_by=future(45),
                            claim="A claim anchored to an ordinary weekday date")
        self.add_prediction(resolve_by=year_end,
                            claim="A claim anchored to a tidy year-end boundary")
        rows = self.C.orphans()
        self.assertTrue(rows[0]["round_date"], "round-number dates are the worst case")

    def test_resolved_predictions_are_not_flagged(self):
        p = self.add_prediction(resolve_by=future(200))
        self.L.resolve(p.id, True, "adjudicated against the named source")
        self.assertEqual(self.C.orphans(), [])


class Closing(StoreCase):
    def test_upcoming_respects_the_window(self):
        self.add_catalyst(date=future(10))
        self.add_catalyst(date=future(100), title="A second scheduled event next quarter")
        self.assertEqual(len(self.C.upcoming(days=30)), 1)
        self.assertEqual(len(self.C.upcoming(days=365)), 2)

    def test_a_past_catalyst_with_no_outcome_is_overdue(self):
        self.write_raw(self.catalysts_path, {
            "kind": "catalyst", "id": "stale", "title": "An event that already happened",
            "date": past(3), "resolves": "whether the thing happened on schedule",
            "domain": "macro", "precision": "day", "prediction_ids": [],
            "thesis_ids": [], "source": "", "created_at": "2026-01-01T00:00:00+00:00"})
        self.assertEqual([c["id"] for c in self.C.overdue()], ["stale"])

    def test_resolving_clears_it_and_cannot_be_repeated(self):
        c = self.add_catalyst()
        self.C.resolve(c.id, "DTCC announced general availability on schedule")
        self.assertEqual(self.C.overdue(), [])
        with self.assertRaises(ValidationError):
            self.C.resolve(c.id, "it happened again somehow")

    def test_resolving_an_unknown_catalyst_raises(self):
        with self.assertRaises(KeyError):
            self.C.resolve("ghost", "something occurred that nobody scheduled")
