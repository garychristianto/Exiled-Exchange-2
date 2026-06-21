# crafting-optimizer (prototype)

A PoE2 crafting **optimizer** — not a simulator. Given a target item, it computes
the *cheapest expected-cost strategy* to craft it from scratch, and the optimal
**next action for any item you scan**. Built as a stochastic-shortest-path MDP.

This is a **toy-data prototype**: the mod pool in `craftsim/mods.py` is hand-made
so every probability is hand-checkable. The engine is real; only the data is fake.

```
python demo.py            # optimize a target amulet, show the adaptive policy
python tests/test_engine.py   # analytic sanity checks (closed-form expected costs)
```

## Why an MDP (and why this beats Craft of Exile / PoEDB)

Existing tools *simulate* a strategy you pick. PoE2 crafting is low-control
(no bench, no scour, no essence-spam), so the hard question is **which** strategy,
and what to do after each gamble. That is a Markov Decision Process:

```
minimize  E[ total currency cost ]  to reach a state containing the target mods

V(goal) = 0
V(s)    = min over legal actions a of [ cost(a) + Σ P(s'|s,a) · V(s') ]
```

The argmin action per state is the **optimal policy** — the best click for *any*
board state. That is exactly what powers "scan item → tell me the next step".
A human can enumerate a few fixed strategies; the solver returns the whole
adaptive decision tree, priced, including non-obvious recovery branches.

## What's modeled

**Actions** (`craftsim/actions.py`) — PoE2 mechanics, *not* PoE1:

| Action | Effect |
|---|---|
| Transmute / Augment / Regal / Alchemy | normal→magic→rare progression, weighted random adds |
| Exalt (+ Sinistral/Dextral omen) | add a mod; omen locks it to prefix/suffix |
| Chaos | remove 1 random mod, add 1 random mod |
| Annul (+ Sinistral/Dextral omen) | remove a mod; omen locks the slot |
| Essence | magic→rare with one **guaranteed** mod (single-use, no spam) |
| **Buy** | stop and buy the finished item — answers *is crafting even worth it?* |
| **Restart** | abandon to a fresh white base — PoE2's only real "scour" |

Each action is a probabilistic transition `state → {state: probability}` computed
from spawn weights, open prefix/suffix slots, mod families (coexistence), and ilvl.

**Solver** (`craftsim/solver.py`) — value iteration over the reachable state set.
The `Buy` terminal makes every state able to reach the goal at finite cost, so the
SSP is *proper* and iteration converges cleanly.

**Prices** (`craftsim/prices.py`) — currency/item costs in exalt-equivalent. The
demo shows the policy shifting as prices change (buy-vs-craft flip; when targeting
omens become worth using).

## What's intentionally NOT modeled yet (the plug-in points)

- **Real spawn weights** — toy numbers. *Real data path: ingest poe2db mod tables*
  (prefix/suffix, family/group, required ilvl, tags, spawn weight) into the
  `Mod`/`ModPool` shapes in `mods.py`. Nothing else changes.
- **Tag re-weighting** — adding a mod can change later weights via tags. Hook:
  `_addable()` in `actions.py` (swap static `m.weight` for a tag-adjusted weight).
- **Tiers / value ranges** — success is currently "mod present". Add tier to the
  state and a `Divine` action to reroll values within a tier.
- **State abstraction for scale** — the toy tracks exact mod identities (422 states
  here). At full scale, abstract to (target mods present, junk-prefix count,
  junk-suffix count, relevant tags) — collapses millions of states to a few
  thousand without changing the solver. See `state.py` header.
- **Recombinators** — a two-item operation; breaks the single-item state and needs
  a higher-level search on top. Deliberately out of scope for v1.

## Live-data integration (later)

The two runtime inputs already exist in this repo's app:
- **currency / item prices** → the existing `overviewData.json` + trade exchange feeds.
- **the finished-item buy price** (the `Buy` terminal) → a trade search for the target.

So the optimizer drops into the existing price pipeline; only the **mod/weight data**
(from poe2db) is net-new.

## Validation

`tests/test_engine.py` pins the SSP math against closed-form expected costs on tiny
pools (single guaranteed mod; geometric retry-with-restart; buy-beats-craft). The
next validation step is to reproduce a handful of Craft of Exile "chance to hit
mod X" numbers once real poe2db weights are loaded.
