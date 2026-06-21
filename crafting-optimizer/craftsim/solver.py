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
from .state import WHITE, State
from .target import Target


@dataclass
class Solution:
    value: dict[State, float]          # expected cost-to-go for every state
    policy: dict[State, Action]        # best action per state
    states: list[State]
    target: Target
    pool: ModPool
    prices: Prices

    def best(self, state: State) -> tuple[Action, float]:
        """Optimal next action and expected remaining cost for a (scanned) state."""
        return self.policy[state], self.value[state]


def _reachable(start: State, pool: ModPool, actions: list[Action],
               target: Target) -> list[State]:
    seen: set[State] = {start, SUCCESS}
    frontier = [start]
    while frontier:
        s = frontier.pop()
        if target.met(s):              # goal: no need to expand further
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


def solve(pool: ModPool, target: Target, actions: list[Action],
          prices: Prices, start: State = WHITE,
          tol: float = 1e-7, max_iter: int = 100_000) -> Solution:
    states = _reachable(start, pool, actions, target)
    idx = {s: i for i, s in enumerate(states)}

    # Compile each state's legal moves into index/probability arrays so the
    # value-iteration hot loop touches only Python lists/floats (no dict hashing
    # or transition recomputation per sweep). Actions are kept parallel for the
    # policy. Terminals (goal / SUCCESS) get no moves and keep value 0.
    move_acts: list[list[Action]] = [[] for _ in states]
    move_costs: list[list[float]] = [[] for _ in states]
    move_dists: list[list[tuple[tuple[int, float], ...]]] = [[] for _ in states]
    for i, s in enumerate(states):
        if s is SUCCESS or target.met(s):
            continue
        for a in actions:
            if not a.applicable(s, pool):
                continue
            dist = a.transition(s, pool)
            if not dist:
                continue
            move_acts[i].append(a)
            move_costs[i].append(a.cost(prices))
            move_dists[i].append(tuple((idx[s2], p) for s2, p in dist.items()))

    n = len(states)
    V = [0.0] * n
    best = [-1] * n
    # Iterate only over non-terminal states (Gauss-Seidel, in place).
    active = [i for i in range(n) if move_acts[i]]

    for _ in range(max_iter):
        delta = 0.0
        for i in active:
            costs, dists = move_costs[i], move_dists[i]
            bc = float("inf")
            bj = -1
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
    policy = {s: move_acts[idx[s]][best[idx[s]]]
              for s in states if best[idx[s]] >= 0}
    return Solution(value, policy, states, target, pool, prices)
