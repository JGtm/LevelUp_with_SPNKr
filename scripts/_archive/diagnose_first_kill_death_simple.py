#!/usr/bin/env python3
"""Script de diagnostic simplifié pour analyser pourquoi le graphe 'Temps du premier kill / première mort' est vide.

Ce script utilise directement DuckDB sans dépendances complexes.
"""

import sys
from pathlib import Path

# Ajouter le répertoire racine au path
root = Path(__file__).parent.parent
sys.path.insert(0, str(root))

try:
    import duckdb
except ImportError:
    print("ERREUR: Le module 'duckdb' n'est pas installé.")
    print("Installez-le avec: pip install duckdb")
    sys.exit(1)


def diagnose_first_kill_death(db_path: str, xuid: str) -> None:
    """Diagnostique pourquoi le graphe premier kill/mort est vide."""
    db_path_abs = Path(db_path).resolve()

    print("=" * 80)
    print("DIAGNOSTIC: Temps du premier kill / première mort")
    print("=" * 80)
    print(f"\nBase de données: {db_path_abs}")
    print(f"XUID: {xuid}")

    if not db_path_abs.exists():
        print(f"\n❌ ERREUR: Le fichier {db_path_abs} n'existe pas!")
        return

    conn = duckdb.connect(str(db_path_abs), read_only=True)

    try:
        # 1. Vérifier si la table existe
        print("\n[1] Vérification de l'existence de la table highlight_events...")
        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main' AND table_name = 'highlight_events'"
        ).fetchall()

        if not tables:
            print("❌ La table highlight_events n'existe pas!")
            print("   → Solution: Synchroniser les matchs avec l'option with_highlight_events=True")
            return
        print("✅ La table highlight_events existe")

        # 2. Compter le nombre total d'événements
        print("\n[2] Nombre total d'événements dans highlight_events...")
        total_count = conn.execute("SELECT COUNT(*) FROM highlight_events").fetchone()[0]
        print(f"   Total: {total_count} événements")

        if total_count == 0:
            print("❌ La table est vide!")
            print("   → Solution: Synchroniser les matchs avec l'option with_highlight_events=True")
            return

        # 3. Analyser les event_type présents
        print("\n[3] Analyse des types d'événements présents...")
        event_types = conn.execute(
            "SELECT event_type, COUNT(*) as count FROM highlight_events GROUP BY event_type ORDER BY count DESC"
        ).fetchall()

        print("   Types d'événements trouvés:")
        for event_type, count in event_types:
            print(f"     - '{event_type}': {count} événements")

        # Vérifier la casse
        kill_variants = [et for et, _ in event_types if et.lower() == "kill"]
        death_variants = [et for et, _ in event_types if et.lower() == "death"]

        if kill_variants:
            print(f"\n   ⚠️  Variantes de 'Kill' trouvées: {kill_variants}")
        if death_variants:
            print(f"   ⚠️  Variantes de 'Death' trouvées: {death_variants}")

        # 4. Vérifier les événements pour le xuid spécifié
        print(f"\n[4] Événements pour le XUID '{xuid}'...")
        xuid_count = conn.execute(
            "SELECT COUNT(*) FROM highlight_events WHERE xuid = ?", [xuid]
        ).fetchone()[0]
        print(f"   Total: {xuid_count} événements pour ce XUID")

        if xuid_count == 0:
            print("   ⚠️  Aucun événement pour ce XUID!")
            print("   → Vérification des XUIDs présents dans la table...")
            xuids = conn.execute(
                "SELECT DISTINCT xuid, COUNT(*) as count FROM highlight_events WHERE xuid IS NOT NULL GROUP BY xuid ORDER BY count DESC LIMIT 5"
            ).fetchall()
            if xuids:
                print("   XUIDs les plus fréquents:")
                for xu, cnt in xuids:
                    print(f"     - {xu}: {cnt} événements")

        # 5. Obtenir quelques match_ids pour tester
        print("\n[5] Récupération de quelques match_ids pour tester...")
        match_ids_sample = conn.execute(
            "SELECT DISTINCT match_id FROM highlight_events WHERE xuid = ? LIMIT 10", [xuid]
        ).fetchall()

        if match_ids_sample:
            match_ids_list = [m[0] for m in match_ids_sample]
            print(f"   {len(match_ids_list)} match_ids trouvés pour ce XUID")

            # 6. Tester la requête exacte utilisée par le code
            print("\n[6] Test de la requête exacte utilisée par get_first_kill_death_times()...")

            placeholders = ", ".join(["?" for _ in match_ids_list])

            # Test pour "Kill" (avec majuscule)
            kills_upper = conn.execute(
                f"""
                SELECT match_id, MIN(time_ms) as first_time
                FROM highlight_events
                WHERE match_id IN ({placeholders})
                  AND event_type = ?
                  AND xuid = ?
                GROUP BY match_id
                """,
                [*match_ids_list, "Kill", xuid],
            ).fetchall()
            print(f"   Requête avec event_type='Kill': {len(kills_upper)} résultats")

            # Test pour "kill" (avec minuscule)
            kills_lower = conn.execute(
                f"""
                SELECT match_id, MIN(time_ms) as first_time
                FROM highlight_events
                WHERE match_id IN ({placeholders})
                  AND event_type = ?
                  AND xuid = ?
                GROUP BY match_id
                """,
                [*match_ids_list, "kill", xuid],
            ).fetchall()
            print(f"   Requête avec event_type='kill': {len(kills_lower)} résultats")

            # Test pour "Death" (avec majuscule)
            deaths_upper = conn.execute(
                f"""
                SELECT match_id, MIN(time_ms) as first_time
                FROM highlight_events
                WHERE match_id IN ({placeholders})
                  AND event_type = ?
                  AND xuid = ?
                GROUP BY match_id
                """,
                [*match_ids_list, "Death", xuid],
            ).fetchall()
            print(f"   Requête avec event_type='Death': {len(deaths_upper)} résultats")

            # Test pour "death" (avec minuscule)
            deaths_lower = conn.execute(
                f"""
                SELECT match_id, MIN(time_ms) as first_time
                FROM highlight_events
                WHERE match_id IN ({placeholders})
                  AND event_type = ?
                  AND xuid = ?
                GROUP BY match_id
                """,
                [*match_ids_list, "death", xuid],
            ).fetchall()
            print(f"   Requête avec event_type='death': {len(deaths_lower)} résultats")

            # Test case-insensitive
            kills_ci = conn.execute(
                f"""
                SELECT match_id, MIN(time_ms) as first_time
                FROM highlight_events
                WHERE match_id IN ({placeholders})
                  AND LOWER(event_type) = ?
                  AND xuid = ?
                GROUP BY match_id
                """,
                [*match_ids_list, "kill", xuid],
            ).fetchall()
            print(f"   Requête case-insensitive (LOWER) pour 'kill': {len(kills_ci)} résultats")

            deaths_ci = conn.execute(
                f"""
                SELECT match_id, MIN(time_ms) as first_time
                FROM highlight_events
                WHERE match_id IN ({placeholders})
                  AND LOWER(event_type) = ?
                  AND xuid = ?
                GROUP BY match_id
                """,
                [*match_ids_list, "death", xuid],
            ).fetchall()
            print(f"   Requête case-insensitive (LOWER) pour 'death': {len(deaths_ci)} résultats")
        else:
            print("   ⚠️  Aucun match_id trouvé pour ce XUID")

        # 7. Résumé et recommandations
        print("\n" + "=" * 80)
        print("RÉSUMÉ ET RECOMMANDATIONS")
        print("=" * 80)

        if total_count == 0:
            print("\n❌ PROBLÈME: La table highlight_events est vide")
            print("   → Solution: Synchroniser les matchs avec:")
            print("      python scripts/sync.py --delta --player JGtm --with-highlight-events")
        elif xuid_count == 0:
            print("\n❌ PROBLÈME: Aucun événement pour ce XUID")
            print("   → Vérifier que le XUID est correct")
            print(
                "   → Vérifier que les événements sont bien associés à ce XUID lors de la synchronisation"
            )
        else:
            # Vérifier la casse
            has_kill_upper = any(et == "Kill" for et, _ in event_types)
            has_kill_lower = any(et == "kill" for et, _ in event_types)
            has_death_upper = any(et == "Death" for et, _ in event_types)
            has_death_lower = any(et == "death" for et, _ in event_types)

            if (has_kill_lower and not has_kill_upper) or (has_death_lower and not has_death_upper):
                print("\n⚠️  PROBLÈME IDENTIFIÉ: Différence de casse dans event_type")
                print(
                    "   Le code cherche 'Kill'/'Death' (majuscule) mais les données contiennent 'kill'/'death' (minuscule)"
                )
                print(
                    "   → Solution: Modifier load_first_event_times() pour utiliser LOWER(event_type)"
                )
            else:
                print("\n✅ Les données semblent correctes")
                print("   → Si le graphe est toujours vide, vérifier:")
                print(
                    "      - Que les match_ids passés à get_first_kill_death_times() sont corrects"
                )
                print("      - Que le xuid utilisé correspond bien aux données")
                print("      - Les logs d'erreur dans l'interface Streamlit")

    finally:
        conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Diagnostique pourquoi le graphe premier kill/mort est vide"
    )
    parser.add_argument("db_path", help="Chemin vers la base DuckDB")
    parser.add_argument("xuid", help="XUID du joueur")

    args = parser.parse_args()

    diagnose_first_kill_death(args.db_path, args.xuid)
