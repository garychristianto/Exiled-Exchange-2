"""Currency / item prices, all in exalted-orb-equivalent.

In production these come straight from this repo's existing price feeds
(overviewData.json + the trade exchange endpoint). For the prototype they are a
plain dict so you can see how the optimal policy SHIFTS when prices change
(e.g. when omens are cheap, targeted crafting wins; when they're expensive,
spam-and-restart wins).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Prices:
    table: dict[str, float] = field(default_factory=dict)

    def get(self, key: str) -> float:
        if key not in self.table:
            raise KeyError(f"no price for {key!r}")
        return self.table[key]

    def with_(self, **overrides: float) -> "Prices":
        return Prices({**self.table, **overrides})


# Illustrative exalt-equivalent prices. Omens are the expensive levers; the
# finished item ("buy_item") is what crafting competes against.
DEFAULT_PRICES = Prices({
    "transmute": 0.02,
    "augment": 0.05,
    "regal": 0.2,
    "alchemy": 0.3,
    "exalt": 1.0,
    "chaos": 0.25,
    "annul": 2.0,
    "essence": 1.5,
    "divine": 4.0,
    "omen_dextral_exalt": 6.0,
    "omen_sinistral_exalt": 6.0,
    "omen_dextral_annul": 5.0,
    "omen_sinistral_annul": 5.0,
    "base_item": 0.1,
    "buy_item": 40.0,
})
