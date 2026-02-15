#!/usr/bin/env python3
"""
Analyse les citations H5G non mappées et leur alignement potentiel avec personal_score_awards.

Objectif : Identifier quelles citations peuvent être calculées en utilisant les awards.
"""

import json
import sys
from pathlib import Path
from typing import Any

# Ajouter le chemin racine au PYTHONPATH
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from src.ui.commendations import (
    CUSTOM_CITATION_RULES,
    _normalize_name,
    load_h5g_commendations_json,
    load_h5g_commendations_tracking_rules,
)

# Catégories d'awards connues dans personal_score_awards
AWARD_CATEGORIES = {
    "kill": ["Kill", "Melee Kill", "Headshot Kill", "Assassination", "Power Weapon Kill"],
    "assist": ["Assist", "Driver Assist", "Callout Assist"],
    "objective": [
        "Flag Capture",
        "Flag Carrier Kill",
        "Flag Defense",
        "Flag Return",
        "Zone Capture",
        "Zone Defense",
        "Stockpile Deposit",
    ],
    "vehicle": [
        "Vehicle Destruction",
        "Vehicle Hijack",
        "Ram",
        "Splatter",
    ],
    "penalty": ["Betrayal", "Suicide", "Death"],
}

# Mots-clés pour détecter les citations compatibles awards
KEYWORDS_TO_AWARDS = {
    # Kills par arme/véhicule
    "tuez": "kill",
    "eliminez": "kill",
    "éliminez": "kill",
    "kill": "kill",
    "tuer": "kill",
    # Assists
    "assist": "assist",
    "assistance": "assist",
    "aidez": "assist",
    # Objectifs
    "capture": "objective",
    "capturez": "objective",
    "défense": "objective",
    "defense": "objective",
    "drapeau": "objective",
    "flag": "objective",
    "zone": "objective",
    "stockpile": "objective",
    # Véhicules
    "vehicule": "vehicle",
    "véhicule": "vehicle",
    "vehicle": "vehicle",
    "destruction": "vehicle",
    "detruisez": "vehicle",
    "détruisez": "vehicle",
    "splatter": "vehicle",
    "ecrasement": "vehicle",
    "écrasement": "vehicle",
    # Modes de jeu (pour victoires)
    "victoire": "wins_mode",
    "gagnez": "wins_mode",
    "remportez": "wins_mode",
    # KD
    "ratio": "matches_mode_kd",
    "efficacité": "matches_mode_kd",
    "efficacite": "matches_mode_kd",
}


def analyze_citation_description(description: str) -> dict[str, Any]:
    """Analyse la description d'une citation pour identifier son type potentiel."""
    desc_lower = description.lower()

    detected_types = set()
    for keyword, award_type in KEYWORDS_TO_AWARDS.items():
        if keyword in desc_lower:
            detected_types.add(award_type)

    return {
        "detected_types": list(detected_types),
        "is_mappable_to_awards": len(detected_types) > 0,
        "confidence": "high"
        if len(detected_types) >= 2
        else "medium"
        if len(detected_types) == 1
        else "low",
    }


def suggest_award_names(citation_name: str, description: str) -> list[str]:
    """Suggère des award_name potentiels basés sur la description."""
    desc_lower = description.lower()
    suggestions = set()

    # Kills génériques
    if any(kw in desc_lower for kw in ["tuez", "éliminez", "tuer", "kill"]):
        suggestions.add("Kill")

        # Spécialisations
        if any(kw in desc_lower for kw in ["headshot", "tête", "tete"]):
            suggestions.add("Headshot Kill")
        if any(kw in desc_lower for kw in ["melee", "mêlée", "melee"]):
            suggestions.add("Melee Kill")
        if any(kw in desc_lower for kw in ["assassination", "assassinat"]):
            suggestions.add("Assassination")
        if any(kw in desc_lower for kw in ["power weapon", "arme de puissance"]):
            suggestions.add("Power Weapon Kill")

    # Assists
    if any(kw in desc_lower for kw in ["assist", "assistance", "aidez"]):
        suggestions.add("Assist")
        if any(kw in desc_lower for kw in ["driver", "conducteur", "pilote"]):
            suggestions.add("Driver Assist")
        if any(kw in desc_lower for kw in ["callout", "marquage"]):
            suggestions.add("Callout Assist")

    # Objectifs
    if "flag" in desc_lower or "drapeau" in desc_lower:
        if "capture" in desc_lower or "capturez" in desc_lower:
            suggestions.add("Flag Capture")
        if "défense" in desc_lower or "defense" in desc_lower:
            suggestions.add("Flag Defense")
        if "return" in desc_lower or "retour" in desc_lower:
            suggestions.add("Flag Return")
        if "kill" in desc_lower or "tuez" in desc_lower:
            suggestions.add("Flag Carrier Kill")

    if "zone" in desc_lower:
        if "capture" in desc_lower:
            suggestions.add("Zone Capture")
        if "défense" in desc_lower or "defense" in desc_lower:
            suggestions.add("Zone Defense")

    if "stockpile" in desc_lower and "deposit" in desc_lower:
        suggestions.add("Stockpile Deposit")

    # Véhicules
    if any(kw in desc_lower for kw in ["vehicle", "véhicule", "vehicule"]):
        if "destruction" in desc_lower or "détruisez" in desc_lower:
            suggestions.add("Vehicle Destruction")
        if "hijack" in desc_lower or "piratage" in desc_lower:
            suggestions.add("Vehicle Hijack")

    if any(kw in desc_lower for kw in ["splatter", "écrasement", "ecrasement"]):
        suggestions.add("Splatter")

    return sorted(suggestions)


