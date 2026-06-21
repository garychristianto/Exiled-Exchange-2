"""Abstraction tests: it must agree with the exact engine and stay pool-size
independent.

- Uniform junk weights make the family-exhaustion correction exact, so the
  abstract value must match the exact value to solver tolerance.
- Non-uniform junk is the worst case; we only require it to stay close.
- The abstract state count must NOT depend on pool size.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from craftsim import DEFAULT_PRICES  # noqa: E402
from craftsim.actions import default_actions  # noqa: E402
from craftsim.solver import solve  # noqa: E402
from craftsim.abstract import solve_abstract  # noqa: E402
from craftsim.examples import TARGET_ESSENCE, make_amulet_pool, make_target  # noqa: E402
from craftsim.state import WHITE  # noqa: E402

TARGET = make_target()
GATES = TARGET.value_gates()
ACTS = default_actions(GATES, essence_mod=TARGET_ESSENCE)


def _exact(pool):
    return solve(pool, TARGET, ACTS, DEFAULT_PRICES).value[WHITE]


def _abstract(pool):
    sol = solve_abstract(pool, TARGET, DEFAULT_PRICES, essence_mod=TARGET_ESSENCE)
    return sol.value[sol.model.start], len(sol.states)


def test_abstract_matches_exact_for_uniform_junk():
    pool = make_amulet_pool(4, uniform=True)
    ev = _exact(pool)
    av, _ = _abstract(pool)
    assert abs(ev - av) < 1e-3, (ev, av)   # correction is exact here


def test_abstract_close_for_nonuniform_junk():
    pool = make_amulet_pool(4, uniform=False)
    ev = _exact(pool)
    av, _ = _abstract(pool)
    assert abs(ev - av) / ev < 0.06, (ev, av)


def test_abstract_state_count_is_pool_size_independent():
    _, s_small = _abstract(make_amulet_pool(10))
    _, s_big = _abstract(make_amulet_pool(200))
    assert s_small == s_big, (s_small, s_big)


def test_abstract_scales_to_large_pool_quickly():
    pool = make_amulet_pool(400)            # ~800 mods, exact is intractable
    assert len(pool.mods) > 800
    t = time.time()
    av, n = _abstract(pool)
    assert av > 0 and n < 2000
    assert time.time() - t < 5.0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all abstraction checks passed")
