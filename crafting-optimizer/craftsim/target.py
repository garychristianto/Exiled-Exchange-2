"""Target specification: what counts as a finished item.

A target is a list of Requirements. Each Requirement is satisfied when ANY of its
acceptable mods is present, optionally with a minimum rolled value:

    Requirement(accept={"p_life_t1", "p_life_t2"})            # at least T2 life
    Requirement(accept={"s_allres_t1", "s_allres_t2"}, min_value=11)  # all-res >= 11

`min_value` is what makes Divine meaningful: a present mod can satisfy its
requirement's value (tracked in State.good) or not, and Divine rerolls values.
"""
from __future__ import annotations

from dataclasses import dataclass

from .state import State


@dataclass(frozen=True)
class Requirement:
    accept: frozenset[str]          # acceptable mod ids (e.g. acceptable tiers)
    min_value: float | None = None  # if set, the present mod must roll >= this

    def __post_init__(self):
        object.__setattr__(self, "accept", frozenset(self.accept))


@dataclass(frozen=True)
class Target:
    reqs: tuple[Requirement, ...]

    def met(self, state: State) -> bool:
        for r in self.reqs:
            present = r.accept & state.mods
            if not present:
                return False
            if r.min_value is not None and not (present & state.good):
                return False  # the acceptable mod is present but value too low
        return True

    def value_gates(self) -> dict[str, float]:
        """mod_id -> min_value, for mods whose rolled value is tracked in state."""
        gates: dict[str, float] = {}
        for r in self.reqs:
            if r.min_value is not None:
                for mid in r.accept:
                    gates[mid] = r.min_value
        return gates


def require(*reqs: Requirement) -> Target:
    return Target(tuple(reqs))
