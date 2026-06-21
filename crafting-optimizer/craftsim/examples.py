"""Synthetic pools/targets for demonstrating the abstraction at scale.

`make_amulet_pool(n)` builds the tiered Life/AllRes/Attr target mods plus `n`
neutral junk families per slot, so the pool can be grown arbitrarily while the
target stays fixed — exactly the regime where the abstraction shines.
"""
from __future__ import annotations

from .mods import Gen, Mod, ModPool
from .target import Requirement, require

TARGET_ESSENCE = "p_life_t2"

_TARGET_MODS = (
    Mod("p_life_t1", "+# to maximum Life", Gen.PREFIX, "Life", 75, 400, ("life",), 1, 90, 110),
    Mod("p_life_t2", "+# to maximum Life", Gen.PREFIX, "Life", 50, 800, ("life",), 2, 60, 89),
    Mod("p_life_t3", "+# to maximum Life", Gen.PREFIX, "Life", 1, 1000, ("life",), 3, 30, 59),
    Mod("s_allres_t1", "+#% all Elemental Res", Gen.SUFFIX, "AllRes", 75, 100, ("resistance",), 1, 13, 15),
    Mod("s_allres_t2", "+#% all Elemental Res", Gen.SUFFIX, "AllRes", 50, 250, ("resistance",), 2, 9, 12),
    Mod("s_attr", "+# to all Attributes", Gen.SUFFIX, "Attributes", 30, 500, ("attribute",)),
)


def make_target():
    return require(
        Requirement(accept={"p_life_t1", "p_life_t2"}),                 # life >= T2
        Requirement(accept={"s_allres_t1", "s_allres_t2"}, min_value=11),  # all-res >= 11
        Requirement(accept={"s_attr"}),                                 # attributes
    )


def make_amulet_pool(n_junk_per_slot: int, total_junk_weight: int = 2400,
                     uniform: bool = True, ilvl: int = 82) -> ModPool:
    mods = list(_TARGET_MODS)
    n = max(1, n_junk_per_slot)
    base = max(1, total_junk_weight // n)
    for i in range(n):
        # uniform=False perturbs weights so the family-exhaustion correction is
        # only approximate (worst case for the abstraction).
        wp = base if uniform else max(1, base + (i % 3 - 1) * base // 2)
        ws = base if uniform else max(1, base + (i % 2) * base // 2)
        mods.append(Mod(f"jp{i}", "junk prefix", Gen.PREFIX, f"JP{i}", 1, wp))
        mods.append(Mod(f"js{i}", "junk suffix", Gen.SUFFIX, f"JS{i}", 1, ws))
    return ModPool("Amulet", ilvl, tuple(mods))
