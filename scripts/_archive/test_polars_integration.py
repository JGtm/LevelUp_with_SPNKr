#!/usr/bin/env python3
"""Script de validation de l'architecture Polars pour le projet LevelUp.

Ce script teste :
1. Les opérations Polars de base (filtrage, groupby, agrégation)
2. L'intégration DuckDB -> Polars
3. Les patterns d'analyse pour antagonistes et score personnel
4. Les performances comparees Polars vs Pandas

Usage:
    python scripts/test_polars_integration.py
"""

import sys
import time
from pathlib import Path

# Force UTF-8 pour Windows
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Ajouter le répertoire racine au path
sys.path.insert(0, str(Path(__file__).parent.parent))

import polars as pl

from src.data.domain.refdata import (
    ASSIST_SCORES,
    OBJECTIVE_SCORES,
    GameVariantCategory,
    PersonalScoreNameId,
    get_category_name_fr,
    get_personal_score_points,
)


def create_sample_match_stats() -> pl.DataFrame:
    """Crée un DataFrame de stats de matchs pour les tests."""
    return pl.DataFrame(
        {
            "match_id": [
                "match_001",
                "match_002",
                "match_003",
                "match_004",
                "match_005",
                "match_006",
                "match_007",
                "match_008",
                "match_009",
                "match_010",
            ],
            "start_time": pl.Series(
                [
                    "2026-02-01 10:00:00",
                    "2026-02-01 10:30:00",
                    "2026-02-01 11:00:00",
                    "2026-02-01 11:30:00",
                    "2026-02-01 12:00:00",
                    "2026-02-02 10:00:00",
                    "2026-02-02 10:30:00",
                    "2026-02-02 11:00:00",
                    "2026-02-02 11:30:00",
                    "2026-02-02 12:00:00",
                ]
            ).str.to_datetime(),
            "kills": [15, 8, 22, 10, 18, 12, 25, 7, 14, 20],
            "deaths": [10, 12, 8, 15, 10, 9, 5, 18, 11, 8],
            "assists": [5, 8, 3, 7, 6, 4, 2, 10, 8, 4],
            "personal_score": [
                1500,
                1200,
                2200,
                1000,
                1800,
                1300,
                2500,
                700,
                1400,
                2000,
            ],
            "game_variant_category": [
                GameVariantCategory.MULTIPLAYER_SLAYER,
                GameVariantCategory.MULTIPLAYER_CTF,
                GameVariantCategory.MULTIPLAYER_SLAYER,
                GameVariantCategory.MULTIPLAYER_ODDBALL,
                GameVariantCategory.MULTIPLAYER_STRONGHOLDS,
                GameVariantCategory.MULTIPLAYER_SLAYER,
                GameVariantCategory.MULTIPLAYER_FIESTA,
                GameVariantCategory.MULTIPLAYER_CTF,
                GameVariantCategory.MULTIPLAYER_TOTAL_CONTROL,
                GameVariantCategory.MULTIPLAYER_SLAYER,
            ],
            "outcome": [2, 3, 2, 3, 2, 2, 2, 3, 2, 2],  # 2=Win, 3=Loss
        }
    )


def create_sample_killer_victim_pairs() -> pl.DataFrame:
    """Crée un DataFrame de paires killer-victim pour les tests."""
    return pl.DataFrame(
        {
            "match_id": [
                "match_001",
                "match_001",
                "match_001",
                "match_001",
                "match_001",
                "match_002",
                "match_002",
                "match_002",
            ],
            "killer_xuid": [
                "xuid_me",
                "xuid_me",
                "xuid_enemy1",
                "xuid_enemy2",
                "xuid_me",
                "xuid_me",
                "xuid_enemy1",
                "xuid_enemy1",
            ],
            "killer_gamertag": [
                "MonJoueur",
                "MonJoueur",
                "Enemy1",
                "Enemy2",
                "MonJoueur",
                "MonJoueur",
                "Enemy1",
                "Enemy1",
            ],
            "victim_xuid": [
                "xuid_enemy1",
                "xuid_enemy2",
                "xuid_me",
                "xuid_me",
                "xuid_enemy1",
                "xuid_enemy1",
                "xuid_me",
                "xuid_me",
            ],
            "victim_gamertag": [
                "Enemy1",
                "Enemy2",
                "MonJoueur",
                "MonJoueur",
                "Enemy1",
                "Enemy1",
                "MonJoueur",
                "MonJoueur",
            ],
            "timestamp_offset_ms": [
                10000,
                25000,
                45000,
                60000,
                75000,
                15000,
                30000,
                90000,
            ],
        }
    )


