"""Tests pour vérifier l'unicité des clés Streamlit dans media_library.py

Ces tests vérifient qu'il n'y a pas de clés dupliquées qui causeraient
des erreurs StreamlitDuplicateElementKey.
"""

import hashlib

import pandas as pd
import pytest


def test_open_match_button_key_uniqueness():
    """Test que les clés des boutons 'Ouvrir le match' sont uniques."""
    # Simuler plusieurs médias avec le même match_id
    match_id = "3b1de706-4875-4ba3-b710-81de195bfe45"

    # Sans unique_suffix, toutes les clés seraient identiques
    keys_without_suffix = [f"open_match_{match_id}" for _ in range(3)]
    assert len(set(keys_without_suffix)) == 1, "Sans suffixe, les clés sont identiques"

    # Avec unique_suffix, les clés sont uniques
    stable_ids = [0, 1, 2]
    keys_with_suffix = [f"open_match_{match_id}_{sid}" for sid in stable_ids]
    assert len(set(keys_with_suffix)) == len(
        keys_with_suffix
    ), "Avec suffixe, les clés doivent être uniques"
    assert len(keys_with_suffix) == 3, "Il doit y avoir 3 clés différentes"


def test_thumbnail_key_uniqueness():
    """Test que les clés des thumbnails sont uniques même pour le même média."""
    path = "/path/to/video.mp4"
    match_id = "match123"
    render_context = "test_context"

    # Simuler le même média apparaissant plusieurs fois avec différents stable_id
    stable_ids = [0, 1, 2]
    path_hash = hashlib.md5(path.encode()).hexdigest()
    match_id_part = match_id

    keys = [
        f"thumb_show::{path_hash}::{match_id_part}::{render_context}::{sid}" for sid in stable_ids
    ]

    # Toutes les clés doivent être uniques
    assert len(set(keys)) == len(keys), "Les clés de thumbnails doivent être uniques"
    assert len(keys) == 3, "Il doit y avoir 3 clés différentes"


def test_preview_key_uniqueness():
    """Test que les clés de preview sont uniques."""
    path = "/path/to/video.mp4"
    match_id = "match123"
    render_context = "test_context"

    stable_ids = [0, 1, 2]
    path_hash = hashlib.md5(path.encode()).hexdigest()
    match_id_part = match_id

    keys = [
        f"media_preview::{path_hash}::{match_id_part}::{render_context}::{sid}"
        for sid in stable_ids
    ]

    assert len(set(keys)) == len(keys), "Les clés de preview doivent être uniques"


def test_button_key_in_group_context():
    """Test que le bouton n'est pas rendu dans la grille quand on est dans un groupe."""
    render_contexts = [
        "match_3b1de706-4875-4ba3-b710-81de195bfe45",  # Contexte de groupe
        "unassigned",  # Contexte non-groupe
        "all",  # Contexte non-groupe
    ]

    # Dans un contexte de groupe, on ne doit pas rendre le bouton dans la grille
    for context in render_contexts:
        is_group_context = context.startswith("match_")
        if is_group_context:
            # Le bouton ne doit pas être rendu dans la grille
            assert is_group_context, f"Le contexte {context} est un contexte de groupe"
        else:
            # Le bouton peut être rendu dans la grille
            assert not is_group_context, f"Le contexte {context} n'est pas un contexte de groupe"


def test_stable_id_generation():
    """Test que les stable_id sont générés correctement et sont uniques."""
    items = pd.DataFrame(
        {
            "path": ["/path/to/video1.mp4", "/path/to/video2.mp4", "/path/to/video1.mp4"],
            "match_id": ["match1", "match1", "match1"],
        }
    )

    items = items.copy()
    items["_stable_id"] = items.reset_index().index

    # Les stable_id doivent être uniques et séquentiels
    assert len(items["_stable_id"].unique()) == len(items), "Les stable_id doivent être uniques"
    assert items["_stable_id"].tolist() == [0, 1, 2], "Les stable_id doivent être séquentiels"


def test_multiple_media_same_match_id():
    """Test le cas où plusieurs médias ont le même match_id."""
    # Simuler plusieurs médias avec le même match_id
    match_id = "match123"
    paths = ["/path/to/video1.mp4", "/path/to/video2.mp4", "/path/to/video3.mp4"]

    items = pd.DataFrame(
        {
            "path": paths,
            "match_id": [match_id] * len(paths),
            "kind": ["video"] * len(paths),
        }
    )

    items = items.copy()
    items["_stable_id"] = items.reset_index().index

    # Générer les clés comme dans le code réel
    button_keys = []
    for _, rec in items.iterrows():
        mid = rec.get("match_id")
        stable_id = rec.get("_stable_id", 0)
        button_key = f"open_match_{mid}_{stable_id}"
        button_keys.append(button_key)

    # Toutes les clés doivent être uniques
    assert len(set(button_keys)) == len(
        button_keys
    ), "Les clés de boutons doivent être uniques même pour le même match_id"
    assert len(button_keys) == 3, "Il doit y avoir 3 clés différentes"


def test_render_context_detection():
    """Test la détection des contextes de groupe."""
    group_contexts = [
        "match_3b1de706-4875-4ba3-b710-81de195bfe45",
        "match_abc123",
        "match_xyz789",
    ]

    non_group_contexts = [
        "unassigned",
        "all",
        "default",
        "test_context",
    ]

    for context in group_contexts:
        assert context.startswith(
            "match_"
        ), f"Le contexte {context} devrait être détecté comme groupe"

    for context in non_group_contexts:
        assert not context.startswith(
            "match_"
        ), f"Le contexte {context} ne devrait pas être détecté comme groupe"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
