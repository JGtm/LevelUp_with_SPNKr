#!/usr/bin/env python3
"""Compte les citations affichées sans dépendances complexes."""

import json
import re
import unicodedata
from pathlib import Path


def _normalize_name(s: str) -> str:
    """Normalise un nom de citation (même logique que src/ui/commendations.py)."""
    s = (s or "").strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


# CUSTOM_CITATION_RULES hardcodées (copiées depuis src/ui/commendations.py)
CUSTOM_CITATION_RULES = {
    "pilote",
    "ecrasement",
    "assistant",
    "bulldozer",
    "victoireaudrapeau",
    "seulcontretous",
    "victoireenassassin",
    "victoireenbases",
}


def main():
    print("=" * 80)
    print("🔍 Comptage exact des citations affichées")
    print("=" * 80)
    print()

    # 1. Charger les citations
    citations_path = Path("data/wiki/halo5_commendations_fr.json")
    with open(citations_path, encoding="utf-8") as f:
        citations_data = json.load(f)

    all_citations = citations_data.get("items", [])
    print(f"📊 Total citations : {len(all_citations)}")

    # 2. Charger les exclusions
    exclude_path = Path("data/wiki/halo5_commendations_exclude.json")
    with open(exclude_path, encoding="utf-8") as f:
        exclude_data = json.load(f)

    excluded_names = {_normalize_name(name) for name in exclude_data.get("names", [])}
    print(f"🚫 Citations exclues : {len(excluded_names)}")
    print()

    # 3. Filtrer les exclusions
    citations_after_exclude = []
    for cit in all_citations:
        name = cit.get("name", "")
        if _normalize_name(name) not in excluded_names:
            citations_after_exclude.append(cit)

    print(f"✂️  Citations après exclusion : {len(citations_after_exclude)}")
    print()

    # 4. Charger les tracking JSON (s'ils existent)
    tracking_assumed_path = Path("out/commendations_mapping_assumed_old.json")
    tracking_unmatched_path = Path("out/commendations_mapping_unmatched_old.json")

    tracking_rules = set()

    if tracking_assumed_path.exists():
        with open(tracking_assumed_path, encoding="utf-8") as f:
            tracking_data = json.load(f)
            for item in tracking_data.get("items", []):
                name = item.get("name", "")
                if name:
                    tracking_rules.add(_normalize_name(name))

    if tracking_unmatched_path.exists():
        with open(tracking_unmatched_path, encoding="utf-8") as f:
            tracking_data = json.load(f)
            for item in tracking_data.get("items", []):
                name = item.get("name", "")
                if name:
                    tracking_rules.add(_normalize_name(name))

    print(f"📋 Règles de tracking (JSON) : {len(tracking_rules)}")
    print(f"📋 Règles CUSTOM_CITATION_RULES : {len(CUSTOM_CITATION_RULES)}")
    print()

    # 5. Appliquer le filtre de tracking
    displayed_citations = []
    for cit in citations_after_exclude:
        name = cit.get("name", "")
        norm_name = _normalize_name(name)

        # Logique de l'app : norm_name in tracking or norm_name in CUSTOM_CITATION_RULES
        if norm_name in tracking_rules or norm_name in CUSTOM_CITATION_RULES:
            displayed_citations.append(cit)

    print("=" * 80)
    print("✅ RÉSULTAT FINAL")
    print("=" * 80)
    print(f"Citations affichées dans l'app : {len(displayed_citations)}")
    print()

    # 6. Lister toutes les citations affichées
    print("📋 Liste des citations affichées :")
    for i, cit in enumerate(sorted(displayed_citations, key=lambda x: x.get("name", "")), 1):
        name = cit.get("name", "")
        norm_name = _normalize_name(name)

        source = ""
        if norm_name in CUSTOM_CITATION_RULES:
            source = "CUSTOM"
        elif norm_name in tracking_rules:
            source = "JSON"
        else:
            source = "?"

        category = cit.get("category", "")
        print(f"   {i:2d}. [{source:6s}] {name:50s} ({category})")
    print()

    # 7. Statistiques
    custom_only = sum(
        1
        for c in displayed_citations
        if _normalize_name(c.get("name", "")) in CUSTOM_CITATION_RULES
        and _normalize_name(c.get("name", "")) not in tracking_rules
    )
    json_only = sum(
        1
        for c in displayed_citations
        if _normalize_name(c.get("name", "")) in tracking_rules
        and _normalize_name(c.get("name", "")) not in CUSTOM_CITATION_RULES
    )
    both = sum(
        1
        for c in displayed_citations
        if _normalize_name(c.get("name", "")) in tracking_rules
        and _normalize_name(c.get("name", "")) in CUSTOM_CITATION_RULES
    )

    print("📊 STATISTIQUES")
    print(f"   CUSTOM uniquement : {custom_only}")
    print(f"   JSON uniquement : {json_only}")
    print(f"   Les deux : {both}")
    print(f"   TOTAL : {len(displayed_citations)}")
    print()

    if len(tracking_rules) == 0:
        print("⚠️  ATTENTION : Aucun fichier de tracking JSON trouvé !")
        print("   Les fichiers attendus :")
        print(f"   - {tracking_assumed_path}")
        print(f"   - {tracking_unmatched_path}")
        print()
        print("   Si tu vois plus de 8 citations dans l'app, c'est que :")
        print("   1. Les fichiers sont en cache Streamlit")
        print("   2. Ou ils sont stockés ailleurs")
        print()


if __name__ == "__main__":
    main()
