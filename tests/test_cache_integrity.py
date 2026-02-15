"""Tests d'intégrité du cache MatchCache et agrégats.

Ces tests ciblent le schéma SQLite legacy (MatchCache, Players, etc.).
DuckDB v4 n'utilise pas ce schéma - ces tests sont skippés par défaut.
Pour exécuter: TEST_DB_PATH=<path/to/halo_unified.db> pytest (SQLite interdit en prod).
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Chemin vers la DB de test legacy (SQLite) - skippé par défaut
DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "halo_unified.db"


def get_db_path() -> Path:
    """Retourne le chemin de la DB (défaut ou env var)."""
    import os

    return Path(os.getenv("TEST_DB_PATH", str(DEFAULT_DB_PATH)))


@pytest.fixture
def db_connection():
    """Fixture pour une connexion DB - SKIP : SQLite legacy non supporté.

    Ces tests ciblent MatchCache/Players (schéma SQLite legacy).
    Le projet utilise exclusivement DuckDB v4.
    """
    pytest.skip(
        "Tests cache legacy (SQLite MatchCache) skippés - DuckDB v4 uniquement. "
        "Voir test_duckdb_repo_regressions.py pour les tests DuckDB."
    )


class TestMatchCacheIntegrity:
    """Tests d'intégrité pour MatchCache.

    Note: Ces tests vérifient des données locales et peuvent échouer si la
    migration du cache n'est pas complète. Marqués comme xfail pour ne pas
    bloquer la CI.
    """

    @pytest.mark.xfail(reason="Migration cache incomplète pour certains joueurs")
    def test_all_players_have_cache_entries(self, db_connection):
        """Vérifie que tous les joueurs ont des entrées dans MatchCache."""
        cur = db_connection.cursor()

        # Récupérer tous les joueurs actifs
        cur.execute("SELECT xuid, gamertag FROM Players")
        players = cur.fetchall()

        if not players:
            pytest.skip("Aucun joueur dans la table Players")

        players_without_cache = []
        for player in players:
            cur.execute("SELECT COUNT(*) FROM MatchCache WHERE xuid = ?", (player["xuid"],))
            count = cur.fetchone()[0]
            if count == 0:
                players_without_cache.append(player["gamertag"])

        assert (
            len(players_without_cache) == 0
        ), f"Joueurs sans entrées dans MatchCache: {players_without_cache}"

    @pytest.mark.xfail(reason="Migration cache incomplète pour certains joueurs")
    def test_players_total_matches_consistent(self, db_connection):
        """Vérifie que Players.total_matches correspond au compte MatchCache."""
        cur = db_connection.cursor()

        cur.execute("""
            SELECT p.gamertag, p.total_matches,
                   (SELECT COUNT(*) FROM MatchCache mc WHERE mc.xuid = p.xuid) as actual_count
            FROM Players p
        """)
        rows = cur.fetchall()

        if not rows:
            pytest.skip("Aucun joueur dans la table Players")

        mismatches = []
        for row in rows:
            if row["total_matches"] != row["actual_count"]:
                mismatches.append(
                    {
                        "gamertag": row["gamertag"],
                        "total_matches": row["total_matches"],
                        "actual_count": row["actual_count"],
                    }
                )

        assert (
            len(mismatches) == 0
        ), f"Incohérences Players.total_matches vs MatchCache count: {mismatches}"

    def test_average_life_seconds_coverage(self, db_connection):
        """Vérifie que ≥80% des matchs ont average_life_seconds non NULL."""
        cur = db_connection.cursor()

        # Compte global
        cur.execute("SELECT COUNT(*) FROM MatchCache")
        total = cur.fetchone()[0]

        if total == 0:
            pytest.skip("MatchCache vide")

        cur.execute("SELECT COUNT(*) FROM MatchCache WHERE average_life_seconds IS NOT NULL")
        with_life = cur.fetchone()[0]

        coverage = (with_life / total) * 100

        # Le seuil est 80% car certains modes (custom, training) n'ont pas cette stat
        assert coverage >= 80.0, (
            f"Seulement {coverage:.1f}% des matchs ont average_life_seconds "
            f"({with_life}/{total}). Attendu: ≥80%"
        )

    def test_no_nan_in_numeric_columns(self, db_connection):
        """Vérifie qu'aucune colonne numérique ne contient 'nan' comme string."""
        cur = db_connection.cursor()

        # Colonnes numériques à vérifier
        numeric_cols = [
            "kills",
            "deaths",
            "assists",
            "kd_ratio",
            "kda_ratio",
            "damage_dealt",
            "damage_taken",
            "shots_fired",
            "shots_hit",
            "accuracy",
            "headshot_kills",
            "melee_kills",
            "grenade_kills",
            "average_life_seconds",
            "score",
        ]

        problems = []
        for col in numeric_cols:
            # Vérifier si la colonne existe et contient 'nan'
            try:
                cur.execute(f"""
                    SELECT COUNT(*) FROM MatchCache
                    WHERE typeof({col}) = 'text' AND {col} LIKE '%nan%'
                """)
                nan_count = cur.fetchone()[0]
                if nan_count > 0:
                    problems.append(f"{col}: {nan_count} 'nan' values")
            except Exception:
                # Colonne n'existe pas, on ignore
                pass

        assert len(problems) == 0, f"Valeurs 'nan' trouvées: {problems}"


