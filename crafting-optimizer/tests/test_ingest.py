"""Ingestion tests: neutral JSON -> ModPool -> solver, and poe2db adapter units.

These run fully offline. The live poe2db fetch is intentionally NOT exercised
here (it depends on network egress); only its pure pieces are tested.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from craftsim import TOY_AMULET, DEFAULT_PRICES, require  # noqa: E402
from craftsim.target import Requirement  # noqa: E402
from craftsim.actions import default_actions  # noqa: E402
from craftsim.solver import solve  # noqa: E402
from craftsim.state import WHITE  # noqa: E402
from craftsim import ingest, poe2db  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "data", "amulet.mods.json")


def test_fixture_loads_and_matches_toy_pool():
    pool = ingest.load_modpool_json(DATA)
    assert pool.item_class == "Amulet" and pool.ilvl == 82
    assert {m.id for m in pool.mods} == {m.id for m in TOY_AMULET.mods}
    # same weights/tiers/ranges as the hand-written toy pool
    for m in pool.mods:
        t = TOY_AMULET.by_id(m.id)
        assert (m.weight, m.ilvl, m.tier, m.vmin, m.vmax, m.gen_type, m.family) == \
               (t.weight, t.ilvl, t.tier, t.vmin, t.vmax, t.gen_type, t.family)


def test_ingested_pool_solves_identically():
    pool = ingest.load_modpool_json(DATA)
    target = require(
        Requirement(accept={"p_life_t1", "p_life_t2"}),
        Requirement(accept={"s_allres_t1", "s_allres_t2"}, min_value=11),
        Requirement(accept={"s_attr"}),
    )
    acts = default_actions(target.value_gates(), essence_mod="p_life_t2")
    v_ingest = solve(pool, target, acts, DEFAULT_PRICES).value[WHITE]
    v_toy = solve(TOY_AMULET, target, acts, DEFAULT_PRICES).value[WHITE]
    assert abs(v_ingest - v_toy) < 1e-9


def test_to_modpool_rejects_bad_records():
    try:
        ingest.to_modpool("Ring", 80, [{"id": "x", "name": "x", "gen_type": "prefix"}])
    except ValueError as e:
        assert "missing keys" in str(e)
    else:
        raise AssertionError("expected ValueError for incomplete record")


def test_poe2db_url_and_coerce():
    assert poe2db.mod_page_url("Body Armour") == "https://poe2db.tw/us/Body_Armour"
    assert poe2db.mod_page_url("Amulet", "cn") == "https://poe2db.tw/cn/Amulet"
    rec = poe2db._coerce({
        "Id": "life1", "Name": "+# to maximum Life", "GenerationType": "1",
        "Families": "Life", "Level": 75, "SpawnWeight": 400,
    })
    assert rec and rec["gen_type"] == "prefix" and rec["weight"] == 400
    m = ingest.record_to_mod(rec)
    assert m.id == "life1" and m.weight == 400


def test_poe2db_parser_fails_loudly_on_unknown_html():
    try:
        poe2db.extract_records("<html><body>nothing here</body></html>")
    except poe2db.ParseError:
        pass
    else:
        raise AssertionError("expected ParseError when structure is absent")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all ingestion checks passed")
