"""Tests 10C : Persistance complète du cache profil (tous les champs du contrat).

Vérifie que save_cached_appearance → load_cached_appearance est un aller-retour
sans perte pour tous les champs du Spartan ID, y compris adornment_image_url.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.ui.profile_api_cache import (
    ProfileAppearance,
    _cache_path,
    load_cached_appearance,
    save_cached_appearance,
)


@pytest.fixture()
def _clean_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirige le cache profil vers un répertoire temporaire."""
    monkeypatch.setattr(
        "src.ui.profile_api_cache.get_profile_api_cache_dir",
        lambda: tmp_path,
    )
    # Patcher aussi _cache_path pour utiliser le tmp_path
    _ = _cache_path  # référence conservée pour lisibilité

    def patched_cache_path(xuid: str) -> Path:
        safe = "".join(ch for ch in str(xuid or "") if ch.isdigit())
        return tmp_path / f"appearance_{safe}.json"

    monkeypatch.setattr("src.ui.profile_api_cache._cache_path", patched_cache_path)
    return tmp_path


FULL_APPEARANCE = ProfileAppearance(
    service_tag="HERO",
    emblem_image_url="https://example.com/emblem.png",
    backdrop_image_url="https://example.com/backdrop.png",
    nameplate_image_url="https://example.com/nameplate.png",
    rank_label="Héros",
    rank_subtitle="XP 15000/20000",
    rank_image_url="https://gamecms-hacs.svc.halowaypoint.com/hi/images/file/career/rank_272_large.png",
    adornment_image_url="https://gamecms-hacs.svc.halowaypoint.com/hi/images/file/career/rank_272_adornment.png",
)


class TestCacheRoundTrip:
    """Aller-retour complet save → load."""

    def test_all_fields_preserved(self, _clean_cache: Path) -> None:
        """Tous les champs du contrat 10C.1 sont conservés après save/load."""
        xuid = "1234567890"
        save_cached_appearance(xuid, FULL_APPEARANCE)

        loaded = load_cached_appearance(xuid, refresh_hours=24)
        assert loaded is not None

        assert loaded.service_tag == FULL_APPEARANCE.service_tag
        assert loaded.emblem_image_url == FULL_APPEARANCE.emblem_image_url
        assert loaded.backdrop_image_url == FULL_APPEARANCE.backdrop_image_url
        assert loaded.nameplate_image_url == FULL_APPEARANCE.nameplate_image_url
        assert loaded.rank_label == FULL_APPEARANCE.rank_label
        assert loaded.rank_subtitle == FULL_APPEARANCE.rank_subtitle
        assert loaded.rank_image_url == FULL_APPEARANCE.rank_image_url
        assert loaded.adornment_image_url == FULL_APPEARANCE.adornment_image_url

    def test_adornment_image_url_persisted_in_json(self, _clean_cache: Path) -> None:
        """Vérifie que adornment_image_url est physiquement présent dans le JSON."""
        xuid = "9999999999"
        save_cached_appearance(xuid, FULL_APPEARANCE)

        safe = "".join(ch for ch in xuid if ch.isdigit())
        cache_file = _clean_cache / f"appearance_{safe}.json"
        assert cache_file.exists()

        data = json.loads(cache_file.read_text(encoding="utf-8"))
        assert "adornment_image_url" in data
        assert data["adornment_image_url"] == FULL_APPEARANCE.adornment_image_url

    def test_none_fields_handled(self, _clean_cache: Path) -> None:
        """Un ProfileAppearance avec tous les champs None se sauvegarde/charge sans erreur."""
        xuid = "1111111111"
        empty = ProfileAppearance()
        save_cached_appearance(xuid, empty)

        loaded = load_cached_appearance(xuid, refresh_hours=24)
        assert loaded is not None
        assert loaded.adornment_image_url is None
        assert loaded.service_tag is None

    def test_cache_expiry_respected(self, _clean_cache: Path) -> None:
        """Le cache expiré retourne None."""
        xuid = "2222222222"
        save_cached_appearance(xuid, FULL_APPEARANCE)

        # Avec refresh_hours=0, le cache n'est jamais "fresh"
        loaded = load_cached_appearance(xuid, refresh_hours=0)
        assert loaded is None


class TestProfileAppearanceDataclass:
    """Vérifie la structure du contrat Spartan ID (10C.1)."""

    def test_all_contract_fields_exist(self) -> None:
        """Le dataclass contient tous les champs requis par le contrat 10C.1."""
        required_fields = {
            "service_tag",
            "emblem_image_url",
            "nameplate_image_url",
            "backdrop_image_url",
            "rank_label",
            "rank_subtitle",
            "adornment_image_url",
        }
        actual_fields = {f.name for f in ProfileAppearance.__dataclass_fields__.values()}
        missing = required_fields - actual_fields
        assert not missing, f"Champs manquants dans ProfileAppearance: {missing}"

    def test_frozen_dataclass(self) -> None:
        """ProfileAppearance est immutable (frozen)."""
        app = ProfileAppearance(service_tag="TEST")
        with pytest.raises(AttributeError):
            app.service_tag = "CHANGED"  # type: ignore[misc]
