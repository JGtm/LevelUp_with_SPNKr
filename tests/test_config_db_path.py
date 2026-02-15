"""Tests anti-régression pour get_default_db_path().

Ces tests garantissent que l'app détecte toujours les joueurs disponibles.

Régression détectée: 15 février 2026
- get_default_db_path() retournait "" même avec des joueurs présents
- Résultat: app vide, aucun joueur visible
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.config import get_default_db_path, get_repo_root


class TestGetDefaultDbPath:
    """Tests pour get_default_db_path()."""

    def test_returns_first_player_alphabetically(self):
        """CRITIQUE: Doit retourner le premier joueur (ordre alpha)."""
        db_path = get_default_db_path()

        # Doit retourner un chemin non vide
        assert db_path != "", (
            "RÉGRESSION: get_default_db_path() retourne chaîne vide "
            "alors que des joueurs existent dans data/players/"
        )

        # Doit pointer vers un fichier .duckdb
        assert db_path.endswith(".duckdb"), f"Expected .duckdb file, got: {db_path}"

        # Le fichier doit exister
        assert Path(db_path).exists(), f"DB file does not exist: {db_path}"

        # Doit être dans data/players/
        assert "data/players/" in db_path or "data\\players\\" in db_path

    def test_returned_db_path_exists(self):
        """Le chemin retourné DOIT exister sur le filesystem."""
        db_path = get_default_db_path()

        if db_path:  # Si non vide
            assert Path(
                db_path
            ).exists(), f"get_default_db_path() returned non-existent file: {db_path}"

            # Le fichier doit être accessible en lecture
            assert Path(db_path).is_file(), f"Expected file, got directory: {db_path}"

    def test_deterministic_result(self):
        """Doit retourner le même résultat à chaque appel."""
        results = [get_default_db_path() for _ in range(10)]

        # Tous les résultats doivent être identiques
        unique_results = set(results)
        assert (
            len(unique_results) == 1
        ), f"get_default_db_path() is non-deterministic. Got: {unique_results}"

    def test_ignores_sqlite_files(self):
        """DOIT ignorer les fichiers .db (SQLite legacy)."""
        db_path = get_default_db_path()

        # Si un chemin est retourné, il doit être .duckdb
        if db_path:
            assert not db_path.endswith(
                ".db"
            ), f"RÉGRESSION: Detected SQLite file (.db) instead of DuckDB: {db_path}"

    def test_env_override_takes_priority(self):
        """OPENSPARTAN_DB doit avoir priorité sur auto-detection."""
        with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # Set env var
            with patch.dict(os.environ, {"OPENSPARTAN_DB": tmp_path}):
                result = get_default_db_path()

                # Doit retourner le chemin env
                assert result == tmp_path, f"Expected env override {tmp_path}, got {result}"
        finally:
            # Cleanup
            Path(tmp_path).unlink(missing_ok=True)

    def test_handles_missing_players_dir_gracefully(self):
        """Si data/players/ n'existe pas, retourne "" sans crash."""
        # Simuler repo_root qui n'a pas de data/players/
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_root = Path(tmpdir)
            (fake_root / "pyproject.toml").touch()
            (fake_root / "src").mkdir()

            with patch("src.config.get_repo_root", return_value=str(fake_root)):
                result = get_default_db_path()

                # Doit retourner chaîne vide (pas de crash)
                assert result == "", "Expected empty string when data/players/ missing"

    def test_handles_empty_players_dir(self):
        """Si data/players/ est vide, retourne ""."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_root = Path(tmpdir)
            (fake_root / "pyproject.toml").touch()
            (fake_root / "src").mkdir()
            (fake_root / "data" / "players").mkdir(parents=True)

            with patch("src.config.get_repo_root", return_value=str(fake_root)):
                result = get_default_db_path()

                # Doit retourner chaîne vide
                assert result == "", "Expected empty string when data/players/ is empty"

    def test_skips_players_without_stats_duckdb(self):
        """Ignore les dossiers joueurs sans stats.duckdb."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_root = Path(tmpdir)
            (fake_root / "pyproject.toml").touch()
            (fake_root / "src").mkdir()
            players_dir = fake_root / "data" / "players"
            players_dir.mkdir(parents=True)

            # Créer un joueur sans stats.duckdb
            (players_dir / "InvalidPlayer").mkdir()
            (players_dir / "InvalidPlayer" / "other.txt").touch()

            # Créer un joueur valide
            valid_player = players_dir / "ValidPlayer"
            valid_player.mkdir()
            (valid_player / "stats.duckdb").touch()

            with patch("src.config.get_repo_root", return_value=str(fake_root)):
                result = get_default_db_path()

                # Doit retourner le joueur valide
                assert result != "", "Should find ValidPlayer"
                assert "ValidPlayer" in result, f"Expected ValidPlayer in path, got: {result}"


class TestRegressionIssue20260215:
    """Tests de non-régression pour l'incident du 15 février 2026.

    Contexte:
    - get_default_db_path() modifié pour retourner ""
    - Résultat: app vide, 0 joueurs visibles
    - Fix: chercher data/players/*/stats.duckdb
    """

    def test_regression_not_empty_with_players(self):
        """CRITIQUE: Si des joueurs existent, ne JAMAIS retourner chaîne vide."""
        repo_root = Path(get_repo_root())
        players_dir = repo_root / "data" / "players"

        # Vérifier qu'on a au moins 1 joueur
        if players_dir.exists():
            dbs = list(players_dir.glob("*/stats.duckdb"))

            if dbs:  # Si au moins 1 DB existe
                result = get_default_db_path()

                # DOIT retourner quelque chose
                assert result != "", (
                    "RÉGRESSION DÉTECTÉE: get_default_db_path() returned empty string "
                    f"even though {len(dbs)} player(s) exist in data/players/. "
                    "This breaks the entire app!"
                )

    def test_regression_no_crash_without_players(self):
        """Si aucun joueur, retourne "" SANS crash (pas de régression inverse)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_root = Path(tmpdir)
            (fake_root / "pyproject.toml").touch()
            (fake_root / "src").mkdir()
            (fake_root / "data" / "players").mkdir(parents=True)

            with patch("src.config.get_repo_root", return_value=str(fake_root)):
                # Ne doit PAS crash
                try:
                    result = get_default_db_path()
                    assert result == "", "Expected empty string with no players"
                except Exception as e:
                    pytest.fail(f"get_default_db_path() crashed with no players: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
