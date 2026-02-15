# Guide de Migration Refdata

> Sprint 8 - Migration des tables `killer_victim_pairs` et `personal_score_awards`

## Vue d'ensemble

Cette migration ajoute deux nouvelles tables à la base de données joueur pour stocker :

1. **`killer_victim_pairs`** : Paires killer→victim calculées depuis les highlight events
2. **`personal_score_awards`** : Décomposition du score personnel (future implémentation)

Ces tables permettent des requêtes rapides pour :
- Calculer le némésis (qui m'a le plus tué)
- Calculer le souffre-douleur (qui j'ai le plus tué)
- Analyser la contribution aux objectifs

---

## Prérequis

- Python 3.10+
- DuckDB 0.10.0+
- Base de données joueur existante (`data/players/{gamertag}/stats.duckdb`)

---

## Étapes de migration

### 1. Migrer le schéma (colonnes manquantes)

Ajoute la colonne `game_variant_category` à `match_stats` :

```bash
# Un joueur spécifique
python scripts/migrate_game_variant_category.py --gamertag MonGamertag

# Tous les joueurs
python scripts/migrate_game_variant_category.py --all

# Dry-run (simulation)
python scripts/migrate_game_variant_category.py --all --dry-run
```

### 2. Backfill des paires killer→victim

Calcule et insère les paires depuis les `highlight_events` existants :

```bash
# Un joueur spécifique
python scripts/backfill_killer_victim_pairs.py --gamertag MonGamertag

# Tous les joueurs
python scripts/backfill_killer_victim_pairs.py --all

# Dry-run (simulation)
python scripts/backfill_killer_victim_pairs.py --gamertag MonGT --dry-run

# Forcer le retraitement (même si déjà fait)
python scripts/backfill_killer_victim_pairs.py --all --force
```

**Options disponibles :**

| Option | Description |
|--------|-------------|
| `--gamertag`, `-g` | Gamertag du joueur |
| `--all`, `-a` | Traiter tous les joueurs |
| `--db-path`, `-d` | Chemin direct vers stats.duckdb |
| `--tolerance-ms` | Tolérance jointure kill/death (défaut: 5ms) |
| `--dry-run` | Simulation sans modification |
| `--force`, `-f` | Retraiter tous les matchs |
| `--verbose`, `-v` | Mode verbeux |

### 3. Valider l'intégrité

Vérifie que la migration s'est bien passée :

```bash
# Un joueur spécifique
python scripts/validate_refdata_integrity.py --gamertag MonGamertag

# Tous les joueurs
python scripts/validate_refdata_integrity.py --all

# Rapport JSON détaillé
python scripts/validate_refdata_integrity.py --all --json --output validation_report.json
```

---

## Schéma des nouvelles tables

### Table `killer_victim_pairs`

```sql
CREATE TABLE killer_victim_pairs (
    id INTEGER PRIMARY KEY,
    match_id VARCHAR NOT NULL,
    killer_xuid VARCHAR NOT NULL,
    killer_gamertag VARCHAR,
    victim_xuid VARCHAR NOT NULL,
    victim_gamertag VARCHAR,
    kill_count INTEGER DEFAULT 1,
    time_ms INTEGER,
    is_validated BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index pour les requêtes
CREATE INDEX idx_kv_match ON killer_victim_pairs(match_id);
CREATE INDEX idx_kv_killer ON killer_victim_pairs(killer_xuid);
CREATE INDEX idx_kv_victim ON killer_victim_pairs(victim_xuid);
```

### Table `personal_score_awards`

```sql
CREATE TABLE personal_score_awards (
    id INTEGER PRIMARY KEY,
    match_id VARCHAR NOT NULL,
    xuid VARCHAR NOT NULL,
    award_name VARCHAR NOT NULL,
    award_category VARCHAR,
    award_count INTEGER DEFAULT 1,
    award_score INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index pour les requêtes
CREATE INDEX idx_psa_match ON personal_score_awards(match_id);
CREATE INDEX idx_psa_xuid ON personal_score_awards(xuid);
CREATE INDEX idx_psa_category ON personal_score_awards(award_category);
```

---

## Requêtes d'exemple

### Top némésis (qui m'a le plus tué)

```sql
SELECT
    killer_xuid,
    killer_gamertag,
    SUM(kill_count) as times_killed_by
FROM killer_victim_pairs
WHERE victim_xuid = 'mon_xuid'
GROUP BY killer_xuid, killer_gamertag
ORDER BY times_killed_by DESC
LIMIT 10;
```

### Top victimes (qui j'ai le plus tué)

```sql
SELECT
    victim_xuid,
    victim_gamertag,
    SUM(kill_count) as times_killed
FROM killer_victim_pairs
WHERE killer_xuid = 'mon_xuid'
GROUP BY victim_xuid, victim_gamertag
ORDER BY times_killed DESC
LIMIT 10;
```

### Historique d'un duel

```sql
SELECT
    match_id,
    SUM(CASE WHEN killer_xuid = 'mon_xuid' THEN kill_count ELSE 0 END) as my_kills,
    SUM(CASE WHEN victim_xuid = 'mon_xuid' THEN kill_count ELSE 0 END) as their_kills
FROM killer_victim_pairs
WHERE (killer_xuid = 'mon_xuid' AND victim_xuid = 'adversaire_xuid')
   OR (killer_xuid = 'adversaire_xuid' AND victim_xuid = 'mon_xuid')
GROUP BY match_id;
```

---

## Utilisation avec Polars

Les données peuvent être chargées en DataFrame Polars pour analyse :

```python
from src.data.repositories.duckdb_repo import DuckDBRepository

# Charger le repository
repo = DuckDBRepository(
    "data/players/MonGT/stats.duckdb",
    xuid="123456789",
)

# Charger les paires en Polars
pairs_df = repo.load_killer_victim_pairs_as_polars()

# Utiliser les fonctions d'analyse Sprint 3
from src.analysis.killer_victim import (
    compute_personal_antagonists_from_pairs_polars,
)

result = compute_personal_antagonists_from_pairs_polars(pairs_df, me_xuid="123456789")
print(f"Némésis: {result.nemesis_gamertag} ({result.nemesis_times_killed_by} kills)")
print(f"Victime: {result.victim_gamertag} ({result.victim_times_killed} kills)")
```

---

## Dépannage

### Erreur "Table non trouvée"

Exécutez d'abord la synchronisation pour créer les tables :

```bash
python scripts/sync.py --gamertag MonGT --delta
```

### Couverture incomplète

Si le rapport indique une couverture < 100%, certains matchs n'ont pas d'events.
Cela peut arriver si :
- Les events n'ont pas été téléchargés lors de la sync
- L'API n'a pas retourné d'events pour certains matchs

Relancez une sync avec `--with-events` :

```bash
python scripts/sync.py --gamertag MonGT --full --with-events
```

### Performance lente

Pour les grandes bases (>5000 matchs), le backfill peut prendre plusieurs minutes.
Surveillez la progression avec `--verbose`.

---

## Rollback

Pour supprimer les données de migration :

```sql
-- Supprimer les paires
DROP TABLE IF EXISTS killer_victim_pairs;

-- Supprimer les awards
DROP TABLE IF EXISTS personal_score_awards;

-- Supprimer la colonne game_variant_category (si nécessaire)
-- Note: DuckDB ne supporte pas DROP COLUMN directement
-- Recréez la table sans cette colonne si besoin
```

---

## Références

- [Plan d'implémentation combiné](../.ai/features/COMBINED_IMPLEMENTATION_PLAN.md)
- [Documentation SQL Schema](SQL_SCHEMA.md)
- [Analyse killer_victim.py](../src/analysis/killer_victim.py)

---

*Dernière mise à jour : Sprint 8 (2026-02-03)*
