"""ARGUS relation graph — the signature move, made mechanical.

The README has always claimed cross-domain correlation as the differentiator,
and until now nothing computed it. This module builds one graph over everything
ARGUS records -- predictions, theses, catalysts, tickers, domains, and the
memory brain's entries -- and then asks it the four questions that are hard to
answer by reading:

**What is actually one bet?** Positions that share a catalyst resolve together.
The brain already noticed this once by hand, writing that five tokenization
names were "one bet expressed five ways, not diversification." `concentration`
and `clusters` find that shape every time instead of when someone happens to
look. `argus.edge.size_cluster` then sizes the group as the single bet it is.

**What single event breaks the most of the book?** `cutpoints` runs
Hopcroft-Tarjan articulation points: nodes whose removal disconnects the graph.
An articulation point that is a catalyst is a concentrated dependency wearing
the costume of a diversified book.

**Where are the cross-domain connections?** `bridges` finds nodes whose
neighbourhood spans two or more domains. A ticker that touches both the macro
cluster and the tokenization cluster is exactly the propagation path the
mission statement is about -- and the graph surfaces it whether or not anyone
was clever enough to look for it.

**What is dangling?** `orphans` collects every broken or missing link across
all four stores at once.

Read-only over every store, including the memory brain: this module never
writes to `argus/memory/`, `data/`, or anywhere else.

CLI:
    python -m argus.graph clusters | concentration | bridges | cutpoints
    python -m argus.graph orphans | report | stats [--json]
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Iterable

from . import store

MEMORY_DIR = Path(store.REPO_ROOT / "argus" / "memory")

# `### M20260821a — Title here`  (em dash, en dash, or hyphen)
_MEM_HEAD = re.compile(r"^###\s+(M\d{8}[a-z]+)\s*[—–-]\s*(.+?)\s*$", re.MULTILINE)
_MEM_TAGS = re.compile(r"#([a-z0-9][a-z0-9-]*)", re.IGNORECASE)
# `SECZ (NYSE)`, `CPU (Computershare, ASX)`, `HLNE (Hamilton Lane, Nasdaq)` --
# a deliberately narrow pattern: the symbol must be followed by a parenthetical
# naming a real venue. Scanning prose for bare capitals finds "GDP", "SEC" and
# "AUM" and poisons the graph with edges that mean nothing.
_MEM_TICKER = re.compile(
    r"\b([A-Z]{1,5})\s*\([^)]{0,48}?\b(?:NYSE|NASDAQ|Nasdaq|ASX|TSE|KRX|TWSE|LSE|AMEX|"
    r"SIX|Euronext|XETRA|TSX)\b[^)]{0,12}\)"
)
_MEM_REF = re.compile(r"\bM\d{8}[a-z]+\b")


# --------------------------------------------------------------------------
# Graph construction
# --------------------------------------------------------------------------


class Graph:
    """Undirected multi-typed graph. Nodes are `"<type>:<key>"` strings."""

    def __init__(self) -> None:
        self.adj: dict[str, set[str]] = defaultdict(set)
        self.attrs: dict[str, dict[str, Any]] = {}

    def node(self, node_id: str, **attrs: Any) -> str:
        self.attrs.setdefault(node_id, {"id": node_id, "type": node_id.split(":", 1)[0]})
        self.attrs[node_id].update({k: v for k, v in attrs.items() if v is not None})
        self.adj.setdefault(node_id, set())
        return node_id

    def link(self, a: str, b: str) -> None:
        if a == b:
            return
        self.adj[a].add(b)
        self.adj[b].add(a)

    def nodes_of(self, type_: str) -> list[str]:
        return [n for n in self.adj if n.startswith(f"{type_}:")]

    def degree(self, node_id: str) -> int:
        return len(self.adj.get(node_id, ()))

    # -- algorithms --------------------------------------------------------

    def components(self) -> list[set[str]]:
        seen: set[str] = set()
        out: list[set[str]] = []
        for start in self.adj:
            if start in seen:
                continue
            comp: set[str] = set()
            queue = deque([start])
            seen.add(start)
            while queue:
                cur = queue.popleft()
                comp.add(cur)
                for nxt in self.adj[cur]:
                    if nxt not in seen:
                        seen.add(nxt)
                        queue.append(nxt)
            out.append(comp)
        return sorted(out, key=len, reverse=True)

    def articulation_points(self) -> set[str]:
        """Hopcroft-Tarjan cut vertices, iteratively (no recursion limit).

        A cut vertex is a node whose removal increases the number of connected
        components -- structurally, a single point of failure.
        """
        disc: dict[str, int] = {}
        low: dict[str, int] = {}
        parent: dict[str, str | None] = {}
        cuts: set[str] = set()
        timer = 0

        for root in list(self.adj):
            if root in disc:
                continue
            parent[root] = None
            root_children = 0
            stack: list[tuple[str, Iterable[str]]] = [(root, iter(sorted(self.adj[root])))]
            disc[root] = low[root] = timer
            timer += 1

            while stack:
                node, children = stack[-1]
                advanced = False
                for child in children:
                    if child not in disc:
                        parent[child] = node
                        disc[child] = low[child] = timer
                        timer += 1
                        if node == root:
                            root_children += 1
                        stack.append((child, iter(sorted(self.adj[child]))))
                        advanced = True
                        break
                    if child != parent.get(node):
                        low[node] = min(low[node], disc[child])
                if advanced:
                    continue

                stack.pop()
                if stack:
                    up = stack[-1][0]
                    low[up] = min(low[up], low[node])
                    if parent.get(up) is not None and low[node] >= disc[up]:
                        cuts.add(up)

            if root_children > 1:
                cuts.add(root)
        return cuts


def _memory_entries(memory_dir: Path = MEMORY_DIR) -> list[dict[str, Any]]:
    """Parse the brain's monthly journals. Read-only, tolerant of drift.

    Anything that does not match the entry format in `argus/ARGUS.md` is simply
    not indexed, rather than raising -- the journals are written by hand and the
    graph must never be the reason a memory write fails.
    """
    entries: list[dict[str, Any]] = []
    if not memory_dir.exists():
        return entries
    for path in sorted(memory_dir.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        heads = list(_MEM_HEAD.finditer(text))
        for i, match in enumerate(heads):
            body_end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
            body = text[match.end():body_end]
            entries.append({
                "id": match.group(1),
                "title": match.group(2).strip(),
                "file": path.name,
                "tags": sorted({t.lower() for t in _MEM_TAGS.findall(body.split("\n")[0])
                                or _MEM_TAGS.findall(body[:300])}),
                "tickers": sorted(set(_MEM_TICKER.findall(body))),
                "refs": sorted(set(_MEM_REF.findall(body)) - {match.group(1)}),
            })
    return entries


def build(*, ledger_path: Path | None = None,
          theses_path: Path | None = None,
          catalysts_path: Path | None = None,
          memory_dir: Path | None = None) -> Graph:
    from . import catalysts as C
    from . import ledger as L
    from . import theses as T

    g = Graph()
    preds = L.load_state(ledger_path or L.LEDGER_PATH)
    thes = T.load_state(theses_path or T.THESES_PATH)
    cats = C.load_state(catalysts_path or C.CATALYSTS_PATH)
    mems = _memory_entries(memory_dir or MEMORY_DIR)

    # -- predictions -------------------------------------------------------
    for pid, p in preds.items():
        n = g.node(f"prediction:{pid}", label=p["claim"][:80], domain=p["domain"],
                   resolve_by=p["resolve_by"], probability=p["probability"],
                   open=p["outcome"] is None)
        g.link(n, g.node(f"domain:{p['domain']}", label=p["domain"]))
        for tk in p.get("tickers") or []:
            g.link(n, g.node(f"ticker:{tk.upper()}", label=tk.upper()))
        if p.get("catalyst"):
            g.link(n, g.node(f"catalyst:{p['catalyst']}"))
        # A prediction's free-text `thesis` tag counts as a link only when it
        # names a registered thesis; loose tags stay out of the graph rather
        # than manufacturing edges that mean nothing.
        if p.get("thesis") and p["thesis"] in thes:
            g.link(n, g.node(f"thesis:{p['thesis']}"))

    # -- theses ------------------------------------------------------------
    for tid, t in thes.items():
        n = g.node(f"thesis:{tid}", label=t["title"][:80], domain=t["domain"],
                   stage=t["stage"], direction=t["direction"],
                   closed=t.get("closed"))
        g.link(n, g.node(f"domain:{t['domain']}", label=t["domain"]))
        for pid in t.get("prediction_ids") or []:
            g.link(n, g.node(f"prediction:{pid}"))
        for cid in t.get("catalyst_ids") or []:
            g.link(n, g.node(f"catalyst:{cid}"))
        for tk in t.get("tickers") or []:
            g.link(n, g.node(f"ticker:{tk.upper()}", label=tk.upper()))
        for mid in t.get("memory_ids") or []:
            g.link(n, g.node(f"memory:{mid}"))

    # -- catalysts ---------------------------------------------------------
    for cid, c in cats.items():
        n = g.node(f"catalyst:{cid}", label=c["title"][:80], domain=c["domain"],
                   date=c["date"], precision=c.get("precision"),
                   resolved=c.get("what_happened") is not None)
        g.link(n, g.node(f"domain:{c['domain']}", label=c["domain"]))
        for pid in c.get("prediction_ids") or []:
            g.link(n, g.node(f"prediction:{pid}"))
        for tid in c.get("thesis_ids") or []:
            g.link(n, g.node(f"thesis:{tid}"))

    # -- memory brain ------------------------------------------------------
    known_tickers = {n.split(":", 1)[1] for n in g.nodes_of("ticker")}
    for m in mems:
        n = g.node(f"memory:{m['id']}", label=m["title"][:80], file=m["file"],
                   tags=m["tags"])
        for ref in m["refs"]:
            g.link(n, g.node(f"memory:{ref}"))
        for tk in m["tickers"]:
            g.link(n, g.node(f"ticker:{tk.upper()}", label=tk.upper()))
        # Tickers named in prose without an exchange only join the graph if the
        # structured stores already know them -- whitelist, never guess.
        for tk in known_tickers:
            if re.search(rf"\b{re.escape(tk)}\b", m["title"]):
                g.link(n, g.node(f"ticker:{tk}"))
    return g


# --------------------------------------------------------------------------
# Analyses
# --------------------------------------------------------------------------


def concentration(g: Graph | None = None, *, min_dependents: int = 2) -> list[dict[str, Any]]:
    """Catalysts that more than one position depends on.

    This is "five names, one catalyst chain" computed rather than noticed. Sort
    order is by how much of the book rides on the single event.
    """
    g = g or build()
    rows = []
    for cat in g.nodes_of("catalyst"):
        deps = g.adj[cat]
        theses = sorted(n for n in deps if n.startswith("thesis:"))
        preds = sorted(n for n in deps if n.startswith("prediction:"))
        tickers: set[str] = set()
        domains: set[str] = set()
        for t in theses:
            tickers |= {n.split(":", 1)[1] for n in g.adj[t] if n.startswith("ticker:")}
            domains |= {n.split(":", 1)[1] for n in g.adj[t] if n.startswith("domain:")}
        for p in preds:
            tickers |= {n.split(":", 1)[1] for n in g.adj[p] if n.startswith("ticker:")}
            domains |= {n.split(":", 1)[1] for n in g.adj[p] if n.startswith("domain:")}
        if len(theses) + len(preds) < min_dependents:
            continue
        rows.append({
            "catalyst": cat.split(":", 1)[1],
            "title": g.attrs[cat].get("label", ""),
            "date": g.attrs[cat].get("date"),
            "theses": [t.split(":", 1)[1] for t in theses],
            "predictions": [p.split(":", 1)[1] for p in preds],
            "tickers": sorted(tickers),
            "domains": sorted(domains),
            "dependents": len(theses) + len(preds),
        })
    return sorted(rows, key=lambda r: -r["dependents"])


def clusters(g: Graph | None = None) -> list[dict[str, Any]]:
    """Connected components, each described in terms a human can act on.

    A component is one bet. Two theses in the same component are correlated by
    construction, whatever their tickers or domains say.
    """
    g = g or build()
    out = []
    for comp in g.components():
        by_type: dict[str, list[str]] = defaultdict(list)
        for n in sorted(comp):
            by_type[n.split(":", 1)[0]].append(n.split(":", 1)[1])
        if len(comp) < 2:
            continue
        out.append({
            "size": len(comp),
            "domains": sorted(by_type.get("domain", [])),
            "theses": by_type.get("thesis", []),
            "predictions": by_type.get("prediction", []),
            "catalysts": by_type.get("catalyst", []),
            "tickers": by_type.get("ticker", []),
            "memory": by_type.get("memory", []),
            # More than one domain in a component is the cross-domain
            # propagation the mission is built on -- or an accident worth
            # looking at. Either way it wants eyes.
            "cross_domain": len(by_type.get("domain", [])) > 1,
        })
    return out


def bridges(g: Graph | None = None, *, hops: int = 2) -> list[dict[str, Any]]:
    """Nodes whose neighbourhood spans two or more domains.

    The cross-domain connection, found by structure instead of by inspiration.
    A ticker reachable from both `macro` and `tokenization` is a propagation
    path someone has already half-drawn without noticing.
    """
    g = g or build()
    rows = []
    for node in g.adj:
        if node.startswith("domain:"):
            continue
        seen = {node}
        frontier = {node}
        domains: set[str] = set()
        for _ in range(hops):
            nxt: set[str] = set()
            for cur in frontier:
                for nb in g.adj[cur]:
                    if nb.startswith("domain:"):
                        domains.add(nb.split(":", 1)[1])
                    if nb not in seen:
                        seen.add(nb)
                        nxt.add(nb)
            frontier = nxt
        if len(domains) >= 2:
            rows.append({
                "node": node,
                "type": node.split(":", 1)[0],
                "label": g.attrs[node].get("label", node.split(":", 1)[1]),
                "domains": sorted(domains),
                "degree": g.degree(node),
            })
    return sorted(rows, key=lambda r: (-len(r["domains"]), -r["degree"], r["node"]))


def cutpoints(g: Graph | None = None) -> list[dict[str, Any]]:
    """Articulation points — single events or entities holding the book together."""
    g = g or build()
    rows = []
    for node in sorted(g.articulation_points()):
        rows.append({
            "node": node,
            "type": node.split(":", 1)[0],
            "label": g.attrs[node].get("label", node.split(":", 1)[1]),
            "degree": g.degree(node),
            "date": g.attrs[node].get("date"),
        })
    return sorted(rows, key=lambda r: -r["degree"])


def orphans() -> dict[str, Any]:
    """Every dangling link across all four stores, in one place."""
    from . import catalysts as C
    from . import theses as T

    t_orph = T.orphans()
    g = build()
    idle_catalysts = [
        n.split(":", 1)[1] for n in g.nodes_of("catalyst")
        if not any(nb.startswith(("thesis:", "prediction:")) for nb in g.adj[n])
    ]
    # Memory entries that flagged an idea or a watch and never became a thesis.
    # These are the most common place edge goes to die: noticed, then dropped.
    unconverted = [
        {"id": n.split(":", 1)[1], "title": g.attrs[n].get("label", "")}
        for n in g.nodes_of("memory")
        if set(g.attrs[n].get("tags") or []) & {"idea", "watch", "prediction"}
        and not any(nb.startswith("thesis:") for nb in g.adj[n])
    ]
    return {
        "predictions_with_no_thesis": t_orph["predictions_with_no_thesis"],
        "theses_with_no_live_call": t_orph["theses_with_no_live_call"],
        "predictions_with_no_catalyst": [r["id"] for r in C.orphans()],
        "catalysts_nothing_depends_on": idle_catalysts,
        "memory_ideas_never_converted": unconverted,
    }


def stats(g: Graph | None = None) -> dict[str, Any]:
    g = g or build()
    counts = defaultdict(int)
    for n in g.adj:
        counts[n.split(":", 1)[0]] += 1
    comps = g.components()
    return {
        "nodes": len(g.adj),
        "edges": sum(len(v) for v in g.adj.values()) // 2,
        "by_type": dict(sorted(counts.items())),
        "components": len(comps),
        "largest_component": len(comps[0]) if comps else 0,
        "cross_domain_clusters": sum(1 for c in clusters(g) if c["cross_domain"]),
    }


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------


def report() -> str:
    g = build()
    s = stats(g)
    lines = ["# ARGUS relation graph", ""]
    lines.append(
        f"{s['nodes']} nodes / {s['edges']} edges across {s['components']} components "
        f"({', '.join(f'{v} {k}' for k, v in s['by_type'].items())})."
    )
    lines.append("")

    conc = concentration(g)
    lines.append("## Concentration — what is actually one bet")
    lines.append("")
    if not conc:
        lines.append("No catalyst carries more than one position. Either the book is "
                     "genuinely independent, or catalysts are not being linked — "
                     "check `python -m argus.catalysts orphans`.")
    else:
        for row in conc:
            lines.append(
                f"- **{row['catalyst']}** ({row['date']}) — {row['dependents']} dependents "
                f"across domains {row['domains']}, tickers {row['tickers'] or '—'}. "
                "Size these as ONE position: `argus.edge.size_cluster`."
            )
    lines.append("")

    cuts = [c for c in cutpoints(g) if c["degree"] > 1]
    lines.append("## Single points of failure")
    lines.append("")
    if not cuts:
        lines.append("No articulation points with meaningful degree.")
    else:
        for c in cuts[:12]:
            lines.append(f"- `{c['node']}` (degree {c['degree']}) — {c['label']}")
        lines.append("")
        lines.append("Removing any of these splits the book. A catalyst here means "
                     "one dated event decides several apparently separate positions.")
    lines.append("")

    br = bridges(g)
    lines.append("## Cross-domain bridges — where the signature move lives")
    lines.append("")
    if not br:
        lines.append("No node spans two domains. The book is siloed; the cross-domain "
                     "premise is currently unexercised.")
    else:
        for b in br[:15]:
            lines.append(f"- `{b['node']}` — spans {b['domains']} (degree {b['degree']}) — {b['label']}")
        lines.append("")
        lines.append("Each of these is a propagation path already half-drawn. Ask of "
                     "each: does a move in one domain force a move in the other, and "
                     "is that forcing already priced?")
    lines.append("")

    o = orphans()
    lines.append("## Dangling links")
    lines.append("")
    for key, label in [
        ("predictions_with_no_thesis", "open predictions with no thesis"),
        ("theses_with_no_live_call", "theses with nothing left to falsify them"),
        ("predictions_with_no_catalyst", "predictions anchored to no catalyst (EP-000b)"),
        ("catalysts_nothing_depends_on", "catalysts nothing depends on"),
        ("memory_ideas_never_converted", "memory ideas never turned into a thesis"),
    ]:
        items = o[key]
        lines.append(f"- **{label}:** {len(items)}"
                     + (f" — {', '.join(str(i if isinstance(i, str) else i['id']) for i in items[:8])}"
                        + (" …" if len(items) > 8 else "") if items else ""))
    lines.append("")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _print(payload: Any, as_json: bool) -> int:
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    elif isinstance(payload, list) and not payload:
        print("(none)")
    elif isinstance(payload, list):
        for row in payload:
            print(json.dumps(row, ensure_ascii=False))
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="argus.graph", description=__doc__)
    ap.add_argument("command", choices=["clusters", "concentration", "bridges",
                                        "cutpoints", "orphans", "stats", "report"])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.command == "report":
        print(report(), end="")
        return 0
    g = build()
    fn = {"clusters": clusters, "concentration": concentration, "bridges": bridges,
          "cutpoints": cutpoints, "stats": stats}.get(args.command)
    if fn is not None:
        return _print(fn(g), args.json)
    return _print(orphans(), True)


if __name__ == "__main__":
    raise SystemExit(main())
