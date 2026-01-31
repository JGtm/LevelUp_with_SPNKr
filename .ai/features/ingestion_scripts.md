# Ingestion Scripts - Scripts d'Import et Migration

## Résumé
Collection de scripts CLI pour l'ingestion, la migration, et la maintenance des données Halo Infinite. Couvre l'import des référentiels JSON vers SQLite, la synchronisation des matchs via SPNKr, et les migrations entre formats de stockage.

## Inputs
- **Fichiers JSON** : Référentiels (playlists, médailles, commendations)
- **API SPNKr** : Matchs, profils, événements
- **Bases SQLite existantes** : Anciennes versions, DB à fusionner

## Outputs
- **SQLite** : `data/warehouse/metadata.db`
- **Parquet** : `data/warehouse/match_facts/`
- **Logs** : Résultats d'opérations

## Dépendances
- **Packages externes** :
  - `pydantic` v2 : Validation des données
  - `duckdb` : Vérification post-ingestion
  - `polars` : Écriture Parquet
  - `spnkr` : Client API Halo
- **Modules internes** :
  - `src.data.domain.models.*` : Modèles Pydantic
  - `src.data.infrastructure.*` : SQLite, Parquet

## Scripts Disponibles

### Ingestion des Référentiels
```bash
# Tout ingérer (playlists + médailles + vérification)
python scripts/ingest_halo_data.py --action all

# Actions individuelles
python scripts/ingest_halo_data.py --action playlists
python scripts/ingest_halo_data.py --action medals
python scripts/ingest_halo_data.py --action verify
python scripts/ingest_halo_data.py --action summary
```

### Authentification SPNKr
```bash
# Obtenir le refresh token initial
python scripts/spnkr_get_refresh_token.py
# → Ouvre navigateur pour auth Xbox Live
# → Génère SPNKR_OAUTH_REFRESH_TOKEN

# Import des matchs depuis l'API
python scripts/spnkr_import_db.py --xuid 1234567890 --limit 100
```

### Migration de Données
```bash
# Migration vers cache centralisé
python scripts/migrate_to_cache.py

# Migration vers format Parquet
python scripts/migrate_to_parquet.py --source db.sqlite --xuid 1234

# Migration des aliases vers DB
python scripts/migrate_aliases_to_db.py
```

### Fusion de Bases
```bash
# Fusionner plusieurs DB SPNKr
python scripts/merge_databases.py db1.sqlite db2.sqlite --output merged.sqlite
```

### Génération de Référentiels
```bash
# Générer le mapping des commendations H5
python scripts/generate_commendations_mapping.py

# Générer les traductions FR des médailles
python scripts/generate_medals_fr.py

# Télécharger les icônes des Career Ranks
python scripts/download_career_rank_icons.py
```

## Logique Métier

### ingest_halo_data.py
```python
class MetadataIngester:
    def __init__(db_path):
        # Crée le schéma SQLite si nécessaire
        
    def ingest_playlists(json_path):
        # 1. Lire Playlist_modes_translations.json
        # 2. Valider avec PlaylistModesData (Pydantic)
        # 3. INSERT OR REPLACE dans playlists, game_modes, categories
        
    def ingest_medals(json_path_fr, json_path_en):
        # 1. Lire medals_fr.json et medals_en.json
        # 2. Valider chaque entrée avec MedalDefinition
        # 3. INSERT OR REPLACE dans medal_definitions
        
    def verify_with_duckdb():
        # 1. Attacher SQLite en mode lecture
        # 2. COUNT(*) sur chaque table
        # 3. Vérifier les fichiers Parquet s'ils existent
```

### Modèles Pydantic utilisés
```python
class PlaylistTranslation(BaseModel):
    uuid: str | None
    en: str
    fr: str

class GameModeTranslation(BaseModel):
    en: str
    fr: str
    category: str

class MedalDefinition(BaseModel):
    name_id: int  # Validé depuis string
    name_fr: str
    name_en: str | None

class PlaylistModesData(BaseModel):
    playlists: list[PlaylistTranslation]
    modes: list[GameModeTranslation]
    categories: dict[str, str]
```

### Résultat d'Ingestion
```python
@dataclass
class IngestionResult:
    success: bool
    table_name: str
    rows_inserted: int
    errors: list[str]
```

## Points d'Attention
- **Idempotence** : `INSERT OR REPLACE` permet de relancer sans erreur
- **Validation stricte** : Pydantic rejette les données invalides
- **Logging** : Chaque étape loggée avec niveau INFO/ERROR
- **Exit codes** : 0 = succès, 1 = erreur (pour CI/CD)
- **Chemins relatifs** : Basés sur `PROJECT_ROOT = Path(__file__).parent.parent`

## Fichiers Clés
| Script | Rôle |
|--------|------|
| `scripts/ingest_halo_data.py` | Ingestion principale |
| `scripts/spnkr_get_refresh_token.py` | Auth OAuth SPNKr |
| `scripts/spnkr_import_db.py` | Import matchs API |
| `scripts/sync.py` | Synchronisation complète |
| `scripts/merge_databases.py` | Fusion de DB |
| `scripts/migrate_to_parquet.py` | Migration Parquet |
| `scripts/generate_medals_fr.py` | Génération traductions |