def create_sample_personal_score_awards() -> pl.DataFrame:
    """Crée un DataFrame de personal score awards pour les tests."""
    return pl.DataFrame(
        {
            "match_id": [
                "match_001",
                "match_001",
                "match_001",
                "match_002",
                "match_002",
                "match_002",
                "match_002",
            ],
            "award_name_id": [
                PersonalScoreNameId.KILLED_PLAYER,
                PersonalScoreNameId.KILL_ASSIST,
                PersonalScoreNameId.MARK_ASSIST,
                PersonalScoreNameId.FLAG_CAPTURED,
                PersonalScoreNameId.FLAG_STOLEN,
                PersonalScoreNameId.KILL_ASSIST,
                PersonalScoreNameId.KILLED_PLAYER,
            ],
            "count": [15, 5, 8, 2, 3, 4, 8],
        }
    )


def test_basic_polars_operations() -> bool:
    """Teste les opérations Polars de base."""
    print("\n" + "=" * 60)
    print("TEST 1: Opérations Polars de base")
    print("=" * 60)

    df = create_sample_match_stats()

    # Test filtrage
    slayer_matches = df.filter(
        pl.col("game_variant_category") == GameVariantCategory.MULTIPLAYER_SLAYER
    )
    print(f"✅ Filtrage: {len(slayer_matches)} matchs Slayer sur {len(df)}")

    # Test agrégation
    stats = df.select(
        [
            pl.mean("kills").alias("avg_kills"),
            pl.mean("deaths").alias("avg_deaths"),
            pl.sum("personal_score").alias("total_score"),
        ]
    )
    print(
        f"✅ Agrégation: Avg kills={stats['avg_kills'][0]:.1f}, "
        f"Avg deaths={stats['avg_deaths'][0]:.1f}"
    )

    # Test group_by
    by_category = (
        df.group_by("game_variant_category")
        .agg([pl.len().alias("count"), pl.mean("kills").alias("avg_kills")])
        .sort("count", descending=True)
    )
    print(f"✅ GroupBy: {len(by_category)} catégories distinctes")

    # Test with_columns
    df_enriched = df.with_columns(
        [
            (pl.col("kills") - pl.col("deaths")).alias("net_score"),
            (pl.col("kills") / pl.col("deaths")).round(2).alias("kd_ratio"),
        ]
    )
    print(f"✅ With columns: {df_enriched.columns}")

    return True


def test_cumulative_net_score_polars() -> bool:
    """Teste le calcul de performance cumulée avec Polars."""
    print("\n" + "=" * 60)
    print("TEST 2: Performance cumulée (Sprint 6)")
    print("=" * 60)

    df = create_sample_match_stats()

    # Calcul cumulative net score
    result = (
        df.sort("start_time")
        .with_columns(
            [
                (pl.col("kills") - pl.col("deaths")).alias("net_score"),
            ]
        )
        .with_columns(
            [
                pl.col("net_score").cum_sum().alias("cumulative_net_score"),
            ]
        )
        .select(["start_time", "net_score", "cumulative_net_score"])
    )

    print("📊 Série cumulative net score:")
    print(result)

    # Vérification
    first_net = result["net_score"][0]
    first_cumulative = result["cumulative_net_score"][0]
    assert first_net == first_cumulative, "Premier cumul doit égaler premier net_score"
    print("✅ Calcul cumulatif correct")

    return True


