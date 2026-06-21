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
# Weights are illustrative but in a realistic *shape*: a basic resist is common,
# "all resistances" is a rare chase suffix, etc. This is what makes targeting
# (omens) actually pay off, which is the whole point of the optimizer.
# --------------------------------------------------------------------------
TOY_AMULET = ModPool(
    item_class="Amulet",
    ilvl=82,
    mods=(
        # prefixes
        Mod("p_life",  "# to maximum Life",         Gen.PREFIX, "Life",        1, 1000, ("life",)),
        Mod("p_es",    "# to maximum Energy Shield", Gen.PREFIX, "EnergyShield", 1,  800, ("energy_shield",)),
        Mod("p_mana",  "# to maximum Mana",          Gen.PREFIX, "Mana",        1, 1000, ("mana",)),
        Mod("p_phys",  "#% increased Phys Damage",   Gen.PREFIX, "PhysDamage",  1,  600, ("damage", "physical")),
        # suffixes
        Mod("s_fire",  "#% to Fire Resistance",      Gen.SUFFIX, "FireRes",    1, 1000, ("resistance", "fire")),
        Mod("s_cold",  "#% to Cold Resistance",      Gen.SUFFIX, "ColdRes",    1, 1000, ("resistance", "cold")),
        Mod("s_allres", "#% to all Elemental Res",   Gen.SUFFIX, "AllRes",    50,  250, ("resistance",)),
        Mod("s_attr",  "# to all Attributes",        Gen.SUFFIX, "Attributes", 30,  500, ("attribute",)),
        Mod("s_cast",  "#% increased Cast Speed",    Gen.SUFFIX, "CastSpeed",  20,  400, ("caster", "speed")),
    ),
)
