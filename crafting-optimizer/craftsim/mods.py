"""Mod data model and a hand-made toy mod pool.

This is the PLUGGABLE data layer. For the prototype it is hand-written so that
every probability is checkable by hand. In production this module would be fed
by a poe2db ingestion step that yields the same `Mod` / `ModPool` shapes
(see README -> "Real data path").

What a real poe2db record gives us, and where it maps here:
  - prefix/suffix          -> Mod.gen_type
  - mod group / family     -> Mod.family   (two mods of one family can't coexist)
  - required item level    -> Mod.ilvl
  - tags                   -> Mod.tags     (used later for tag-weighted spawn odds)
  - spawn weight           -> Mod.weight
  - tier index             -> Mod.tier     (a "stat" is a family of tiers)
  - rolled value range     -> Mod.vmin / Mod.vmax   (Divine rerolls within this)

A mod TIER is just a row: e.g. "Life" is a family with three rows (t1/t2/t3),
each its own ilvl, weight and value range. Family exclusion already prevents two
tiers of the same stat coexisting, so tiers need no special machinery — only the
data. Targeting "at least T2 life" = accept the set {life_t1, life_t2}.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Gen(Enum):
    """Affix slot. Mirrors GGG's `GenerationType` (1=prefix, 2=suffix)."""
    PREFIX = "prefix"
    SUFFIX = "suffix"


@dataclass(frozen=True)
class Mod:
    id: str
    name: str
    gen_type: Gen
    family: str          # coexistence group: at most one mod per family on an item
    ilvl: int            # minimum item level for this mod to be able to roll
    weight: int          # base spawn weight (tag adjustments applied later)
    tags: tuple[str, ...] = field(default_factory=tuple)
    tier: int = 0        # 1 = best; 0 = "untiered" toy mod
    vmin: float = 0.0    # rolled-value range (for Divine / value thresholds)
    vmax: float = 0.0

    def p_value_at_least(self, threshold: float) -> float:
        """P(a fresh roll of this mod is >= threshold), assuming uniform value."""
        if self.vmax <= self.vmin:
            return 1.0 if self.vmin >= threshold else 0.0
        if threshold <= self.vmin:
            return 1.0
        if threshold > self.vmax:
            return 0.0
        return (self.vmax - threshold) / (self.vmax - self.vmin)

    def __repr__(self) -> str:  # keep policy printouts short
        return self.id


@dataclass(frozen=True)
class ModPool:
    """The set of mods that can roll on one item base (one item class + ilvl)."""
    item_class: str
    ilvl: int
    mods: tuple[Mod, ...]

    def by_id(self, mod_id: str) -> Mod:
        for m in self.mods:
            if m.id == mod_id:
                return m
        raise KeyError(mod_id)

    def eligible(self, gen: Gen) -> list[Mod]:
        """All mods of a slot type that this base's ilvl can roll (family/slot
        openness is checked later against a concrete item state)."""
        return [m for m in self.mods if m.gen_type is gen and m.ilvl <= self.ilvl]


# --------------------------------------------------------------------------
# Toy pool: a Stellar Amulet at ilvl 82.
# Weights/ranges are illustrative but in a realistic *shape*: higher tiers need
# higher ilvl and roll rarer; "all resistances" is a low-weight chase suffix.
# Life and AllRes are TIERED (a family of rows) to exercise tier targeting and
# Divine; the rest are single-tier junk/filler.
# --------------------------------------------------------------------------
TOY_AMULET = ModPool(
    item_class="Amulet",
    ilvl=82,
    mods=(
        # --- Life prefix: 3 tiers (family "Life") ---
        Mod("p_life_t1", "+# to maximum Life", Gen.PREFIX, "Life", 75, 400, ("life",), tier=1, vmin=90, vmax=110),
        Mod("p_life_t2", "+# to maximum Life", Gen.PREFIX, "Life", 50, 800, ("life",), tier=2, vmin=60, vmax=89),
        Mod("p_life_t3", "+# to maximum Life", Gen.PREFIX, "Life", 1, 1000, ("life",), tier=3, vmin=30, vmax=59),
        # --- other prefixes (single tier filler) ---
        Mod("p_es",   "+# to maximum Energy Shield", Gen.PREFIX, "EnergyShield", 1, 800, ("energy_shield",)),
        Mod("p_mana", "+# to maximum Mana",          Gen.PREFIX, "Mana",         1, 1000, ("mana",)),
        Mod("p_phys", "#% increased Phys Damage",    Gen.PREFIX, "PhysDamage",   1, 600, ("damage", "physical")),
        # --- AllRes suffix: 2 tiers (family "AllRes"), the chase mod ---
        Mod("s_allres_t1", "+#% to all Elemental Resistances", Gen.SUFFIX, "AllRes", 75, 100, ("resistance",), tier=1, vmin=13, vmax=15),
        Mod("s_allres_t2", "+#% to all Elemental Resistances", Gen.SUFFIX, "AllRes", 50, 250, ("resistance",), tier=2, vmin=9, vmax=12),
        # --- other suffixes (single tier filler) ---
        Mod("s_fire", "+#% to Fire Resistance", Gen.SUFFIX, "FireRes",    1, 1000, ("resistance", "fire")),
        Mod("s_cold", "+#% to Cold Resistance", Gen.SUFFIX, "ColdRes",    1, 1000, ("resistance", "cold")),
        Mod("s_attr", "+# to all Attributes",   Gen.SUFFIX, "Attributes", 30, 500, ("attribute",)),
        Mod("s_cast", "#% increased Cast Speed", Gen.SUFFIX, "CastSpeed",  20, 400, ("caster", "speed")),
    ),
)
