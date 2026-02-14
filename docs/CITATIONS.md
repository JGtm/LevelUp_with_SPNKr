# Citations — Architecture & Guide

> Système de citations DuckDB-first pour LevelUp.

## Architecture

### Tables

| Table | Base | Description |
|-------|------|-------------|
| `citation_mappings` | `metadata.duckdb` | Règles de mapping (14 citations) |
| `match_citations` | `stats.duckdb` (par joueur) | Valeurs calculées par match |

### Schéma `citation_mappings`

```sql
CREATE TABLE citation_mappings (
    citation_name_norm   TEXT PRIMARY KEY,   -- ex: "pilote"
    citation_name_display TEXT NOT NULL,      -- ex: "Pilote"
    mapping_type         TEXT NOT NULL,       -- medal | stat | award | custom
    medal_id             BIGINT,             -- ID médaille (type medal)
    medal_ids            TEXT,               -- IDs multiples (réservé)
    stat_name            TEXT,               -- Nom colonne stats (type stat)
    award_name           TEXT,               -- Nom award (type award)
    award_category       TEXT,               -- Catégorie award
    custom_function      TEXT,               -- Nom fonction (type custom)
    confidence           TEXT,               -- high | medium | low
    notes                TEXT,
    enabled              BOOLEAN DEFAULT TRUE, -- FALSE = citation désactivée
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

> **Note** : La colonne `enabled` remplace le fichier JSON d'exclusion
> (`halo5_commendations_exclude.json`). `load_mappings()` filtre
> `WHERE enabled IS NOT FALSE`.

### Compatibilité V5 (Shared Matches)

`CitationEngine` supporte la lecture depuis `shared_matches.duckdb` :

- **`shared_db_path`** : auto-détecté (`data/warehouse/shared_matches.duckdb`)
- **`load_match_medals()`** : lit `shared.medals_earned` (filtré par xuid) si disponible
- **`load_match_stats()`** / **`load_match_df()`** : lit `shared.match_participants` + `shared.match_registry`
- **`load_match_awards()`** : reste local (`personal_score_awards`)
- **Fallback V4** : si la shared DB n'existe pas, lit depuis les tables locales

### Schéma `match_citations`

```sql
CREATE TABLE match_citations (
    match_id           TEXT NOT NULL,
    citation_name_norm TEXT NOT NULL,
    value              INTEGER NOT NULL,
    PRIMARY KEY (match_id, citation_name_norm)
);
CREATE INDEX idx_match_citations_name ON match_citations(citation_name_norm);
```

## Les 14 Citations

| Nom normalisé | Type | Source | Origine |
|---------------|------|--------|---------|
| `pilote` | medal | ID 3169118333 | existante |
| `ecrasement` | medal | ID 221693153 | existante |
| `assistant` | stat | `assists` | existante |
| `bulldozer` | custom | `compute_bulldozer` | existante |
| `victoire au drapeau` | custom | `compute_wins_ctf` | existante |
| `seul contre tous` | custom | `compute_wins_firefight` | existante |
| `victoire en assassin` | custom | `compute_wins_slayer` | existante |
| `victoire en bases` | custom | `compute_wins_strongholds` | existante |
| `defenseur du drapeau` | award | `Flag Defense` | réintégrée |
| `je te tiens` | award | `Flag Return` | réintégrée |
| `sus au porteur du drapeau` | award | `Flag Carrier Kill` | réintégrée |
| `partie prenante` | award | `Zone Defense` | réintégrée |
| `a la charge` | award | `Zone Capture` | réintégrée |
| `annexion forcee` | custom | `compute_annexion_forcee` | réintégrée |

## Flux de données

```
Sync match → backfill_citations() → CitationEngine.compute_and_store_for_match()
                                          ↓
                               match_citations (INSERT OR REPLACE)
                                          ↓
                               CitationEngine.aggregate_for_display()
                                          ↓
                               render_h5g_commendations_section() → UI
```

## Backfill CLI

```bash
# Backfill citations pour un joueur (incrémental)
python scripts/backfill_data.py --player MonGT --citations

# Forcer le recalcul complet
python scripts/backfill_data.py --player MonGT --citations --force-citations

# Tous les joueurs
python scripts/backfill_data.py --all --citations
```

## Ajouter une nouvelle citation

1. **Définir la règle** dans `scripts/create_citation_mappings_table.py` :
   - Type `medal` : fournir `medal_id` (BIGINT)
   - Type `stat` : fournir `stat_name` (colonne de `match_stats`)
   - Type `award` : fournir `award_name` (valeur de `personal_score_awards.award_name`)
   - Type `custom` : fournir `custom_function` (nom dans `CUSTOM_FUNCTIONS`)

2. **Si type `custom`** : implémenter la fonction dans `src/analysis/citations/custom_rules.py`
   et l'ajouter au registre `CUSTOM_FUNCTIONS`.

3. **Exécuter le script** :
   ```bash
   python scripts/create_citation_mappings_table.py
   ```

4. **Backfill** les données :
   ```bash
   python scripts/backfill_data.py --all --citations --force-citations
   ```

5. **Retirer de la blacklist** si nécessaire :
   Éditer `data/wiki/halo5_commendations_exclude.json`.

## API Python

```python
from src.analysis.citations.engine import CitationEngine

engine = CitationEngine(db_path="data/players/JGtm/stats.duckdb", xuid="12345")

# Charger les mappings
mappings = engine.load_mappings()

# Agréger toutes les citations
totals = engine.aggregate_for_display()
# → {"pilote": 42, "assistant": 1234, ...}

# Agréger avec filtre de matchs
filtered = engine.aggregate_for_display(match_ids=["m1", "m2", "m3"])

# Calculer + stocker pour un match
engine.compute_and_store_for_match("match-uuid-123")
```

## FAQ

**Comment changer la règle d'une citation existante ?**
Modifier l'entrée dans `create_citation_mappings_table.py`, ré-exécuter le script,
puis backfill avec `--force-citations`.

**Quel est l'impact disque ?**
~14 lignes par match dans `match_citations` (une par citation avec valeur > 0).
Pour 1000 matchs : environ 50-100 Ko.

**Comment voir l'évolution temporelle d'une citation ?**
```sql
SELECT
    DATE_TRUNC('month', ms.start_time) AS mois,
    SUM(mc.value) AS total
FROM match_citations mc
JOIN match_stats ms ON mc.match_id = ms.match_id
WHERE mc.citation_name_norm = 'pilote'
GROUP BY 1
ORDER BY 1;
```

**Comment diagnostiquer les problèmes ?**
```bash
python scripts/diagnose_citations.py
```
