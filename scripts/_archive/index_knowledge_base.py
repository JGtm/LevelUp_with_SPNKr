#!/usr/bin/env python3
"""
Script d'indexation de la base de connaissances RAG.

Usage:
    # Indexer les sources par défaut
    python scripts/index_knowledge_base.py

    # Indexer le repo Grunt
    python scripts/index_knowledge_base.py --github https://github.com/dend/grunt

    # Indexer un répertoire spécifique
    python scripts/index_knowledge_base.py --directory docs/

    # Réindexer tout (efface la base existante)
    python scripts/index_knowledge_base.py --rebuild

    # Voir les stats
    python scripts/index_knowledge_base.py --stats
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ajouter le répertoire racine au path
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))


def main():
    parser = argparse.ArgumentParser(
        description="Indexe la base de connaissances RAG pour OpenSpartan Graph"
    )

    parser.add_argument("--directory", "-d", type=str, help="Répertoire à indexer")

    parser.add_argument("--github", "-g", type=str, help="URL du repository GitHub à indexer")

    parser.add_argument(
        "--branch", "-b", type=str, default="master", help="Branche GitHub (défaut: master)"
    )

    parser.add_argument(
        "--rebuild", action="store_true", help="Efface la base existante et réindexe tout"
    )

    parser.add_argument("--stats", action="store_true", help="Affiche les statistiques de la base")

    parser.add_argument(
        "--persist-dir",
        type=str,
        default="data/rag",
        help="Répertoire de persistance (défaut: data/rag)",
    )

    parser.add_argument(
        "--export-manifest", type=str, help="Exporte le manifest vers un fichier JSON"
    )

    args = parser.parse_args()

    # Vérifier que LanceDB est installé
    try:
        from src.ai.rag import HaloKnowledgeBase, RAGConfig
    except ImportError as e:
        print(f"[ERROR] Erreur d'import: {e}")
        print("\n[INFO] Installez les dependances avec:")
        print("   pip install lancedb httpx")
        sys.exit(1)

    # Créer la configuration
    config = RAGConfig(persist_directory=args.persist_dir)

    print(f"[DB] Base de connaissances: {args.persist_dir}")
    print()

    # Initialiser la base
    kb = HaloKnowledgeBase(config)

    # Mode stats uniquement
    if args.stats:
        stats = kb.get_stats()
        print("[STATS] Statistiques de la base de connaissances:")
        print(f"   - Documents indexes: {stats['total_documents']}")
        print(f"   - Table: {stats['table_name']}")
        print(f"   - Chunk size: {stats['chunk_size']}")
        print(f"   - Backend: {stats['backend']}")

        if args.export_manifest:
            kb.export_index_manifest(args.export_manifest)
            print(f"\n[FILE] Manifest exporte vers: {args.export_manifest}")

        return

    # Rebuild si demandé
    if args.rebuild:
        print("[CLEAN] Suppression de la base existante...")
        kb.clear()
        print("[OK] Base videe")
        print()

    indexed_files = {}

    # Indexer le répertoire spécifié
    if args.directory:
        dir_path = Path(args.directory)
        if not dir_path.exists():
            print(f"[ERROR] Repertoire non trouve: {dir_path}")
            sys.exit(1)

        print(f"[DIR] Indexation du repertoire: {dir_path}")
        results = kb.index_directory(dir_path)
        indexed_files.update(results)
        print(f"   [OK] {len(results)} fichiers indexes")

    # Indexer le repo GitHub
    if args.github:
        print(f"[GITHUB] Indexation du repository: {args.github}")
        print(f"   Branche: {args.branch}")

        try:
            results = kb.index_github_repo(args.github, branch=args.branch)
            indexed_files.update(results)
            print(f"   [OK] {len(results)} fichiers indexes")
        except Exception as e:
            print(f"   [ERROR] {e}")

    # Si aucune source spécifiée, indexer les sources par défaut
    if not args.directory and not args.github:
        print("[INDEX] Indexation des sources par defaut...")
        print()

        # Sources locales
        default_sources = [
            ("docs/", "Documentation"),
            (".ai/", "Contexte agentique"),
            ("src/", "Code source"),
        ]

        for source_path, description in default_sources:
            path = ROOT_DIR / source_path
            if path.exists():
                print(f"   [DIR] {description} ({source_path})")
                try:
                    results = kb.index_directory(path)
                    indexed_files.update(results)
                    total_chunks = sum(results.values())
                    print(f"      [OK] {len(results)} fichiers, {total_chunks} chunks")
                except Exception as e:
                    print(f"      [ERROR] {e}")

        print()

        # Repo Grunt (source principale API Halo)
        print("   [GITHUB] Repository Grunt (API Halo Infinite)")
        try:
            results = kb.index_github_repo("https://github.com/dend/grunt", branch="master")
            indexed_files.update({f"grunt/{k}": v for k, v in results.items()})
            total_chunks = sum(results.values())
            print(f"      [OK] {len(results)} fichiers, {total_chunks} chunks")
        except Exception as e:
            print(f"      [ERROR] GitHub: {e}")
            print("      [INFO] Verifiez votre connexion internet")

    # Résumé
    print()
    print("=" * 60)
    print("[SUMMARY] RESUME")
    print("=" * 60)

    stats = kb.get_stats()
    print(f"   - Total documents: {stats['total_documents']} chunks")
    print(f"   - Fichiers traites: {len(indexed_files)}")
    print(f"   - Backend: {stats['backend']}")

    # Top 5 des fichiers les plus gros
    if indexed_files:
        print()
        print("   [TOP5] Fichiers (par nombre de chunks):")
        sorted_files = sorted(indexed_files.items(), key=lambda x: x[1], reverse=True)[:5]
        for file_path, chunks in sorted_files:
            # Tronquer le chemin si trop long
            display_path = file_path if len(file_path) < 50 else "..." + file_path[-47:]
            print(f"      - {display_path}: {chunks} chunks")

    # Export manifest si demandé
    if args.export_manifest:
        kb.export_index_manifest(args.export_manifest)
        print(f"\n[FILE] Manifest exporte vers: {args.export_manifest}")

    print()
    print("[DONE] Indexation terminee!")
    print()
    print("[USAGE] Exemple:")
    print("   from src.ai.rag import HaloKnowledgeBase, RAGConfig")
    print("   kb = HaloKnowledgeBase(RAGConfig())")
    print('   results = kb.search("Comment fonctionne l\'auth Spartan Token?")')


if __name__ == "__main__":
    main()
