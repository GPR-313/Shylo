"""The append-only substrate: ids, folding, and tolerance of a damaged file."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from argus import store


class Helpers(unittest.TestCase):
    def test_slugify_is_stable_and_url_safe(self):
        self.assertEqual(store.slugify("DTC Tokenized Entitlements: Collateral Value?"),
                         "dtc-tokenized-entitlements-collateral-value")
        self.assertEqual(store.slugify("Café  —  Résumé"), "cafe-resume")

    def test_slugify_never_returns_empty(self):
        self.assertTrue(store.slugify("!!!"))

    def test_slugify_truncates(self):
        self.assertLessEqual(len(store.slugify("word " * 40)), 48)

    def test_split_csv_trims_and_drops_blanks(self):
        self.assertEqual(store.split_csv(" NVDA, AMD , ,"), ["NVDA", "AMD"])
        self.assertEqual(store.split_csv(None), [])
        self.assertEqual(store.split_csv(""), [])

    def test_record_kind_reads_both_schemas(self):
        self.assertEqual(store.record_kind({"kind": "prediction"}), "prediction")
        self.assertEqual(store.record_kind({"type": "prediction"}), "prediction")
        self.assertIsNone(store.record_kind({}))

    def test_short_ids_do_not_collide_in_bulk(self):
        ids = {store.short_id() for _ in range(5000)}
        self.assertEqual(len(ids), 5000)

    def test_utc_now_is_timezone_aware_iso(self):
        self.assertTrue(store.utc_now().endswith("+00:00"))


class AppendAndFold(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "s.jsonl"

    def test_reading_a_missing_file_yields_nothing(self):
        self.assertEqual(list(store.iter_records(self.path)), [])

    def test_append_writes_one_line_per_record(self):
        store.append_record(self.path, {"kind": "thing", "id": "a"})
        store.append_record(self.path, {"kind": "thing", "id": "b"})
        self.assertEqual(len(self.path.read_text().strip().split("\n")), 2)

    def test_a_corrupt_line_is_skipped_not_fatal(self):
        store.append_record(self.path, {"kind": "thing", "id": "a"})
        with self.path.open("a") as fh:
            fh.write("{not json at all\n")
        store.append_record(self.path, {"kind": "thing", "id": "b"})
        with open("/dev/null", "w") as devnull:
            import contextlib
            with contextlib.redirect_stderr(devnull):
                recs = list(store.iter_records(self.path))
        self.assertEqual([r["id"] for r in recs], ["a", "b"])

    def test_blank_lines_are_ignored(self):
        self.path.write_text('{"kind":"thing","id":"a"}\n\n\n')
        self.assertEqual(len(list(store.iter_records(self.path))), 1)

    def test_fold_applies_events_in_order(self):
        def bump(entity, event):
            entity["count"] = entity.get("count", 0) + event["by"]

        store.append_record(self.path, {"kind": "thing", "id": "a"})
        store.append_record(self.path, {"kind": "bump", "thing_id": "a", "by": 2})
        store.append_record(self.path, {"kind": "bump", "thing_id": "a", "by": 3})
        state = store.fold(self.path, base_kind="thing",
                           apply_events={"bump": bump}, initial={"count": 0})
        self.assertEqual(state["a"]["count"], 5)

    def test_an_event_for_an_unknown_entity_is_dropped_loudly(self):
        import contextlib, io
        store.append_record(self.path, {"kind": "bump", "thing_id": "ghost", "by": 1})
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            state = store.fold(self.path, base_kind="thing",
                               apply_events={"bump": lambda e, v: None})
        self.assertEqual(state, {})
        self.assertIn("unknown thing", err.getvalue())

    def test_a_later_base_record_replaces_the_earlier_one(self):
        # Re-declaring an id is a hand-edit smell; fold takes the last word and
        # the per-store `audit` is what flags the duplicate.
        store.append_record(self.path, {"kind": "thing", "id": "a", "v": 1})
        store.append_record(self.path, {"kind": "thing", "id": "a", "v": 2})
        self.assertEqual(store.fold(self.path, base_kind="thing")["a"]["v"], 2)

    def test_unicode_survives_a_round_trip(self):
        store.append_record(self.path, {"kind": "thing", "id": "a", "t": "café — résumé"})
        self.assertEqual(list(store.iter_records(self.path))[0]["t"], "café — résumé")
        self.assertIn("café", self.path.read_text(encoding="utf-8"))
