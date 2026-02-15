#!/usr/bin/env python3
"""
Crée la table citation_mappings dans metadata.duckdb et initialise les 6 citations validées.

Citations réintégrées :
- 5 objectives simples (award direct)
- 1 objective complexe (custom function)
"""

import sys
from pathlib import Path

import duckdb

# Ajouter le chemin racine au PYTHONPATH
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))


def create_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Crée la table citation_mappings."""
    print("📋 Création de la table citation_mappings...")

    conn.execute("DROP TABLE IF EXISTS citation_mappings")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS citation_mappings (
            citation_name_norm TEXT PRIMARY KEY,
            citation_name_display TEXT NOT NULL,
            mapping_type TEXT NOT NULL,  -- 'medal' | 'stat' | 'award' | 'custom'

            -- Pour type = 'medal'
            medal_id BIGINT,
            medal_ids TEXT,  -- JSON array pour multiples médailles

            -- Pour type = 'stat'
            stat_name TEXT,

            -- Pour type = 'award'
            award_name TEXT,
            award_category TEXT,

            -- Pour type = 'custom'
            custom_function TEXT,

            -- Métadonnées
            confidence TEXT,  -- 'high' | 'medium' | 'low'
            notes TEXT,
            enabled BOOLEAN DEFAULT TRUE,  -- FALSE = citation désactivée (non affichée)
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    print("✅ Table créée")


def insert_existing_citations(conn: duckdb.DuckDBPyConnection) -> None:
    """Insère les 8 citations actuellement en CUSTOM_CITATION_RULES."""
    print("\n📥 Migration des citations existantes...")

    existing = [
        (
            "pilote",
            "Pilote",
            "medal",
            3169118333,
            None,
            None,
            None,
            None,
            None,
            "high",
            "Médaille Pilote",
        ),
        (
            "ecrasement",
            "Écrasement",
            "medal",
            221693153,
            None,
            None,
            None,
            None,
            None,
            "high",
            "Médaille Splatter",
        ),
        (
            "assistant",
            "Assistant",
            "stat",
            None,
            None,
            "assists",
            None,
            None,
            None,
            "high",
            "Total assists",
        ),
        (
            "bulldozer",
            "Bulldozer",
            "custom",
            None,
            None,
            None,
            None,
            None,
            "compute_bulldozer",
            "high",
            "Parties Assassin avec KD > 8",
        ),
        (
            "victoire au drapeau",
            "Victoire au drapeau",
            "custom",
            None,
            None,
            None,
            None,
            None,
            "compute_wins_ctf",
            "high",
            "Victoires CTF",
        ),
        (
            "seul contre tous",
            "Seul contre tous",
            "custom",
            None,
            None,
            None,
            None,
            None,
            "compute_wins_firefight",
            "high",
            "Victoires Firefight",
        ),
        (
            "victoire en assassin",
            "Victoire en Assassin",
            "custom",
            None,
            None,
            None,
            None,
            None,
            "compute_wins_slayer",
            "high",
            "Victoires Slayer",
        ),
        (
            "victoire en bases",
            "Victoire en Bases",
            "custom",
            None,
            None,
            None,
            None,
            None,
            "compute_wins_strongholds",
            "high",
            "Victoires Strongholds",
        ),
    ]

    conn.executemany(
        """
        INSERT INTO citation_mappings
        (citation_name_norm, citation_name_display, mapping_type, medal_id, medal_ids,
         stat_name, award_name, award_category, custom_function, confidence, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        existing,
    )

    print(f"✅ {len(existing)} citations existantes migrées")


