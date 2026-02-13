"""Tests de gate Sprint 17 — vérification des cibles legacy-free.

Ce module vérifie automatiquement les métriques du Sprint 17 :
- duckdb_repo.py < 1500 lignes
- cache.py < 100 lignes (façade)
- cache_loaders.py < 800 lignes
- cache_filters.py < 800 lignes
- 0 import pandas dans les fichiers migrés (sauf exceptions documentées)
- 0 from src.db dans le code principal (sauf shim)
- _arrow_bridge.py existe et exporte result_to_polars/ensure_polars
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _count_lines(path: Path) -> int:
    """Compte les lignes d'un fichier."""
    return len(path.read_text(encoding="utf-8").splitlines())


def _grep_imports(pattern: str, path: Path) -> list[str]:
    """Cherche un pattern d'import dans un fichier, retourne les lignes matchées."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if pattern in line and not line.strip().startswith("#")]


class TestSprintTargetsFileSize:
    """Cibles de taille de fichiers Sprint 17."""

    def test_duckdb_repo_under_1500_lines(self):
        """duckdb_repo.py doit être < 1500 lignes après extraction des mixins."""
        path = ROOT / "src" / "data" / "repositories" / "duckdb_repo.py"
        lines = _count_lines(path)
        assert lines < 1500, f"duckdb_repo.py a {lines} lignes (cible < 1500)"

    def test_cache_facade_under_100_lines(self):
        """cache.py (façade) doit être < 100 lignes."""
        path = ROOT / "src" / "ui" / "cache.py"
        lines = _count_lines(path)
        assert lines < 100, f"cache.py a {lines} lignes (cible < 100, c'est une façade)"

    def test_cache_loaders_under_800_lines(self):
        """cache_loaders.py doit être < 800 lignes."""
        path = ROOT / "src" / "ui" / "cache_loaders.py"
        lines = _count_lines(path)
        assert lines < 800, f"cache_loaders.py a {lines} lignes (cible < 800)"

    def test_cache_filters_under_800_lines(self):
        """cache_filters.py doit être < 800 lignes."""
        path = ROOT / "src" / "ui" / "cache_filters.py"
        lines = _count_lines(path)
        assert lines < 800, f"cache_filters.py a {lines} lignes (cible < 800)"


class TestSprintTargetsMixinsSplit:
    """Vérification de l'existence des fichiers Mixin extraits."""

    @pytest.mark.parametrize(
        "filename",
        [
            "_match_queries.py",
            "_roster_loader.py",
            "_materialized_views.py",
            "_antagonists_repo.py",
            "_arrow_bridge.py",
        ],
    )
    def test_mixin_files_exist(self, filename: str):
        """Les fichiers Mixin et le bridge Arrow existent."""
        path = ROOT / "src" / "data" / "repositories" / filename
        assert path.exists(), f"{filename} n'existe pas"


class TestSprintTargetsNoPandasInMigratedFiles:
    """Vérification que les fichiers migrés n'importent plus pandas."""

    # Fichiers qui ne doivent PLUS avoir de `import pandas`
    MIGRATED_FILES = [
        "src/ui/cache_loaders.py",
        "src/ui/cache_filters.py",
        "src/data/services/teammates_service.py",
        "src/data/services/timeseries_service.py",
        "src/app/filters.py",
        "src/app/filters_render.py",
        "src/app/kpis.py",
        "src/app/kpis_render.py",
        "src/app/helpers.py",
        "src/app/page_router.py",
        "src/analysis/stats.py",
        "src/analysis/maps.py",
        "src/ui/formatting.py",
        "src/ui/perf.py",
        "src/ui/commendations.py",
        "src/data/repositories/duckdb_repo.py",
        "src/data/repositories/_match_queries.py",
        "src/data/repositories/_roster_loader.py",
        "src/data/repositories/_materialized_views.py",
        "src/data/repositories/_antagonists_repo.py",
        "src/data/repositories/_arrow_bridge.py",
    ]

    @pytest.mark.parametrize("rel_path", MIGRATED_FILES)
    def test_no_pandas_import(self, rel_path: str):
        """Aucun fichier migré ne doit importer pandas."""
        path = ROOT / rel_path
        if not path.exists():
            pytest.skip(f"{rel_path} n'existe pas")
        hits = _grep_imports("import pandas", path)
        # Filtrer les imports conditionnels TYPE_CHECKING
        real_hits = [h for h in hits if "TYPE_CHECKING" not in h]
        assert not real_hits, f"{rel_path} importe encore pandas: {real_hits}"


