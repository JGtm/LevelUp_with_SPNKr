# Plan : Évolution du Score de Performance v4

> Planification détaillée pour l'intégration de nouvelles métriques dans le score de performance relatif.  
> Date : 2026-02-09  
> Statut : 📋 Planification

---

## 🎯 Objectif

Évoluer le score de performance relatif (v3) vers la v4 en intégrant :
1. **Personal Score Per Minute (PSPM)** - Impact global (objectifs, kills, assists)
2. **Damage Per Minute (DPM)** - Efficacité au combat
3. **Rank Performance (MMR-adjusted)** - Rang contextualisé par l'écart MMR

---

## 📊 Nouvelle Configuration (v4)

### Pondérations proposées

```python
RELATIVE_WEIGHTS_V4 = {
    "kpm": 0.22,        # Kills/min (réduit de 30% → 22%)
    "dpm_deaths": 0.18, # Deaths/min inversé (réduit de 25% → 18%)
    "apm": 0.10,        # Assists/min (réduit de 15% → 10%)
    "kda": 0.15,        # KDA (réduit de 20% → 15%)
    "accuracy": 0.08,   # Précision (réduit de 10% → 8%)
    "pspm": 0.12,       # Personal Score/min (NOUVEAU)
    "dpm_damage": 0.10, # Damage Per Minute (NOUVEAU)
    "rank_perf": 0.05,  # Rank vs Expected (NOUVEAU, optionnel)
}
```

**Total : 100%** ✅

---

## 🔧 Modifications de Code

### 1. Configuration (`src/analysis/performance_config.py`)

**Changements** :
- [ ] Mettre à jour `PERFORMANCE_SCORE_VERSION` : `"v3-relative"` → `"v4-relative"`
- [ ] Ajouter `RELATIVE_WEIGHTS_V4` avec les nouvelles pondérations
- [ ] Mettre à jour `RELATIVE_WEIGHTS` pour pointer vers `RELATIVE_WEIGHTS_V4` (ou garder v3 pour compatibilité)
- [ ] Mettre à jour `PERFORMANCE_SCORE_FULL_DESC` avec les nouvelles métriques
- [ ] Mettre à jour `PERFORMANCE_SCORE_COMPACT_DESC`

**Détails** :
```python
# Option A : Remplacer directement
RELATIVE_WEIGHTS = RELATIVE_WEIGHTS_V4

# Option B : Garder v3 pour compatibilité, utiliser v4 par défaut
RELATIVE_WEIGHTS = RELATIVE_WEIGHTS_V4  # Par défaut
RELATIVE_WEIGHTS_V3 = {...}  # Ancienne version pour migration
```

---

### 2. Calcul du Score (`src/analysis/performance_score.py`)

#### 2.1 Fonction `_prepare_history_metrics()`

**Modifications** :
- [ ] Ajouter calcul de `pspm` (Personal Score Per Minute) dans l'historique
- [ ] Ajouter calcul de `dpm_damage` (Damage Per Minute) dans l'historique
- [ ] Ajouter calcul de `rank_perf` (Rank Performance) dans l'historique

**Nouvelle signature** :
```python
def _prepare_history_metrics(df_history: pd.DataFrame) -> pd.DataFrame:
    """Prépare les métriques normalisées par minute pour l'historique.
    
    Retourne DataFrame avec colonnes:
    - kpm, dpm, apm, kda, accuracy (existants)
    - pspm, dpm_damage, rank_perf (nouveaux)
    """
```

**Détails d'implémentation** :
- `pspm` : `personal_score / (duration / 60.0)` si `personal_score` disponible
- `dpm_damage` : `damage_dealt / (duration / 60.0)` si `damage_dealt` disponible
- `rank_perf` : Calculer `expected_rank` basé sur `delta_mmr`, puis `rank_percentile` vs historique

#### 2.2 Fonction `compute_relative_performance_score()`

