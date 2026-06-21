"""Human-readable presentation + slot analysis for a parsed item.

Slot classification uses a keyword table of common PoE2 affixes (life/ES/mana and
added/increased damage are prefixes; resistances/attributes/speed/crit are
suffixes). It's a heuristic — without the real mod database it can't be perfect —
so unknown lines are shown as '?' rather than guessed.
"""
from __future__ import annotations

from .item_parse import ParsedItem, ParsedMod

# (keyword, slot). First match wins; order matters (specific before generic).
_RULES: list[tuple[str, str]] = [
    # --- prefixes ---
    ("maximum life", "prefix"),
    ("maximum mana", "prefix"),
    ("maximum energy shield", "prefix"),
    ("increased energy shield", "prefix"),
    ("increased armour", "prefix"),
    ("increased evasion", "prefix"),
    ("increased physical damage", "prefix"),
    ("increased spell damage", "prefix"),
    ("increased elemental damage", "prefix"),
    ("adds ", "prefix"),               # "Adds # to # X Damage"
    ("increased damage", "prefix"),
    ("flat life regeneration", "prefix"),
    # --- suffixes ---
    ("all elemental resistances", "suffix"),
    ("resistance", "suffix"),
    ("all attributes", "suffix"),
    ("to strength", "suffix"),
    ("to dexterity", "suffix"),
    ("to intelligence", "suffix"),
    ("to spirit", "suffix"),
    ("attack speed", "suffix"),
    ("cast speed", "suffix"),
    ("critical", "suffix"),
    ("accuracy", "suffix"),
    ("mana regeneration", "suffix"),
    ("life regeneration", "suffix"),
    ("increased rarity", "suffix"),
    ("skill speed", "suffix"),
    ("light radius", "suffix"),
]

_CAPS = {"normal": (0, 0), "magic": (1, 1), "rare": (3, 3), "unique": (3, 3)}


def classify(mod: ParsedMod) -> str:
    low = mod.text.lower()
    for kw, slot in _RULES:
        if kw in low:
            return slot
    return "?"


def _bar(label: str, used: int, cap: int) -> str:
    return f"{label}: {used}/{cap}  " + "●" * used + "○" * (cap - used)


def present(item: ParsedItem) -> str:
    out: list[str] = []
    out.append("═" * 60)
    title = item.name or "(unknown)"
    if item.base and item.base != item.name:
        title += f"   [{item.base}]"
    out.append(title)
    meta = []
    if item.rarity:
        meta.append(item.rarity)
    if item.item_class:
        meta.append(item.item_class)
    if item.ilvl is not None:
        meta.append(f"ilvl {item.ilvl}")
    if item.quality:
        meta.append(f"Q{item.quality}%")
    if item.corrupted:
        meta.append("CORRUPTED")
    if meta:
        out.append("  " + " · ".join(meta))
    out.append("═" * 60)

    if item.implicits:
        out.append("implicit:")
        for m in item.implicits:
            out.append(f"    {m.text}")

    # explicit affixes with slot classification
    pre = [m for m in item.explicits if classify(m) == "prefix"]
    suf = [m for m in item.explicits if classify(m) == "suffix"]
    unk = [m for m in item.explicits if classify(m) == "?"]
    out.append("explicit modifiers:")
    for m in pre:
        out.append(f"    [P] {m.text}")
    for m in suf:
        out.append(f"    [S] {m.text}")
    for m in unk:
        out.append(f"    [?] {m.text}")

    rarity = (item.rarity or "rare").lower()
    capP, capS = _CAPS.get(rarity, (3, 3))
    out.append("")
    out.append(_bar("prefixes", len(pre), capP))
    out.append(_bar("suffixes", len(suf), capS))
    if unk:
        out.append(f"  ({len(unk)} modifier(s) couldn't be slot-classified without the mod DB)")

    out.append("")
    out.append("suggested next step:")
    for line in _advice(rarity, len(pre), len(suf), capP, capS, item.corrupted):
        out.append("  • " + line)
    return "\n".join(out)


def _advice(rarity, np_, ns, capP, capS, corrupted) -> list[str]:
    if corrupted:
        return ["Item is CORRUPTED — modifiers can no longer be changed."]
    openP, openS = capP - np_, capS - ns
    if rarity == "normal":
        return ["White base. Transmute → Augment → Regal to build up, or Alchemy "
                "for an instant rare (4 random mods).",
                "If you want a specific opening mod, use an Essence on the Magic step."]
    if rarity == "magic":
        tips = []
        if openP + openS > 0:
            tips.append(f"{openP} prefix / {openS} suffix slot(s) open — Augment to add a mod.")
        tips.append("Regal to upgrade to Rare (adds one mod).")
        return tips
    # rare
    tips = []
    if openP or openS:
        tips.append(f"{openP} prefix / {openS} suffix slot(s) open.")
        if openP and openS:
            tips.append("Exalt adds to a random open slot; use Omen of Sinistral/"
                        "Dextral Exaltation to force prefix/suffix.")
        elif openS:
            tips.append("Only suffixes open — a plain Exalt can only add a suffix.")
        elif openP:
            tips.append("Only prefixes open — a plain Exalt can only add a prefix.")
    else:
        tips.append("All six slots full. To change a mod: Chaos (swap one random "
                    "mod) or Annul (remove one) — use omens to target prefix/suffix.")
    tips.append("To improve mod VALUES without changing which mods: Divine.")
    return tips
