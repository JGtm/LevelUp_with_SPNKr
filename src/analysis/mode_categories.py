"""Catégories de modes custom (alignées avec les filtres sidebar).

Objectif : utiliser la même logique de regroupement que le composant
`render_hierarchical_checkbox_filter` (sidebar), afin que les calculs de moyennes
historiques et les filtres parlent le même langage.

Catégories renvoyées : Assassin, Fiesta, BTB, Ranked, Firefight, Other.
"""

from __future__ import annotations

import re
from typing import Final

from src.ui.translations import translate_pair_name


_LABEL_SUFFIX_RE: Final[re.Pattern[str]] = re.compile(
    r"^(.*?)(?:\s*[\-–—]\s*[0-9A-Za-z]{8,})$", re.IGNORECASE
)


def normalize_pair_name_to_mode_ui(pair_name: str | None) -> str | None:
    """Normalise un `pair_name` (DB) vers le libellé UI de mode.

    Aligne le comportement avec `src.app.helpers.normalize_mode_label`:
    - traduction via `translate_pair_name`
    - suppression de la carte ("X on Map")
    - suppression des suffixes Forge/Ranked

    Args:
        pair_name: Nom du pair (mode + carte), ex: "Arena:Slayer on Aquarius".

    Returns:
        Libellé UI, ex: "Arène : Assassin", ou None.
    """
    if pair_name is None:
        return None

    raw = str(pair_name).strip()
    if not raw:
        return None

    m = _LABEL_SUFFIX_RE.match(raw)
    if m:
        raw = (m.group(1) or "").strip()

    translated = translate_pair_name(raw)
    if translated is None:
        return None

    s = str(translated).strip()
    if not s:
        return None

    if " on " in s:
        s = s.split(" on ", 1)[0].strip()

    s = re.sub(r"\s*-\s*Forge\b", "", s, flags=re.IGNORECASE).strip()
    s = re.sub(r"\s*-\s*Ranked\b", "", s, flags=re.IGNORECASE).strip()

    return s or None


PREFIX_TO_CATEGORY: Final[dict[str, str]] = {
    # Assassin (Arena, Tactical, Community, etc.)
    "Arena": "Assassin",
    "Arène": "Assassin",
    "Tactical": "Assassin",
    "Tactique": "Assassin",
    "Community": "Assassin",
    "Communauté": "Assassin",
    "Assault": "Assassin",
    # Fiesta (Super Fiesta, Husky Raid, Castle Wars, etc.)
    "Fiesta": "Fiesta",
    "Super Fiesta": "Fiesta",
    "Husky Raid": "Fiesta",
    "Super Husky Raid": "Fiesta",
    "Castle Wars": "Fiesta",
    # BTB
    "BTB": "BTB",
    "BTB Heavies": "BTB",
    # Ranked
    "Ranked": "Ranked",
    "Classé": "Ranked",
    # Firefight
    "Firefight": "Firefight",
    "Baptême du feu": "Firefight",
    "Bapteme du feu": "Firefight",
    "Gruntpocalypse": "Firefight",
    # Autre
    "Event": "Other",
    "Événement": "Other",
    "Evenement": "Other",
}


def infer_mode_super_category(mode_ui: str) -> str:
    """Infère la catégorie custom d'un mode UI.

    Cette logique est volontairement identique à celle de
    `src.ui.components.checkbox_filter._infer_category`.

    Args:
        mode_ui: Libellé UI, ex: "Arène : Assassin".

    Returns:
        Une des catégories : Assassin, Fiesta, BTB, Ranked, Firefight, Other.
    """
    mode_lower = (mode_ui or "").lower()

    # Détecter les modes Fiesta par leur contenu (pas seulement le préfixe)
    if "fiesta" in mode_lower or "husky raid" in mode_lower or "castle wars" in mode_lower:
        return "Fiesta"

    # Extraire le préfixe (avant ":" ou " : ")
    prefix: str | None = None
    if " : " in mode_ui:
        prefix = mode_ui.split(" : ", 1)[0].strip()
    elif ":" in mode_ui:
        prefix = mode_ui.split(":", 1)[0].strip()

    if prefix:
        if prefix in PREFIX_TO_CATEGORY:
            return PREFIX_TO_CATEGORY[prefix]
        for p, cat in PREFIX_TO_CATEGORY.items():
            if prefix.lower() == p.lower():
                return cat

    return "Other"


def infer_custom_category_from_pair_name(pair_name: str | None) -> str:
    """Infère la catégorie custom à partir du `pair_name` (DB).

    Args:
        pair_name: Valeur MatchStats.pair_name.

    Returns:
        Catégorie custom (Assassin/Fiesta/BTB/Ranked/Firefight/Other).
    """
    mode_ui = normalize_pair_name_to_mode_ui(pair_name)
    if not mode_ui:
        return "Other"
    return infer_mode_super_category(mode_ui)


__all__ = [
    "normalize_pair_name_to_mode_ui",
    "infer_mode_super_category",
    "infer_custom_category_from_pair_name",
]