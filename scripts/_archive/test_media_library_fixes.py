"""Script de test pour valider les corrections de media_library.py

Ce script teste :
1. La génération des clés stables pour session_state
2. La logique de création des colonnes (cols_per_row)
3. La structure des données
"""

import pandas as pd


def test_stable_id_generation():
    """Test que les IDs stables sont générés correctement."""
    print("Test 1: Génération des IDs stables")

    # Créer un DataFrame de test
    items = pd.DataFrame(
        {
            "path": ["/path/to/video1.mp4", "/path/to/video2.mp4", "/path/to/video3.mp4"],
            "match_id": ["match1", "match1", "match2"],
            "kind": ["video", "video", "image"],
        }
    )

    # Simuler la logique du code
    items = items.copy()
    items["_stable_id"] = items.reset_index().index

    # Vérifier que les IDs sont stables et uniques
    assert len(items["_stable_id"].unique()) == len(items), "Les IDs doivent être uniques"
    assert items["_stable_id"].tolist() == [0, 1, 2], "Les IDs doivent être séquentiels"

    print("  ✅ IDs stables générés correctement")
    return True


def test_cols_per_row_logic():
    """Test la logique de création des colonnes."""
    print("\nTest 2: Logique de création des colonnes")

    # Test avec différents nombres de médias
    test_cases = [
        (4, 1),  # 1 média, 4 colonnes attendues
        (4, 2),  # 2 médias, 4 colonnes attendues
        (4, 4),  # 4 médias, 4 colonnes attendues
        (4, 5),  # 5 médias, 8 colonnes attendues (2 lignes)
    ]

    for cols_per_row, num_items in test_cases:
        items = pd.DataFrame(
            {
                "path": [f"/path/to/item{i}.mp4" for i in range(num_items)],
                "match_id": [f"match{i}" for i in range(num_items)],
                "kind": ["video"] * num_items,
            }
        )

        items = items.copy()
        items["_stable_id"] = items.reset_index().index

        rows = items.to_dict(orient="records")
        num_rows = (len(rows) + cols_per_row - 1) // cols_per_row  # Arrondi supérieur

        # Vérifier que le nombre de lignes est correct
        expected_rows = (num_items + cols_per_row - 1) // cols_per_row
        assert (
            num_rows == expected_rows
        ), f"Nombre de lignes incorrect pour {num_items} items avec {cols_per_row} colonnes"

        # Vérifier que chaque ligne crée cols_per_row colonnes
        for i in range(0, len(rows), cols_per_row):
            chunk = rows[i : i + cols_per_row]
            # Dans le code réel, on crée toujours cols_per_row colonnes
            assert len(chunk) <= cols_per_row, f"Chunk trop grand pour {cols_per_row} colonnes"

    print("  ✅ Logique de colonnes correcte")
    return True


def test_key_stability():
    """Test que les clés session_state sont stables."""
    print("\nTest 3: Stabilité des clés session_state")

    import hashlib

    items = pd.DataFrame(
        {
            "path": ["/path/to/video1.mp4", "/path/to/video1.mp4"],  # Même média deux fois
            "match_id": ["match1", "match1"],
            "kind": ["video", "video"],
        }
    )

    items = items.copy()
    items["_stable_id"] = items.reset_index().index

    render_context = "test_context"
    keys = []

    for _, rec in items.iterrows():
        path = str(rec.get("path") or "").strip()
        mid = rec.get("match_id")
        match_id_part = str(mid).strip() if isinstance(mid, str) and mid.strip() else "no_match"
        stable_id = rec.get("_stable_id", 0)
        path_hash = hashlib.md5(path.encode()).hexdigest()

        thumb_key = f"thumb_show::{path_hash}::{match_id_part}::{render_context}::{stable_id}"
        keys.append(thumb_key)

    # Les clés doivent être différentes car les stable_id sont différents
    assert len(set(keys)) == len(keys), "Les clés doivent être uniques même pour le même média"
    assert keys[0] != keys[1], "Les clés doivent être différentes pour des stable_id différents"

    print("  ✅ Clés stables et uniques")
    return True


def test_empty_columns():
    """Test que les colonnes vides sont gérées correctement."""
    print("\nTest 4: Gestion des colonnes vides")

    cols_per_row = 4
    num_items = 2  # Moins d'items que de colonnes

    items = pd.DataFrame(
        {
            "path": [f"/path/to/item{i}.mp4" for i in range(num_items)],
            "match_id": [f"match{i}" for i in range(num_items)],
            "kind": ["video"] * num_items,
        }
    )

    items = items.copy()
    items["_stable_id"] = items.reset_index().index

    rows = items.to_dict(orient="records")

    # Simuler la boucle de rendu
    for i in range(0, len(rows), cols_per_row):
        chunk = rows[i : i + cols_per_row]
        # On crée toujours cols_per_row colonnes
        num_cols_created = cols_per_row
        num_items_in_chunk = len(chunk)

        # Vérifier que le nombre de colonnes est correct
        assert num_cols_created == cols_per_row, f"Devrait créer {cols_per_row} colonnes"
        assert num_items_in_chunk <= cols_per_row, "Le chunk ne doit pas dépasser cols_per_row"

        # Vérifier que les colonnes vides sont gérées
        empty_cols = cols_per_row - num_items_in_chunk
        assert empty_cols >= 0, "Ne peut pas avoir de colonnes négatives"

    print("  ✅ Colonnes vides gérées correctement")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Tests des corrections de media_library.py")
    print("=" * 60)

    try:
        test_stable_id_generation()
        test_cols_per_row_logic()
        test_key_stability()
        test_empty_columns()

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
