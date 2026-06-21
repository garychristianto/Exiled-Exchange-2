"""Validate the analytic transition engine against an independent Monte-Carlo
simulator (the same affix-probability model Craft of Exile emulates).

Run:  python validate.py

For each scenario we compute the next-state distribution two independent ways —
analytically (craftsim.actions) and by sampling (craftsim.simulate) — and report
the total-variation distance. TV ~ 0 means they agree. A hand-computed reference
for the simplest case is printed so the absolute numbers are checkable too.
"""
from __future__ import annotations

import random
from collections import Counter, defaultdict

from craftsim import TOY_AMULET, Rarity, State, require
from craftsim.target import Requirement
from craftsim import actions, simulate
from craftsim.state import WHITE

POOL = TOY_AMULET


def engine_action(name: str, gates: dict):
    from craftsim.mods import Gen
    return {
        "transmute": actions.transmute(gates),
        "augment": actions.augment(gates),
        "regal": actions.regal(gates),
        "exalt": actions.exalt(gates=gates),
        "exalt_suffix": actions.exalt(Gen.SUFFIX, None, gates),
        "chaos": actions.chaos(gates),
        "annul": actions.annul(),
        "divine": actions.divine(gates),
    }[name]


def mc_dist(name, state, gates, n, rng):
    c = Counter()
    for _ in range(n):
        c[simulate.step(name, state, POOL, gates, rng)] += 1
    return {s: v / n for s, v in c.items()}


def tv(a: dict, b: dict) -> float:
    keys = set(a) | set(b)
    return 0.5 * sum(abs(a.get(k, 0.0) - b.get(k, 0.0)) for k in keys)


def engine_seq(start, names, gates):
    dist = {start: 1.0}
    for nm in names:
        act = engine_action(nm, gates)
        nd = defaultdict(float)
        for s, p in dist.items():
            tr = act.transition(s, POOL) if act.applicable(s, POOL) else None
            if not tr:
                nd[s] += p
            else:
                for s2, p2 in tr.items():
                    nd[s2] += p * p2
        dist = dict(nd)
    return dist


def mc_seq_success(start, names, gates, target, n, rng):
    hits = 0
    for _ in range(n):
        s = start
        for nm in names:
            act = engine_action(nm, gates)
            if act.applicable(s, POOL):
                s = simulate.step(nm, s, POOL, gates, rng)
        hits += target.met(s)
    return hits / n


def main():
    rng = random.Random(12345)
    N = 120_000
    gates = {"s_allres_t2": 11.0, "s_allres_t1": 11.0}

    scenarios = [
        ("transmute @ white", "transmute", WHITE, {}),
        ("exalt @ rare[life_t2]", "exalt",
         State(Rarity.RARE, frozenset({"p_life_t2"})), {}),
        ("chaos @ rare[life,fire,cold]", "chaos",
         State(Rarity.RARE, frozenset({"p_life_t2", "s_fire", "s_cold"})), {}),
        ("annul @ rare[life,fire]", "annul",
         State(Rarity.RARE, frozenset({"p_life_t2", "s_fire"})), {}),
        ("transmute w/ value gate", "transmute", WHITE, gates),
        ("divine @ rare[life,allres_t2(bad)]", "divine",
         State(Rarity.RARE, frozenset({"p_life_t2", "s_allres_t2"})), gates),
    ]

    print(f"Single-action: analytic vs Monte-Carlo (N={N:,})")
    print(f"{'scenario':<38}{'TV distance':>12}   verdict")
    print("-" * 66)
    worst = 0.0
    for label, name, state, g in scenarios:
        eng = engine_action(name, g).transition(state, POOL)
        mc = mc_dist(name, state, g, N, rng)
        d = tv(eng, mc)
        worst = max(worst, d)
        print(f"{label:<38}{d:>12.5f}   {'OK' if d < 0.01 else 'FAIL'}")

    # Hand-computable reference: transmute on a white amulet. P(p_life_t3) =
    # 1000 / (sum of all weights eligible at ilvl 82).
    elig = [m for m in POOL.mods if WHITE.as_rarity(Rarity.MAGIC).can_take(POOL, m.id)]
    total = sum(m.weight for m in elig)
    eng = engine_action("transmute", {}).transition(WHITE, POOL)
    p_t3 = eng[State(Rarity.MAGIC, frozenset({"p_life_t3"}))]
    print(f"\nReference check: P(transmute -> life_t3) = 1000/{total} = "
          f"{1000/total:.5f}; engine = {p_t3:.5f}")

    # Full-sequence success probability: transmute->regal->exalt->exalt, want a
    # rare with >=T2 life AND any all-res (value>=11) AND attributes.
    target = require(
        Requirement(accept={"p_life_t1", "p_life_t2"}),
        Requirement(accept={"s_allres_t1", "s_allres_t2"}, min_value=11),
        Requirement(accept={"s_attr"}),
    )
    seq = ["transmute", "regal", "exalt", "exalt"]
    g = target.value_gates()
    dist = engine_seq(WHITE, seq, g)
    eng_succ = sum(p for s, p in dist.items() if target.met(s))
    mc_succ = mc_seq_success(WHITE, seq, g, target, N, rng)
    print(f"\nFull sequence {seq}:")
    print(f"  P(success) engine = {eng_succ:.5f}   Monte-Carlo = {mc_succ:.5f}   "
          f"diff = {abs(eng_succ - mc_succ):.5f}")

    print(f"\nWorst single-action TV distance: {worst:.5f}  "
          f"-> {'ALL CONSISTENT' if worst < 0.01 else 'MISMATCH'}")


if __name__ == "__main__":
    main()
