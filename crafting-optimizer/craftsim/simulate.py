"""Independent Monte-Carlo sampler for validation.

This re-implements the crafting mechanics a SECOND time, by random sampling,
completely separately from the analytic transition functions in actions.py. If
the analytic engine and this sampler agree across many scenarios, the transition
probabilities are correct — this is exactly the affix-probability model that
Craft of Exile emulates: P(mod) = weight / Σ(eligible weights), with eligibility
gated by open slot, family, and ilvl.

Deliberately uses only `State.can_take` (the eligibility *spec*) and raw weights;
it never calls `_add_one`, `_place`, or `Action.transition`.
"""
from __future__ import annotations

import random
from typing import Optional

from .mods import Gen, ModPool
from .state import Rarity, State


def _eligible(state: State, pool: ModPool, slot: Optional[Gen]):
    return [m for m in pool.mods
            if (slot is None or m.gen_type is slot) and state.can_take(pool, m.id)]


def sample_add_one(state: State, pool: ModPool, slot: Optional[Gen],
                   rarity: Optional[Rarity], gates: dict, rng: random.Random) -> State:
    base = state.as_rarity(rarity) if rarity is not None else state
    cands = _eligible(base, pool, slot)
    if not cands:
        return base
    m = rng.choices(cands, weights=[c.weight for c in cands], k=1)[0]
    good = (m.id in gates) and (rng.random() < m.p_value_at_least(gates[m.id]))
    return base.with_mod(m.id, value_good=good)


def sample_remove_one(state: State, pool: ModPool, slot: Optional[Gen],
                      rng: random.Random) -> State:
    ids = [m for m in state.mods if slot is None or pool.by_id(m).gen_type is slot]
    if not ids:
        return state
    return state.without_mod(rng.choice(ids))


def sample_chaos(state: State, pool: ModPool, gates: dict, rng: random.Random) -> State:
    if not state.mods:
        return state
    s1 = sample_remove_one(state, pool, None, rng)
    return sample_add_one(s1, pool, None, None, gates, rng)


def sample_divine(state: State, pool: ModPool, gates: dict, rng: random.Random) -> State:
    good = set()
    for m in state.mods:
        if m in gates and rng.random() < pool.by_id(m).p_value_at_least(gates[m]):
            good.add(m)
    return state.with_good(frozenset(good))


# name -> (sampler, rarity-promotion, slot)
def step(name: str, state: State, pool: ModPool, gates: dict, rng: random.Random) -> State:
    if name == "transmute":
        return sample_add_one(state, pool, None, Rarity.MAGIC, gates, rng)
    if name == "augment":
        return sample_add_one(state, pool, None, None, gates, rng)
    if name == "regal":
        return sample_add_one(state, pool, None, Rarity.RARE, gates, rng)
    if name == "exalt":
        return sample_add_one(state, pool, None, None, gates, rng)
    if name == "exalt_suffix":
        return sample_add_one(state, pool, Gen.SUFFIX, None, gates, rng)
    if name == "chaos":
        return sample_chaos(state, pool, gates, rng)
    if name == "annul":
        return sample_remove_one(state, pool, None, rng)
    if name == "divine":
        return sample_divine(state, pool, gates, rng)
    raise ValueError(name)


def simulate_sequence(start: State, names: list[str], pool: ModPool,
                      gates: dict, rng: random.Random) -> State:
    s = start
    for nm in names:
        s = step(nm, s, pool, gates, rng)
    return s
