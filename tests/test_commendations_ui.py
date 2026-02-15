"""Tests pour le refactoring UI des citations (Sprint 4).

Vérifie que ``render_h5g_commendations_section`` utilise ``CitationEngine``
et ne dépend plus de CUSTOM_CITATION_RULES ni des fichiers tracking JSON.
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# 4.1 — Code obsolète supprimé
# ---------------------------------------------------------------------------


class TestObsoleteCodeRemoved:
    """Vérifie que le code obsolète a bien été supprimé de commendations.py."""

    def test_no_custom_citation_rules(self) -> None:
        """CUSTOM_CITATION_RULES ne doit plus exister dans commendations.py."""
        from src.ui import commendations

        assert not hasattr(
            commendations, "CUSTOM_CITATION_RULES"
        ), "CUSTOM_CITATION_RULES devrait être supprimé"

    def test_no_compute_custom_citation_value(self) -> None:
        """_compute_custom_citation_value ne doit plus exister."""
        from src.ui import commendations

        assert not hasattr(
            commendations, "_compute_custom_citation_value"
        ), "_compute_custom_citation_value devrait être supprimé"

    def test_no_tracking_rules_loader(self) -> None:
        """load_h5g_commendations_tracking_rules ne doit plus exister."""
        from src.ui import commendations

        assert not hasattr(
            commendations, "load_h5g_commendations_tracking_rules"
        ), "load_h5g_commendations_tracking_rules devrait être supprimé"

    def test_no_tracking_constants(self) -> None:
        """Les constantes DEFAULT_H5G_TRACKING_*_PATH ne doivent plus exister."""
        from src.ui import commendations

        assert not hasattr(commendations, "DEFAULT_H5G_TRACKING_ASSUMED_PATH")
        assert not hasattr(commendations, "DEFAULT_H5G_TRACKING_UNMATCHED_PATH")

    def test_no_grep_custom_citation_rules_in_source(self) -> None:
        """Aucune référence à CUSTOM_CITATION_RULES dans le code source src/."""
        src_dir = os.path.join(os.path.dirname(__file__), "..", "src")
        for root, _dirs, files in os.walk(src_dir):
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                fp = os.path.join(root, fn)
                with open(fp, encoding="utf-8") as f:
                    content = f.read()
                assert (
                    "CUSTOM_CITATION_RULES" not in content
                ), f"Référence résiduelle à CUSTOM_CITATION_RULES dans {fp}"


# ---------------------------------------------------------------------------
# 4.2 — Nouvelle signature de render_h5g_commendations_section
# ---------------------------------------------------------------------------


class TestNewSignature:
    """Vérifie que la fonction accepte les nouveaux paramètres."""

    def test_accepts_db_path_xuid(self) -> None:
        """La fonction accepte db_path et xuid comme kwargs."""
        import inspect

        from src.ui.commendations import render_h5g_commendations_section

        sig = inspect.signature(render_h5g_commendations_section)
        param_names = set(sig.parameters.keys())
        assert "db_path" in param_names, "Paramètre db_path manquant"
        assert "xuid" in param_names, "Paramètre xuid manquant"

    def test_accepts_filtered_match_ids(self) -> None:
        """La fonction accepte filtered_match_ids comme kwarg."""
        import inspect

        from src.ui.commendations import render_h5g_commendations_section

        sig = inspect.signature(render_h5g_commendations_section)
        param_names = set(sig.parameters.keys())
        assert "filtered_match_ids" in param_names

    def test_no_old_params(self) -> None:
        """Les anciens paramètres ne doivent plus être dans la signature."""
        import inspect

        from src.ui.commendations import render_h5g_commendations_section

        sig = inspect.signature(render_h5g_commendations_section)
        param_names = set(sig.parameters.keys())
        old_params = {
            "counts_by_medal",
            "stats_totals",
            "counts_by_medal_full",
            "stats_totals_full",
            "df",
            "df_full",
        }
        found = param_names & old_params
        assert not found, f"Anciens paramètres encore présents : {found}"


# ---------------------------------------------------------------------------
# 4.3 — CitationEngine intégré dans l'UI
# ---------------------------------------------------------------------------


class TestCitationEngineIntegration:
    """Vérifie que la fonction utilise CitationEngine."""

    def test_source_imports_engine(self) -> None:
        """Le code source de render_h5g_commendations_section importe CitationEngine."""
        import inspect

        from src.ui.commendations import render_h5g_commendations_section

        source = inspect.getsource(render_h5g_commendations_section)
        assert (
            "CitationEngine" in source
        ), "render_h5g_commendations_section devrait utiliser CitationEngine"

    def test_source_uses_aggregate(self) -> None:
        """Le code utilise aggregate_for_display ou aggregate_citations."""
        import inspect

        from src.ui.commendations import render_h5g_commendations_section

        source = inspect.getsource(render_h5g_commendations_section)
        assert "aggregate_for_display" in source or "aggregate_citations" in source


# ---------------------------------------------------------------------------
# 4.4 — Réduction taille du fichier
# ---------------------------------------------------------------------------


class TestFileSizeReduction:
    """Vérifie que le fichier est bien plus court après le refactoring."""

    def test_commendations_under_650_lines(self) -> None:
        """Le fichier commendations.py devrait être < 650 lignes (était ~950)."""
        fp = os.path.join(os.path.dirname(__file__), "..", "src", "ui", "commendations.py")
        with open(fp, encoding="utf-8") as f:
            lines = len(f.readlines())
        assert lines < 650, f"commendations.py a {lines} lignes (cible < 650)"

    def test_no_iter_rows(self) -> None:
        """Pas d'iter_rows dans commendations.py (source de lenteur)."""
        fp = os.path.join(os.path.dirname(__file__), "..", "src", "ui", "commendations.py")
        with open(fp, encoding="utf-8") as f:
            content = f.read()
        assert (
            "iter_rows" not in content
        ), "iter_rows ne devrait plus être présent (remplacé par agrégation SQL)"
