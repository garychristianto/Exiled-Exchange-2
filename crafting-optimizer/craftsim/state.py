"""Immutable item state used as the MDP state.

A state is (rarity, frozenset-of-mod-ids). Rarity is tracked explicitly because
it gates which actions are legal and the affix caps (a 2-mod item could be a
*full magic* or a *non-full rare* — different legal moves).

For the toy pool we track exact mod identities. At production scale this is
where state ABSTRACTION plugs in: keep only (which target mods are present,
count of junk prefixes, count of junk suffixes, relevant tags). That collapses
millions of states into a few thousand without changing the solver. The toy
pool is small enough that exact tracking is fine and easier to verify.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from .mods import Gen, ModPool


class Rarity(IntEnum):
    NORMAL = 0
    MAGIC = 1
    RARE = 2


# affix caps per rarity: (max prefixes, max suffixes)
CAPS: dict[Rarity, tuple[int, int]] = {
    Rarity.NORMAL: (0, 0),
    Rarity.MAGIC: (1, 1),
    Rarity.RARE: (3, 3),
}


@dataclass(frozen=True)
class State:
    rarity: Rarity
    mods: frozenset[str]  # mod ids currently on the item

    # ---- queries -------------------------------------------------------
    def prefixes(self, pool: ModPool) -> list[str]:
        return [m for m in self.mods if pool.by_id(m).gen_type is Gen.PREFIX]

    def suffixes(self, pool: ModPool) -> list[str]:
        return [m for m in self.mods if pool.by_id(m).gen_type is Gen.SUFFIX]

    def families(self, pool: ModPool) -> set[str]:
        return {pool.by_id(m).family for m in self.mods}

    def open_slots(self, pool: ModPool, gen: Gen) -> int:
        maxp, maxs = CAPS[self.rarity]
        if gen is Gen.PREFIX:
            return maxp - len(self.prefixes(pool))
        return maxs - len(self.suffixes(pool))

    def can_take(self, pool: ModPool, mod_id: str) -> bool:
        """Is `mod_id` a legal addition right now? (open slot of its type, its
        family not already present, ilvl satisfied by the base.)"""
        m = pool.by_id(mod_id)
        if m.id in self.mods:
            return False
        if m.family in self.families(pool):
            return False
        if self.open_slots(pool, m.gen_type) <= 0:
            return False
        return m.ilvl <= pool.ilvl

    # ---- transforms (return new immutable states) ----------------------
    def with_mod(self, mod_id: str, rarity: Rarity | None = None) -> "State":
        return State(rarity if rarity is not None else self.rarity, self.mods | {mod_id})

    def without_mod(self, mod_id: str) -> "State":
        return State(self.rarity, self.mods - {mod_id})

    def as_rarity(self, rarity: Rarity) -> "State":
        return State(rarity, self.mods)

    def __repr__(self) -> str:
        body = ",".join(sorted(self.mods)) if self.mods else "-"
        return f"{self.rarity.name[:1]}[{body}]"


WHITE = State(Rarity.NORMAL, frozenset())


def meets(state: State, target: frozenset[str]) -> bool:
    """Success = every required target mod is present (tiers/values ignored in v0)."""
    return target <= state.mods
