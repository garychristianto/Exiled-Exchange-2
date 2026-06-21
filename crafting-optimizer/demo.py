"""Demonstration: optimize crafting a target amulet from a white base.

Run:  python demo.py
"""
from __future__ import annotations

from craftsim import DEFAULT_PRICES, Rarity, State, TOY_AMULET, solve
from craftsim.actions import default_actions
from craftsim.state import WHITE


def line(title: str) -> None:
    print("\n" + title)
    print("-" * len(title))


def main() -> None:
    pool = TOY_AMULET
    prices = DEFAULT_PRICES

    # Goal needs a RARE: one prefix + TWO suffixes, where one suffix (all-res) is
    # a low-weight chase mod. Because you need two specific suffixes, blind
    # Exalts waste slots on prefixes -> suffix-targeting omens can pay off.
    target = frozenset({"p_life", "s_allres", "s_attr"})
    actions = default_actions(essence_mod="p_life")

    sol = solve(pool, target, actions, prices)
    craft_cost = sol.value[WHITE]
    buy_cost = prices.get("buy_item")

    print("=" * 72)
    print("TARGET (rare amulet):  p_life  +  s_allres  +  s_attr")
    print("   s_allres is a low-weight chase suffix; two suffixes needed -> a")
    print("   blind Exalt can waste a slot on a prefix, so targeting matters.")
    print("=" * 72)

    line("1) Worth crafting at all?  (buy-vs-craft terminal)")
    print(f"   E[cost] to CRAFT from white : {craft_cost:6.2f} ex")
    print(f"   Cost to BUY finished item   : {buy_cost:6.2f} ex")
    print(f"   -> Recommendation: {'CRAFT' if craft_cost < buy_cost else 'BUY'}")

    line("2) The adaptive policy:  scan an item -> best next action")
    # A curated set of states a player might scan, chosen to show the policy
    # making *different* decisions depending on the board.
    examples = [
        ("white base", WHITE),
        ("got the life prefix (magic)",
         State(Rarity.MAGIC, frozenset({"p_life"}))),
        ("rare, life + all-res, one suffix slot left",
         State(Rarity.RARE, frozenset({"p_life", "s_allres"}))),
        ("rare, suffixes FULL with two junk -> need a removal",
         State(Rarity.RARE, frozenset({"p_life", "s_allres", "s_fire", "s_cold"}))),
        ("rare, two prefixes wasted + junk suffix",
         State(Rarity.RARE, frozenset({"p_es", "p_mana", "s_fire"}))),
    ]
    for label, s in examples:
        if s in sol.policy:
            act, v = sol.best(s)
            print(f"   {label:<48} -> {act.name:<16} (E[cost left]={v:5.2f}ex)")
        else:
            print(f"   {label:<48} -> (already complete)")

    line("3a) Policy responds to PRICES:  drop the buy price -> CRAFT flips to BUY")
    for bp in (40.0, 8.0, 4.0):
        s = solve(pool, target, actions, prices.with_(buy_item=bp))
        rec = "CRAFT" if s.value[WHITE] < bp else "BUY"
        print(f"   buy_item={bp:5.1f}ex  ->  E[craft]={s.value[WHITE]:5.2f}ex  ->  {rec}")

    line("3b) When are targeting OMENS actually worth it?")
    def omen_states(solution):
        return sum(1 for a in solution.policy.values() if "+" in a.name)
    print(f"   omens @ default ({prices.get('omen_dextral_annul'):.0f}ex): "
          f"used in {omen_states(sol)} of {len(sol.states)} states")
    for op in (3.0, 1.0, 0.3):
        s = solve(pool, target, actions, prices.with_(
            omen_dextral_annul=op, omen_sinistral_annul=op,
            omen_dextral_exalt=op, omen_sinistral_exalt=op))
        print(f"   omens @ {op:>4.1f}ex          : "
              f"used in {omen_states(s)} states, E[craft]={s.value[WHITE]:.2f}ex")

    print(f"\n[reachable states explored: {len(sol.states)}]")


if __name__ == "__main__":
    main()
