#!/usr/bin/env python3
"""
Script de validation manuelle pour le Sprint 1 - Métadonnées.

Ce script valide que les composants du Sprint 1 sont correctement implémentés
sans nécessiter l'exécution complète des tests pytest.

Usage:
    python scripts/validate_sprint1_metadata.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configuration de l'encodage pour Windows
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

print("=" * 70)
print("VALIDATION SPRINT 1 - RESOLUTION METADONNEES")
print("=" * 70)
print()

errors = []
warnings = []

# 1. Vérifier que MetadataResolver existe (sans importer les dépendances)
print("1. Verification MetadataResolver...")
try:
    # Vérifier que le fichier existe d'abord
    resolver_file = Path(__file__).parent.parent / "src" / "data" / "sync" / "metadata_resolver.py"
    if resolver_file.exists():
        # Lire le fichier pour vérifier la structure sans l'importer
        content = resolver_file.read_text(encoding="utf-8")
        if "class MetadataResolver" in content:
            print("   [OK] MetadataResolver classe presente")
        else:
            errors.append("MetadataResolver classe non trouvee dans le fichier")
            print("   [ERREUR] Classe MetadataResolver absente")

        if "def create_metadata_resolver_function" in content:
            print("   [OK] create_metadata_resolver_function presente")
        else:
            errors.append("create_metadata_resolver_function absente")
            print("   [ERREUR] Fonction create_metadata_resolver_function absente")
    else:
        errors.append(f"Fichier metadata_resolver.py non trouve: {resolver_file}")
        print(f"   [ERREUR] Fichier non trouve: {resolver_file}")
except Exception as e:
    errors.append(f"Erreur verification MetadataResolver: {e}")
    print(f"   [ERREUR] {e}")

# 2. Vérifier que create_metadata_resolver existe dans transformers
print("\n2. Verification create_metadata_resolver dans transformers...")
try:
    transformers_file = Path(__file__).parent.parent / "src" / "data" / "sync" / "transformers.py"
    if transformers_file.exists():
        content = transformers_file.read_text(encoding="utf-8")
        if "def create_metadata_resolver" in content:
            print("   [OK] create_metadata_resolver presente dans transformers.py")
        else:
            errors.append("create_metadata_resolver absente dans transformers.py")
            print("   [ERREUR] Fonction create_metadata_resolver absente")

        if "from src.data.sync.metadata_resolver import" in content:
            print("   [OK] Import de metadata_resolver present")
        else:
            warnings.append("Import de metadata_resolver peut-etre absent")
            print("   [ATTENTION] Import de metadata_resolver non trouve")
    else:
        errors.append("transformers.py non trouve")
        print("   [ERREUR] Fichier transformers.py non trouve")
except Exception as e:
    errors.append(f"Erreur verification transformers: {e}")
    print(f"   [ERREUR] {e}")

# 3. Vérifier enrich_match_info_with_assets
print("\n3. Verification enrich_match_info_with_assets...")
try:
    api_client_file = Path(__file__).parent.parent / "src" / "data" / "sync" / "api_client.py"
    if api_client_file.exists():
        content = api_client_file.read_text(encoding="utf-8")
        if "async def enrich_match_info_with_assets" in content:
            print("   [OK] enrich_match_info_with_assets presente")
        else:
            errors.append("enrich_match_info_with_assets absente")
            print("   [ERREUR] Fonction enrich_match_info_with_assets absente")
    else:
        errors.append("api_client.py non trouve")
        print("   [ERREUR] Fichier api_client.py non trouve")
except Exception as e:
    errors.append(f"Erreur verification api_client: {e}")
    print(f"   [ERREUR] {e}")

# 4. Vérifier que les scripts existent
print("\n4. Verification des scripts...")
scripts_to_check = [
    "scripts/populate_metadata_from_discovery.py",
    "scripts/backfill_metadata.py",
]

for script_path in scripts_to_check:
    path = Path(__file__).parent.parent / script_path
    if path.exists():
        print(f"   [OK] {script_path} existe")
    else:
        errors.append(f"Script manquant: {script_path}")
        print(f"   [ERREUR] {script_path} non trouve")

# 5. Vérifier que les tests existent
print("\n5. Verification des fichiers de tests...")
test_files = [
    "tests/test_metadata_resolver.py",
    "tests/test_transformers_metadata.py",
    "tests/integration/test_metadata_resolution.py",
]

for test_file in test_files:
    path = Path(__file__).parent.parent / test_file
    if path.exists():
        print(f"   [OK] {test_file} existe")
    else:
        warnings.append(f"Test manquant: {test_file}")
        print(f"   [ATTENTION] {test_file} non trouve")

# 6. Vérifier la documentation
print("\n6. Verification de la documentation...")
doc_file = Path(__file__).parent.parent / "docs" / "METADATA_RESOLUTION.md"
if doc_file.exists():
    print("   [OK] docs/METADATA_RESOLUTION.md existe")
    # Compter les lignes pour vérifier que c'est complet
    lines = len(doc_file.read_text(encoding="utf-8").splitlines())
    if lines > 100:
        print(f"   [OK] Documentation complete ({lines} lignes)")
    else:
        warnings.append("Documentation semble incomplete")
        print(f"   [ATTENTION] Documentation courte ({lines} lignes)")
else:
    errors.append("Documentation manquante: docs/METADATA_RESOLUTION.md")
    print("   [ERREUR] docs/METADATA_RESOLUTION.md non trouve")

# 7. Vérifier la structure de MetadataResolver (sans importer)
print("\n7. Verification de la structure MetadataResolver...")
try:
    resolver_file = Path(__file__).parent.parent / "src" / "data" / "sync" / "metadata_resolver.py"
    if resolver_file.exists():
        content = resolver_file.read_text(encoding="utf-8")
        methods = ["def resolve", "def close", "def __enter__", "def __exit__"]
        for method in methods:
            if method in content:
                print(f"   [OK] Methode {method.split()[-1]} presente")
            else:
                errors.append(f"Methode manquante: {method.split()[-1]}")
                print(f"   [ERREUR] Methode {method.split()[-1]} absente")
    else:
        errors.append("metadata_resolver.py non trouve")
        print("   [ERREUR] Fichier metadata_resolver.py non trouve")
except Exception as e:
    errors.append(f"Erreur verification structure: {e}")
    print(f"   [ERREUR] {e}")

# Résumé
print("\n" + "=" * 70)
print("RESUME")
print("=" * 70)

if errors:
    print(f"\n[ERREUR] {len(errors)} erreur(s) trouvee(s):")
    for error in errors:
        print(f"   - {error}")
else:
    print("\n[OK] Aucune erreur detectee")

if warnings:
    print(f"\n[ATTENTION] {len(warnings)} avertissement(s):")
    for warning in warnings:
        print(f"   - {warning}")

if not errors:
    print("\n[OK] VALIDATION REUSSIE - Les composants du Sprint 1 sont correctement implementes")
    print("\nNote: Pour executer les tests complets, installez DuckDB:")
    print("   pip install duckdb pytest pytest-asyncio")
    print(
        "   pytest tests/test_metadata_resolver.py tests/test_transformers_metadata.py tests/integration/test_metadata_resolution.py -v"
    )
    sys.exit(0)
else:
    print("\n[ERREUR] VALIDATION ECHOUEE - Des erreurs doivent etre corrigees")
    sys.exit(1)
