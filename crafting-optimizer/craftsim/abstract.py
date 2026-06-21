"""Pool-size-independent state abstraction.

The exact engine (craftsim.state/actions) tracks every mod identity, so adding a
500-mod real pool explodes the reachable state set. But the optimizer only cares
about:

  * which TARGET-relevant mods are present (acceptable tiers, and whether a
    target family got blocked by a wrong-tier mod), tracked exactly; and
  * how many junk prefixes / junk suffixes occupy slots — a COUNT, not identities.

So the abstract state is:

    (rarity, per-requirement status, neutral_junk_prefix_count, junk_suffix_count)

with status in { ABSENT, BLOCKED, ('h', mod_id, value_ok) }. Its size depends on
the number of target requirements (a handful), NOT on the pool size.

Transition weights aggregate the real pool once:
    P(hit acceptable mod of R) = w / Wtotal
    P(block R)                 = w_block_R / Wtotal   (wrong-tier mod of R's family)
    P(junk prefix)             = W_junk_prefix / Wtotal
    ... etc, where Wtotal sums only categories whose slot is open.

ONE approximation: neutral-junk weight is treated as an inexhaustible pool (we
don't subtract the families of junk already placed). This is the standard
crafting-calculator approximation; its error shrinks as the pool grows and is
measured against the exact engine in tests/test_abstract.py.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import product
from typing import Optional

from .mods import Gen, ModPool
from .prices import Prices
from .solver import Solution, solve_mdp
from .state import CAPS, Rarity
from .target import Target

ABSENT = 0
BLOCKED = 1
ABS_SUCCESS = ("__SUCCESS__",)   # terminal sentinel for the Buy action


@dataclass(frozen=True)
class AbstractState:
    rarity: int
    statuses: tuple           # one entry per requirement
    njp: int = 0              # neutral junk prefixes
    njs: int = 0              # neutral junk suffixes

    def __repr__(self) -> str:
        parts = []
        for st in self.statuses:
            if st == ABSENT:
                parts.append("-")
            elif st == BLOCKED:
                parts.append("X")
            else:
                parts.append(st[1] + ("*" if st[2] else "?"))
        return f"{Rarity(self.rarity).name[:1]}[{','.join(parts)}|j{self.njp}/{self.njs}]"


class Act:
    __slots__ = ("name",)

    def __init__(self, name: str):
        self.name = name

    def __repr__(self):
        return self.name


@dataclass(frozen=True)
class _Req:
    slot: Gen
    accept: tuple             # (mod_id, weight, p_good, gated)
    block_weight: float


class AbstractModel:
    def __init__(self, pool: ModPool, target: Target, prices: Prices,
                 essence_mod: Optional[str] = None):
        self.pool, self.prices, self.essence_mod = pool, prices, essence_mod
        reqs: list[_Req] = []
        accept_ids: set[str] = set()
        target_families: set[str] = set()
        for r in target.reqs:
            mods = [pool.by_id(m) for m in r.accept]
            slot = mods[0].gen_type
            fams = {m.family for m in mods}
            target_families |= fams
            accept_ids |= set(r.accept)
            accept = []
            for m in mods:
                if m.ilvl <= pool.ilvl:
                    pg = m.p_value_at_least(r.min_value) if r.min_value is not None else 1.0
                    accept.append((m.id, float(m.weight), pg, r.min_value is not None))
            block = sum(m.weight for m in pool.mods
                        if m.family in fams and m.id not in r.accept and m.ilvl <= pool.ilvl)
            reqs.append(_Req(slot, tuple(accept), float(block)))
        self.reqs = tuple(reqs)
        # neutral junk = mods sharing no family with any target requirement.
        # Track total weight AND the number of distinct families per slot, so we
        # can approximate family exhaustion as junk accumulates (see _njw_eff).
        njw = {Gen.PREFIX: 0.0, Gen.SUFFIX: 0.0}
        nfam = {Gen.PREFIX: set(), Gen.SUFFIX: set()}
        for m in pool.mods:
            if m.ilvl > pool.ilvl or m.id in accept_ids or m.family in target_families:
                continue
            njw[m.gen_type] += m.weight
            nfam[m.gen_type].add(m.family)
        self.njw = njw
        self.nfam = {k: len(v) for k, v in nfam.items()}
        self.start = AbstractState(Rarity.NORMAL, tuple(ABSENT for _ in reqs), 0, 0)

    def _njw_eff(self, slot: Gen, placed: int) -> float:
        """Eligible neutral-junk weight for `slot` once `placed` junk of that slot
        already occupy families. First-order family-exhaustion correction: remove
        the average family's weight per junk already there (exact for uniform
        weights; error -> 0 as the family count grows, i.e. on real pools)."""
        f = self.nfam[slot]
        if f == 0 or placed >= f:
            return 0.0
        return self.njw[slot] * (f - placed) / f

    # ---- helpers -------------------------------------------------------
    def _used(self, st: AbstractState, rarity: int) -> tuple[int, int]:
        up = us = 0
        for status, r in zip(st.statuses, self.reqs):
            if status != ABSENT:
                if r.slot is Gen.PREFIX:
                    up += 1
                else:
                    us += 1
        return up + st.njp, us + st.njs

    def _set(self, st, i, val, rarity) -> AbstractState:
        return AbstractState(rarity, st.statuses[:i] + (val,) + st.statuses[i + 1:],
                             st.njp, st.njs)

    def is_goal(self, s) -> bool:
        if s is ABS_SUCCESS:
            return True
        return all(isinstance(st, tuple) and st[2] for st in s.statuses)

    # ---- primitive distributions --------------------------------------
    def _add(self, st, slot_lock, set_rarity):
        rarity = set_rarity if set_rarity is not None else st.rarity
        capP, capS = CAPS[rarity]
        up, us = self._used(st, rarity)
        openP, openS = capP - up, capS - us
        cats: list[tuple[float, AbstractState]] = []
        for i, (status, r) in enumerate(zip(st.statuses, self.reqs)):
            if status != ABSENT or (slot_lock is not None and r.slot is not slot_lock):
                continue
            if (openP if r.slot is Gen.PREFIX else openS) <= 0:
                continue
            for (mid, w, pg, _gated) in r.accept:
                if pg > 0:
                    cats.append((w * pg, self._set(st, i, ("h", mid, True), rarity)))
                if pg < 1:
                    cats.append((w * (1 - pg), self._set(st, i, ("h", mid, False), rarity)))
            if r.block_weight > 0:
                cats.append((r.block_weight, self._set(st, i, BLOCKED, rarity)))
        njp_w = self._njw_eff(Gen.PREFIX, st.njp)
        njs_w = self._njw_eff(Gen.SUFFIX, st.njs)
        if slot_lock in (None, Gen.PREFIX) and openP > 0 and njp_w > 0:
            cats.append((njp_w, AbstractState(rarity, st.statuses, st.njp + 1, st.njs)))
        if slot_lock in (None, Gen.SUFFIX) and openS > 0 and njs_w > 0:
            cats.append((njs_w, AbstractState(rarity, st.statuses, st.njp, st.njs + 1)))
        total = sum(w for w, _ in cats)
        if total <= 0:
            return None
        out: dict = {}
        for w, ns in cats:
            out[ns] = out.get(ns, 0.0) + w / total
        return out

    def _addN(self, st, n, set_rarity):
        cur = {AbstractState(set_rarity, st.statuses, st.njp, st.njs): 1.0}
        for _ in range(n):
            cur = self._compose(cur, lambda s: self._add(s, None, None))
        return cur

    def _remove(self, st, slot_lock):
        units: list[tuple[AbstractState, int]] = []
        for i, (status, r) in enumerate(zip(st.statuses, self.reqs)):
            if status == ABSENT or (slot_lock is not None and r.slot is not slot_lock):
                continue
            units.append((self._set(st, i, ABSENT, st.rarity), 1))
        if slot_lock in (None, Gen.PREFIX) and st.njp > 0:
            units.append((AbstractState(st.rarity, st.statuses, st.njp - 1, st.njs), st.njp))
        if slot_lock in (None, Gen.SUFFIX) and st.njs > 0:
            units.append((AbstractState(st.rarity, st.statuses, st.njp, st.njs - 1), st.njs))
        total = sum(m for _, m in units)
        if total <= 0:
            return None
        out: dict = defaultdict(float)
        for ns, m in units:
            out[ns] += m / total
        return dict(out)

    def _divine(self, st):
        rerollable = []
        for i, status in enumerate(st.statuses):
            if isinstance(status, tuple):
                for (mid, w, pg, gated) in self.reqs[i].accept:
                    if mid == status[1] and gated:
                        rerollable.append((i, pg))
                        break
        if not rerollable:
            return None
        out: dict = defaultdict(float)
        for combo in product((True, False), repeat=len(rerollable)):
            prob = 1.0
            statuses = list(st.statuses)
            for (i, pg), g in zip(rerollable, combo):
                prob *= pg if g else (1 - pg)
                statuses[i] = ("h", statuses[i][1], g)
            if prob > 0:
                out[AbstractState(st.rarity, tuple(statuses), st.njp, st.njs)] += prob
        return dict(out)

    def _essence(self, st):
        mid = self.essence_mod
        for i, r in enumerate(self.reqs):
            for (m2, w, pg, gated) in r.accept:
                if m2 == mid:
                    if st.statuses[i] != ABSENT:
                        return None
                    out = {}
                    if pg > 0:
                        out[self._set(st, i, ("h", mid, True), Rarity.RARE)] = pg
                    if pg < 1:
                        out[self._set(st, i, ("h", mid, False), Rarity.RARE)] = 1 - pg
                    return out
        return None

    @staticmethod
    def _compose(dist, fn):
        out: dict = defaultdict(float)
        for s, p in dist.items():
            d2 = fn(s)
            if not d2:
                out[s] += p
            else:
                for s2, p2 in d2.items():
                    out[s2] += p * p2
        return dict(out)

    def _chaos(self, st):
        rm = self._remove(st, None)
        if not rm:
            return None
        return self._compose(rm, lambda s: self._add(s, None, None))

    def _total_mods(self, st) -> int:
        return sum(1 for x in st.statuses if x != ABSENT) + st.njp + st.njs

    def _has_open(self, st, slot=None) -> bool:
        capP, capS = CAPS[st.rarity]
        up, us = self._used(st, st.rarity)
        if slot is Gen.PREFIX:
            return capP - up > 0
        if slot is Gen.SUFFIX:
            return capS - us > 0
        return (capP - up > 0) or (capS - us > 0)

    # ---- expand --------------------------------------------------------
    def expand(self, st):
        P = self.prices
        out = []

        def add(name, cost, dist):
            if dist:
                out.append((Act(name), cost, dist))

        R = st.rarity
        if R == Rarity.NORMAL:
            add("Transmute", P.get("transmute"), self._add(st, None, Rarity.MAGIC))
            add("Alchemy", P.get("alchemy"), self._addN(st, 4, Rarity.RARE))
        if R == Rarity.MAGIC:
            if self._has_open(st):
                add("Augment", P.get("augment"), self._add(st, None, None))
            add("Regal", P.get("regal"), self._add(st, None, Rarity.RARE))
            if self.essence_mod:
                add("Essence", P.get("essence"), self._essence(st))
        if R == Rarity.RARE:
            if self._has_open(st):
                add("Exalt", P.get("exalt"), self._add(st, None, None))
            if self._has_open(st, Gen.PREFIX):
                add("Exalt+Sinistral", P.get("exalt") + P.get("omen_sinistral_exalt"),
                    self._add(st, Gen.PREFIX, None))
            if self._has_open(st, Gen.SUFFIX):
                add("Exalt+Dextral", P.get("exalt") + P.get("omen_dextral_exalt"),
                    self._add(st, Gen.SUFFIX, None))
            if self._total_mods(st) > 0:
                add("Chaos", P.get("chaos"), self._chaos(st))
        if R in (Rarity.MAGIC, Rarity.RARE) and self._total_mods(st) > 0:
            add("Annul", P.get("annul"), self._remove(st, None))
            add("Annul+Sinistral", P.get("annul") + P.get("omen_sinistral_annul"),
                self._remove(st, Gen.PREFIX))
            add("Annul+Dextral", P.get("annul") + P.get("omen_dextral_annul"),
                self._remove(st, Gen.SUFFIX))
        add("Divine", P.get("divine"), self._divine(st))
        if st != self.start:
            add("Restart", P.get("base_item"), {self.start: 1.0})
        add("BUY", P.get("buy_item"), {ABS_SUCCESS: 1.0})
        return out


def solve_abstract(pool: ModPool, target: Target, prices: Prices,
                   essence_mod: Optional[str] = None) -> Solution:
    model = AbstractModel(pool, target, prices, essence_mod)
    value, policy, states = solve_mdp(model.start, model.expand, model.is_goal)
    sol = Solution(value, policy, states, target, pool, prices)
    sol.model = model           # expose start/model for querying
    return sol
