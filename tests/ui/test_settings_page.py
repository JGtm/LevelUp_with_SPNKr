"""Tests pour la page Paramètres (Sprint 7bis).

Couvre :
- render_settings_page avec MockStreamlit
- Vérification que tous les toggles/expanders sont rendus
- Vérification du retour AppSettings
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestRenderSettingsPage:
    """Tests de la render function render_settings_page."""

    def _setup_mocks(self, ms):
        """Configure les mocks communs pour settings."""

        ms.calls["toggle"].return_value = True
        ms.calls["selectbox"].return_value = "matchmaking"
        ms.calls["number_input"].return_value = 200
        ms.calls["slider"].return_value = 3
        ms.calls["text_input"].return_value = ""
        ms.calls["button"].return_value = False

        # Les colonnes du bas ont un bouton qui doit retourner False
        def _cols(n, *_a, **_kw):
            count = n if isinstance(n, int) else len(n) if isinstance(n, list | tuple) else 2
            cols = [MagicMock(name=f"col_{i}") for i in range(count)]
            for c in cols:
                c.__enter__ = lambda s: s
                c.__exit__ = lambda _s, *_a: None
                c.button = MagicMock(return_value=False)
            return cols

        ms.calls["columns"] = MagicMock(side_effect=_cols)
        ms._monkeypatch.setattr(ms._module.st, "columns", ms.calls["columns"])

    def test_returns_settings(self, mock_st) -> None:
        """La function retourne les settings passés (sans clic Enregistrer)."""
        from src.ui import AppSettings
        from src.ui.pages import settings as mod

        ms = mock_st(mod)
        self._setup_mocks(ms)

        settings = AppSettings()

        with (
            patch.object(mod, "render_source_section"),
            patch.object(mod, "get_default_db_path", return_value="dummy.duckdb"),
            patch.object(mod, "directory_input", return_value=""),
            patch.object(mod, "file_input", return_value=""),
        ):
            result = mod.render_settings_page(
                settings,
                get_local_dbs_fn=lambda: [],
                on_clear_caches_fn=lambda: None,
            )

        assert result is settings  # Pas de modification sans clic

    def test_expanders_rendered(self, mock_st) -> None:
        """Vérifie que les expanders principaux sont créés."""
        from src.ui import AppSettings
        from src.ui.pages import settings as mod

        ms = mock_st(mod)
        self._setup_mocks(ms)

        settings = AppSettings()

        with (
            patch.object(mod, "render_source_section"),
            patch.object(mod, "get_default_db_path", return_value="dummy.duckdb"),
            patch.object(mod, "directory_input", return_value=""),
            patch.object(mod, "file_input", return_value=""),
        ):
            mod.render_settings_page(
                settings,
                get_local_dbs_fn=lambda: [],
                on_clear_caches_fn=lambda: None,
            )

        # Le subheader "Paramètres" est appelé
        ms.calls["subheader"].assert_called_once()
        # Plusieurs expanders sont créés (Source, SPNKr, Médias, etc.)
        assert ms.calls["expander"].call_count >= 4

    def test_toggles_rendered(self, mock_st) -> None:
        """Vérifie que les toggles sont rendus."""
        from src.ui import AppSettings
        from src.ui.pages import settings as mod

        ms = mock_st(mod)
        self._setup_mocks(ms)
        ms.calls["toggle"].return_value = False

        settings = AppSettings()

        with (
            patch.object(mod, "render_source_section"),
            patch.object(mod, "get_default_db_path", return_value="dummy.duckdb"),
            patch.object(mod, "directory_input", return_value=""),
            patch.object(mod, "file_input", return_value=""),
        ):
            mod.render_settings_page(
                settings,
                get_local_dbs_fn=lambda: [],
                on_clear_caches_fn=lambda: None,
            )

        # Au moins 3 toggles sont rendus (SPNKr, Médias, etc.)
        assert ms.calls["toggle"].call_count >= 3

    def test_custom_settings_values(self, mock_st) -> None:
        """Teste avec des settings non-default."""
        from src.ui import AppSettings
        from src.ui.pages import settings as mod

        ms = mock_st(mod)
        self._setup_mocks(ms)
        ms.calls["toggle"].return_value = False
        ms.calls["selectbox"].return_value = "all"
        ms.calls["number_input"].return_value = 500
        ms.calls["slider"].return_value = 10

        settings = AppSettings(
            media_enabled=False,
            media_tolerance_minutes=10,
            spnkr_refresh_max_matches=500,
            spnkr_refresh_rps=5,
        )

        with (
            patch.object(mod, "render_source_section"),
            patch.object(mod, "get_default_db_path", return_value="dummy.duckdb"),
            patch.object(mod, "directory_input", return_value=""),
            patch.object(mod, "file_input", return_value=""),
        ):
            result = mod.render_settings_page(
                settings,
                get_local_dbs_fn=lambda: ["db1.duckdb"],
                on_clear_caches_fn=lambda: None,
            )

        assert result is settings