**Modifications** :
- [ ] Extraire `personal_score` du match actuel
- [ ] Extraire `damage_dealt` du match actuel
- [ ] Extraire `rank`, `team_mmr`, `enemy_mmr` du match actuel
- [ ] Calculer `pspm`, `dpm_damage`, `rank_perf` pour le match actuel
- [ ] Calculer les percentiles pour ces nouvelles métriques
- [ ] Intégrer dans la moyenne pondérée finale

**Nouvelle logique** :
```python
# PSPM
if personal_score is not None:
    pspm = personal_score / (duration / 60.0)
    pspm_series = history_metrics["pspm"].dropna()
    if not pspm_series.empty:
        percentiles["pspm"] = _percentile_rank(pspm, pspm_series)
        weights_used["pspm"] = RELATIVE_WEIGHTS["pspm"]

# DPM Damage
if damage_dealt is not None:
    dpm_damage = damage_dealt / (duration / 60.0)
    dpm_damage_series = history_metrics["dpm_damage"].dropna()
    if not dpm_damage_series.empty:
        percentiles["dpm_damage"] = _percentile_rank(dpm_damage, dpm_damage_series)
        weights_used["dpm_damage"] = RELATIVE_WEIGHTS["dpm_damage"]

# Rank Performance (MMR-adjusted)
if rank is not None and team_mmr is not None and enemy_mmr is not None:
    rank_perf = _compute_rank_performance(rank, team_mmr, enemy_mmr, history_metrics)
    if rank_perf is not None:
        percentiles["rank_perf"] = rank_perf
        weights_used["rank_perf"] = RELATIVE_WEIGHTS["rank_perf"]
```

#### 2.3 Nouvelle fonction `_compute_rank_performance()`

**À créer** :
```python
def _compute_rank_performance(
    rank: int,
    team_mmr: float,
    enemy_mmr: float,
    history_metrics: pd.DataFrame,
) -> float | None:
    """Calcule le percentile de performance du rang contextualisé par MMR.
    
    Args:
        rank: Rang réel dans le match (1 = meilleur)
        team_mmr: MMR de l'équipe
        enemy_mmr: MMR de l'équipe adverse
        history_metrics: DataFrame avec colonnes rank, team_mmr, enemy_mmr
        
    Returns:
        Percentile 0-100 ou None si données insuffisantes.
    """
    # Calculer le rang attendu basé sur l'écart MMR
    # Formule simplifiée pour un match 4v4 (rang moyen = 4.5)
    delta_mmr = team_mmr - enemy_mmr
    expected_rank = 4.5 - (delta_mmr / 100.0) * 0.5
    
    # Performance = différence entre rang attendu et réel
    # Rang 1 vs attendu 3 → surperformance
    # Rang 5 vs attendu 3 → sous-performance
    rank_diff = expected_rank - rank  # Positif = mieux que prévu
    
    # Comparer à l'historique des rank_diff
    if "rank_perf_diff" not in history_metrics.columns:
        return None
    
    rank_diff_series = history_metrics["rank_perf_diff"].dropna()
    if rank_diff_series.empty:
        return None
    
    return _percentile_rank(rank_diff, rank_diff_series)
```

**Note** : Cette fonction nécessite de pré-calculer `rank_perf_diff` dans `_prepare_history_metrics()`.

---

### 3. Script de Migration (`scripts/compute_historical_performance.py`)

**Problème actuel** : Le script utilise SQLite (legacy), mais le projet utilise DuckDB.

**Actions** :
- [ ] **Option A** : Adapter le script existant pour DuckDB
- [ ] **Option B** : Créer un nouveau script `scripts/recompute_performance_scores_duckdb.py`

**Recommandation** : Option B (nouveau script dédié DuckDB)

#### 3.1 Nouveau script : `scripts/recompute_performance_scores_duckdb.py`

**Fonctionnalités** :
- [ ] Parcourir toutes les DB DuckDB dans `data/players/{gamertag}/stats.duckdb`
- [ ] Pour chaque joueur :
  - Charger tous les matchs triés par `start_time`
  - Pour chaque match (approche rolling) :
    - Charger l'historique (matchs précédents)
    - Recalculer le score avec la nouvelle formule v4
    - Mettre à jour `performance_score` dans `match_stats`
