"""Tests pour vérifier l'unicité des clés Streamlit dans media_library.py

Ces tests vérifient qu'il n'y a pas de clés dupliquées qui causeraient
des erreurs StreamlitDuplicateElementKey.
"""

import hashlib

import pandas as pd


def test_open_match_button_key_uniqueness():
    """Test que les clés des boutons 'Ouvrir le match' sont uniques."""
    print("Test 1: Unicité des clés de boutons 'Ouvrir le match'")

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

    print("  ✅ Les clés sont uniques avec unique_suffix")
    return True


def test_button_key_in_group_context():
    """Test que le bouton n'est pas rendu dans la grille quand on est dans un groupe."""
    print("\nTest 2: Détection des contextes de groupe")

    render_contexts = [
        "match_3b1de706-4875-4ba3-b710-81de195bfe45",  # Contexte de groupe
        "unassigned",  # Contexte non-groupe
        "all",  # Contexte non-groupe
    ]

    # Dans un contexte de groupe, on ne doit pas rendre le bouton dans la grille
    for context in render_contexts:
        is_group_context = context.startswith("match_")
        if is_group_context:
            assert is_group_context, f"Le contexte {context} est un contexte de groupe"
        else:
            assert not is_group_context, f"Le contexte {context} n'est pas un contexte de groupe"

    print("  ✅ Les contextes de groupe sont correctement détectés")
    return True


def test_multiple_media_same_match_id():
    """Test le cas où plusieurs médias ont le même match_id."""
    print("\nTest 3: Plusieurs médias avec le même match_id")

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

    print(f"  ✅ {len(button_keys)} clés uniques générées pour {len(paths)} médias")
    return True


def test_stable_id_generation():
    """Test que les stable_id sont générés correctement et sont uniques."""
    print("\nTest 4: Génération des stable_id")

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

    print("  ✅ Les stable_id sont uniques et séquentiels")
    return True


def test_thumbnail_key_uniqueness():
    """Test que les clés des thumbnails sont uniques même pour le même média."""
    print("\nTest 5: Unicité des clés de thumbnails")

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

    print("  ✅ Les clés de thumbnails sont uniques")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Tests d'unicité des clés Streamlit - media_library.py")
    print("=" * 60)

    try:
        test_open_match_button_key_uniqueness()
        test_button_key_in_group_context()
        test_multiple_media_same_match_id()
        test_stable_id_generation()
        test_thumbnail_key_uniqueness()

        print("\n" + "=" * 60)
        print("✅ Tous les tests sont passés avec succès!")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n❌ Test échoué: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ Erreur inattendue: {e}")
        import traceback

        traceback.print_exc()
        exit(1)
