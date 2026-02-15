#!/usr/bin/env python3
"""Script de test pour vérifier l'accès aux données."""

from src.config import get_default_db_path
from src.ui import load_settings
from src.utils.profiles import load_profiles

print("=" * 60)
print("TEST: Accès aux données")
print("=" * 60)

# 1. Test get_default_db_path
default_db = get_default_db_path()
print(f"\n✅ Default DB: {default_db}")

# 2. Test load_profiles
profiles = load_profiles()
print(f"\n✅ Profils chargés: {len(profiles)} joueur(s)")
for name, info in profiles.items():
    print(f"   - {name}: {info['db_path']}")

# 3. Test load_settings
settings = load_settings()
print("\n✅ Settings chargés")
print(f"   - media_enabled: {settings.media_enabled}")
print(f"   - prefer_spnkr: {settings.prefer_spnkr_db_if_available}")

print("\n" + "=" * 60)
print("✅ TOUS LES TESTS PASSENT")
print("=" * 60)
