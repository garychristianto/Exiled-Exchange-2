"""Ingestion: turn neutral mod records into a `ModPool` the solver can use.

This is the stable seam between *data sources* and the *engine*. Any source
(poe2db, the repo's own dataParser, a hand-written fixture) just has to emit a
list of records in this neutral schema; the engine never sees source quirks.

Neutral mod record (one per mod TIER):
    {
      "id":       "amulet.life.t1",     # unique
      "name":     "+# to maximum Life",
      "gen_type": "prefix" | "suffix",
      "family":   "Life",                # coexistence group
      "ilvl":     75,                     # required item level
      "weight":   400,                    # spawn weight
      "tags":     ["life"],               # optional
      "tier":     1,                      # optional (1 = best)
      "vmin":     90, "vmax": 110         # optional rolled-value range
    }
"""
from __future__ import annotations

import json
from typing import Any, Iterable

from .mods import Gen, Mod, ModPool

REQUIRED = ("id", "name", "gen_type", "family", "ilvl", "weight")


def record_to_mod(r: dict[str, Any]) -> Mod:
    missing = [k for k in REQUIRED if k not in r]
    if missing:
        raise ValueError(f"mod record {r.get('id', '?')!r} missing keys: {missing}")
    if r["gen_type"] not in ("prefix", "suffix"):
        raise ValueError(f"{r['id']}: gen_type must be 'prefix'/'suffix', got {r['gen_type']!r}")
    return Mod(
        id=str(r["id"]),
        name=str(r["name"]),
        gen_type=Gen(r["gen_type"]),
        family=str(r["family"]),
        ilvl=int(r["ilvl"]),
        weight=int(r["weight"]),
        tags=tuple(r.get("tags", ())),
        tier=int(r.get("tier", 0)),
        vmin=float(r.get("vmin", 0.0)),
        vmax=float(r.get("vmax", 0.0)),
    )


def to_modpool(item_class: str, ilvl: int, records: Iterable[dict[str, Any]]) -> ModPool:
    mods = tuple(record_to_mod(r) for r in records)
    ids = [m.id for m in mods]
    if len(ids) != len(set(ids)):
        dup = {i for i in ids if ids.count(i) > 1}
        raise ValueError(f"duplicate mod ids: {sorted(dup)}")
    return ModPool(item_class=item_class, ilvl=ilvl, mods=mods)


def load_modpool_json(path: str, item_class: str | None = None,
                      ilvl: int | None = None) -> ModPool:
    """Load a ModPool from a JSON file. The file may be either a bare list of
    records, or an object {item_class, ilvl, mods:[...]}. Explicit args override
    fields in the file."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, list):
        records = data
        meta: dict[str, Any] = {}
    else:
        records = data["mods"]
        meta = data
    ic = item_class or meta.get("item_class")
    il = ilvl if ilvl is not None else meta.get("ilvl")
    if ic is None or il is None:
        raise ValueError("item_class and ilvl must be provided (arg or in file)")
    return to_modpool(ic, int(il), records)
