"""Tests pour les labels de médailles (medals_fr.json / medals_en.json).

- Valide le **format** des fichiers JSON (structure, clés numériques, valeurs non vides).
- Valide que les médailles listées dans le fixture ont un label FR/EN (valeurs chargées
  dynamiquement depuis tests/fixtures/medals_new_ids.json).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# Répertoire static/medals (repo root = parent du dossier tests)
REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC_MEDALS_DIR = REPO_ROOT / "static" / "medals"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
MEDALS_NEW_IDS_PATH = FIXTURES_DIR / "medals_new_ids.json"

# Clés acceptées pour un libellé dans une valeur dict (aligné sur src.ui.medals._load)
LABEL_KEYS = ("fr", "name_fr", "nameFr", "label_fr", "labelFr", "label", "name")


def _load_json(path: Path) -> dict | None:
    """Charge un JSON depuis path. Retourne None si fichier absent ou invalide."""
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


def _extract_label_value(val: str | dict) -> str | None:
    """Retourne le libellé extrait (string non vide) ou None."""
    if isinstance(val, str) and val.strip():
        return val.strip()
    if isinstance(val, dict):
        for key in LABEL_KEYS:
            v = val.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return None


def _is_valid_medal_key(key: str) -> bool:
    """True si la clé est une chaîne numérique (ID de médaille)."""
    return isinstance(key, str) and key.isdigit() and len(key) >= 1


class TestMedalsJsonFormat:
    """Validation du format des fichiers medals_fr.json et medals_en.json (sans valeurs en dur)."""

    @pytest.mark.parametrize("filename", ["medals_fr.json", "medals_en.json"])
    def test_file_exists_and_valid_json(self, filename: str) -> None:
        """Le fichier existe et est un JSON valide (objet)."""
        path = STATIC_MEDALS_DIR / filename
        data = _load_json(path)
        assert data is not None, f"{filename} doit exister et être un JSON objet (dict)"
        assert isinstance(data, dict), f"{filename} doit être un objet JSON, pas une liste"

    @pytest.mark.parametrize("filename", ["medals_fr.json", "medals_en.json"])
    def test_all_keys_are_numeric_strings(self, filename: str) -> None:
        """Toutes les clés sont des chaînes numériques (ID médailles)."""
        path = STATIC_MEDALS_DIR / filename
        data = _load_json(path)
        if not data:
            pytest.skip(f"{filename} absent ou invalide")
        for key in data:
            assert _is_valid_medal_key(
                key
            ), f"{filename}: clé '{key}' doit être une chaîne numérique (ex: '1427176344')"

    @pytest.mark.parametrize("filename", ["medals_fr.json", "medals_en.json"])
    def test_all_values_are_non_empty_labels(self, filename: str) -> None:
        """Chaque valeur est soit une chaîne non vide, soit un dict avec un libellé (label/name/fr/...)."""
        path = STATIC_MEDALS_DIR / filename
        data = _load_json(path)
        if not data:
            pytest.skip(f"{filename} absent ou invalide")
        for key, val in data.items():
            label = _extract_label_value(val)
            assert (
                label is not None
            ), f"{filename}: entrée '{key}' doit avoir un libellé non vide (string ou dict avec {LABEL_KEYS})"


class TestNewMedalsLabels:
    """Vérifie que les médailles listées dans le fixture ont un label FR/EN (IDs chargés dynamiquement)."""

    @pytest.fixture(scope="class")
    def expected_new_medal_ids(self) -> list[int]:
        """Charge la liste des IDs attendus depuis le fixture JSON (source unique, pas de valeur en dur)."""
        if not MEDALS_NEW_IDS_PATH.exists():
            pytest.skip(
                f"Fixture absent: {MEDALS_NEW_IDS_PATH}. "
                "Créer un JSON array de strings (IDs médailles) pour activer ces tests."
            )
        with open(MEDALS_NEW_IDS_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        assert isinstance(raw, list), "medals_new_ids.json doit être un tableau de strings (IDs)"
        ids = []
        for item in raw:
            s = str(item).strip()
            assert s.isdigit(), f"ID invalide dans fixture: {item!r}"
            ids.append(int(s))
        return ids

    @pytest.fixture
    def medal_maps(self):
        """Charge les maps FR/EN via le module medals (même logique que l'app)."""
        from src.ui.medals import load_medal_name_maps

        return load_medal_name_maps()

    def test_new_medals_have_known_label(self, expected_new_medal_ids: list[int]) -> None:
        """Chaque ID du fixture a un label connu (FR ou EN)."""
        from src.ui.medals import medal_has_known_label

        for nid in expected_new_medal_ids:
            assert medal_has_known_label(
                nid
            ), f"Médaille {nid} (fixture) doit avoir un label dans medals_fr.json ou medals_en.json"

    def test_new_medals_have_french_label(
        self, expected_new_medal_ids: list[int], medal_maps
    ) -> None:
        """Chaque ID du fixture a un libellé français non vide."""
        fr_map, _en_map = medal_maps
        for nid in expected_new_medal_ids:
            key = str(nid)
            assert (
                key in fr_map
            ), f"Médaille {nid} doit être présente dans medals_fr.json (clé {key})"
            assert fr_map[key].strip(), f"Médaille {nid} ne doit pas avoir un libellé FR vide"

    def test_new_medals_have_english_label(
        self, expected_new_medal_ids: list[int], medal_maps
    ) -> None:
        """Chaque ID du fixture a un libellé anglais non vide."""
        _fr_map, en_map = medal_maps
        for nid in expected_new_medal_ids:
            key = str(nid)
            assert (
                key in en_map
            ), f"Médaille {nid} doit être présente dans medals_en.json (clé {key})"
            assert en_map[key].strip(), f"Médaille {nid} ne doit pas avoir un libellé EN vide"

    def test_new_medals_label_is_not_placeholder(self, expected_new_medal_ids: list[int]) -> None:
        """medal_label() ne renvoie pas le placeholder pour les IDs du fixture."""
        from src.ui.medals import medal_label

        for nid in expected_new_medal_ids:
            label = medal_label(nid)
            placeholder = f"Médaille #{nid}"
            assert (
                label != placeholder
            ), f"Médaille {nid} ne doit pas afficher le placeholder '{placeholder}'"
            assert label.strip(), f"Médaille {nid} doit avoir un libellé non vide"
