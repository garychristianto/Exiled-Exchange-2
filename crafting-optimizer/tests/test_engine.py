"""Analytic sanity checks: the solver must match hand-computable expected costs.

These pin the SSP math on tiny pools where the answer is a closed form, so a
regression in the transition engine or value iteration is caught immediately.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from craftsim import Gen, Mod, ModPool, Prices, Rarity, State, require  # noqa: E402
from craftsim.target import Requirement  # noqa: E402
from craftsim.actions import annul, buy, divine, restart, transmute  # noqa: E402
from craftsim.solver import solve  # noqa: E402
from craftsim.state import WHITE  # noqa: E402


def _req(*ids, min_value=None):
    return require(Requirement(accept=set(ids), min_value=min_value))


def test_single_guaranteed_mod():
    """One eligible suffix, only transmute available -> cost == transmute price."""
    pool = ModPool("Ring", 80, (Mod("s_x", "x", Gen.SUFFIX, "X", 1, 1000),))
    prices = Prices({"transmute": 0.02, "buy_item": 99.0})
    sol = solve(pool, _req("s_x"), [transmute(), buy()], prices)
    assert abs(sol.value[WHITE] - 0.02) < 1e-6
    assert sol.policy[WHITE].name == "Transmute"


def test_geometric_with_restart_recovery():
    """Two equally-weighted suffixes, target one. On a miss the cheapest recovery
    is Restart (annul correctly leaves an *empty magic* item in PoE2):

        V(white) = 2*transmute + base_item
    """
    pool = ModPool("Ring", 80, (
        Mod("s_t", "target", Gen.SUFFIX, "T", 1, 1000),
        Mod("s_j", "junk", Gen.SUFFIX, "J", 1, 1000),
    ))
    t, b = 0.05, 0.1
    prices = Prices({"transmute": t, "annul": 1.5, "base_item": b, "buy_item": 999.0})
    sol = solve(pool, _req("s_t"), [transmute(), annul(), restart(), buy()], prices)
    assert abs(sol.value[WHITE] - (2 * t + b)) < 1e-6, sol.value[WHITE]


def test_buy_beats_crafting_when_cheap():
    """If the finished item is cheaper than any craft, policy must say BUY."""
    pool = ModPool("Ring", 80, (
        Mod("s_t", "target", Gen.SUFFIX, "T", 1, 50),
        *[Mod(f"s_j{i}", "junk", Gen.SUFFIX, f"J{i}", 1, 1000) for i in range(5)],
    ))
    prices = Prices({"transmute": 0.02, "annul": 2.0, "base_item": 0.1, "buy_item": 0.5})
    sol = solve(pool, _req("s_t"), [transmute(), annul(), restart(), buy()], prices)
    assert sol.policy[WHITE].name == "BUY"
    assert abs(sol.value[WHITE] - 0.5) < 1e-9


def test_tier_targeting_accepts_any_acceptable_tier():
    """Life has 3 tiers; target accepts T1 or T2. Transmute hits an acceptable
    tier w.p. (400+800)/2200 = 6/11, else lands T3 (junk) -> restart.

        V(white) = (11*transmute + 5*base_item) / 6
    """
    pool = ModPool("Amulet", 82, (
        Mod("life_t1", "life", Gen.PREFIX, "Life", 75, 400, tier=1),
        Mod("life_t2", "life", Gen.PREFIX, "Life", 50, 800, tier=2),
        Mod("life_t3", "life", Gen.PREFIX, "Life", 1, 1000, tier=3),
    ))
    t, b = 0.02, 0.1
    prices = Prices({"transmute": t, "base_item": b, "buy_item": 999.0})
    sol = solve(pool, _req("life_t1", "life_t2"), [transmute(), restart(), buy()], prices)
    expected = (11 * t + 5 * b) / 6
    assert abs(sol.value[WHITE] - expected) < 1e-6, (sol.value[WHITE], expected)


def test_divine_reroll_value_threshold():
    """One gated suffix, value uniform 0..10, need >= 5 (p_good = 0.5). On a bad
    roll, Divine self-loops at p=0.5:

        V(bad)   = 2*divine
        V(white) = transmute + 0.5*V(bad) = transmute + divine
    (with divine cheap enough that Divine beats Restart).
    """
    pool = ModPool("Ring", 80, (Mod("s", "x", Gen.SUFFIX, "X", 1, 1000, vmin=0, vmax=10),))
    t, d, b = 0.02, 0.05, 0.1
    prices = Prices({"transmute": t, "divine": d, "base_item": b, "buy_item": 99.0})
    target = _req("s", min_value=5)
    gates = target.value_gates()   # must be threaded into every ADD action
    sol = solve(pool, target, [transmute(gates), divine(gates), restart(), buy()], prices)
    bad = State(Rarity.MAGIC, frozenset({"s"}), frozenset())   # present but value too low
    assert abs(sol.value[WHITE] - (t + d)) < 1e-6, sol.value[WHITE]
    assert abs(sol.value[bad] - 2 * d) < 1e-6, sol.value[bad]
    assert sol.policy[bad].name == "Divine"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all analytic checks passed")
