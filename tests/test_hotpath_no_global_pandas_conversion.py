"""Tests Sprint 19 — Vérification absence de Pandas sur chemins chauds.

Vérifie que les modules de rendu hot-path n'importent pas Pandas
et ne font pas de conversions Pandas inutiles.
"""

from __future__ import annotations

import ast
import inspect

# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def _get_top_level_imports(module) -> set[str]:
    """Extrait les noms de modules importés au top-level d'un module Python."""
    source = inspect.getsource(module)
    tree = ast.parse(source)
    imports = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    return imports


def _source_contains(module, pattern: str) -> list[str]:
    """Retourne les lignes source contenant le pattern."""
    source = inspect.getsource(module)
    return [
        line.strip()
        for line in source.split("\n")
        if pattern in line
        and not line.strip().startswith("#")
        and not line.strip().startswith('"""')
        and "TYPE_CHECKING" not in line
    ]


# ─────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────


class TestNoGlobalPandasConversion:
    """Vérifie que les hot paths n'importent pas Pandas au top-level."""

    def test_timeseries_no_pandas_import(self):
        """timeseries.py n'importe pas pandas."""
        from src.visualization import timeseries

        imports = _get_top_level_imports(timeseries)
        assert "pandas" not in imports, "timeseries.py importe pandas au top-level"

    def test_timeseries_combat_no_pandas_import(self):
        """timeseries_combat.py n'importe pas pandas."""
        from src.visualization import timeseries_combat

        imports = _get_top_level_imports(timeseries_combat)
        assert "pandas" not in imports, "timeseries_combat.py importe pandas au top-level"

    def test_cache_loaders_no_pandas_import(self):
        """cache_loaders.py n'importe pas pandas au top-level."""
        from src.ui import cache_loaders

        imports = _get_top_level_imports(cache_loaders)
        assert "pandas" not in imports, "cache_loaders.py importe pandas au top-level"

    def test_page_router_no_pandas_import(self):
        """page_router.py n'importe pas pandas."""
        from src.app import page_router

        imports = _get_top_level_imports(page_router)
        assert "pandas" not in imports, "page_router.py importe pandas au top-level"

    def test_main_helpers_no_pandas_import(self):
        """main_helpers.py n'importe pas pandas."""
        from src.app import main_helpers

        imports = _get_top_level_imports(main_helpers)
        assert "pandas" not in imports, "main_helpers.py importe pandas au top-level"


class TestNoToPandasInHotPaths:
    """Vérifie qu'il n'y a pas de .to_pandas() dans les fichiers hot-path."""

    def test_timeseries_no_to_pandas(self):
        """timeseries.py ne contient pas .to_pandas()."""
        from src.visualization import timeseries

        hits = _source_contains(timeseries, ".to_pandas()")
        assert len(hits) == 0, f"timeseries.py contient .to_pandas(): {hits}"

    def test_timeseries_combat_no_to_pandas(self):
        """timeseries_combat.py ne contient pas .to_pandas()."""
        from src.visualization import timeseries_combat

        hits = _source_contains(timeseries_combat, ".to_pandas()")
        assert len(hits) == 0, f"timeseries_combat.py contient .to_pandas(): {hits}"

    def test_cache_loaders_no_to_pandas(self):
        """cache_loaders.py ne contient pas .to_pandas()."""
        from src.ui import cache_loaders

        hits = _source_contains(cache_loaders, ".to_pandas()")
        assert len(hits) == 0, f"cache_loaders.py contient .to_pandas(): {hits}"

    def test_cache_filters_no_to_pandas_except_bridge(self):
        """cache_filters.py ne contient .to_pandas() que dans le bridge d'intégration."""
        from src.ui import cache_filters

        hits = _source_contains(cache_filters, ".to_pandas()")
        # Le seul usage toléré est dans le bridge load_df_hybrid (from_pandas, pas to_pandas)
        assert len(hits) == 0, f"cache_filters.py contient .to_pandas(): {hits}"


class TestSmartScatterIntegration:
    """Vérifie que smart_scatter est utilisé dans les modules timeseries."""

    def test_timeseries_uses_smart_scatter(self):
        """timeseries.py utilise smart_scatter."""
        from src.visualization import timeseries

        source = inspect.getsource(timeseries)
        assert "smart_scatter" in source

    def test_timeseries_combat_uses_smart_scatter(self):
        """timeseries_combat.py utilise smart_scatter."""
        from src.visualization import timeseries_combat

        source = inspect.getsource(timeseries_combat)
        assert "smart_scatter" in source

    def test_no_direct_go_scatter_in_timeseries(self):
        """timeseries.py n'utilise plus go.Scatter() directement."""
        from src.visualization import timeseries

        source = inspect.getsource(timeseries)
        lines = source.split("\n")
        direct_scatter = [
            (i + 1, line.strip())
            for i, line in enumerate(lines)
            if "go.Scatter(" in line and "smart_scatter" not in line
        ]
        assert (
            len(direct_scatter) == 0
        ), f"go.Scatter() direct trouvé dans timeseries.py: {direct_scatter}"

    def test_no_direct_go_scatter_in_timeseries_combat(self):
        """timeseries_combat.py n'utilise plus go.Scatter() directement."""
        from src.visualization import timeseries_combat

        source = inspect.getsource(timeseries_combat)
        lines = source.split("\n")
        direct_scatter = [
            (i + 1, line.strip())
            for i, line in enumerate(lines)
            if "go.Scatter(" in line and "smart_scatter" not in line
        ]
        assert (
            len(direct_scatter) == 0
        ), f"go.Scatter() direct trouvé dans timeseries_combat.py: {direct_scatter}"


class TestZeroCopyPathAvailable:
    """Vérifie que le chemin zero-copy est exposé et fonctionnel."""

    def test_load_matches_as_polars_exists(self):
        """La méthode load_matches_as_polars existe dans MatchQueriesMixin."""
        from src.data.repositories._match_queries import MatchQueriesMixin

        assert hasattr(MatchQueriesMixin, "load_matches_as_polars")

    def test_load_matches_duckdb_v4_polars_exists(self):
        """_load_matches_duckdb_v4_polars est exposée dans cache_loaders."""
        from src.ui.cache_loaders import _load_matches_duckdb_v4_polars

        assert callable(_load_matches_duckdb_v4_polars)

    def test_enrich_matches_df_exists(self):
        """_enrich_matches_df est exposée dans cache_loaders."""
        from src.ui.cache_loaders import _enrich_matches_df

        assert callable(_enrich_matches_df)