def main() -> None:
    """Analyse principale."""
    print("=" * 80)
    print("🔍 Analyse des citations H5G - Alignement avec awards")
    print("=" * 80)
    print()

    # 1. Charger toutes les citations
    citations_data = load_h5g_commendations_json()
    all_citations = citations_data.get("items", [])
    print(f"📊 Total citations : {len(all_citations)}")

    # 2. Charger les règles existantes
    tracking_rules = load_h5g_commendations_tracking_rules()
    print(f"📋 Citations avec tracking JSON : {len(tracking_rules)}")
    print(f"📋 Citations avec CUSTOM_RULES : {len(CUSTOM_CITATION_RULES)}")

    # Union des règles
    all_mapped = set(tracking_rules.keys()) | set(CUSTOM_CITATION_RULES.keys())
    print(f"✅ Total citations mappées : {len(all_mapped)}")
    print()

    # 3. Identifier les citations non mappées
    unmapped_citations = []
    for citation in all_citations:
        name = str(citation.get("name") or "").strip()
        if not name:
            continue
        norm_name = _normalize_name(name)
        if norm_name not in all_mapped:
            unmapped_citations.append(citation)

    print(f"❌ Citations NON mappées : {len(unmapped_citations)}")
    print()

    # 4. Analyser chaque citation non mappée
    results = {
        "high_confidence": [],
        "medium_confidence": [],
        "low_confidence": [],
    }

    for citation in unmapped_citations:
        name = citation.get("name", "").strip()
        description = citation.get("description", "").strip()
        category = citation.get("category", "").strip()

        analysis = analyze_citation_description(description)
        award_suggestions = suggest_award_names(name, description)

        citation_info = {
            "name": name,
            "category": category,
            "description": description,
            "detected_types": analysis["detected_types"],
            "award_suggestions": award_suggestions,
            "is_mappable": analysis["is_mappable_to_awards"],
        }

        if analysis["confidence"] == "high":
            results["high_confidence"].append(citation_info)
        elif analysis["confidence"] == "medium":
            results["medium_confidence"].append(citation_info)
        else:
            results["low_confidence"].append(citation_info)

    # 5. Afficher les résultats
    print("=" * 80)
    print("🎯 CITATIONS HAUTE PRIORITÉ (haute confiance pour mapping awards)")
    print("=" * 80)
    print(f"Total : {len(results['high_confidence'])}")
    print()

    for cit in results["high_confidence"][:20]:  # Top 20
        print(f"📌 {cit['name']}")
        print(f"   Catégorie: {cit['category']}")
        print(f"   Description: {cit['description']}")
        print(f"   Types détectés: {', '.join(cit['detected_types'])}")
        if cit["award_suggestions"]:
            print(f"   💡 Awards suggérés: {', '.join(cit['award_suggestions'])}")
        print()

    print("=" * 80)
    print("🔶 CITATIONS PRIORITÉ MOYENNE (confiance moyenne)")
    print("=" * 80)
    print(f"Total : {len(results['medium_confidence'])}")
    print()

    for cit in results["medium_confidence"][:15]:  # Top 15
        print(f"📌 {cit['name']}")
        print(f"   Catégorie: {cit['category']}")
        print(f"   Description: {cit['description']}")
        print(f"   Types détectés: {', '.join(cit['detected_types'])}")
        if cit["award_suggestions"]:
            print(f"   💡 Awards suggérés: {', '.join(cit['award_suggestions'])}")
        print()

    print("=" * 80)
    print("⚪ CITATIONS BASSE PRIORITÉ (confiance faible)")
    print("=" * 80)
    print(f"Total : {len(results['low_confidence'])}")
    print("(Non affichées, nécessitent analyse manuelle)")
    print()

    # 6. Exporter les résultats
    output_path = Path("out") / "citations_awards_alignment.json"
    output_path.parent.mkdir(exist_ok=True)

    export_data = {
        "summary": {
            "total_citations": len(all_citations),
            "mapped_citations": len(all_mapped),
            "unmapped_citations": len(unmapped_citations),
            "high_confidence": len(results["high_confidence"]),
            "medium_confidence": len(results["medium_confidence"]),
            "low_confidence": len(results["low_confidence"]),
        },
        "high_confidence_citations": results["high_confidence"],
        "medium_confidence_citations": results["medium_confidence"],
        "low_confidence_citations": results["low_confidence"],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)

    print(f"✅ Résultats exportés : {output_path}")
    print()

    # 7. Statistiques par type détecté
    print("=" * 80)
    print("📊 STATISTIQUES PAR TYPE DÉTECTÉ")
    print("=" * 80)

    type_counts = {}
    for conf_level in ["high_confidence", "medium_confidence"]:
        for cit in results[conf_level]:
            for det_type in cit["detected_types"]:
                type_counts[det_type] = type_counts.get(det_type, 0) + 1

    for det_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"{det_type:20s} : {count:3d} citations")
    print()

    # 8. Recommandations
    print("=" * 80)
    print("💡 RECOMMANDATIONS")
    print("=" * 80)
    print()
    print("1. Commencer par les citations haute confiance :")
    print(f"   → {len(results['high_confidence'])} citations prêtes pour mapping awards")
    print()
    print("2. Types d'awards les plus utilisables :")
    for det_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"   → {det_type}: {count} citations")
    print()
    print("3. Prochaines étapes :")
    print("   a) Créer un nouveau type de règle 'award' dans CUSTOM_CITATION_RULES")
    print("   b) Ajouter support pour filtrer par award_name dans personal_score_awards")
    print("   c) Implémenter les 20-30 citations haute priorité")
    print()


if __name__ == "__main__":
    main()