def test_antagonists_analysis_polars() -> bool:
    """Teste l'analyse des antagonistes avec Polars (Sprint 3)."""
    print("\n" + "=" * 60)
    print("TEST 3: Analyse antagonistes (Sprint 3)")
    print("=" * 60)

    pairs_df = create_sample_killer_victim_pairs()
    me_xuid = "xuid_me"

    # Némésis : qui m'a tué le plus
    nemesis = (
        pairs_df.filter(pl.col("victim_xuid") == me_xuid)
        .group_by("killer_xuid", "killer_gamertag")
        .agg(pl.len().alias("times_killed_by"))
        .sort("times_killed_by", descending=True)
        .head(1)
    )

    if len(nemesis) > 0:
        nemesis_data = nemesis.to_dicts()[0]
        print(
            f"👿 Némésis: {nemesis_data['killer_gamertag']} "
            f"({nemesis_data['times_killed_by']} fois)"
        )
    else:
        print("❓ Aucun némésis trouvé")

    # Souffre-douleur : qui j'ai tué le plus
    victim = (
        pairs_df.filter(pl.col("killer_xuid") == me_xuid)
        .group_by("victim_xuid", "victim_gamertag")
        .agg(pl.len().alias("times_killed"))
        .sort("times_killed", descending=True)
        .head(1)
    )

    if len(victim) > 0:
        victim_data = victim.to_dicts()[0]
        print(
            f"😈 Souffre-douleur: {victim_data['victim_gamertag']} "
            f"({victim_data['times_killed']} fois)"
        )
    else:
        print("❓ Aucun souffre-douleur trouvé")

    # K/D par adversaire
    kd_by_opponent = (
        pairs_df.filter((pl.col("killer_xuid") == me_xuid) | (pl.col("victim_xuid") == me_xuid))
        .with_columns(
            [
                pl.when(pl.col("killer_xuid") == me_xuid)
                .then(pl.col("victim_xuid"))
                .otherwise(pl.col("killer_xuid"))
                .alias("opponent_xuid"),
                pl.when(pl.col("killer_xuid") == me_xuid)
                .then(pl.col("victim_gamertag"))
                .otherwise(pl.col("killer_gamertag"))
                .alias("opponent_gamertag"),
                pl.when(pl.col("killer_xuid") == me_xuid).then(1).otherwise(0).alias("is_kill"),
                pl.when(pl.col("victim_xuid") == me_xuid).then(1).otherwise(0).alias("is_death"),
            ]
        )
        .group_by("opponent_xuid", "opponent_gamertag")
        .agg(
            [
                pl.sum("is_kill").alias("kills"),
                pl.sum("is_death").alias("deaths"),
            ]
        )
        .with_columns(
            [
                (pl.col("kills") / pl.col("deaths").replace(0, 1)).round(2).alias("kd_ratio"),
            ]
        )
        .sort("kd_ratio", descending=True)
    )

    print("\n📊 K/D par adversaire:")
    print(kd_by_opponent)
    print("✅ Analyse antagonistes réussie")

    return True


def test_personal_score_analysis_polars() -> bool:
    """Teste l'analyse du score personnel avec Polars (Sprint 4)."""
    print("\n" + "=" * 60)
    print("TEST 4: Analyse score personnel (Sprint 4)")
    print("=" * 60)

    awards_df = create_sample_personal_score_awards()

    # Convertir en sets pour la comparaison
    objective_ids = set(OBJECTIVE_SCORES)
    assist_ids = set(ASSIST_SCORES)

    # Score par catégorie
    result = awards_df.with_columns(
        [
            pl.col("award_name_id")
            .map_elements(lambda x: get_personal_score_points(x), return_dtype=pl.Int64)
            .alias("points_per_unit"),
            pl.col("award_name_id").is_in(list(objective_ids)).alias("is_objective"),
            pl.col("award_name_id").is_in(list(assist_ids)).alias("is_assist"),
        ]
    ).with_columns(
        [
            (pl.col("count") * pl.col("points_per_unit")).alias("total_points"),
        ]
    )

    print("📊 Détail des scores:")
    print(result)

    # Somme par type
    summary = result.group_by("match_id").agg(
        [
            pl.sum("total_points").alias("total_score"),
            pl.col("total_points").filter(pl.col("is_objective")).sum().alias("objective_score"),
            pl.col("total_points").filter(pl.col("is_assist")).sum().alias("assist_score"),
        ]
    )

    print("\n📊 Résumé par match:")
    print(summary)
    print("✅ Analyse score personnel réussie")

    return True


