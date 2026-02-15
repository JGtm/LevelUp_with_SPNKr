# Guide Backup & Restore

> Documentation pour la sauvegarde et restauration des données joueur.

## Vue d'ensemble

OpenSpartan Graph stocke les données des joueurs dans des fichiers DuckDB (`stats.duckdb`).
Ces scripts permettent d'exporter et restaurer ces données au format Parquet avec compression Zstd.

### Avantages du format Parquet + Zstd

| Aspect | Avantage |
|--------|----------|
| Portabilité | Format standard, lisible par Python, R, Spark, etc. |
| Compression | Zstd offre un ratio ~3x meilleur que gzip |
| Vitesse | Import/export natif DuckDB, ultra-rapide |
| Intégrité | Format colonnaire avec checksums intégrés |
| Archivage | Idéal pour cold storage longue durée |

---

## Script de Backup

### Usage basique

```bash
# Sauvegarder un joueur
python scripts/backup_player.py --gamertag Chocoboflor

# Sauvegarder tous les joueurs
python scripts/backup_player.py --all

# Lister les joueurs disponibles
python scripts/backup_player.py --list
```

### Options avancées

```bash
# Spécifier un répertoire de sortie
python scripts/backup_player.py --gamertag JGtm --output ./mes_backups

# Ajuster le niveau de compression (1-22)
python scripts/backup_player.py --gamertag JGtm --compression-level 15

# Sans métadonnées JSON
python scripts/backup_player.py --gamertag JGtm --no-metadata
```

### Niveaux de compression Zstd

| Niveau | Usage | Vitesse | Compression |
|--------|-------|---------|-------------|
| 1-3 | Backups rapides | Très rapide | Faible |
| 6-9 | **Recommandé (défaut: 9)** | Équilibré | Bon |
| 15-19 | Archivage longue durée | Lent | Élevée |
| 20-22 | Compression maximale | Très lent | Maximale |

### Structure de sortie

```
data/backups/
└── Chocoboflor/
    ├── match_stats_20260201_143025.parquet
    ├── medals_earned_20260201_143025.parquet
    ├── teammates_aggregate_20260201_143025.parquet
    ├── antagonists_20260201_143025.parquet
    ├── mv_map_stats_20260201_143025.parquet
    ├── mv_mode_category_stats_20260201_143025.parquet
    ├── mv_global_stats_20260201_143025.parquet
    └── backup_metadata_20260201_143025.json
```

### Fichier de métadonnées

Le fichier `backup_metadata_*.json` contient :

```json
{
  "gamertag": "Chocoboflor",
  "backup_timestamp": "20260201_143025",
  "backup_datetime": "2026-02-01T14:30:25.123456",
  "source_db": "data/players/Chocoboflor/stats.duckdb",
  "compression": "zstd",
  "compression_level": 9,
  "tables": {
    "match_stats": {
      "rows": 1500,
      "file_size_bytes": 2500000,
      "file": "match_stats_20260201_143025.parquet"
    }
  },
  "total_size_bytes": 5000000,
  "total_size_mb": 4.77
}
```

---

## Script de Restore

### Usage basique

```bash
# Restaurer un joueur
python scripts/restore_player.py --gamertag Chocoboflor --backup ./data/backups/Chocoboflor

# Simuler sans écrire (dry-run)
python scripts/restore_player.py --gamertag Chocoboflor --backup ./data/backups/Chocoboflor --dry-run

# Lister les tables dans un backup
python scripts/restore_player.py --gamertag Chocoboflor --backup ./data/backups/Chocoboflor --list
```

### Options avancées

```bash
# Restaurer des tables spécifiques seulement
python scripts/restore_player.py --gamertag JGtm --backup ./backups/JGtm \
    --tables match_stats,medals_earned

# Remplacer les données existantes (au lieu d'ajouter)
python scripts/restore_player.py --gamertag JGtm --backup ./backups/JGtm --replace
```

### Comportement par défaut

| Option | Comportement |
|--------|--------------|
| Sans `--replace` | Ajoute les données (peut créer des doublons) |
| Avec `--replace` | Supprime la table existante avant import |
| Avec `--dry-run` | Simule sans modifier les données |

---

## Cas d'usage

### Migration vers une nouvelle machine

```bash
# Sur l'ancienne machine
python scripts/backup_player.py --all --output ./export

# Copier le dossier export vers la nouvelle machine
# Sur la nouvelle machine
python scripts/restore_player.py --gamertag Chocoboflor --backup ./export/Chocoboflor --replace
```

### Archivage mensuel automatisé

```bash
#!/bin/bash
# Script cron mensuel
DATE=$(date +%Y%m)
python scripts/backup_player.py --all --output "/archives/halo/$DATE" --compression-level 15
```

### Récupération après corruption

```bash
# Vérifier le contenu du backup
python scripts/restore_player.py --gamertag Chocoboflor --backup ./backups/Chocoboflor --list

# Restaurer avec remplacement
python scripts/restore_player.py --gamertag Chocoboflor --backup ./backups/Chocoboflor --replace
```

---

## Lecture directe des fichiers Parquet

Les fichiers Parquet peuvent être lus directement sans restauration :

### Python + DuckDB

```python
import duckdb

# Lire un fichier Parquet
df = duckdb.read_parquet("backup/match_stats_20260201_143025.parquet")
print(df.df())  # Convertir en pandas DataFrame
```

### Python + Polars

```python
import polars as pl

df = pl.read_parquet("backup/match_stats_20260201_143025.parquet")
print(df.head())
```

### Python + Pandas

```python
import pandas as pd

df = pd.read_parquet("backup/match_stats_20260201_143025.parquet")
print(df.head())
```

---

## Bonnes pratiques

### Fréquence de backup

| Fréquence | Cas d'usage |
|-----------|-------------|
| Hebdomadaire | Joueurs actifs, données critiques |
| Mensuelle | Usage normal |
| Avant migration | Toujours faire un backup complet |

### Stockage des backups

- **Local** : Facile, rapide, mais risque de perte en cas de panne disque
- **Cloud** : Recommandé pour les backups critiques (S3, GCS, Azure Blob)
- **NAS/Disque externe** : Bon compromis coût/sécurité

### Vérification des backups

```bash
# Vérifier qu'un backup est lisible
python scripts/restore_player.py --gamertag Chocoboflor --backup ./backups/Chocoboflor --list

# Simuler une restauration
python scripts/restore_player.py --gamertag Chocoboflor --backup ./backups/Chocoboflor --dry-run
```

---

## Dépannage

### Erreur "DB non trouvée"

```
Backup non trouvé: DB non trouvée pour JGtm
```

**Solution** : Vérifiez que le joueur existe dans `data/players/{gamertag}/stats.duckdb`.

### Erreur de permission

```
PermissionError: [Errno 13] Permission denied
```

**Solution** : Vérifiez les permissions du répertoire de sortie ou exécutez avec `sudo`.

### Fichiers Parquet corrompus

DuckDB vérifie automatiquement l'intégrité des fichiers Parquet via les checksums intégrés.
Si une erreur de lecture survient, le fichier est probablement corrompu.

**Solution** : Restaurez depuis un backup antérieur.

---

*Dernière mise à jour : 2026-02-01*
