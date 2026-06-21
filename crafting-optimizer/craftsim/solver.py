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
"""
from __future__ import annotations

from dataclasses import dataclass

from .actions import SUCCESS, Action
from .mods import ModPool
from .prices import Prices
from .state import WHITE, State, meets


@dataclass
class Solution:
    value: dict[State, float]          # expected cost-to-go for every state
    policy: dict[State, Action]        # best action per state
    states: list[State]
    target: frozenset[str]
    pool: ModPool
    prices: Prices

    def best(self, state: State) -> tuple[Action, float]:
        """Optimal next action and expected remaining cost for a (scanned) state."""
        return self.policy[state], self.value[state]


def _reachable(start: State, pool: ModPool, actions: list[Action],
               target: frozenset[str]) -> list[State]:
    seen: set[State] = {start, SUCCESS}
    frontier = [start]
    while frontier:
        s = frontier.pop()
        if meets(s, target):           # goal: no need to expand further
            continue
        for a in actions:
            if not a.applicable(s, pool):
                continue
            dist = a.transition(s, pool)
            if not dist:
                continue
            for s2 in dist:
                if s2 not in seen:
                    seen.add(s2)
                    frontier.append(s2)
    return list(seen)


def solve(pool: ModPool, target: frozenset[str], actions: list[Action],
          prices: Prices, start: State = WHITE,
          tol: float = 1e-9, max_iter: int = 100_000) -> Solution:
    states = _reachable(start, pool, actions, target)

    # Precompute (action, cost, distribution) per state, skipping illegal /
    # no-op moves so value iteration stays cheap.
    moves: dict[State, list[tuple[Action, float, dict]]] = {}
    for s in states:
        if s is SUCCESS or meets(s, target):
            moves[s] = []
            continue
        ms = []
        for a in actions:
            if not a.applicable(s, pool):
                continue
            dist = a.transition(s, pool)
            if not dist:
                continue
            ms.append((a, a.cost(prices), dist))
        moves[s] = ms

    V: dict[State, float] = {s: 0.0 for s in states}
    policy: dict[State, Action] = {}

    for _ in range(max_iter):
        delta = 0.0
        for s in states:
            if not moves[s]:           # terminal (goal or SUCCESS): V stays 0
                continue
            best_cost = float("inf")
            best_act = None
            for a, c, dist in moves[s]:
                q = c + sum(p * V[s2] for s2, p in dist.items())
                if q < best_cost:
                    best_cost, best_act = q, a
            delta = max(delta, abs(best_cost - V[s]))
            V[s] = best_cost
            policy[s] = best_act
        if delta < tol:
            break

    return Solution(V, policy, states, target, pool, prices)