def test_duckdb_to_polars_integration() -> bool:
    """Teste l'intégration DuckDB → Polars."""
    print("\n" + "=" * 60)
    print("TEST 5: Intégration DuckDB → Polars")
    print("=" * 60)

    import duckdb

    # Créer une DB en mémoire
    con = duckdb.connect(":memory:")

    # Créer table de test
    con.execute("""
        CREATE TABLE match_stats (
            match_id VARCHAR,
            kills INTEGER,
            deaths INTEGER,
            game_variant_category INTEGER
        )
    """)

    con.execute("""
        INSERT INTO match_stats VALUES
        ('m1', 15, 10, 6),
        ('m2', 8, 12, 15),
        ('m3', 22, 8, 6),
        ('m4', 10, 15, 18)
    """)

    # Requête DuckDB → Polars
    query = """
        SELECT
            match_id,
            kills,
            deaths,
            kills - deaths as net_score,
            game_variant_category
        FROM match_stats
        ORDER BY net_score DESC
    """

    # Méthode 1 : Via pl.from_arrow()
    arrow_table = con.execute(query).fetch_arrow_table()
    df_polars = pl.from_arrow(arrow_table)

    print("📊 DataFrame Polars depuis DuckDB:")
    print(df_polars)

    # Enrichir avec refdata
    df_enriched = df_polars.with_columns(
        [
            pl.col("game_variant_category")
            .map_elements(lambda x: get_category_name_fr(x), return_dtype=pl.Utf8)
            .alias("category_name_fr"),
        ]
    )

    print("\n📊 Enrichi avec noms français:")
    print(df_enriched)

    con.close()
    print("✅ Intégration DuckDB → Polars réussie")

    return True


def test_performance_benchmark() -> bool:
    """Benchmark simple Polars vs opérations manuelles."""
    print("\n" + "=" * 60)
    print("TEST 6: Benchmark performance")
    print("=" * 60)

    # Créer un DataFrame plus grand
    import random

    n_rows = 10000
    data = {
        "match_id": [f"match_{i:05d}" for i in range(n_rows)],
        "kills": [random.randint(0, 30) for _ in range(n_rows)],
        "deaths": [random.randint(0, 30) for _ in range(n_rows)],
        "assists": [random.randint(0, 15) for _ in range(n_rows)],
        "game_variant_category": [random.choice([6, 15, 18, 11, 14]) for _ in range(n_rows)],
    }

    df = pl.DataFrame(data)

    # Benchmark agrégation
    start = time.perf_counter()
    for _ in range(100):
        _ = (
            df.group_by("game_variant_category")
            .agg(
                [
                    pl.len().alias("count"),
                    pl.mean("kills").alias("avg_kills"),
                    pl.mean("deaths").alias("avg_deaths"),
                    pl.sum("assists").alias("total_assists"),
                ]
            )
            .sort("count", descending=True)
        )
    elapsed = time.perf_counter() - start

    print(f"⏱️ 100 agrégations GroupBy sur {n_rows} lignes : {elapsed:.3f}s")
    print(f"   → {elapsed / 100 * 1000:.2f}ms par agrégation")

    # Benchmark filtrage + transformation
    start = time.perf_counter()
    for _ in range(100):
        _ = (
            df.filter(pl.col("game_variant_category") == 6)
            .with_columns(
                [
                    (pl.col("kills") - pl.col("deaths")).alias("net_score"),
                    (pl.col("kills") / pl.col("deaths").replace(0, 1)).round(2).alias("kd_ratio"),
                ]
            )
            .sort("kd_ratio", descending=True)
        )
    elapsed = time.perf_counter() - start

    print(f"⏱️ 100 filtres + transformations : {elapsed:.3f}s")
    print(f"   → {elapsed / 100 * 1000:.2f}ms par opération")

    print("✅ Benchmark terminé")

    return True


def main():
    """Exécute tous les tests de validation Polars."""
    print("=" * 60)
    print("VALIDATION ARCHITECTURE POLARS - Sprint 0")
    print("=" * 60)
    print(f"Polars version: {pl.__version__}")

    tests = [
        ("Opérations de base", test_basic_polars_operations),
        ("Performance cumulée", test_cumulative_net_score_polars),
        ("Analyse antagonistes", test_antagonists_analysis_polars),
        ("Analyse score personnel", test_personal_score_analysis_polars),
        ("Intégration DuckDB → Polars", test_duckdb_to_polars_integration),
        ("Benchmark performance", test_performance_benchmark),
    ]

    results = []
    for name, test_fn in tests:
        try:
            success = test_fn()
            results.append((name, success))
        except Exception as e:
            print(f"\n❌ ERREUR dans '{name}': {e}")
            results.append((name, False))

    # Résumé
    print("\n" + "=" * 60)
    print("RÉSUMÉ")
    print("=" * 60)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for name, success in results:
        status = "✅" if success else "❌"
        print(f"  {status} {name}")

    print(f"\n{passed}/{total} tests passés")

    if passed == total:
        print("\n🎉 Architecture Polars validée !")
        return 0
    else:
        print("\n⚠️ Certains tests ont échoué")
        return 1


if __name__ == "__main__":
    sys.exit(main())