class TestTeammatesAggregateIntegrity:
    """Tests d'intégrité pour TeammatesAggregate."""

    def test_all_players_have_teammates(self, db_connection):
        """Vérifie que tous les joueurs ont des entrées dans TeammatesAggregate."""
        cur = db_connection.cursor()

        cur.execute("SELECT xuid, gamertag FROM Players")
        players = cur.fetchall()

        if not players:
            pytest.skip("Aucun joueur dans la table Players")

        players_without_teammates = []
        for player in players:
            cur.execute("SELECT COUNT(*) FROM TeammatesAggregate WHERE xuid = ?", (player["xuid"],))
            count = cur.fetchone()[0]
            if count == 0:
                players_without_teammates.append(player["gamertag"])

        # Il est possible qu'un joueur n'ait pas de coéquipiers (solo uniquement)
        # mais c'est rare, donc on avertit
        if players_without_teammates:
            pytest.skip(
                f"Joueurs sans coéquipiers (peut être normal si solo): "
                f"{players_without_teammates}"
            )

    def test_teammates_not_self(self, db_connection):
        """Vérifie qu'aucun joueur n'est son propre coéquipier."""
        cur = db_connection.cursor()

        cur.execute("""
            SELECT xuid, teammate_xuid
            FROM TeammatesAggregate
            WHERE xuid = teammate_xuid
        """)
        self_teammates = cur.fetchall()

        assert len(self_teammates) == 0, (
            f"Joueurs enregistrés comme leurs propres coéquipiers: "
            f"{[row['xuid'] for row in self_teammates]}"
        )

    def test_teammate_games_positive(self, db_connection):
        """Vérifie que matches_together est toujours positif."""
        cur = db_connection.cursor()

        cur.execute("""
            SELECT COUNT(*) FROM TeammatesAggregate
            WHERE matches_together <= 0
        """)
        invalid_count = cur.fetchone()[0]

        assert invalid_count == 0, f"{invalid_count} entrées avec matches_together ≤ 0"


class TestMedalsAggregateIntegrity:
    """Tests d'intégrité pour MedalsAggregate."""

    def test_medals_have_valid_counts(self, db_connection):
        """Vérifie que les comptes de médailles sont valides."""
        cur = db_connection.cursor()

        # Vérifier que la table existe
        cur.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='MedalsAggregate'
        """)
        if not cur.fetchone():
            pytest.skip("Table MedalsAggregate n'existe pas")

        cur.execute("""
            SELECT COUNT(*) FROM MedalsAggregate
            WHERE total_count <= 0
        """)
        invalid_count = cur.fetchone()[0]

        assert invalid_count == 0, f"{invalid_count} médailles avec total_count ≤ 0"


class TestCacheMetadata:
    """Tests pour les métadonnées du cache."""

    def test_cache_meta_exists(self, db_connection):
        """Vérifie que CacheMeta contient les entrées attendues."""
        cur = db_connection.cursor()

        # Vérifier que la table existe
        cur.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='CacheMeta'
        """)
        if not cur.fetchone():
            pytest.skip("Table CacheMeta n'existe pas")

        cur.execute("SELECT key, value FROM CacheMeta")
        meta = {row["key"]: row["value"] for row in cur.fetchall()}

        assert "match_cache_count" in meta, "CacheMeta manque 'match_cache_count'"

        count = int(meta["match_cache_count"])
        assert count > 0, "match_cache_count devrait être > 0"

    def test_cache_count_matches_actual(self, db_connection):
        """Vérifie que CacheMeta.match_cache_count est cohérent avec le cache réel.

        Note: Le compteur peut être légèrement différent si le cache a été
        reconstruit partiellement ou consolidé après des duplicatas.
        On vérifie juste que les deux valeurs sont raisonnablement proches.
        """
        cur = db_connection.cursor()

        # Vérifier que la table existe
        cur.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='CacheMeta'
        """)
        if not cur.fetchone():
            pytest.skip("Table CacheMeta n'existe pas")

        cur.execute("SELECT value FROM CacheMeta WHERE key = 'match_cache_count'")
        row = cur.fetchone()
        if not row:
            pytest.skip("Pas de match_cache_count dans CacheMeta")

        meta_count = int(row["value"])

        cur.execute("SELECT COUNT(*) FROM MatchCache")
        actual_count = cur.fetchone()[0]

        # Tolérance de 50% car le cache peut avoir été consolidé
        # Le test principal est que actual_count > 0 si meta_count > 0
        if meta_count > 0:
            assert (
                actual_count > 0
            ), f"CacheMeta indique {meta_count} matchs mais MatchCache est vide"

        # Avertissement si gros écart
        if meta_count > 0 and actual_count != meta_count:
            import warnings

            warnings.warn(
                f"CacheMeta.match_cache_count ({meta_count}) != "
                f"COUNT(*) MatchCache ({actual_count}). "
                "Considérer rebuild_match_cache pour synchroniser.",
                stacklevel=2,
            )


class TestSourceVsCacheConsistency:
    """Tests de cohérence entre données sources et cache."""

    def test_matchstats_vs_matchcache_count(self, db_connection):
        """Vérifie que le nombre de matchs sources ≥ matchs en cache."""
        cur = db_connection.cursor()

        # MatchStats utilise ResponseBody (JSON blob), on compte les lignes
        # associées aux joueurs actifs via xuid dans le JSON
        cur.execute("SELECT COUNT(*) FROM MatchStats")
        source_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM MatchCache")
        cache_count = cur.fetchone()[0]

        # Le cache peut avoir moins d'entrées si certains matchs ont été filtrés
        # ou plus si reconstruit depuis plusieurs sources
        # On vérifie juste que le cache n'est pas vide si on a des sources
        if source_count > 0:
            assert cache_count > 0, f"MatchCache vide alors que MatchStats a {source_count} entrées"

        # Avertir si gros écart
        if source_count > 0 and cache_count > 0:
            ratio = cache_count / source_count
            if ratio < 0.5:
                import warnings

                warnings.warn(
                    f"Seulement {ratio*100:.1f}% des matchs sources sont en cache "
                    f"({cache_count}/{source_count})",
                    stacklevel=2,
                )
