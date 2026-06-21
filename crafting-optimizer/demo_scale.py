"""Demonstrate the state abstraction: same answer, but pool-size independent.

Run:  python demo_scale.py

The exact engine tracks every mod identity, so its state space explodes as the
mod pool grows. The abstract engine tracks only target-relevant mods + junk
*counts*, so its state space (and runtime) stay flat — while giving the same
expected cost (exactly so for uniform junk; within a few % otherwise).
"""
from __future__ import annotations

import time

from craftsim import DEFAULT_PRICES
from craftsim.actions import default_actions
from craftsim.solver import solve
from craftsim.abstract import solve_abstract
from craftsim.examples import TARGET_ESSENCE, make_amulet_pool, make_target
from craftsim.state import WHITE

target = make_target()
gates = target.value_gates()
acts = default_actions(gates, essence_mod=TARGET_ESSENCE)


def run_exact(pool):
    t = time.time()
    sol = solve(pool, target, acts, DEFAULT_PRICES)
    return sol.value[WHITE], len(sol.states), time.time() - t


def run_abstract(pool):
    t = time.time()
    sol = solve_abstract(pool, target, DEFAULT_PRICES, essence_mod=TARGET_ESSENCE)
    return sol.value[sol.model.start], len(sol.states), time.time() - t


def main():
    print("Exact vs abstract as the pool grows (uniform junk weights):")
    print(f"{'mods':>6} {'exact E[c]':>11} {'abs E[c]':>9} {'err':>6}"
          f" {'exStates':>9} {'absStates':>10} {'exact t':>9} {'abs t':>7}")
    print("-" * 78)
    for nf in (3, 6):                     # exact is only tractable for small pools
        pool = make_amulet_pool(nf)
        ev, es, et = run_exact(pool)
        av, as_, at = run_abstract(pool)
        nmods = len(pool.mods)
        print(f"{nmods:>6} {ev:>11.3f} {av:>9.3f} {100*abs(ev-av)/ev:>5.1f}%"
              f" {es:>9} {as_:>10} {et:>8.1f}s {at:>6.2f}s")

    print("\nAbstract only — pools the exact engine cannot finish:")
    print(f"{'mods':>6} {'abs E[c]':>9} {'absStates':>10} {'abs t':>7}")
    print("-" * 36)
    for nf in (25, 100, 400):
        pool = make_amulet_pool(nf)
        av, as_, at = run_abstract(pool)
        print(f"{len(pool.mods):>6} {av:>9.3f} {as_:>10} {at:>6.2f}s")

    print("\nNon-uniform junk (worst case for the correction):")
    for nf in (3, 12, 40):
        pool = make_amulet_pool(nf, uniform=False)
        ev, es, et = run_exact(pool) if nf <= 6 else (None, None, None)
        av, as_, at = run_abstract(pool)
        if ev is not None:
            print(f"  {len(pool.mods):>3} mods: exact {ev:.3f} vs abstract {av:.3f}"
                  f"  ({100*abs(ev-av)/ev:.1f}% err)")
        else:
            print(f"  {len(pool.mods):>3} mods: abstract {av:.3f}  (exact intractable)")


if __name__ == "__main__":
    main()
