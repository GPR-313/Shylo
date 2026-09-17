"""The dot-connector: components, cut vertices, concentration, and bridges.

The articulation-point tests use hand-checked graphs rather than fixtures from
a run, because "which single event breaks the most of the book" is a claim the
agent will act on and a wrong answer there is worse than no answer.
"""

from __future__ import annotations

import unittest

from argus import graph as G
from tests.support import StoreCase, future


class ArticulationPoints(unittest.TestCase):
    @staticmethod
    def _graph(edges):
        g = G.Graph()
        for a, b in edges:
            g.node(a); g.node(b); g.link(a, b)
        return g

    def test_middle_of_a_path_is_the_only_cut_vertex(self):
        g = self._graph([("n:a", "n:b"), ("n:b", "n:c")])
        self.assertEqual(g.articulation_points(), {"n:b"})

    def test_a_pure_cycle_has_no_cut_vertices(self):
        g = self._graph([("n:a", "n:b"), ("n:b", "n:c"), ("n:c", "n:a")])
        self.assertEqual(g.articulation_points(), set())

    def test_tail_attached_to_a_cycle(self):
        # a - b - c, with c in a c-d-e triangle. Removing b strands a;
        # removing c strands {a, b}. Nothing else disconnects anything.
        g = self._graph([("n:a", "n:b"), ("n:b", "n:c"),
                         ("n:c", "n:d"), ("n:d", "n:e"), ("n:e", "n:c")])
        self.assertEqual(g.articulation_points(), {"n:b", "n:c"})

    def test_a_star_centre_is_a_cut_vertex(self):
        g = self._graph([("n:hub", f"n:leaf{i}") for i in range(4)])
        self.assertEqual(g.articulation_points(), {"n:hub"})

    def test_disconnected_subgraphs_are_handled_independently(self):
        g = self._graph([("n:a", "n:b"), ("n:b", "n:c"), ("n:x", "n:y")])
        self.assertEqual(g.articulation_points(), {"n:b"})

    def test_components_are_sorted_largest_first(self):
        g = self._graph([("n:a", "n:b"), ("n:b", "n:c"), ("n:x", "n:y")])
        comps = g.components()
        self.assertEqual([len(c) for c in comps], [3, 2])


class MemoryParsing(StoreCase):
    def _journal(self, text: str):
        d = self.tmp / "memory"
        d.mkdir(exist_ok=True)
        (d / "2026-08.md").write_text(text, encoding="utf-8")
        return d

    def test_parses_ids_tags_refs_and_exchange_qualified_tickers(self):
        d = self._journal(
            "# Memory — 2026-08\n\n"
            "### M20260821e — Watch list seeded: five candidates\n"
            "tags: #watch #idea | source: session | confidence: med\n"
            "SECZ (Securitize, NYSE) and CPU (Computershare, ASX) both qualify. "
            "See M20260821c for the institutional posture.\n"
        )
        entries = G._memory_entries(d)
        self.assertEqual(len(entries), 1)
        e = entries[0]
        self.assertEqual(e["id"], "M20260821e")
        self.assertEqual(e["tags"], ["idea", "watch"])
        self.assertEqual(e["tickers"], ["CPU", "SECZ"])
        self.assertEqual(e["refs"], ["M20260821c"])

    def test_bare_capitals_in_prose_are_not_mistaken_for_tickers(self):
        d = self._journal(
            "### M20260821a — GDP and the SEC both moved\n"
            "tags: #market | source: session | confidence: high\n"
            "The SEC approved it and GDP rose; AUM grew. No tickers here at all.\n"
        )
        self.assertEqual(G._memory_entries(d)[0]["tickers"], [])

    def test_a_missing_memory_directory_is_not_an_error(self):
        self.assertEqual(G._memory_entries(self.tmp / "nope"), [])

    def test_unparseable_prose_is_skipped_rather_than_raising(self):
        d = self._journal("just some notes with no entry headers at all\n")
        self.assertEqual(G._memory_entries(d), [])


