#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Identifie les citations H5G sans méthode de calcul et propose des mappings vers awards.

Objectif : Trouver les citations qui pourraient être calculées à partir des
PersonalScoreAwards disponibles dans Halo Infinite.
"""

import json
import re
import sys
import unicodedata
from pathlib import Path

# Fix encoding pour Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Charger les citations
citations_path = Path("data/wiki/halo5_commendations_fr.json")
with open(citations_path, encoding="utf-8") as f:
    citations_data = json.load(f)

citations = citations_data.get("items", [])

# Règles de calcul personnalisées existantes (copié de src/ui/commendations.py)
CUSTOM_CITATION_RULES = {
    "pilote": {"type": "medal", "medal_id": 3169118333},
    "ecrasement": {"type": "medal", "medal_id": 221693153},
    "assistant": {"type": "stat", "stat": "assists"},
    "bulldozer": {
        "type": "matches_mode_kd",
        "mode_pattern": r"slayer|assassin",
        "exclude_playlist_pattern": r"firefight|baptême|btb|big team|grande bataille",
        "kd_threshold": 8.0,
    },
    "victoire au drapeau": {
        "type": "wins_mode",
        "mode_pattern": r"ctf|capture.*drapeau|drapeau.*neutre|neutral.*flag",
    },
    "seul contre tous": {"type": "wins_mode", "mode_pattern": r"firefight|baptême|bapteme"},
    "victoire en assassin": {"type": "wins_mode", "mode_pattern": r"slayer|assassin"},
    "victoire en bases": {"type": "wins_mode", "mode_pattern": r"stronghold|bases"},
}

def normalize(text):
    """Normalise un texte pour comparaison."""
    text = str(text).lower().strip()
    # Supprimer accents
    text = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
    return text

def has_rule(citation_name):
    """Vérifie si une citation a déjà une règle de calcul."""
    norm = normalize(citation_name)
    return norm in CUSTOM_CITATION_RULES

# Catégories d'awards personnels (PersonalScoreAwards)
AWARD_CATEGORIES = {
    "kill": [
        "Kill", "Headshot Kill", "Melee Kill", "Grenade Kill",
        "Power Weapon Kill", "Sniper Kill", "Vehicle Destruction",
        "Double Kill", "Triple Kill", "Overkill", "Killtacular",
        "Killing Spree", "Killing Frenzy"
    ],
    "assist": [
        "Assist", "Driver Assist", "Callout Assist", "EMP Assist"
    ],
    "objective": [
        "Flag Capture", "Flag Return", "Flag Carrier Kill",
        "Oddball Carrier Kill", "Oddball Time",
        "Zone Capture", "Zone Defense", "Zone Neutralization",
        "Power Seed Deposit", "Stockpile Goal"
    ],
    "vehicle": [
        "Vehicle Kill", "Wheelman", "Splatter", "Hijack"
    ],
    "penalty": [
        "Betrayal", "Suicide"
    ]
}

def suggest_award_mapping(citation_name, citation_desc):
    """Suggère un mapping vers un award basé sur le nom et la description."""
    norm_name = normalize(citation_name)
    norm_desc = normalize(citation_desc)

    suggestions = []

    # Mots-clés → Awards
    mappings = {
        # Kills
        r'\b(kill|tue|tuer|elimine|eliminer)\b': ("kill", ["Kill"]),
        r'\b(tir a la tete|headshot|tete)\b': ("kill", ["Headshot Kill"]),
        r'\b(corps a corps|melee|pugilat|rapproche)\b': ("kill", ["Melee Kill"]),
        r'\b(grenade)\b': ("kill", ["Grenade Kill"]),
        r'\b(arme puissante|power weapon)\b': ("kill", ["Power Weapon Kill"]),
        r'\b(sniper)\b': ("kill", ["Sniper Kill"]),
        r'\b(double|triple|overkill|serie|spree|frenzy)\b': ("kill", ["Double Kill", "Triple Kill", "Killing Spree"]),

        # Assists
        r'\b(assist|aide|assister|protege)\b': ("assist", ["Assist"]),
        r'\b(conducteur|pilote|driver)\b': ("assist", ["Driver Assist"]),

        # Objectifs
        r'\b(drapeau|flag|capture)\b': ("objective", ["Flag Capture", "Flag Return", "Flag Carrier Kill"]),
        r'\b(oddball|balle)\b': ("objective", ["Oddball Carrier Kill", "Oddball Time"]),
        r'\b(zone|base|stronghold)\b': ("objective", ["Zone Capture", "Zone Defense"]),
        r'\b(stockpile|seed)\b': ("objective", ["Power Seed Deposit"]),

        # Véhicules
        r'\b(vehicule|ecrase|splatter)\b': ("vehicle", ["Vehicle Kill", "Splatter"]),
        r'\b(conducteur|wheelman)\b': ("vehicle", ["Wheelman"]),
        r'\b(abord|hijack)\b': ("vehicle", ["Hijack"]),

        # Modes de jeu
        r'\b(ctf|capture.*drapeau)\b': ("mode", "CTF"),
        r'\b(assassin|slayer)\b': ("mode", "Slayer"),
        r'\b(bases|stronghold)\b': ("mode", "Strongholds"),
        r'\b(elimination|breakout)\b': ("mode", "Elimination"),
        r'\b(firefight|bapteme)\b': ("mode", "Firefight"),
        r'\b(grifball)\b': ("mode", "Grifball"),
        r'\b(infection)\b': ("mode", "Infection"),
    }

    text = norm_name + " " + norm_desc

    for pattern, (category, awards) in mappings.items():
        if re.search(pattern, text):
            if category == "mode":
                suggestions.append(("wins_mode", awards))
            else:
                suggestions.append((category, awards))

    return suggestions

# Analyser les citations
print(f"📊 Total citations : {len(citations)}")
print(f"📋 Citations avec règles : {len(CUSTOM_CITATION_RULES)}\n")

citations_without_rules = []
for citation in citations:
    name = citation.get('name', '')
    if not has_rule(name):
        citations_without_rules.append(citation)

print(f"❌ Citations SANS règle de calcul : {len(citations_without_rules)}\n")

print("=" * 80)
print("ANALYSE DES CITATIONS SANS RÈGLE")
print("=" * 80)

# Grouper par catégorie
by_category = {}
for citation in citations_without_rules:
    category = citation.get('category', 'Autre')
    if category not in by_category:
        by_category[category] = []
    by_category[category].append(citation)

# Analyse par catégorie
for category, cits in sorted(by_category.items()):
    print(f"\n📁 Catégorie : {category} ({len(cits)} citations)")
    print("-" * 80)

    for citation in cits[:10]:  # Limiter à 10 par catégorie pour la lisibilité
        name = citation.get('name', '')
        desc = citation.get('description', '')

        print(f"\n🎯 {name}")
        print(f"   Description: {desc[:70]}..." if len(desc) > 70 else f"   Description: {desc}")

        suggestions = suggest_award_mapping(name, desc)

        if suggestions:
            print("   💡 Suggestions de mapping :")
            seen = set()
            for sug_type, awards in suggestions:
                key = (sug_type, tuple(awards) if isinstance(awards, list) else awards)
                if key not in seen:
                    seen.add(key)
                    if sug_type == "wins_mode":
                        print(f"      → Type: wins_mode, Mode: {awards}")
                    else:
                        print(f"      → Catégorie: {sug_type}, Awards: {', '.join(awards[:3])}")
        else:
            print("   ⚠️  Pas de suggestion évidente")

    if len(cits) > 10:
        print(f"\n   ... et {len(cits) - 10} autres")

print("\n" + "=" * 80)
print("📊 STATISTIQUES")
print("=" * 80)

mappable_count = 0
for citation in citations_without_rules:
    name = citation.get('name', '')
    desc = citation.get('description', '')
    suggestions = suggest_award_mapping(name, desc)
    if suggestions:
        mappable_count += 1

print(f"""
Citations sans règle       : {len(citations_without_rules)}
Citations potentiellement
  mappables sur awards     : {mappable_count}
Citations difficiles à
  mapper                   : {len(citations_without_rules) - mappable_count}

Couverture actuelle        : {len(CUSTOM_CITATION_RULES)}/{len(citations)} ({100*len(CUSTOM_CITATION_RULES)/len(citations):.1f}%)
Couverture potentielle     : {len(CUSTOM_CITATION_RULES) + mappable_count}/{len(citations)} ({100*(len(CUSTOM_CITATION_RULES) + mappable_count)/len(citations):.1f}%)
""")

print("=" * 80)
print("💡 RECOMMANDATIONS")
print("=" * 80)
print("""
1. Les citations d'ARMES spécifiques sont mappables si on a les données d'armes
   par match (pas encore disponible dans personal_score_awards)

2. Les citations de MÉDAILLES sont mappables si on a la table medals_earned

3. Les citations de MODES/VICTOIRES sont mappables avec wins_mode

4. Les citations d'ENNEMIS IA (Covenants, Forerunners) nécessitent des données
   Firefight qui ne sont pas tracées actuellement

5. Prioriser :
   - Médailles communes (kills multiples, sprees)
   - Modes de jeu (victoires CTF, Slayer, Strongholds)
   - Actions objectives (flags, zones)
""")
