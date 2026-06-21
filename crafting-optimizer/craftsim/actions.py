"""PoE2 crafting actions as probabilistic state transitions.

Each Action exposes:
  - cost(prices)            -> currency cost in exalted-equivalent
  - applicable(state, pool) -> bool
  - transition(state, pool) -> {next_state: probability}  (sums to 1.0)

Mechanics modeled (PoE2, not PoE1 — no bench, no scour, no essence-spam):
  Transmute  Normal -> Magic, +1 random mod
  Augment    Magic  -> +1 random mod into an open slot
  Regal      Magic  -> Rare, +1 random mod
  Alchemy    Normal -> Rare, +4 random mods
  Exalt      Rare   -> +1 random mod (open slot)
  Chaos      Rare   -> remove 1 random mod, then add 1 random mod
  Annul      Magic/Rare -> remove 1 random mod
  Essence    Magic  -> Rare, + one GUARANTEED mod (deterministic)
  Omen variants of Exalt/Annul force the affected slot to prefix or suffix.
  Buy        any -> SUCCESS, pay market price of the finished item
  Restart    any -> fresh white base (the only "scour" PoE2 has)

Two deliberate simplifications for the toy (both are clean plug-in points):
  * spawn weights are static (no tag re-weighting yet)
  * tiers / numeric value ranges are ignored (success = mod present)
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Optional

from .mods import Gen, Mod, ModPool
from .prices import Prices
from .state import CAPS, WHITE, Rarity, State

# Sentinel terminal state for "stop crafting, you have the item" (buy / done).
SUCCESS = State(Rarity.RARE, frozenset({"__SUCCESS__"}))

Dist = dict[State, float]


# --------------------------------------------------------------------------
# weighted-draw helpers
# --------------------------------------------------------------------------
def _addable(state: State, pool: ModPool, slot: Optional[Gen]) -> list[Mod]:
    mods = [pool.by_id(m) for m in _all_ids(pool)]
    out = []
    for m in mods:
        if slot is not None and m.gen_type is not slot:
            continue
        if state.can_take(pool, m.id):
            out.append(m)
    return out


def _all_ids(pool: ModPool) -> list[str]:
    return [m.id for m in pool.mods]


def _add_one(state: State, pool: ModPool, slot: Optional[Gen],
             rarity: Optional[Rarity] = None) -> Optional[Dist]:
    """Distribution after adding ONE weighted-random mod (optionally slot-locked).
    If `rarity` is given the item is promoted FIRST (e.g. Transmute NORMAL->MAGIC),
    so slot openness is judged at the new rarity's caps. Returns None if nothing
    can be added (the orb would have no legal outcome)."""
    base = state.as_rarity(rarity) if rarity is not None else state
    cands = _addable(base, pool, slot)
    if not cands:
        return None
    total = sum(m.weight for m in cands)
    out: Dist = {}
    for m in cands:
        ns = base.with_mod(m.id)
        out[ns] = out.get(ns, 0.0) + m.weight / total
    return out


def _add_n(state: State, pool: ModPool, n: int,
           rarity: Optional[Rarity] = None) -> Optional[Dist]:
    """Distribution after adding N weighted mods sequentially (no replacement of
    family/slot). Used by Alchemy. Caps stop it early if the item fills up."""
    cur: Dist = {state.as_rarity(rarity) if rarity is not None else state: 1.0}
    for _ in range(n):
        nxt: Dist = defaultdict(float)
        for s, p in cur.items():
            step = _add_one(s, pool, slot=None)
            if step is None:        # item is full: remaining draws do nothing
                nxt[s] += p
            else:
                for s2, p2 in step.items():
                    nxt[s2] += p * p2
        cur = dict(nxt)
    return cur


def _remove_one(state: State, pool: ModPool, slot: Optional[Gen]) -> Optional[Dist]:
    """Remove one UNIFORM-random mod (optionally slot-locked: omen-annul)."""
    ids = list(state.mods)
    if slot is not None:
        ids = [m for m in ids if pool.by_id(m).gen_type is slot]
    if not ids:
        return None
    out: Dist = {}
    for m in ids:
        ns = state.without_mod(m)
        out[ns] = out.get(ns, 0.0) + 1.0 / len(ids)
    return out


# --------------------------------------------------------------------------
# Action definition
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Action:
    name: str
    cost: Callable[[Prices], float]
    applicable: Callable[[State, ModPool], bool]
    transition: Callable[[State, ModPool], Optional[Dist]]


def _has_open(state: State, pool: ModPool, slot: Optional[Gen] = None) -> bool:
    if slot is not None:
        return state.open_slots(pool, slot) > 0
    return state.open_slots(pool, Gen.PREFIX) > 0 or state.open_slots(pool, Gen.SUFFIX) > 0


# ---- basic currency -------------------------------------------------------
def transmute() -> Action:
    return Action(
        "Transmute",
        lambda pr: pr.get("transmute"),
        lambda s, p: s.rarity is Rarity.NORMAL,
        lambda s, p: _add_one(s, p, slot=None, rarity=Rarity.MAGIC),
    )


def augment() -> Action:
    return Action(
        "Augment",
        lambda pr: pr.get("augment"),
        lambda s, p: s.rarity is Rarity.MAGIC and _has_open(s, p),
        lambda s, p: _add_one(s, p, slot=None),
    )


def regal() -> Action:
    return Action(
        "Regal",
        lambda pr: pr.get("regal"),
        lambda s, p: s.rarity is Rarity.MAGIC,
        lambda s, p: _add_one(s, p, slot=None, rarity=Rarity.RARE),
    )


def alchemy() -> Action:
    return Action(
        "Alchemy",
        lambda pr: pr.get("alchemy"),
        lambda s, p: s.rarity is Rarity.NORMAL,
        lambda s, p: _add_n(s, p, 4, rarity=Rarity.RARE),
    )


def exalt(slot: Optional[Gen] = None, omen_cost_key: Optional[str] = None) -> Action:
    label = {None: "Exalt", Gen.PREFIX: "Exalt+Sinistral", Gen.SUFFIX: "Exalt+Dextral"}[slot]

    def cost(pr: Prices) -> float:
        c = pr.get("exalt")
        return c + pr.get(omen_cost_key) if omen_cost_key else c

    return Action(
        label,
        cost,
        lambda s, p: s.rarity is Rarity.RARE and _has_open(s, p, slot),
        lambda s, p: _add_one(s, p, slot=slot),
    )


def chaos() -> Action:
    def trans(s: State, p: ModPool) -> Optional[Dist]:
        removed = _remove_one(s, p, slot=None)
        if removed is None:
            return None
        out: Dist = defaultdict(float)
        for s1, p1 in removed.items():
            added = _add_one(s1, p, slot=None)
            if added is None:          # nothing to add back: leaves item short a mod
                out[s1] += p1
            else:
                for s2, p2 in added.items():
                    out[s2] += p1 * p2
        return dict(out)

    return Action(
        "Chaos",
        lambda pr: pr.get("chaos"),
        lambda s, p: s.rarity is Rarity.RARE and len(s.mods) > 0,
        trans,
    )


def annul(slot: Optional[Gen] = None, omen_cost_key: Optional[str] = None) -> Action:
    label = {None: "Annul", Gen.PREFIX: "Annul+Sinistral", Gen.SUFFIX: "Annul+Dextral"}[slot]

    def cost(pr: Prices) -> float:
        c = pr.get("annul")
        return c + pr.get(omen_cost_key) if omen_cost_key else c

    return Action(
        label,
        cost,
        lambda s, p: s.rarity in (Rarity.MAGIC, Rarity.RARE) and len(s.mods) > 0,
        lambda s, p: _remove_one(s, p, slot=slot),
    )


def essence(mod_id: str) -> Action:
    """PoE2 essence: upgrade a Magic item to Rare adding one guaranteed mod.
    Single-use determinism (no spam) — exactly the PoE2 distinction."""
    def trans(s: State, p: ModPool) -> Optional[Dist]:
        rare = s.as_rarity(Rarity.RARE)
        if not rare.can_take(p, mod_id):
            return None
        return {rare.with_mod(mod_id): 1.0}

    return Action(
        f"Essence:{mod_id}",
        lambda pr: pr.get("essence"),
        lambda s, p: s.rarity is Rarity.MAGIC and s.as_rarity(Rarity.RARE).can_take(p, mod_id),
        trans,
    )


# ---- terminals / recovery -------------------------------------------------
def buy() -> Action:
    """Stop crafting and buy the finished item. Guarantees the MDP is 'proper'
    (every state can reach the goal at finite cost) and answers the real
    question: is it even worth crafting versus buying?"""
    return Action(
        "BUY",
        lambda pr: pr.get("buy_item"),
        lambda s, p: True,
        lambda s, p: {SUCCESS: 1.0},
    )


def restart() -> Action:
    """Abandon the current item, buy a fresh white base. PoE2 has no Scour, so
    this is the genuine 'start over' recovery from a bricked rare."""
    return Action(
        "Restart",
        lambda pr: pr.get("base_item"),
        lambda s, p: s != WHITE,
        lambda s, p: {WHITE: 1.0},
    )


def default_actions(essence_mod: Optional[str] = None) -> list[Action]:
    """The PoE2 action set used by the demo."""
    acts = [
        transmute(), augment(), regal(), alchemy(),
        exalt(), exalt(Gen.PREFIX, "omen_sinistral_exalt"), exalt(Gen.SUFFIX, "omen_dextral_exalt"),
        chaos(),
        annul(), annul(Gen.PREFIX, "omen_sinistral_annul"), annul(Gen.SUFFIX, "omen_dextral_annul"),
        restart(), buy(),
    ]
    if essence_mod:
        acts.append(essence(essence_mod))
    return acts