- [ ] Support `--dry-run` pour simulation (mode `read_only=True`)
- [ ] Support `--force` pour recalculer même si score existe
- [ ] Support `--player GAMERTAG` pour un joueur spécifique
- [ ] Support `--batch-size N` pour commits par batch
- [ ] Barre de progression avec `tqdm`
- [ ] Utiliser `db_profiles.json` pour trouver les joueurs (comme `migrate_player_to_duckdb.py`)

**Structure** :
```python
#!/usr/bin/env python3
"""Script de recalcul des scores de performance v4 pour DuckDB.

Usage:
    python scripts/recompute_performance_scores_duckdb.py --player JGtm
    python scripts/recompute_performance_scores_duckdb.py --all --dry-run
    python scripts/recompute_performance_scores_duckdb.py --all --force
"""

import argparse
import duckdb
import pandas as pd
from pathlib import Path
from tqdm import tqdm

from src.analysis.performance_score import compute_relative_performance_score

def load_player_matches(db_path: Path) -> pd.DataFrame:
    """Charge tous les matchs d'un joueur depuis DuckDB."""
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        df = conn.execute("""
            SELECT 
                match_id, start_time, kills, deaths, assists, kda, accuracy,
                time_played_seconds, personal_score, damage_dealt,
                rank, team_mmr, enemy_mmr
            FROM match_stats
            WHERE start_time IS NOT NULL
            ORDER BY start_time ASC
        """).df()
        return df
    finally:
        conn.close()

def recompute_scores_for_player(
    db_path: Path,
    *,
    dry_run: bool = False,
    force: bool = False,
    batch_size: int = 100,
) -> dict:
    """Recalcule les scores pour un joueur."""
    stats = {"total": 0, "computed": 0, "skipped": 0, "errors": 0}
    
    # Charger matchs
    df = load_player_matches(db_path)
    if df.empty:
        return stats
    
    stats["total"] = len(df)
    
    # Convertir start_time en datetime
    df["start_time"] = pd.to_datetime(df["start_time"], errors="coerce")
    df = df.sort_values("start_time").reset_index(drop=True)
    
    # Ouvrir connexion en écriture si pas dry-run
    if not dry_run:
        conn = duckdb.connect(str(db_path), read_only=False)
    else:
        conn = None
    
    batch_updates = []
    
    try:
        for idx, row in tqdm(df.iterrows(), total=len(df), desc=f"  {db_path.stem}"):
            match_id = row["match_id"]
            
            # Skip si score existe déjà et pas force
            if not force and pd.notna(row.get("performance_score")):
                stats["skipped"] += 1
                continue
            
            # Historique = matchs AVANT ce match
            history = df.iloc[:idx]
            
            # Calculer le score avec la nouvelle formule v4
            try:
                score = compute_relative_performance_score(row, history)
                
                if score is not None:
                    stats["computed"] += 1
                    if not dry_run and conn:
                        batch_updates.append((score, match_id))
                        
                        # Commit par batch
                        if len(batch_updates) >= batch_size:
                            conn.executemany(
                                "UPDATE match_stats SET performance_score = ? WHERE match_id = ?",
                                batch_updates
                            )
                            conn.commit()
                            batch_updates = []
                else:
                    stats["skipped"] += 1
            except Exception as e:
                stats["errors"] += 1
                print(f"Erreur pour {match_id}: {e}")
        
        # Commit restant
        if batch_updates and not dry_run and conn:
            conn.executemany(
                "UPDATE match_stats SET performance_score = ? WHERE match_id = ?",
                batch_updates
            )
            conn.commit()
    finally:
        if conn:
            conn.close()
    
    return stats

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--player", help="Gamertag spécifique")
    parser.add_argument("--all", action="store_true", help="Tous les joueurs")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()
    
    # Trouver les DB à traiter
    # ... (utiliser db_profiles.json ou scanner data/players/)
    
    # Traiter chaque joueur
    # ...

if __name__ == "__main__":
    main()
```

