# Exécution de la correction des métadonnées NULL

## Option 1 : Depuis Streamlit (RECOMMANDÉ)

1. Ouvrez Streamlit : `streamlit run streamlit_app.py`
2. Dans la console Python de Streamlit, exécutez :

```python
import duckdb
from pathlib import Path

base_path = Path(".")

# Pour JGtm
jgtm_db = base_path / "data" / "players" / "JGtm" / "stats.duckdb"
if jgtm_db.exists():
    conn = duckdb.connect(str(jgtm_db), read_only=False)
    conn.execute("""
        UPDATE match_stats
        SET 
            map_name = COALESCE(map_name, map_id),
            playlist_name = COALESCE(playlist_name, playlist_id),
            pair_name = COALESCE(pair_name, pair_id),
            game_variant_name = COALESCE(game_variant_name, game_variant_id)
        WHERE map_name IS NULL 
           OR playlist_name IS NULL 
           OR pair_name IS NULL 
           OR game_variant_name IS NULL
    """)
    conn.commit()
    conn.close()
    print("✅ JGtm corrigé")

# Pour Chocoboflor
choco_db = base_path / "data" / "players" / "Chocoboflor" / "stats.duckdb"
if choco_db.exists():
    conn = duckdb.connect(str(choco_db), read_only=False)
    conn.execute("""
        UPDATE match_stats
        SET 
            map_name = COALESCE(map_name, map_id),
            playlist_name = COALESCE(playlist_name, playlist_id),
            pair_name = COALESCE(pair_name, pair_id),
            game_variant_name = COALESCE(game_variant_name, game_variant_id)
        WHERE match_id = '410f1c01-aca6-4567-9df5-9b16bd550cb2'
           OR map_name IS NULL 
           OR playlist_name IS NULL 
           OR pair_name IS NULL 
           OR game_variant_name IS NULL
    """)
    conn.commit()
    conn.close()
    print("✅ Chocoboflor corrigé")
```

## Option 2 : Depuis un terminal Python avec DuckDB

Si vous avez un environnement Python avec DuckDB installé :

```bash
python -c "
import duckdb

# JGtm
conn = duckdb.connect('data/players/JGtm/stats.duckdb', read_only=False)
conn.execute('UPDATE match_stats SET map_name = COALESCE(map_name, map_id), playlist_name = COALESCE(playlist_name, playlist_id), pair_name = COALESCE(pair_name, pair_id), game_variant_name = COALESCE(game_variant_name, game_variant_id) WHERE map_name IS NULL OR playlist_name IS NULL OR pair_name IS NULL OR game_variant_name IS NULL')
conn.commit()
conn.close()
print('✅ JGtm corrigé')

# Chocoboflor
conn = duckdb.connect('data/players/Chocoboflor/stats.duckdb', read_only=False)
conn.execute('UPDATE match_stats SET map_name = COALESCE(map_name, map_id), playlist_name = COALESCE(playlist_name, playlist_id), pair_name = COALESCE(pair_name, pair_id), game_variant_name = COALESCE(game_variant_name, game_variant_id) WHERE match_id = \\'410f1c01-aca6-4567-9df5-9b16bd550cb2\\' OR map_name IS NULL OR playlist_name IS NULL OR pair_name IS NULL OR game_variant_name IS NULL')
conn.commit()
conn.close()
print('✅ Chocoboflor corrigé')
"
```

## Option 3 : Via un script Python dédié

Créez un fichier `fix_now.py` avec le contenu de `scripts/fix_null_metadata_streamlit.py` et exécutez-le depuis un environnement qui a DuckDB.
