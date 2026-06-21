"""Parser/presenter checks on a sample clipboard item."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from craftsim.item_parse import parse_item  # noqa: E402
from craftsim.present import classify, present  # noqa: E402

SAMPLE = """Item Class: Amulets
Rarity: Rare
Foe Whisper
Stellar Amulet
--------
Requirements:
Level: 65
--------
Item Level: 81
--------
+12 to Spirit (implicit)
--------
+45 to maximum Life
+18% to Cold Resistance
+9% to all Elemental Resistances
--------
"""


def test_parse_header_and_mods():
    it = parse_item(SAMPLE)
    assert it.item_class == "Amulets"
    assert it.rarity == "Rare"
    assert it.base == "Stellar Amulet"
    assert it.ilvl == 81
    assert len(it.implicits) == 1 and it.implicits[0].values == [12.0]
    assert len(it.explicits) == 3


def test_slot_classification():
    it = parse_item(SAMPLE)
    by = {m.text: classify(m) for m in it.explicits}
    assert by["+45 to maximum Life"] == "prefix"
    assert by["+18% to Cold Resistance"] == "suffix"
    assert by["+9% to all Elemental Resistances"] == "suffix"


def test_present_runs():
    out = present(parse_item(SAMPLE))
    assert "prefixes: 1/3" in out and "suffixes: 2/3" in out


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all parse checks passed")
