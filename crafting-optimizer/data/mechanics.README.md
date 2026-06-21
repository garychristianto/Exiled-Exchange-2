# Mechanics spec (`mechanics.template.json`)

This file is **input #2 of three** the optimizer needs. They are separate sources:

| # | Input | Source | Defines |
|---|-------|--------|---------|
| 1 | **Mod pool** | **poe2db** | spawn weights, family/group, ilvl, prefix/suffix, tags, value ranges → the *probabilities* of each transition |
| 2 | **Currency / omen mechanics** | patch notes / wiki / datamine | what each orb/omen *does* → the *structure* of each transition (THIS FILE) |
| 3 | **Prices** | trade API / poe.ninja (already in this repo) | the *cost* of each action |

**poe2db does NOT contain input #2.** How an orb transforms an item is game logic,
not mod-table data — so it is specified here by hand and confirmed against the
live patch.

## How it drives the engine

Each entry maps to one `craftsim` `Action`:
- `operations` → the transition function (set_rarity / add / remove / reroll_values
  / lock / corrupt). The probability of each `add` outcome comes from the poe2db
  mod pool (input #1) filtered by the op's `pool`/`slot`/`tier_floor`.
- `price_key` → the cost, looked up in the prices table (input #3).
- `omen_compatible` → which omens may legally modify the action (each omen entry
  says how: force a slot, override the removal/selection rule, change the count,
  or restrict the pool).

A small loader (future `craftsim/mechanics.py`) reads this JSON and emits the
Action list; the solver is unchanged. New currencies become data edits, not code.

## `verified` flag

`verified: true` only when BOTH the operation shape AND its numbers are confirmed
for the current patch. Today 12/30 are shape-confident basics; the other 18 carry
`null` fields and a `notes` string naming exactly what to fill — e.g. the
`tier_floor` that Greater/Perfect orbs guarantee, the desecrated mod pools per
bone tier, and the **fracture rule** (random vs targeted, min-mod requirement),
which is the single most important unknown because the "isolate then fracture"
line is only optimal if fracture locks a *random* present mod.

## The decisions this is built to answer

- **Ancient vs basic desecrate** → `desecrate_ancient` vs `desecrate_gnawed`: same
  op shape, different `pool` (and price). The optimizer picks by expected cost.
- **Regular Chaos + Whittling vs Greater/Perfect Chaos** → orthogonal levers:
  `whittling` overrides the *removal* to `lowest`; Greater/Perfect raise the
  *added* mod's `tier_floor`. They can combine; the policy chooses per state.

Fill the blanks once poe2db + the patch's mechanic rules are in hand, flip
`verified`, and these become answerable with real expected-cost numbers.