class TestSprintTargetsNoSrcDbInCode:
    """Vérification que les imports src.db sont redirigés vers src.data.sync."""

    # Fichiers qui ne doivent PLUS importer depuis src.db (sauf le shim)
    CODE_FILES = [
        "src/data/sync/engine.py",
        "scripts/backfill/strategies.py",
        "scripts/backfill/orchestrator.py",
        "scripts/backfill/core.py",
    ]

    @pytest.mark.parametrize("rel_path", CODE_FILES)
    def test_no_src_db_import(self, rel_path: str):
        """Les imports doivent utiliser src.data.sync.migrations (pas src.db)."""
        path = ROOT / rel_path
        if not path.exists():
            pytest.skip(f"{rel_path} n'existe pas")
        hits = _grep_imports("from src.db", path)
        assert not hits, f"{rel_path} importe encore depuis src.db: {hits}"


class TestSprintTargetsArrowBridge:
    """Vérification que le bridge Arrow exporte les symboles attendus."""

    def test_result_to_polars_importable(self):
        """result_to_polars est importable depuis _arrow_bridge."""
        from src.data.repositories._arrow_bridge import result_to_polars

        assert callable(result_to_polars)

    def test_ensure_polars_importable(self):
        """ensure_polars est importable depuis _arrow_bridge."""
        from src.data.repositories._arrow_bridge import ensure_polars

        assert callable(ensure_polars)


class TestSprintTargetsCacheFacade:
    """Vérification que la façade cache.py ré-exporte correctement."""

    EXPECTED_SYMBOLS = [
        "cached_compute_sessions_db",
        "cached_list_local_dbs",
        "load_df_optimized",
        "load_df_hybrid",
        "db_cache_key",
        "clear_app_caches",
        "cached_friend_matches_df",
        "cached_same_team_match_ids_with_friend",
        "cached_load_match_rosters",
        "cached_load_highlight_events_for_match",
        "cached_load_match_player_gamertags",
        "top_medals_smart",
        "PARIS_TZ_NAME",
        "_to_polars",
    ]

    @pytest.mark.parametrize("symbol", EXPECTED_SYMBOLS)
    def test_facade_reexports(self, symbol: str):
        """La façade cache.py ré-exporte tous les symboles attendus."""
        import src.ui.cache as cache_module

        assert hasattr(cache_module, symbol), f"cache.py ne ré-exporte pas {symbol}"


class TestSprintTargetsMigrationShim:
    """Vérification que le shim src/db/migrations.py fonctionne."""

    def test_shim_reexports_all_functions(self):
        """Le shim src.db.migrations ré-exporte les fonctions de migration."""
        from src.db.migrations import (
            column_exists,
            ensure_end_time_column,
            ensure_match_participants_columns,
            ensure_match_stats_columns,
            ensure_medals_earned_bigint,
            ensure_performance_score_column,
            get_table_columns,
            table_exists,
        )

        assert callable(ensure_match_stats_columns)
        assert callable(ensure_performance_score_column)
        assert callable(get_table_columns)
        assert callable(table_exists)
        assert callable(column_exists)
        assert callable(ensure_end_time_column)
        assert callable(ensure_match_participants_columns)
        assert callable(ensure_medals_earned_bigint)

    def test_canonical_location_works(self):
        """L'import depuis le nouvel emplacement canonique fonctionne."""
        from src.data.sync.migrations import ensure_match_stats_columns

        assert callable(ensure_match_stats_columns)
