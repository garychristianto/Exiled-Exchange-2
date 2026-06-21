"""Parse the in-game PoE2 'Copy Item' clipboard text into a structured item.

The clipboard format is blocks separated by lines of dashes; the first block has
`Item Class:` / `Rarity:` / name / base, and later blocks hold item level,
requirements, and the modifier lines (implicits tagged `(implicit)`).

This parser is deliberately tolerant — it extracts what it can and keeps the raw
lines, so an unfamiliar line never crashes it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_DASHES = re.compile(r"-{3,}")
_NUM = re.compile(r"[+-]?\d+(?:\.\d+)?")
_TAG = re.compile(r"\(([^)]+)\)\s*$")
_META_PREFIXES = (
    "item class:", "rarity:", "item level:", "quality:", "requirements",
    "level:", "sockets:", "str:", "dex:", "int:", "stack size:", "note:",
    "corrupted", "unidentified",
)


@dataclass
class ParsedMod:
    text: str                 # the line as shown (tag stripped)
    values: list[float] = field(default_factory=list)
    tag: str | None = None    # 'implicit' / 'crafted' / 'fractured' / ...


@dataclass
class ParsedItem:
    item_class: str | None = None
    rarity: str | None = None
    name: str | None = None       # rare name OR magic full name
    base: str | None = None       # base type
    ilvl: int | None = None
    quality: int | None = None
    corrupted: bool = False
    implicits: list[ParsedMod] = field(default_factory=list)
    explicits: list[ParsedMod] = field(default_factory=list)
    raw: str = ""

    @property
    def all_mods(self) -> list[ParsedMod]:
        return self.implicits + self.explicits


def _mk_mod(line: str) -> ParsedMod | None:
    tag = None
    m = _TAG.search(line)
    if m:
        inner = m.group(1).lower()
        if inner in ("implicit", "crafted", "fractured", "enchant", "rune",
                     "scourge", "desecrated", "veiled"):
            tag = inner
            line = line[: m.start()].rstrip()
    values = [float(x) for x in _NUM.findall(line)]
    if not values and "%" not in line and not line.strip():
        return None
    return ParsedMod(text=line.strip(), values=values, tag=tag)


def parse_item(text: str) -> ParsedItem:
    text = text.replace("\r\n", "\n").strip()
    item = ParsedItem(raw=text)
    blocks = [b.strip("\n") for b in _DASHES.split(text)]

    # header
    header = blocks[0].splitlines() if blocks else []
    name_lines: list[str] = []
    for ln in header:
        low = ln.lower()
        if low.startswith("item class:"):
            item.item_class = ln.split(":", 1)[1].strip()
        elif low.startswith("rarity:"):
            item.rarity = ln.split(":", 1)[1].strip()
        elif ln.strip():
            name_lines.append(ln.strip())
    if name_lines:
        item.name = name_lines[0]
        item.base = name_lines[-1] if len(name_lines) > 1 else name_lines[0]

    # later blocks
    for block in blocks[1:]:
        lines = [l for l in block.splitlines() if l.strip()]
        low_first = lines[0].lower() if lines else ""
        if "item level:" in low_first:
            nums = _NUM.findall(lines[0])
            if nums:
                item.ilvl = int(float(nums[0]))
            continue
        if low_first.startswith("quality:"):
            nums = _NUM.findall(lines[0])
            if nums:
                item.quality = int(float(nums[0]))
            continue
        if any(low_first.startswith(p) for p in ("requirements", "sockets")):
            continue
        if block.strip().lower() == "corrupted":
            item.corrupted = True
            continue
        # otherwise: treat as a modifier block
        block_is_implicit = block.strip().endswith("(implicit)")
        for ln in lines:
            low = ln.lower()
            if any(low.startswith(p) for p in _META_PREFIXES):
                continue
            mod = _mk_mod(ln)
            if mod is None:
                continue
            if mod.tag == "implicit" or block_is_implicit:
                mod.tag = mod.tag or "implicit"
                item.implicits.append(mod)
            else:
                item.explicits.append(mod)
    return item
