"""Demonstration: optimize crafting a tiered, value-gated target amulet.

Run:  python demo.py
"""
from __future__ import annotations

from craftsim import DEFAULT_PRICES, Rarity, State, TOY_AMULET, require
from craftsim.target import Requirement
from craftsim.actions import default_actions
from craftsim.solver import solve
from craftsim.state import WHITE


def line(title: str) -> None:
    print("\n" + title)
    print("-" * len(title))


def main() -> None:
    pool = TOY_AMULET
    prices = DEFAULT_PRICES

    # Target (needs a RARE: 1 prefix + 2 suffixes):
    #   - Life at tier T2 or better          (accept the t1/t2 rows)
    #   - All-Res, and its value must be >=11 (t1 always clears it; t2 only 1/3)
    #   - All Attributes (any roll)
    target = require(
        Requirement(accept={"p_life_t1", "p_life_t2"}),
        Requirement(accept={"s_allres_t1", "s_allres_t2"}, min_value=11),
        Requirement(accept={"s_attr"}),
    )
    gates = target.value_gates()
    actions = default_actions(gates, essence_mod="p_life_t2")

    sol = solve(pool, target, actions, prices)
    craft_cost = sol.value[WHITE]
    buy_cost = prices.get("buy_item")

    print("=" * 72)
    print("TARGET (rare amulet):")
    print("   Life  >= T2          (accept tiers t1 or t2)")
    print("   All-Res value >= 11   (t1 always ok; t2 needs a high roll -> Divine)")
    print("   All Attributes        (any roll)")
    print("=" * 72)

    line("1) Worth crafting at all?  (buy-vs-craft terminal)")
    print(f"   E[cost] to CRAFT from white : {craft_cost:6.2f} ex")
    print(f"   Cost to BUY finished item   : {buy_cost:6.2f} ex")
    print(f"   -> Recommendation: {'CRAFT' if craft_cost < buy_cost else 'BUY'}")

    line("2) The adaptive policy:  scan an item -> best next action  (* = value ok)")
    examples = [
        ("white base", WHITE),
        ("magic, got T1 life",
         State(Rarity.MAGIC, frozenset({"p_life_t1"}))),
        ("rare, life + all-res(T1, value ok), one suffix open",
         State(Rarity.RARE, frozenset({"p_life_t2", "s_allres_t1"}), frozenset({"s_allres_t1"}))),
        ("rare, all mods present BUT all-res value too low",
         State(Rarity.RARE, frozenset({"p_life_t2", "s_allres_t2", "s_attr"}), frozenset())),
        ("rare, two junk prefixes + junk suffix",
         State(Rarity.RARE, frozenset({"p_es", "p_mana", "s_fire"}), frozenset())),
    ]
    for label, s in examples:
        if target.met(s):
            print(f"   {label:<52} -> DONE")
        else:
            act, v = sol.best(s)
            print(f"   {label:<52} -> {act.name:<16} (E[cost left]={v:5.2f}ex)")

    line("3) Tier targeting responds to how PICKY you are")
    for label, tgt in [
        ("Life >= T3 (any life)", require(
            Requirement(accept={"p_life_t1", "p_life_t2", "p_life_t3"}),
            Requirement(accept={"s_allres_t1", "s_allres_t2"}),
            Requirement(accept={"s_attr"}))),
        ("Life >= T2", target),
        ("Life >= T1 (best only)", require(
            Requirement(accept={"p_life_t1"}),
            Requirement(accept={"s_allres_t1", "s_allres_t2"}),
            Requirement(accept={"s_attr"}))),
    ]:
        g = tgt.value_gates()
        s = solve(pool, tgt, default_actions(g, essence_mod="p_life_t2"), prices)
        print(f"   {label:<26} -> E[craft] = {s.value[WHITE]:6.2f} ex")

    line("4) Divine usage responds to its price")
    for dp in (8.0, 4.0, 1.0):
        s = solve(pool, target, default_actions(gates, essence_mod="p_life_t2"),
                  prices.with_(divine=dp))
        used = sum(1 for a in s.policy.values() if a.name == "Divine")
        print(f"   divine={dp:4.1f}ex -> used in {used:2d} states, E[craft]={s.value[WHITE]:.2f}ex")

    print(f"\n[reachable states explored: {len(sol.states)}]")


if __name__ == "__main__":
    main()
