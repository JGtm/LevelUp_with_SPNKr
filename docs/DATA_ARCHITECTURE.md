# Architecture de Données Hybride

## Vue d'ensemble

L'architecture de données du projet utilise un pattern "Modern Data Stack Local" combinant :

- **SQLite** : Données chaudes/relationnelles (métadonnées)
- **Parquet** : Données froides/volumineuses (faits)
- **DuckDB** : Moteur de requête OLAP pour les deux

```
┌─────────────────────────────────────────────────────────────────┐
│                        Application UI                           │
│                       (Streamlit)                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Data Repository                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │   Legacy    │  │   Shadow    │  │        Hybrid           │ │
│  │ Repository  │◄─┤ Repository  ├──►   Repository           │ │
│  │ (loaders.py)│  │  (bridge)   │  │(Parquet + DuckDB)      │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
         │                                       │
         ▼                                       ▼
┌─────────────────┐              ┌─────────────────────────────────┐
│     SQLite      │              │         Data Warehouse          │
│   (Legacy DB)   │              │  ┌─────────────────────────────┐│
│                 │              │  │    metadata.db (SQLite)     ││
│  MatchStats     │              │  │  - players                  ││
│  (JSON brut)    │              │  │  - playlists                ││
│                 │              │  │  - sessions                 ││
└─────────────────┘              │  └─────────────────────────────┘│
                                 │  ┌─────────────────────────────┐│
                                 │  │   match_facts/ (Parquet)    ││
                                 │  │   └── player={xuid}/        ││
                                 │  │       └── year=2025/        ││
                                 │  │           └── month=01/     ││
                                 │  └─────────────────────────────┘│
                                 │  ┌─────────────────────────────┐│
                                 │  │     medals/ (Parquet)       ││
                                 │  │   └── player={xuid}/        ││
                                 │  │       └── year=2025/        ││
                                 │  └─────────────────────────────┘│
                                 └─────────────────────────────────┘
```

## Flux de données

### 1. Import des données (API SPNKr → Storage)

```
API SPNKr ──► JSON brut ──► Validation Pydantic ──► Transformation ──┬─► SQLite (métadonnées)
                                                                      └─► Parquet (faits)
```

### 2. Lecture des données (Storage → UI)

```
UI Request ──► DataRepository ──┬─► LegacyRepo ──► SQLite (JSON parsing)
                                │
                                └─► HybridRepo ──► DuckDB ──┬─► SQLite (metadata)
                                                             └─► Parquet (facts)
```

## Structure du Warehouse

```
data/
├── warehouse/
│   ├── metadata.db           # SQLite : métadonnées
│   │
│   ├── match_facts/          # Parquet : faits des matchs
│   │   └── player={xuid}/
│   │       └── year=2025/
│   │           └── month=01/
│   │               └── data.parquet
│   │
│   └── medals/               # Parquet : médailles
│       └── player={xuid}/
│           └── year=2025/
│               └── month=01/
│                   └── data.parquet
│
└── player.db                 # Legacy SQLite (source)
```

## Pattern Shadow Module

Le `ShadowRepository` permet une migration progressive :

```python
# Mode LEGACY (par défaut) : Utilise l'ancien système
repo = get_repository(db_path, xuid, mode=RepositoryMode.LEGACY)

# Mode SHADOW : Lit depuis legacy, écrit en shadow vers hybrid
repo = get_repository(db_path, xuid, mode=RepositoryMode.SHADOW)

# Mode SHADOW_COMPARE : Compare les résultats pour validation
repo = get_repository(db_path, xuid, mode=RepositoryMode.SHADOW_COMPARE)

# Mode HYBRID : Utilise le nouveau système (post-migration)
repo = get_repository(db_path, xuid, mode=RepositoryMode.HYBRID)
```

### Workflow de migration

1. **Phase 1** : `LEGACY` - L'application fonctionne comme avant
2. **Phase 2** : `SHADOW` - Migration progressive en arrière-plan
3. **Phase 3** : `SHADOW_COMPARE` - Validation de la cohérence
4. **Phase 4** : `HYBRID` - Bascule vers le nouveau système

## Performances attendues

| Opération | Legacy (JSON) | Hybrid (Parquet) | Gain |
|-----------|---------------|------------------|------|
| Chargement 10K matchs | ~5s | ~0.3s | 15x |
| Agrégation médailles | ~2s | ~0.1s | 20x |
| Jointure joueurs | ~1s | ~0.05s | 20x |
| Filtrage temporel | ~3s | ~0.2s | 15x |

## Technologies utilisées

- **Pydantic v2** : Validation des données API
- **Polars** : Transformation DataFrame haute performance
- **DuckDB** : Requêtes SQL sur Parquet + SQLite
- **Parquet** : Format de stockage colonaire compressé

## Avantages

1. **Performance** : DuckDB + Parquet = lectures 10-20x plus rapides
2. **Compression** : Parquet compresse ~5x mieux que JSON
3. **Partitionnement** : Lectures sélectives par joueur/date
4. **Évolutivité** : Support de millions de lignes sans dégradation
5. **Migration sûre** : Pattern Shadow pour transition progressive
