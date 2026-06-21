"""poe2db.tw source adapter -> neutral mod records (see ingest.py).

Status of the two halves of this module:
  * fetch() + egress handling .......... testable offline, ready to use.
  * extract_records() HTML parsing ..... PROVISIONAL. The exact poe2db DOM/embedded
    -JSON shape was NOT verifiable from this sandbox (poe2db.tw is not in the
    network egress allowlist here, so no live page could be inspected). The
    parser therefore fails LOUDLY (`ParseError`) if it doesn't find the expected
    structure, rather than emit silently-wrong weights. Validate its selectors
    against a real page, then snapshot to the neutral schema with `cache_to_json`.

Recommended workflow once poe2db.tw is allowlisted (Claude Code on the web ->
environment network egress settings):

    recs = fetch_mods("Amulet")           # live fetch + parse
    cache_to_json(recs, "data/amulet.mods.json")   # snapshot, schema-stable
    pool = ingest.load_modpool_json("data/amulet.mods.json")  # offline thereafter
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

from . import ingest

BASE = "https://poe2db.tw"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


class EgressNotAllowed(RuntimeError):
    """The sandbox network policy blocks the host (not a poe2db error)."""


class ParseError(RuntimeError):
    """Page fetched but its structure didn't match the (provisional) parser."""


def mod_page_url(item_class: str, lang: str = "us") -> str:
    slug = item_class.strip().replace(" ", "_")
    return f"{BASE}/{lang}/{slug}"


def fetch(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace") if e.fp else ""
        if e.code == 403 and "not in allowlist" in body.lower():
            host = urllib.request.urlparse(url).hostname  # type: ignore[attr-defined]
            raise EgressNotAllowed(
                f"{host} is blocked by this environment's network egress policy. "
                f"Add it to the environment's network/egress allowlist, then retry."
            ) from e
        if e.code == 403:
            raise EgressNotAllowed(
                f"{url} returned 403 (likely Cloudflare bot protection). A plain "
                f"urllib fetch may not pass the challenge; use a real browser "
                f"session or a scraper that solves it, then cache_to_json()."
            ) from e
        raise


# --- PROVISIONAL parsing ---------------------------------------------------
# poe2db embeds modifier data for its calculators in the page. The selectors
# below are a best-effort starting point and MUST be checked against a live
# page. They intentionally raise ParseError when nothing matches.
_GEN = {"prefix": "prefix", "suffix": "suffix",
        "1": "prefix", "2": "suffix"}


def extract_records(html: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    # Strategy 1: an embedded JSON blob (poe2db ships calculator data as JSON).
    for m in re.finditer(r'(\{[^{}]*?"[Ss]pawn[_ ]?[Ww]eight[^{}]*?\})', html):
        try:
            obj = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        rec = _coerce(obj)
        if rec:
            records.append(rec)
    if not records:
        raise ParseError(
            "no modifier records found — the provisional poe2db parser needs its "
            "selectors validated against a live page (see module docstring)."
        )
    return records


def _coerce(obj: dict[str, Any]) -> dict[str, Any] | None:
    """Map a poe2db-ish object to a neutral record, tolerating key variants."""
    def pick(*keys):
        for k in keys:
            if k in obj:
                return obj[k]
        return None

    gen = str(pick("gen_type", "GenerationType", "generation_type") or "").lower()
    rec = {
        "id": pick("id", "Id", "Code"),
        "name": pick("name", "Name", "Stat"),
        "gen_type": _GEN.get(gen),
        "family": pick("family", "Families", "group"),
        "ilvl": pick("ilvl", "Level", "level", "required_level"),
        "weight": pick("weight", "SpawnWeight", "spawn_weight"),
        "tags": pick("tags", "ImplicitTags") or [],
        "tier": pick("tier", "Tier") or 0,
        "vmin": pick("vmin", "min", "Stat1ValueMin") or 0,
        "vmax": pick("vmax", "max", "Stat1ValueMax") or 0,
    }
    if not all(rec[k] is not None for k in ingest.REQUIRED):
        return None
    return rec


def fetch_mods(item_class: str, lang: str = "us") -> list[dict[str, Any]]:
    return extract_records(fetch(mod_page_url(item_class, lang)))


def cache_to_json(records: list[dict[str, Any]], path: str,
                  item_class: str | None = None, ilvl: int | None = None) -> None:
    payload: Any = records
    if item_class is not None or ilvl is not None:
        payload = {"item_class": item_class, "ilvl": ilvl, "mods": records}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
