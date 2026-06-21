"""Validation: the analytic transition engine must agree with an independent
Monte-Carlo simulator (the affix-probability model Craft of Exile emulates).

Fixed seed + generous tolerance keep this deterministic. The math is also pinned
to a hand-computed reference so the absolute probabilities are checked, not just
self-consistency.
"""
import os
import random
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from craftsim import TOY_AMULET, Rarity, State, require  # noqa: E402
from craftsim.mods import Gen  # noqa: E402
from craftsim.target import Requirement  # noqa: E402
from craftsim import actions, simulate  # noqa: E402
from craftsim.state import WHITE  # noqa: E402

POOL = TOY_AMULET
N = 60_000
TOL = 0.015


def _act(name, gates):
    return {
        "transmute": actions.transmute(gates),
        "regal": actions.regal(gates),
        "exalt": actions.exalt(gates=gates),
        "chaos": actions.chaos(gates),
        "annul": actions.annul(),
        "divine": actions.divine(gates),
    }[name]


def _tv(a, b):
    return 0.5 * sum(abs(a.get(k, 0.0) - b.get(k, 0.0)) for k in set(a) | set(b))


def _mc(name, state, gates, rng):
    c = Counter()
    for _ in range(N):
        c[simulate.step(name, state, POOL, gates, rng)] += 1
    return {s: v / N for s, v in c.items()}


def test_single_actions_match_monte_carlo():
    rng = random.Random(7)
    gates = {"s_allres_t1": 11.0, "s_allres_t2": 11.0}
    cases = [
        ("transmute", WHITE, {}),
        ("exalt", State(Rarity.RARE, frozenset({"p_life_t2"})), {}),
        ("chaos", State(Rarity.RARE, frozenset({"p_life_t2", "s_fire", "s_cold"})), {}),
        ("annul", State(Rarity.RARE, frozenset({"p_life_t2", "s_fire"})), {}),
        ("transmute", WHITE, gates),
        ("divine", State(Rarity.RARE, frozenset({"p_life_t2", "s_allres_t2"})), gates),
    ]
    for name, state, g in cases:
        eng = _act(name, g).transition(state, POOL)
        mc = _mc(name, state, g, rng)
        assert _tv(eng, mc) < TOL, (name, state, _tv(eng, mc))


def test_reference_probability_is_exact():
    """P(transmute -> life_t3) must equal 1000 / (sum of eligible weights)."""
    elig = [m for m in POOL.mods if WHITE.as_rarity(Rarity.MAGIC).can_take(POOL, m.id)]
    total = sum(m.weight for m in elig)
    eng = actions.transmute({}).transition(WHITE, POOL)
    p = eng[State(Rarity.MAGIC, frozenset({"p_life_t3"}))]
    assert abs(p - 1000 / total) < 1e-12


def test_full_sequence_success_matches_monte_carlo():
    rng = random.Random(99)
    target = require(
        Requirement(accept={"p_life_t1", "p_life_t2"}),
        Requirement(accept={"s_allres_t1", "s_allres_t2"}, min_value=11),
        Requirement(accept={"s_attr"}),
    )
    g = target.value_gates()
    seq = ["transmute", "regal", "exalt", "exalt"]

    dist = {WHITE: 1.0}
    for nm in seq:
        act = _act(nm, g)
        nd = defaultdict(float)
        for s, p in dist.items():
            tr = act.transition(s, POOL) if act.applicable(s, POOL) else None
            if not tr:
                nd[s] += p
            else:
                for s2, p2 in tr.items():
                    nd[s2] += p * p2
        dist = dict(nd)
    eng_succ = sum(p for s, p in dist.items() if target.met(s))

    hits = 0
    for _ in range(N):
        s = WHITE
        for nm in seq:
            if _act(nm, g).applicable(s, POOL):
                s = simulate.step(nm, s, POOL, g, rng)
        hits += target.met(s)
    mc_succ = hits / N
    assert abs(eng_succ - mc_succ) < 0.01, (eng_succ, mc_succ)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all validation checks passed")