def insert_new_citations(conn: duckdb.DuckDBPyConnection) -> None:
    """Insère les 6 nouvelles citations réintégrées."""
    print("\n📥 Ajout des nouvelles citations réintégrées...")

    new_citations = [
        # 5 objectives simples (award direct)
        (
            "defenseur du drapeau",
            "Défenseur du drapeau",
            "award",
            None,
            None,
            None,
            "Flag Defense",
            "objective",
            None,
            "high",
            "Exclue → Réintégrée",
        ),
        (
            "je te tiens",
            "Je te tiens !",
            "award",
            None,
            None,
            None,
            "Flag Return",
            "objective",
            None,
            "high",
            "Exclue → Réintégrée",
        ),
        (
            "sus au porteur du drapeau",
            "Sus au porteur du drapeau",
            "award",
            None,
            None,
            None,
            "Flag Carrier Kill",
            "objective",
            None,
            "high",
            "Exclue → Réintégrée",
        ),
        (
            "partie prenante",
            "Partie prenante",
            "award",
            None,
            None,
            None,
            "Zone Defense",
            "objective",
            None,
            "high",
            "Exclue → Réintégrée",
        ),
        (
            "a la charge",
            "À la charge",
            "award",
            None,
            None,
            None,
            "Zone Capture",
            "objective",
            None,
            "high",
            "Exclue → Réintégrée",
        ),
        # 1 objective complexe (custom function)
        (
            "annexion forcee",
            "Annexion forcée",
            "custom",
            None,
            None,
            None,
            None,
            None,
            "compute_annexion_forcee",
            "medium",
            "3 Zone Capture consécutives sans mourir - Exclue → Réintégrée",
        ),
    ]

    conn.executemany(
        """
        INSERT INTO citation_mappings
        (citation_name_norm, citation_name_display, mapping_type, medal_id, medal_ids,
         stat_name, award_name, award_category, custom_function, confidence, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        new_citations,
    )

    print(f"✅ {len(new_citations)} nouvelles citations ajoutées")


def verify_data(conn: duckdb.DuckDBPyConnection) -> None:
    """Vérifie les données insérées."""
    print("\n🔍 Vérification des données...")

    total = conn.execute("SELECT COUNT(*) FROM citation_mappings").fetchone()[0]
    print(f"   Total citations : {total}")

    by_type = conn.execute("""
        SELECT mapping_type, COUNT(*)
        FROM citation_mappings
        GROUP BY mapping_type
        ORDER BY COUNT(*) DESC
    """).fetchall()

    print("   Répartition par type :")
    for mapping_type, count in by_type:
        print(f"      {mapping_type:10s} : {count:2d}")

    # Afficher les nouvelles citations
    print("\n📋 Nouvelles citations réintégrées :")
    new = conn.execute("""
        SELECT citation_name_display, mapping_type,
               COALESCE(award_name, custom_function, 'N/A') as source
        FROM citation_mappings
        WHERE notes LIKE '%Exclue → Réintégrée%'
        ORDER BY citation_name_display
    """).fetchall()

    for name, type_, source in new:
        print(f"   ✅ {name:35s} → {type_:6s} ({source})")


def main() -> int:
    """Point d'entrée principal."""
    print("=" * 80)
    print("🏗️  Initialisation table citation_mappings")
    print("=" * 80)
    print()

    # Connexion à metadata.duckdb
    metadata_path = Path("data/warehouse/metadata.duckdb")

    if not metadata_path.exists():
        print(f"⚠️  Fichier non trouvé : {metadata_path} — création automatique")
        metadata_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"📂 Connexion à : {metadata_path}")
    conn = duckdb.connect(str(metadata_path))

    try:
        # 1. Créer la table
        create_table(conn)

        # 2. Migrer les citations existantes
        insert_existing_citations(conn)

        # 3. Ajouter les nouvelles citations
        insert_new_citations(conn)

        # 4. Vérifier
        verify_data(conn)

        conn.close()

        print()
        print("=" * 80)
        print("✅ Initialisation terminée avec succès !")
        print("=" * 80)
        print()
        print("📊 Résumé :")
        print("   - 8 citations existantes migrées")
        print("   - 6 nouvelles citations ajoutées")
        print("   - Total : 14 citations dans citation_mappings")
        print()
        print("🎯 Prochaines étapes :")
        print("   1. Créer src/analysis/citations/custom_rules.py")
        print("   2. Implémenter compute_annexion_forcee()")
        print("   3. Créer CitationEngine dans src/analysis/citations/engine.py")
        print("   4. Refactoriser src/ui/commendations.py")
        print()

        return 0

    except Exception as e:
        print(f"\n❌ Erreur : {e}")
        import traceback

        traceback.print_exc()
        conn.close()
        return 1


if __name__ == "__main__":
    sys.exit(main())
