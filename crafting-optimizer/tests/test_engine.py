"""Analytic sanity checks: the solver must match hand-computable expected costs.

These pin the SSP math on tiny pools where the answer is a closed form, so a
regression in the transition engine or value iteration is caught immediately.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from craftsim import Gen, Mod, ModPool, Prices, Rarity, State, solve  # noqa: E402
from craftsim.actions import annul, buy, restart, transmute  # noqa: E402
from craftsim.state import WHITE  # noqa: E402


def test_single_guaranteed_mod():
    """One eligible suffix, only transmute available -> cost == transmute price."""
    pool = ModPool("Ring", 80, (Mod("s_x", "x", Gen.SUFFIX, "X", 1, 1000),))
    prices = Prices({"transmute": 0.02, "buy_item": 99.0})
    sol = solve(pool, frozenset({"s_x"}), [transmute(), buy()], prices)
    assert abs(sol.value[WHITE] - 0.02) < 1e-6
    assert sol.policy[WHITE].name == "Transmute"


def test_geometric_with_restart_recovery():
    """Two equally-weighted suffixes, target one of them. Transmute hits it w.p.
    1/2; on a miss the cheapest recovery is Restart (annul correctly leaves an
    *empty magic* item in PoE2, so annul+restart is strictly worse than restart).
    Closed form (buy_item large enough to never be chosen):

        V(magic-with-junk) = base_item + V(white)
        V(white)           = transmute + 0.5*0 + 0.5*V(magic-with-junk)
      => V(white) = 2*transmute + base_item
    """
    pool = ModPool("Ring", 80, (
        Mod("s_t", "target", Gen.SUFFIX, "T", 1, 1000),
        Mod("s_j", "junk", Gen.SUFFIX, "J", 1, 1000),
    ))
    t, b = 0.05, 0.1
    prices = Prices({"transmute": t, "annul": 1.5, "base_item": b, "buy_item": 999.0})
    sol = solve(pool, frozenset({"s_t"}), [transmute(), annul(), restart(), buy()], prices)
    expected = 2 * t + b
    assert abs(sol.value[WHITE] - expected) < 1e-6, (sol.value[WHITE], expected)


def test_buy_beats_crafting_when_cheap():
    """If the finished item is cheaper than any craft, policy must say BUY."""
    pool = ModPool("Ring", 80, (
        Mod("s_t", "target", Gen.SUFFIX, "T", 1, 50),
        *[Mod(f"s_j{i}", "junk", Gen.SUFFIX, f"J{i}", 1, 1000) for i in range(5)],
    ))
    prices = Prices({"transmute": 0.02, "annul": 2.0, "base_item": 0.1, "buy_item": 0.5})
    sol = solve(pool, frozenset({"s_t"}), [transmute(), annul(), restart(), buy()], prices)
    assert sol.policy[WHITE].name == "BUY"
    assert abs(sol.value[WHITE] - 0.5) < 1e-9


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all analytic checks passed")
