#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Identifie les citations H5G qui n'ont AUCUNE méthode de calcul (ni tracking JSON, ni CUSTOM_CITATION_RULES).

Trie les citations non mappées par facilité d'implémentation.
"""

import json
import os
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

# Règles personnalisées hardcodées (copié de src/ui/commendations.py)
CUSTOM_CITATION_RULES = {
    "pilote",
    "ecrasement",
    "assistant",
    "bulldozer",
    "victoire au drapeau",
    "seul contre tous",
    "victoire en assassin",
    "victoire en bases",
}

def normalize(text):
    """Normalise un texte pour comparaison."""
    text = str(text).lower().strip()
    # Supprimer accents
    text = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
    return text

# Charger les tracking rules depuis JSON (si elles existent)
TRACKING_RULES = set()
tracking_paths = [
    "out/commendations_mapping_assumed_old.json",
    "out/commendations_mapping_unmatched_old.json",
]

for path in tracking_paths:
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
                items = data.get("items", [])
                for item in items:
                    if isinstance(item, dict):
                        name = item.get("name", "")
                        if name:
                            TRACKING_RULES.add(normalize(name))
        except Exception as e:
            print(f"⚠️  Erreur lecture {path}: {e}")

# Identifier les citations non mappées
unmapped = []
for citation in citations:
    name = citation.get('name', '')
    norm_name = normalize(name)

    # Vérifier si déjà calculée
    if norm_name in CUSTOM_CITATION_RULES:
        continue
    if norm_name in TRACKING_RULES:
        continue

    unmapped.append(citation)

print(f"📊 Total citations : {len(citations)}")
print(f"✅ Citations avec CUSTOM_RULES : {len(CUSTOM_CITATION_RULES)}")
print(f"✅ Citations avec tracking JSON : {len(TRACKING_RULES)}")
print(f"❌ Citations NON mappées : {len(unmapped)}\n")

# Classifier les citations non mappées par potentiel de mapping
def classify_mappability(citation):
    """Retourne (priorité, catégorie, raison)."""
    name = citation.get('name', '')
    desc = citation.get('description', '').lower()
    norm_name = normalize(name)
    norm_desc = normalize(desc)

    # Priorité 1: Médailles probables (mentions explicites)
    medal_patterns = [
        r'\bmedaille',
        r'\bremportez',
        r'\bdouble',
        r'\btriple',
        r'\bspree',
        r'\bfrenzy',
        r'\bkilling',
        r'\bheadshot',
        r'\bmelee',
        r'\bassassinate',
    ]
    if any(re.search(p, norm_desc) for p in medal_patterns):
        return (1, "Médailles", "Mention explicite de médaille dans la description")

    # Priorité 2: Victoires par mode
    mode_patterns = [
        r'gagner.*partie',
        r'remporter.*partie',
        r'victoire',
        r'win.*match',
    ]
    if any(re.search(p, norm_desc) for p in mode_patterns):
        return (2, "Victoires mode", "Victoire dans un mode spécifique")

    # Priorité 3: Actions objectives (flags, zones)
    objective_patterns = [
        r'\bdrapeau\b',
        r'\bflag\b',
        r'\bbase',
        r'\bzone',
        r'\bcapture',
    ]
    if any(re.search(p, norm_desc) for p in objective_patterns):
        return (3, "Objectifs", "Action sur objectif (flag/zone)")

    # Priorité 4: Stats simples (kills, assists)
    stat_patterns = [
        r'\btue\b',
        r'\btuer\b',
        r'\bkill\b',
        r'\bassist',
        r'\baide',
    ]
    if any(re.search(p, norm_desc) for p in stat_patterns):
        # Vérifier si c'est une arme spécifique (moins prioritaire)
        weapon_patterns = [
            r'\ba l\'aide d[eu]',
            r'\bavec.*fusil',
            r'\bavec.*pistolet',
            r'\bavec.*grenade',
            r'\bavec.*vehicule',
        ]
        if any(re.search(p, norm_desc) for p in weapon_patterns):
            return (5, "Armes spécifiques", "Nécessite tracking par arme")
        return (4, "Stats combat", "Kills/assists généraux")

    # Priorité 5: Ennemis IA (Firefight uniquement)
    ai_patterns = [
        r'\belite',
        r'\bgrognar',
        r'\bchasseur',
        r'\bcovenant',
        r'\bprometheen',
        r'\bforerunner',
    ]
    if any(re.search(p, norm_desc) for p in ai_patterns):
        return (6, "Ennemis IA", "Firefight uniquement (non implémenté)")

    # Priorité 6: Armes/véhicules spécifiques
    return (5, "Armes/Véhicules", "Nécessite stats détaillées par arme/véhicule")

# Grouper par priorité
by_priority = {}
for citation in unmapped:
    priority, category, reason = classify_mappability(citation)
    if priority not in by_priority:
        by_priority[priority] = []
    by_priority[priority].append((citation, category, reason))

# Afficher par priorité
print("=" * 80)
print("CITATIONS NON MAPPÉES - TRIÉES PAR PRIORITÉ D'IMPLÉMENTATION")
print("=" * 80)

for priority in sorted(by_priority.keys()):
    items = by_priority[priority]
    category_name = items[0][1] if items else "Autre"

    print(f"\n{'🟢' if priority <= 2 else '🟡' if priority <= 4 else '🔴'} Priorité {priority}: {category_name} ({len(items)} citations)")
    print("-" * 80)

    for citation, cat, reason in items[:10]:  # Limiter à 10 pour lisibilité
        name = citation.get('name', '')
        desc = citation.get('description', '')
        print(f"\n  • {name}")
        print(f"    {desc[:75]}..." if len(desc) > 75 else f"    {desc}")
        print(f"    → {reason}")

    if len(items) > 10:
        print(f"\n  ... et {len(items) - 10} autres")

# Résumé actionable
print("\n" + "=" * 80)
print("📊 RÉSUMÉ ACTIONABLE")
print("=" * 80)

p1_count = len(by_priority.get(1, []))
p2_count = len(by_priority.get(2, []))
p3_count = len(by_priority.get(3, []))
p4_count = len(by_priority.get(4, []))

print(f"""
🟢 PRIORITÉ HAUTE (facile à implémenter) :
   - Médailles : {p1_count} citations
   - Victoires par mode : {p2_count} citations
   → TOTAL : {p1_count + p2_count} citations