**Usage** :
```bash
# Simulation pour tous les joueurs
python scripts/recompute_performance_scores_duckdb.py --all --dry-run

# Recalcul pour un joueur spécifique
python scripts/recompute_performance_scores_duckdb.py --player JGtm

# Force recalcul pour tous
python scripts/recompute_performance_scores_duckdb.py --all --force
```

---

### 4. Mise à jour du Sync (`src/data/sync/engine.py`)

**Modifications** :
- [ ] S'assurer que `_compute_and_update_performance_score()` utilise la nouvelle version
- [ ] Vérifier que les colonnes nécessaires sont disponibles dans la requête d'historique :
  - `personal_score`
  - `damage_dealt`
  - `rank`
  - `team_mmr`
  - `enemy_mmr`

**Requête à mettre à jour** (ligne ~914) :
```python
history_df = conn.execute("""
    SELECT
        match_id, start_time, kills, deaths, assists, kda, accuracy,
        time_played_seconds, avg_life_seconds,
        personal_score, damage_dealt,  -- NOUVEAUX
        rank, team_mmr, enemy_mmr       -- NOUVEAUX
    FROM match_stats
    WHERE match_id != ?
      AND start_time IS NOT NULL
      AND start_time < CAST(? AS TIMESTAMP)
    ORDER BY start_time ASC
""", (match_id, current_start_time_str)).df()
```

---

### 5. Backfill (`scripts/backfill_data.py`)

**Modifications** :
- [ ] S'assurer que `_compute_performance_score_for_match()` utilise la nouvelle version
- [ ] Vérifier que les colonnes nécessaires sont chargées depuis `match_stats`

**Note** : Le backfill devrait automatiquement utiliser la nouvelle formule si `compute_relative_performance_score()` est mise à jour.

---

## 📝 Documentation

### 6.1 Mise à jour `docs/PERFORMANCE_SCORE.md`

**Changements** :
- [ ] Mettre à jour la section "Formule v3-relative" → "Formule v4-relative"
- [ ] Ajouter les nouvelles métriques dans le tableau
- [ ] Mettre à jour les exemples de calcul
- [ ] Documenter la migration depuis v3

### 6.2 Mise à jour `.ai/thought_log.md`

**À ajouter** :
- [ ] Entrée expliquant la décision d'ajouter PSPM, DPM damage, Rank perf
- [ ] Référence au plan détaillé

---

## 🧪 Tests

### 7.1 Tests unitaires (`tests/test_performance_score.py`)

**À ajouter** :
- [ ] Test calcul PSPM avec historique
- [ ] Test calcul DPM damage avec historique
- [ ] Test calcul Rank Performance avec MMR
- [ ] Test que les nouvelles métriques sont optionnelles (graceful degradation)
- [ ] Test compatibilité avec données v3 (scores existants)

### 7.2 Tests d'intégration

**À ajouter** :
- [ ] Test recalcul batch pour un joueur avec historique complet
- [ ] Test que le sync calcule correctement les nouveaux scores
- [ ] Test que le backfill utilise la nouvelle formule

---

## 🔄 Migration des Données Existantes

### Stratégie

**Oui, il faut recalculer tous les scores existants** pour garantir la cohérence.

**Raisons** :
1. Les nouvelles métriques changent les pondérations
2. Les scores relatifs doivent être comparables entre eux
3. Un score v3 et un score v4 ne sont pas directement comparables

### Processus de Migration

1. **Phase 1 : Préparation**
   - [ ] Déployer le code v4 (nouvelle formule)
   - [ ] Vérifier que les colonnes nécessaires existent (`personal_score`, `damage_dealt`, `rank`, `team_mmr`, `enemy_mmr`)

2. **Phase 2 : Recalcul**
   - [ ] Exécuter `scripts/recompute_performance_scores_duckdb.py --dry-run` pour vérifier
   - [ ] Exécuter le script réel pour tous les joueurs
   - [ ] Vérifier les statistiques (nombre de scores recalculés, erreurs)

3. **Phase 3 : Validation**
   - [ ] Comparer quelques scores v3 vs v4 pour vérifier la cohérence
   - [ ] Vérifier que les nouveaux matchs utilisent automatiquement v4

