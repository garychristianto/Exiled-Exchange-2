"""Stochastic-shortest-path solver over the crafting MDP.

We minimise EXPECTED currency cost (exalt-equivalent) to reach a state that
contains all target mods. Because the `BUY` action lets every state reach the
goal in one step at finite cost, the problem is a *proper* SSP and plain value
iteration converges.

    V(goal)  = 0
    V(s)     = min over legal actions a of [ cost(a) + sum_s' P(s'|s,a) * V(s') ]

The argmin action in each state is the optimal policy — i.e. the best click to
make given whatever the item currently is. That is exactly what powers a
"scan item -> tell me the next step" feature.

`solve_mdp` is the generic engine: it takes any hashable states, an `expand`
function (state -> list of (action, cost, {state: prob})) and an `is_goal`
predicate. Both the exact identity-tracking model (`solve`) and the abstract,
pool-size-independent model (craftsim.abstract) drive it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Hashable

from .actions import SUCCESS, Action
from .mods import ModPool
from .prices import Prices
from .state import WHITE, State
from .target import Target

Expand = Callable[[Hashable], "list[tuple]"]
IsGoal = Callable[[Hashable], bool]


@dataclass
class Solution:
    value: dict                        # state -> expected cost-to-go
    policy: dict                       # state -> best action
    states: list
    target: Target | None = None
    pool: ModPool | None = None
    prices: Prices | None = None

    def best(self, state):
        """Optimal next action and expected remaining cost for a (scanned) state."""
        return self.policy[state], self.value[state]


def solve_mdp(start: Hashable, expand: Expand, is_goal: IsGoal,
              tol: float = 1e-7, max_iter: int = 100_000):
    """Generic stochastic-shortest-path value iteration over arbitrary states.

    Returns (value, policy, states). Goal states are terminal with value 0;
    every other state must be able to reach a goal (the Buy terminal guarantees
    this), so iteration converges. The hot loop runs on integer-indexed arrays.
    """
    # 1) discover reachable states and cache their compiled moves
    expanded: dict = {}
    seen = {start}
    frontier = [start]
    while frontier:
        s = frontier.pop()
        if is_goal(s):
            expanded[s] = []
            continue
        ms = expand(s)
        expanded[s] = ms
        for _, _, dist in ms:
            for s2 in dist:
                if s2 not in seen:
                    seen.add(s2)
                    frontier.append(s2)

    states = list(seen)
    idx = {s: i for i, s in enumerate(states)}
    move_acts = [[] for _ in states]
    move_costs = [[] for _ in states]
    move_dists = [[] for _ in states]
    for s, i in idx.items():
        for a, c, dist in expanded.get(s, []):
            move_acts[i].append(a)
            move_costs[i].append(c)
            move_dists[i].append(tuple((idx[s2], p) for s2, p in dist.items()))

    n = len(states)
    V = [0.0] * n
    best = [-1] * n
    active = [i for i in range(n) if move_acts[i]]
    for _ in range(max_iter):
        delta = 0.0
        for i in active:
            costs, dists = move_costs[i], move_dists[i]
            bc, bj = float("inf"), -1
            for j in range(len(costs)):
                q = costs[j]
                for k, p in dists[j]:
                    q += p * V[k]
                if q < bc:
                    bc, bj = q, j
            if abs(bc - V[i]) > delta:
                delta = abs(bc - V[i])
            V[i] = bc
            best[i] = bj
        if delta < tol:
            break

    value = {s: V[idx[s]] for s in states}
    policy = {s: move_acts[idx[s]][best[idx[s]]] for s in states if best[idx[s]] >= 0}
    return value, policy, states


def solve(pool: ModPool, target: Target, actions: list[Action],
          prices: Prices, start: State = WHITE,
          tol: float = 1e-7, max_iter: int = 100_000) -> Solution:
    """Exact, identity-tracking solve over the full mod pool."""
    def expand(s: State):
        out = []
        for a in actions:
            if not a.applicable(s, pool):
                continue
            dist = a.transition(s, pool)
            if dist:
                out.append((a, a.cost(prices), dist))
        return out

    def is_goal(s: State) -> bool:
        return s is SUCCESS or target.met(s)

    value, policy, states = solve_mdp(start, expand, is_goal, tol, max_iter)
    return Solution(value, policy, states, target, pool, prices)
