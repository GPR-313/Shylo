"""Append-only event store — the shared spine under every ARGUS record type.

The prediction ledger proved the pattern: write facts, never mutate them, and
fold the log into current state at read time. `git log` then *is* the audit
trail, and "no silent memory-holing" becomes structural rather than aspirational.

Three stores now use it — predictions (`ledger.py`), theses (`theses.py`), and
catalysts (`catalysts.py`) — so the plumbing lives here instead of being
reimplemented three times with three subtly different bugs.

Stdlib only, deliberately. The spine keeps working when `requirements.txt` rots.
"""

from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
import uuid
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("ARGUS_DATA_DIR", REPO_ROOT / "data"))


class ValidationError(ValueError):
    """Raised when a record fails its write-time gate.

    Every store has one. The gate is the point: a record that cannot be
    adjudicated, or a thesis with no mechanism, is rejected at write time
    rather than caught in review three months later.
    """


# --------------------------------------------------------------------------
# Primitives
# --------------------------------------------------------------------------


def utc_now() -> str:
    """Timestamp for the `*_at` fields. Second precision; UTC always."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def short_id() -> str:
    return uuid.uuid4().hex[:12]


_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def slugify(text: str, max_len: int = 48) -> str:
    """Stable, human-readable id. Thesis and catalyst ids are slugs because a
    human reads them in a brief; prediction ids stay opaque because they are
    quoted verbatim and must never collide."""
    norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = _SLUG_STRIP.sub("-", norm.lower()).strip("-")
    return slug[:max_len].strip("-") or short_id()


def as_dict(record: Any) -> dict[str, Any]:
    return asdict(record) if is_dataclass(record) else dict(record)


# --------------------------------------------------------------------------
# Read / write
# --------------------------------------------------------------------------


def append_record(path: Path, record: Any) -> dict[str, Any]:
    """One record, one line, one git diff. Never rewrites what is already there."""
    payload = as_dict(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return payload


def iter_records(path: Path) -> Iterator[dict[str, Any]]:
    """Yield every record. A corrupt line warns and is skipped rather than
    killing a scheduled run — `audit` is what turns corruption into an error."""
    if not path.exists():
        return
    with path.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"warn: {path.name}: bad JSON at line {lineno}: {exc}",
                      file=sys.stderr)


def record_kind(rec: dict[str, Any]) -> str | None:
    """Discriminator, tolerant of the pre-0.2 ledger schema.

    Records written by the retired `scripts/ledger.py` used `type`; everything
    since uses `kind`. Reading both is what keeps the twenty seeded predictions
    from silently vanishing at a schema change (see ADR 0002 — this exact
    mismatch once reported twenty open predictions as zero).
    """
    return rec.get("kind") or rec.get("type")


def fold(
    path: Path,
    *,
    base_kind: str,
    id_field: str = "id",
    apply_events: dict[str, Any] | None = None,
    initial: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Replay the log into current state, keyed by id.

    `base_kind` records create entities; every other kind is an event applied to
    an existing entity by `apply_events[kind](entity, event)`. Events naming an
    unknown entity warn and are dropped — an event with no subject is either a
    typo or a hand edit, and both want to be loud.
    """
    apply_events = apply_events or {}
    state: dict[str, dict[str, Any]] = {}

    for raw in iter_records(path):
        kind = record_kind(raw)
        if kind == base_kind:
            key = raw.get(id_field)
            if key is None:
                print(f"warn: {path.name}: {base_kind} with no {id_field}", file=sys.stderr)
                continue
            state[key] = {**raw, "kind": kind, **(initial or {})}
        elif kind in apply_events:
            target = raw.get(f"{base_kind}_id") or raw.get(id_field)
            entity = state.get(target)
            if entity is None:
                print(f"warn: {path.name}: {kind} for unknown {base_kind} {target!r}",
                      file=sys.stderr)
                continue
            apply_events[kind](entity, raw)
        elif kind is not None:
            print(f"warn: {path.name}: unknown record kind {kind!r}", file=sys.stderr)

    return state


def split_csv(value: str | None) -> list[str]:
    """`--tickers NVDA, AMD ,` -> ['NVDA', 'AMD']. CLI ergonomics, one place."""
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]