### Estimation

- **Temps de recalcul** : ~1-2 secondes par joueur (selon nombre de matchs)
- **Pour 10 joueurs avec 1000 matchs chacun** : ~20-40 secondes
- **Pour 50 joueurs avec 2000 matchs chacun** : ~2-4 minutes

---

## 📋 Checklist de Déploiement

### Avant le déploiement

- [ ] Code v4 implémenté et testé
- [ ] Script de migration créé et testé en dry-run
- [ ] Documentation mise à jour
- [ ] Tests unitaires passent
- [ ] Backup des DB existantes (optionnel mais recommandé)

### Déploiement

- [ ] Déployer le code v4
- [ ] Exécuter le script de migration en dry-run sur un joueur test
- [ ] Vérifier les résultats
- [ ] Exécuter le script réel pour tous les joueurs
- [ ] Vérifier les statistiques de migration

### Après déploiement

- [ ] Vérifier que les nouveaux matchs utilisent v4
- [ ] Monitorer les erreurs potentielles
- [ ] Documenter les changements dans `.ai/thought_log.md`

---

## 🚨 Points d'Attention

### 1. Données manquantes

**Problème** : Tous les matchs n'ont pas forcément `personal_score`, `damage_dealt`, `rank`, `team_mmr`, `enemy_mmr`.

**Solution** : Graceful degradation
- Si une métrique n'est pas disponible, elle est simplement ignorée
- Les poids sont renormalisés automatiquement
- Le score reste calculable avec les métriques disponibles

### 2. Compatibilité avec v3

**Problème** : Les scores v3 et v4 ne sont pas directement comparables.

**Solution** :
- Stocker la version dans `performance_score` n'est pas nécessaire (trop complexe)
- Les scores sont recalculés lors de la migration
- Les nouveaux matchs utilisent automatiquement v4

### 3. Performance du recalcul

**Problème** : Recalculer tous les scores peut être long.

**Solution** :
- Utiliser des batches pour les commits
- Paralléliser par joueur (si plusieurs DB)
- Option `--force` pour éviter de skip les scores existants

### 4. Rank Performance - Complexité

**Problème** : Le calcul du rang attendu est simplifié (assume 4v4).

**Solution** :
- Utiliser une formule simple pour commencer
- Améliorer plus tard si nécessaire (détection du nombre de joueurs)

---

## 📊 Métriques de Succès

- [ ] Tous les scores recalculés avec succès
- [ ] Aucune erreur lors du recalcul
- [ ] Les nouveaux matchs utilisent automatiquement v4
- [ ] Les scores sont cohérents (pas de valeurs aberrantes)
- [ ] Performance acceptable (< 5 min pour 50 joueurs)

---

## 🔗 Fichiers Impactés

| Fichier | Type | Changement |
|---------|------|------------|
| `src/analysis/performance_config.py` | Config | Nouveaux poids, version |
| `src/analysis/performance_score.py` | Core | Nouvelle logique de calcul |
| `scripts/recompute_performance_scores_duckdb.py` | Script | Nouveau script de migration |
| `src/data/sync/engine.py` | Sync | Mise à jour requête historique |
| `docs/PERFORMANCE_SCORE.md` | Doc | Documentation v4 |
| `tests/test_performance_score.py` | Tests | Nouveaux tests |

---

## 📅 Timeline Estimé

- **Phase 1 : Développement** : 2-3 heures
  - Implémentation des nouvelles métriques
  - Création du script de migration
  - Tests unitaires

- **Phase 2 : Tests** : 1-2 heures
  - Tests d'intégration
  - Validation sur données réelles

- **Phase 3 : Migration** : 30 min - 1 heure
  - Exécution du script de migration
  - Vérification des résultats

**Total estimé** : 4-6 heures

---

## ✅ Prochaines Étapes

1. Valider ce plan avec l'équipe
2. Commencer l'implémentation
3. Tester sur un joueur pilote
4. Déployer progressivement

---

**Note** : Ce plan est détaillé mais peut être ajusté selon les retours et les contraintes techniques rencontrées.
