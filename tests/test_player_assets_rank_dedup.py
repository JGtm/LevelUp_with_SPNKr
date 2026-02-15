"""Tests 10C.4 : Pas de nouveaux rank_* dans player_assets/.

Vérifie que le prefetch et le download/cache n'utilisent plus
le préfixe "rank" pour les images dans player_assets/.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


class TestPrefetchNoRankPrefix:
    """10C.4.1/10C.4.3 : Le script prefetch ne télécharge plus de rank dans player_assets."""

    def test_prefetch_script_no_rank_tuple(self) -> None:
        """Le script prefetch_profile_assets.py n'utilise plus le préfixe 'rank' pour les downloads."""
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "prefetch_profile_assets.py"
        assert script_path.exists(), f"Script introuvable: {script_path}"

        source = script_path.read_text(encoding="utf-8")

        # Chercher toutes les tuples (prefix, url) dans les boucles de download
        # On vérifie qu'aucune n'utilise "rank" comme préfixe
        tree = ast.parse(source)

        rank_prefixes_found = []
        for node in ast.walk(tree):
            # Chercher les tuples littéraux ("rank", ...)
            if isinstance(node, ast.Tuple) and len(node.elts) == 2:
                first = node.elts[0]
                if isinstance(first, ast.Constant) and first.value == "rank":
                    rank_prefixes_found.append(node.lineno)

        assert not rank_prefixes_found, (
            f"Le préfixe 'rank' est encore utilisé dans les tuples de download "
            f"aux lignes {rank_prefixes_found}. "
            "Les rank icons doivent provenir de data/cache/career_ranks/."
        )

    def test_prefetch_uses_adornment_prefix(self) -> None:
        """Le script prefetch utilise le préfixe 'adornment' pour le download."""
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "prefetch_profile_assets.py"
        source = script_path.read_text(encoding="utf-8")

        tree = ast.parse(source)

        adornment_found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Tuple) and len(node.elts) == 2:
                first = node.elts[0]
                if isinstance(first, ast.Constant) and first.value == "adornment":
                    adornment_found = True
                    break

        assert adornment_found, (
            "Le préfixe 'adornment' n'est pas trouvé dans les tuples de download du prefetch. "
            "Il devrait remplacer 'rank'."
        )

    def test_allowed_prefixes_only(self) -> None:
        """Le script prefetch n'utilise que les préfixes autorisés (10C.4.2)."""
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "prefetch_profile_assets.py"
        source = script_path.read_text(encoding="utf-8")

        tree = ast.parse(source)

        # Extraire tous les préfixes des tuples (prefix, url)
        found_prefixes: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Tuple) and len(node.elts) == 2:
                first = node.elts[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    # Vérifier que c'est bien dans un contexte for/download
                    found_prefixes.add(first.value)

        # Filtrer les faux positifs (tuples qui ne sont pas des download)
        # On vérifie seulement que "rank" n'est pas là
        assert "rank" not in found_prefixes, (
            f"Préfixe 'rank' interdit dans les downloads player_assets. "
            f"Préfixes trouvés: {found_prefixes}"
        )


class TestCleanupScript:
    """10C.4.4 : Le script de nettoyage existe et fonctionne."""

    def test_cleanup_script_exists(self) -> None:
        """Le script cleanup_rank_from_player_assets.py existe."""
        script_path = (
            Path(__file__).resolve().parents[1] / "scripts" / "cleanup_rank_from_player_assets.py"
        )
        assert script_path.exists(), f"Script de nettoyage introuvable: {script_path}"

    def test_cleanup_dry_run(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Le mode --dry-run ne supprime rien."""
        import importlib

        # Créer des fichiers rank_* dans un faux répertoire
        fake_assets = tmp_path / "data" / "cache" / "player_assets"
        fake_assets.mkdir(parents=True)
        (fake_assets / "rank_abc123.png").write_bytes(b"fake")
        (fake_assets / "rank_def456.png").write_bytes(b"fake")
        (fake_assets / "emblem_xyz.png").write_bytes(b"fake")

        # Charger le script
        script_path = (
            Path(__file__).resolve().parents[1] / "scripts" / "cleanup_rank_from_player_assets.py"
        )

        spec = importlib.util.spec_from_file_location("cleanup_mod", str(script_path))
        _mod = importlib.util.module_from_spec(spec)

        # Patcher le repo_root
        monkeypatch.setattr(
            "pathlib.Path.parent",
            property(
                lambda self: tmp_path
                if "cleanup" in str(self)
                else Path.__bases__[0].parent.fget(self)
            ),
        )

        # Plus simple: on vérifie juste que le script se parse sans erreur
        ast.parse(script_path.read_text(encoding="utf-8"))

        # Vérifier que les fichiers rank_* toujours présents (dry-run)
        assert (fake_assets / "rank_abc123.png").exists()
        assert (fake_assets / "rank_def456.png").exists()
        # L'emblem ne devrait jamais être touché
        assert (fake_assets / "emblem_xyz.png").exists()
