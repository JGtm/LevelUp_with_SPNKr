#!/usr/bin/env python3
"""
Compte exactement combien de citations sont affichées dans l'app.

Reproduit la logique de src/ui/commendations.py :
1. Charge les 159 citations
2. Applique les exclusions (blacklist)
3. Filtre par tracking rules (CUSTOM_RULES + JSON)
"""

import os
import sys
from pathlib import Path
from typing import Any

# Ajouter le chemin racine au PYTHONPATH
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from src.ui.commendations import (
    CUSTOM_CITATION_RULES,
    _normalize_name,
    load_h5g_commendations_exclude,
    load_h5g_commendations_json,
    load_h5g_commendations_tracking_rules,
)


def _image_basename_from_item(it: dict[str, Any]) -> str | None:
    """Extrait le nom de fichier de l'image."""
    p = it.get("image_path")
    if not isinstance(p, str) or not p.strip():
        return None
    return os.path.basename(p.strip().replace("\\", "/"))


def main() -> None:
    print("=" * 80)
    print("🔍 Comptage exact des citations affichées dans l'app")
    print("=" * 80)
    print()

    # 1. Charger toutes les citations
    data = load_h5g_commendations_json()
    items: list[dict[str, Any]] = list(data.get("items") or [])
    print(f"📊 Total citations (halo5_commendations_fr.json) : {len(items)}")

    # 2. Appliquer les exclusions
    excluded_images, excluded_names = load_h5g_commendations_exclude()
    print(f"🚫 Citations dans la blacklist : {len(excluded_names)}")
    print(f"🚫 Images dans la blacklist : {len(excluded_images)}")
    print()

    if items and (excluded_images or excluded_names):
        kept: list[dict[str, Any]] = []
        for it in items:
            key = _image_basename_from_item(it)
            if key and key in excluded_images:
                continue
            if _normalize_name(str(it.get("name") or "")) in excluded_names:
                continue
            kept.append(it)
        excluded_count = len(items) - len(kept)
        items = kept
        print(f"✂️  Citations après exclusion : {len(items)} ({excluded_count} exclues)")
    else:
        excluded_count = 0
        print(f"✅ Aucune exclusion appliquée : {len(items)} citations candidates")

    print()

    # 3. Charger les règles de tracking
    tracking = load_h5g_commendations_tracking_rules()
    print(f"📋 Règles de tracking (JSON) : {len(tracking)}")
    print(f"📋 Règles CUSTOM_CITATION_RULES : {len(CUSTOM_CITATION_RULES)}")
    print()

    # 4. Afficher les citations avec tracking JSON
    if tracking:
        print("🔍 Citations avec tracking JSON :")
        for i, (norm_name, rule) in enumerate(sorted(tracking.items()), 1):
            # Trouver la citation originale
            original_name = None
            for it in items:
                if _normalize_name(str(it.get("name") or "")) == norm_name:
                    original_name = it.get("name")
                    break

            display_name = original_name or norm_name
            rule_type = "inconnu"
            if "medal_ids" in rule:
                rule_type = f"medal_ids ({len(rule['medal_ids'])} médailles)"
            elif "medal_id" in rule:
                rule_type = f"medal_id ({rule['medal_id']})"
            elif "stat" in rule:
                rule_type = f"stat ({rule['stat']})"

            print(f"   {i:2d}. {display_name:40s} → {rule_type}")
        print()

    # 5. Afficher les CUSTOM_RULES
    print("🔍 Citations avec CUSTOM_CITATION_RULES :")
    for i, (norm_name, rule) in enumerate(sorted(CUSTOM_CITATION_RULES.items()), 1):
        # Trouver la citation originale
        original_name = None
        for it in items:
            if _normalize_name(str(it.get("name") or "")) == norm_name:
                original_name = it.get("name")
                break

        display_name = original_name or norm_name
        rule_type = rule.get("type", "inconnu")
        print(f"   {i:2d}. {display_name:40s} → type: {rule_type}")
    print()

    # 6. Filtrer par tracking rules (logique de l'app)
    def _has_tracking_rule(it: dict[str, Any]) -> bool:
        norm_name = _normalize_name(str(it.get("name") or "").strip())
        return norm_name in tracking or norm_name in CUSTOM_CITATION_RULES

    items_with_tracking = [it for it in items if _has_tracking_rule(it)]

    print("=" * 80)
    print("✅ RÉSULTAT FINAL")
    print("=" * 80)
    print(f"Citations affichées dans l'app : {len(items_with_tracking)}")
    print()

    # 7. Lister toutes les citations affichées
    print("📋 Liste complète des citations affichées :")
    for i, it in enumerate(sorted(items_with_tracking, key=lambda x: x.get("name", "")), 1):
        name = it.get("name", "")
        norm_name = _normalize_name(name)

        # Déterminer la source de la règle
        source = ""
        if norm_name in CUSTOM_CITATION_RULES:
            source = "CUSTOM"
        elif norm_name in tracking:
            source = "JSON"

        print(f"   {i:2d}. [{source:6s}] {name}")
    print()

    # 8. Statistiques
    custom_count = sum(
        1
        for it in items_with_tracking
        if _normalize_name(str(it.get("name") or "")) in CUSTOM_CITATION_RULES
    )
    json_count = sum(
        1 for it in items_with_tracking if _normalize_name(str(it.get("name") or "")) in tracking
    )
    both_count = sum(
        1
        for it in items_with_tracking
        if (
            _normalize_name(str(it.get("name") or "")) in tracking
            and _normalize_name(str(it.get("name") or "")) in CUSTOM_CITATION_RULES
        )
    )

    print("📊 STATISTIQUES")
    print(f"   Citations avec CUSTOM_RULES uniquement : {custom_count - both_count}")
    print(f"   Citations avec JSON uniquement : {json_count - both_count}")
    print(f"   Citations avec les deux : {both_count}")
    print(f"   TOTAL affiché : {len(items_with_tracking)}")
    print()


if __name__ == "__main__":
    main()
