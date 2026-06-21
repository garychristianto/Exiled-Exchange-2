# crafting-optimizer (prototype)

A PoE2 crafting **optimizer** — not a simulator. Given a target item, it computes
the *cheapest expected-cost strategy* to craft it from scratch, and the optimal
**next action for any item you scan**. Built as a stochastic-shortest-path MDP.

This is a **toy-data prototype**: the mod pool in `craftsim/mods.py` is hand-made
so every probability is hand-checkable. The engine is real; only the data is fake.

```
python demo.py               # optimize a tiered, value-gated target amulet
python demo_scale.py         # exact vs abstract as the pool grows (scaling)
python validate.py           # analytic engine vs independent Monte-Carlo
python tests/test_engine.py tests/test_ingest.py \
       tests/test_validation.py tests/test_abstract.py   # 17 checks
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

## Scaling: the abstract engine (`craftsim/abstract.py`)

The exact engine tracks every mod identity, so a real ~500-mod pool explodes the
state set. The **abstract** engine (`solve_abstract`) keeps only what the
optimizer needs:

    (rarity, per-requirement status, junk_prefix_count, junk_suffix_count)

where a requirement status is `absent` / `blocked-by-wrong-tier` / `present(mod,
value_ok)`. Target-relevant mods are tracked exactly; everything else is a per-
slot **count**. The state space therefore depends on the number of target
requirements (a handful), **not** on pool size. Both engines run on the same
generic `solve_mdp`.

Junk weight uses a first-order family-exhaustion correction (`_njw_eff`), which
is **exact for uniform junk weights** and within a few % otherwise. Measured by
`demo_scale.py` / `tests/test_abstract.py`:

| pool | exact E[cost] | abstract | err | exact states | abstract states |
|------|--------------|----------|-----|--------------|-----------------|
| 12 mods | 12.601 | 12.601 | 0.0% | 1,450 | **318** |
| 18 mods | 13.978 | 13.978 | 0.0% | 16,420 | **318** |
| 806 mods | (intractable) | 15.070 | — | — | **318** |

The abstract state count stays flat at 318 while the exact engine goes from 2s to
84s to intractable. Non-uniform junk worst case measured at ~2.7%.

## What's intentionally NOT modeled yet (the plug-in points)

- **Tag re-weighting** — adding a mod can change later weights via tags. Hook:
  `_addable()` / `_place()` in `actions.py` (and the category weights in
  `abstract.py`): swap static `m.weight` for a tag-adjusted weight.
- **Recombinators** — a two-item operation; breaks the single-item state and needs
  a higher-level search on top. Deliberately out of scope for v1.

## Live price integration (later)

The two runtime price inputs already exist in this repo's app:
- **currency / item prices** → the existing `overviewData.json` + trade exchange feeds.
- **the finished-item buy price** (the `Buy` terminal) → a trade search for the target.

So the optimizer drops into the existing price pipeline; only the **mod/weight data**
(from poe2db) is net-new.

## Validation

Three independent layers, all offline and deterministic:

1. **Closed-form** (`tests/test_engine.py`) — the SSP solver matches hand-derived
   expected costs on tiny pools (single guaranteed mod; geometric retry-with-
   restart; buy-beats-craft; tier targeting; Divine value rerolls).
2. **Monte-Carlo cross-check** (`tests/test_validation.py`, `validate.py`) — the
   analytic transition engine is checked against a *separate* random simulator
   (`craftsim/simulate.py`) that re-implements the mechanics by sampling. This is
   exactly the affix-probability model **Craft of Exile** emulates:
   `P(mod) = weight / Σ(eligible weights)`, gated by slot/family/ilvl. Across
   transmute / exalt / chaos / annul / value-gated adds / Divine, and a full
   transmute→regal→exalt→exalt sequence, the two agree to <0.01 total-variation
   distance, and a hand-computed reference (`P(life_t3) = 1000/7850`) is matched
   exactly.
3. **Ingestion** (`tests/test_ingest.py`) — neutral JSON → ModPool → solver, plus
   the poe2db adapter's pure units.

To additionally cross-check against **Craft of Exile's own live numbers for real
PoE2 mods**, allowlist `craftofexile.com` in the environment's egress settings
(same blocker as poe2db) and compare its "chance to hit" output against the
engine on the same imported weights.