🟡 PRIORITÉ MOYENNE (faisable) :
   - Objectifs : {p3_count} citations
   - Stats combat : {p4_count} citations
   → TOTAL : {p3_count + p4_count} citations

🔴 PRIORITÉ BASSE (complexe ou impossible) :
   - Armes spécifiques, Ennemis IA
   → TOTAL : {len(unmapped) - p1_count - p2_count - p3_count - p4_count} citations

💡 Recommandation : Commencer par les {p1_count + p2_count} citations de priorité haute.
""")

# Exemples concrets pour démarrer
print("=" * 80)
print("💡 EXEMPLES CONCRETS POUR DÉMARRER")
print("=" * 80)

if 1 in by_priority:
    print("\n🟢 Médailles (exemples) - À ajouter dans CUSTOM_CITATION_RULES :")
    for citation, _, _ in by_priority[1][:5]:
        name = citation.get('name', '')
        print(f'   "{normalize(name)}": {{"type": "medal", "medal_id": ???}},')

if 2 in by_priority:
    print("\n🟢 Victoires mode (exemples) - À ajouter dans CUSTOM_CITATION_RULES :")
    for citation, _, _ in by_priority[2][:5]:
        name = citation.get('name', '')
        desc = citation.get('description', '').lower()
        # Détecter le mode
        if 'elimination' in desc or 'breakout' in desc:
            mode = "elimination|breakout"
        elif 'grifball' in desc:
            mode = "grifball"
        elif 'infection' in desc:
            mode = "infection"
        elif 'assault' in desc or 'assaut' in desc:
            mode = "assault|assaut"
        else:
            mode = "???"
        print(f'   "{normalize(name)}": {{"type": "wins_mode", "mode_pattern": r"{mode}"}},')
