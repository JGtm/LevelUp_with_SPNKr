#!/usr/bin/env python3
"""Vérifie les règles de tracking chargées dans l'app."""

import sys
from pathlib import Path

# Ajouter la racine du repo au path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ui.commendations import load_h5g_commendations_tracking_rules, CUSTOM_CITATION_RULES

# Charger les règles de tracking depuis les fichiers JSON
tracking_rules = load_h5g_commendations_tracking_rules()

print(f"📊 Règles de tracking JSON : {len(tracking_rules)}")
print(f"📊 Règles CUSTOM hardcodées : {len(CUSTOM_CITATION_RULES)}")
print(f"📊 TOTAL règles disponibles : {len(tracking_rules) + len(CUSTOM_CITATION_RULES)}")

if tracking_rules:
    print("\n" + "=" * 80)
    print("Exemples de règles de tracking JSON (20 premières) :")
    print("=" * 80)
    for i, (name, rule) in enumerate(list(tracking_rules.items())[:20]):
        print(f"\n{i+1}. {name}")
        print(f"   Règle: {rule}")
else:
    print("\n⚠️  Aucune règle de tracking JSON trouvée !")
    print("   Les fichiers out/commendations_mapping_*.json sont peut-être manquants.")

print("\n" + "=" * 80)
print("Règles CUSTOM hardcodées :")
print("=" * 80)
for name in CUSTOM_CITATION_RULES:
    print(f"  • {name}")
