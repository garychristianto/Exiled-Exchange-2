# Design notes — extending the optimizer (fracture, output, currency tiers)

Captured from the design discussion. These are decisions to implement, not yet built.

## 1. "It looks linear" — two separate things

- **The engine is not linear.** It is already a branching MDP: every state maps to
  an action and outcomes fan out probabilistically. It allows non-monotone moves
  (Annul/Chaos/Restart go "backward" in completion but forward in expected cost).
- **The output reads linear — fix this.** Showing one best-action-per-state plus a
  "most-likely line" collapses the policy tree into a chain and hides the
  contingency structure that *is* crafting. **Render results as a conditional
  policy tree:** "Do A → on result R₁ (p, +C ex) do B; on junk Annul and retry."

## 2. Central principle: model mechanics, never strategies

Do not encode "fish → fracture → chaos" as a recipe. Encode each currency's honest
transition; let value iteration *discover* the line if it is optimal, and report
when it is not. Phases are emergent from the value function — no phase variable.

Key consequence: if **Fracture locks a *random* present mod**, the "isolate the
anchor on a small magic base before fracturing" meta falls out automatically,
because random-fracture has higher chance of locking the anchor when fewer mods
are present. The strategy emerges from the honest mechanic.

## 3. Fracture mechanic — concrete design

- **State:** add `fractured: frozenset[mod_id]`. In the abstract engine each target
  mod status becomes `{absent, present, present-fractured, blocked}` + a small
  "fractured junk" count. Compact.
- **Actions (fracture rule PARAMETERIZED — pin from data, do not guess):**
  - `Fracture(random)` — lock a uniformly-random present mod (branches over which).
  - `Fracture(targeted)` — omen-picked lock; costs more; optimizer compares.
  - `PerfectAug`/`GreaterAug` — add-to-magic from a restricted / higher-tier pool.
  - `Chaos`, `Annul` — **guard:** remove only from `mods − fractured` (this makes
    "chaos-spam the 2nd mod" safe).
  - `Divine` — possibly also blocked on fractured mods if values are locked.
- Modeling both fracture variants matters: lets the optimizer weigh cheap
  random-fracture + isolation effort vs expensive targeted-fracture omen.

## 4. Currency-TIER selection is the same problem

Real micro-decisions players ask, all resolved as competing actions (cost vs
tier-bias vs targeting), chosen per state by the MDP:
- **Desecration:** ancient (better desecrated-mod pool/tiers) vs basic bones.
- **Chaos family:** regular Chaos + **Omen of Whittling** (removes the *lowest* mod)
  vs **Greater**/**Perfect** Chaos (bias the *added* mod to higher tiers). Whittling
  controls *which mod leaves*; Greater/Perfect controls *the tier of what arrives* —
  orthogonal, can combine.
- Same for Greater/Perfect Exalt/Regal/Aug.

Each is just another `Action` with its own cost and transition. The exact tier
thresholds / desecrated pools / Greater-Perfect guarantees MUST come from data
(poe2db + mechanic rules), not memory.

## 5. Deferred frontier: multi-item

Recombinators / fracture-transfer (craft two items, merge) break the single-item
state (needs a state over *pairs*) and a higher-level search on top of the per-item
MDP. Single-item fracture lines fit cleanly; recombination is the next tier up.

## Build order

1. **Conditional policy-tree output** (kills the "linear" feel; makes branches
   readable).
2. **Fracture state field + Fracture/Chaos-guard/PerfectAug actions**, rule
   parameterized.
3. **Currency-tier variants** (Greater/Perfect/Whittling/desecrate) as actions.
4. Let the optimizer *discover* whether a given meta line wins; show the tree.
5. (Later) multi-item / recombinators.
