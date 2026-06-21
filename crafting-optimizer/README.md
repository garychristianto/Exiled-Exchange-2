# crafting-optimizer (prototype)

A PoE2 crafting **optimizer** — not a simulator. Given a target item, it computes
the *cheapest expected-cost strategy* to craft it from scratch, and the optimal
**next action for any item you scan**. Built as a stochastic-shortest-path MDP.

This is a **toy-data prototype**: the mod pool in `craftsim/mods.py` is hand-made
so every probability is hand-checkable. The engine is real; only the data is fake.

```
python demo.py               # optimize a tiered, value-gated target amulet
python tests/test_engine.py  # analytic sanity checks (closed-form expected costs)
python tests/test_ingest.py  # data ingestion: neutral JSON -> ModPool -> solver
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
| **Divine** | reroll the *values* of value-gated mods within their tier range |
| **Buy** | stop and buy the finished item — answers *is crafting even worth it?* |
| **Restart** | abandon to a fresh white base — PoE2's only real "scour" |

Each action is a probabilistic transition `state → {state: probability}` computed
from spawn weights, open prefix/suffix slots, mod families (coexistence), and ilvl.

**Tiers & value targets** (`craftsim/target.py`) — a stat like *Life* is a family
of tier rows (t1/t2/t3), each with its own ilvl, weight and value range; family
exclusion already prevents two tiers coexisting, so tiers need only data. A
`Target` is a list of `Requirement`s, each accepting any of a set of mods
(e.g. "T1 **or** T2 life") with an optional `min_value`. A `min_value` makes
**Divine** meaningful: a present mod may or may not clear its value threshold
(tracked in `State.good`), and Divine rerolls. The demo shows craft cost rising
as you demand higher tiers, and Divine being used only when its price is low
enough.

**Solver** (`craftsim/solver.py`) — value iteration over the reachable state set,
compiled to integer-indexed states + value arrays (no dict hashing in the hot
loop). The `Buy` terminal makes every state able to reach the goal at finite
cost, so the SSP is *proper* and iteration converges cleanly.

**Prices** (`craftsim/prices.py`) — currency/item costs in exalt-equivalent. The
demo shows the policy shifting as prices change (buy-vs-craft flip; Divine usage).

## Getting real data (poe2db)

The engine consumes a **neutral mod schema** (`craftsim/ingest.py`); any source
just emits records of that shape, so the engine never sees source quirks:

```python
from craftsim import ingest
pool = ingest.load_modpool_json("data/amulet.mods.json")   # ready-to-solve ModPool
```

`data/amulet.mods.json` is a hand-authored sample in that schema. To populate it
from **poe2db** (`craftsim/poe2db.py`):

```python
from craftsim import poe2db, ingest
recs = poe2db.fetch_mods("Amulet")                       # live fetch + parse
poe2db.cache_to_json(recs, "data/amulet.mods.json",      # snapshot to schema
                     item_class="Amulet", ilvl=82)
pool = ingest.load_modpool_json("data/amulet.mods.json") # offline thereafter
```

Two caveats, surfaced honestly:
1. **Network egress** — `poe2db.tw` must be in this environment's egress
   allowlist; otherwise `fetch` raises `EgressNotAllowed` with instructions.
   (It is *not* allowlisted in the default web sandbox, which is why the live
   fetch path could not be exercised here.)
2. **Parser is provisional** — `extract_records()`'s selectors were written
   without a live page to verify against, so they **fail loudly** (`ParseError`)
   rather than emit wrong weights. Validate them against a real poe2db page, then
   `cache_to_json` — from then on everything runs offline against the snapshot.

## What's intentionally NOT modeled yet (the plug-in points)

- **Tag re-weighting** — adding a mod can change later weights via tags. Hook:
  `_addable()` / `_place()` in `actions.py` (swap static `m.weight` for a
  tag-adjusted weight given the current state's tags).
- **State abstraction for scale** — the toy tracks exact mod identities (~1.5k
  states for a 3-requirement tiered/value-gated target). At full scale, abstract
  to (target mods present, junk-prefix count, junk-suffix count, relevant tags) —
  collapses millions of states to a few thousand without changing the solver.
  See `state.py` header.
- **Recombinators** — a two-item operation; breaks the single-item state and needs
  a higher-level search on top. Deliberately out of scope for v1.

## Live price integration (later)

The two runtime price inputs already exist in this repo's app:
- **currency / item prices** → the existing `overviewData.json` + trade exchange feeds.
- **the finished-item buy price** (the `Buy` terminal) → a trade search for the target.

So the optimizer drops into the existing price pipeline; only the **mod/weight data**
(from poe2db) is net-new.

## Validation

`tests/test_engine.py` pins the SSP math against closed-form expected costs on tiny
pools (single guaranteed mod; geometric retry-with-restart; buy-beats-craft;
**tier targeting**; **Divine value rerolls**). `tests/test_ingest.py` checks the
data path (neutral JSON → ModPool → solver, and the poe2db adapter's pure units).
The next validation step is to reproduce a handful of Craft of Exile "chance to
hit mod X" numbers once real poe2db weights are loaded.