class BuiltGraph(StoreCase):
    def _empty_memory(self):
        d = self.tmp / "memory"
        d.mkdir(exist_ok=True)
        return d

    def test_a_thesis_links_its_predictions_domain_and_tickers(self):
        p = self.add_prediction()
        t = self.add_thesis([p.id], tickers=["BK", "CPU"])
        g = G.build(memory_dir=self._empty_memory())
        self.assertIn(f"prediction:{p.id}", g.adj[f"thesis:{t.id}"])
        self.assertIn("domain:tokenization", g.adj[f"thesis:{t.id}"])
        self.assertIn("ticker:BK", g.adj[f"thesis:{t.id}"])

    def test_a_loose_thesis_tag_does_not_manufacture_an_edge(self):
        p = self.add_prediction(thesis="some free text tag that is not a thesis id")
        g = G.build(memory_dir=self._empty_memory())
        self.assertEqual(
            [n for n in g.adj[f"prediction:{p.id}"] if n.startswith("thesis:")], [])

    def test_concentration_finds_positions_sharing_one_catalyst(self):
        c = self.add_catalyst()
        a = self.add_prediction(catalyst=c.id)
        b = self.add_prediction(catalyst=c.id,
                                claim="A second call resolving off the same dated event")
        t1 = self.add_thesis([a.id], tickers=["BK"], catalyst_ids=[c.id])
        t2 = self.add_thesis([b.id], tickers=["CPU"], catalyst_ids=[c.id],
                             title="Registrar optionality reprices on the same ruling")
        rows = G.concentration(G.build(memory_dir=self._empty_memory()))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["catalyst"], c.id)
        self.assertEqual(sorted(row["theses"]), sorted([t1.id, t2.id]))
        self.assertEqual(row["tickers"], ["BK", "CPU"])
        self.assertGreaterEqual(row["dependents"], 4)

    def test_an_independent_book_reports_no_concentration(self):
        self.add_prediction()
        self.assertEqual(G.concentration(G.build(memory_dir=self._empty_memory())), [])

    def test_a_ticker_held_in_two_domains_is_a_cross_domain_bridge(self):
        p1 = self.add_prediction(domain="tokenization")
        p2 = self.add_prediction(domain="macro",
                                 claim="A macro call that touches the same custodian")
        self.add_thesis([p1.id], tickers=["BK"], domain="tokenization")
        self.add_thesis([p2.id], tickers=["BK"], domain="macro",
                        title="Reserve scarcity reprices custody balance-sheet rent",
                        mechanism=("Falling reserve balances force dealers to economise on "
                                   "balance sheet, which drives custody fees higher because "
                                   "the constraint binds at the settlement layer."),
                        kill="Reserve balances rebuild above the 2026 peak with fees flat")
        br = G.bridges(G.build(memory_dir=self._empty_memory()))
        bk = [b for b in br if b["node"] == "ticker:BK"]
        self.assertEqual(len(bk), 1)
        self.assertEqual(bk[0]["domains"], ["macro", "tokenization"])

    def test_a_single_domain_book_has_no_bridges(self):
        p = self.add_prediction(domain="tokenization")
        self.add_thesis([p.id], tickers=["BK"])
        self.assertEqual(G.bridges(G.build(memory_dir=self._empty_memory())), [])

    def test_orphans_collects_every_dangling_link(self):
        p = self.add_prediction(resolve_by=future(300))
        self.add_catalyst(date=future(3))          # nothing depends on it
        o = G.orphans()
        self.assertIn(p.id, o["predictions_with_no_thesis"])
        self.assertIn(p.id, o["predictions_with_no_catalyst"])
        self.assertEqual(len(o["catalysts_nothing_depends_on"]), 1)

    def test_stats_counts_nodes_edges_and_cross_domain_clusters(self):
        p = self.add_prediction()
        self.add_thesis([p.id], tickers=["BK"])
        s = G.stats(G.build(memory_dir=self._empty_memory()))
        self.assertEqual(s["by_type"]["thesis"], 1)
        self.assertEqual(s["by_type"]["prediction"], 1)
        self.assertGreater(s["edges"], 0)
