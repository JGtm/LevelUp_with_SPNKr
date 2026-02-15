#!/usr/bin/env python3
"""Analyse les écarts entre awards (PersonalScoreAwards) et citations (Commendations H5G).

Identifie les awards qui n'ont pas d'équivalent logique dans les citations.
"""

import json
import re
from pathlib import Path

# Charger les citations
citations_path = Path("data/wiki/halo5_commendations_fr.json")
with open(citations_path, encoding="utf-8") as f:
    citations_data = json.load(f)

citations = citations_data.get("items", [])

print(f"📊 Nombre de citations H5G : {len(citations)}\n")

# Liste des awards typiques (d'après le code)
TYPICAL_AWARDS = [
    # Combat (kill)
    ("Kill", "kill", "Kill standard"),
    ("Headshot Kill", "kill", "Kill en headshot"),
    ("Melee Kill", "kill", "Kill au corps-à-corps"),
    ("Grenade Kill", "kill", "Kill à la grenade"),
    ("Power Weapon Kill", "kill", "Kill avec arme puissante"),
    ("Sniper Kill", "kill", "Kill au sniper"),
    ("Vehicle Destruction", "kill", "Destruction de véhicule"),

    # Support (assist)
    ("Assist", "assist", "Assistance standard"),
    ("Driver Assist", "assist", "Assistance en tant que conducteur"),
    ("Callout Assist", "assist", "Assistance via callout"),
    ("EMP Assist", "assist", "Assistance via EMP"),

    # Objectifs (objective)
    ("Flag Capture", "objective", "Capture de drapeau (CTF)"),
    ("Flag Return", "objective", "Retour du drapeau"),
    ("Flag Carrier Kill", "objective", "Kill du porteur de drapeau"),
    ("Oddball Carrier Kill", "objective", "Kill du porteur de balle"),
    ("Oddball Time", "objective", "Temps avec la balle"),
    ("Zone Capture", "objective", "Capture de zone (Strongholds)"),
    ("Zone Defense", "objective", "Défense de zone"),
    ("Power Seed Deposit", "objective", "Dépôt de seed (Stockpile)"),

    # Véhicules (vehicle)
    ("Vehicle Kill", "vehicle", "Kill depuis un véhicule"),
    ("Wheelman", "vehicle", "Points conducteur"),
    ("Splatter", "vehicle", "Écrasement"),

    # Pénalités (penalty)
    ("Betrayal", "penalty", "Trahison (tir allié)"),
    ("Suicide", "penalty", "Suicide"),
]

def normalize(text):
    """Normalise un texte pour comparaison."""
    text = text.lower().strip()
    # Supprimer accents
    import unicodedata
    text = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
    return text

def find_matching_citations(award_name, award_desc):
    """Trouve les citations qui pourraient correspondre à cet award."""
    matches = []
    norm_award = normalize(award_name)
    norm_desc = normalize(award_desc)

    for citation in citations:
        cit_name = normalize(citation.get('name', ''))
        cit_desc = normalize(citation.get('description', ''))

        # Recherche de mots-clés
        keywords_award = set(norm_award.split())
        keywords_desc = set(norm_desc.split())
        keywords_cit_name = set(cit_name.split())
        keywords_cit_desc = set(cit_desc.split())

        # Score de correspondance
        score = 0

        # Correspondance exacte du nom
        if norm_award in cit_name or cit_name in norm_award:
            score += 10

        # Mots-clés communs dans le nom
        common_name = keywords_award & keywords_cit_name
        score += len(common_name) * 3

        # Mots-clés de l'award dans la description de la citation
        common_desc = keywords_award & keywords_cit_desc
        score += len(common_desc) * 2

        # Mots-clés de description
        common_both = keywords_desc & keywords_cit_desc
        score += len(common_both)

        if score > 0:
            matches.append({
                'citation': citation.get('name'),
                'description': citation.get('description'),
                'score': score
            })

    # Trier par score
    matches.sort(key=lambda x: x['score'], reverse=True)
    return matches[:3]  # Top 3

print("=" * 80)
print("ANALYSE DES CORRESPONDANCES AWARDS ↔ CITATIONS")
print("=" * 80)

awards_without_match = []
awards_with_weak_match = []

for award_name, category, description in TYPICAL_AWARDS:
    print(f"\n🎯 Award: {award_name} ({category})")
    print(f"   Description: {description}")

    matches = find_matching_citations(award_name, description)

    if not matches:
        print("   ❌ AUCUNE CITATION CORRESPONDANTE")
        awards_without_match.append((award_name, category, description))
    elif matches[0]['score'] < 5:
        print(f"   ⚠️  CORRESPONDANCE FAIBLE (score: {matches[0]['score']})")
        print(f"      → {matches[0]['citation']}")
        awards_with_weak_match.append((award_name, category, description, matches[0]))
    else:
        print(f"   ✅ Correspondance trouvée (score: {matches[0]['score']})")
        for i, match in enumerate(matches[:2], 1):
            print(f"      {i}. {match['citation']} (score: {match['score']})")

print("\n" + "=" * 80)
print("📋 RÉSUMÉ")
print("=" * 80)

if awards_without_match:
    print(f"\n❌ Awards SANS correspondance ({len(awards_without_match)}) :")
    for award_name, category, description in awards_without_match:
        print(f"   • {award_name} ({category}) - {description}")

if awards_with_weak_match:
    print(f"\n⚠️  Awards avec correspondance FAIBLE ({len(awards_with_weak_match)}) :")
    for award_name, category, description, best_match in awards_with_weak_match:
        print(f"   • {award_name} ({category})")
        print(f"     Meilleure correspondance: {best_match['citation']}")

print(f"\n✅ Awards avec bonne correspondance : {len(TYPICAL_AWARDS) - len(awards_without_match) - len(awards_with_weak_match)}")

print("\n" + "=" * 80)
print("💡 CONCLUSION")
print("=" * 80)
print("""
Les awards suivants semblent être trop spécifiques/techniques
et n'ont probablement pas d'équivalent direct dans les commendations H5G :

1. Awards techniques de support (Callout Assist, EMP Assist)
2. Awards de modes spécifiques de Infinite (Power Seed, Oddball Time précis)
3. Awards de métrique (Wheelman sans kill associé)
4. Pénalités (Betrayal, Suicide)

Ces awards sont utiles pour calculer le score personnel mais ne correspondent
pas à des commendations traçables.
""")
