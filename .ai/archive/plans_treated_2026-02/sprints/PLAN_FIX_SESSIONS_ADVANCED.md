# Plan : Correction des Sessions avec Logique Avancée

> **Date** : 2026-02-05  
> **Priorité** : 🔴 Critique  
> **Contexte** : Les sessions doivent utiliser la logique avancée (gap temporel + changement de coéquipiers)

---

## 🎯 Objectif

Unifier la logique de calcul des sessions pour qu'elle soit **identique** entre :
1. **Backfill** (`scripts/compute_sessions.py`)
2. **UI/Refresh** (`src/ui/cache.py` → `cached_compute_sessions_db()`)
3. **Sync** (`scripts/sync.py`)

**Règles de session :**
1. Gap temporel > `gap_minutes` (défaut: 120 min) = nouvelle session
2. Changement de `teammates_signature` = nouvelle session
3. Heure de coupure (`cutoff_hour` = 8h) pour sessions "en cours"

---

## 📊 État Actuel

### Problèmes identifiés

| Composant | Fonction utilisée | Logique | Problème |
|-----------|-------------------|---------|----------|
| `scripts/compute_sessions.py` | Logique custom (SQL) | Gap temporel uniquement | ❌ Ignore `teammates_signature` |
| `src/ui/cache.py` | `compute_sessions()` | Gap temporel uniquement | ❌ Ignore `teammates_signature` |
| `scripts/sync.py` | `compute_sessions()` | Gap temporel uniquement | ❌ Ignore `teammates_signature` |
| `src/analysis/sessions.py` | `compute_sessions_with_context()` | Gap + coéquipiers | ✅ Logique correcte mais **non utilisée** |

### Colonne `teammates_signature`

- ✅ **Existe** dans le schéma `match_stats` (ligne 380 de `engine.py`)
- ❓ **État** : À vérifier si elle est remplie lors du sync
- 📝 **Format attendu** : Signature des XUIDs des coéquipiers (triés, séparés par virgule)

---

## 🔧 Plan d'Implémentation

### Phase 1 : Vérifier et Compléter `teammates_signature`

**Objectif** : S'assurer que `teammates_signature` est remplie pour tous les matchs.

#### Étape 1.1 : Vérifier l'état actuel

```python
# Script de diagnostic
# Vérifier combien de matchs ont teammates_signature NULL
SELECT 
    COUNT(*) as total,
    COUNT(teammates_signature) as with_signature,
    COUNT(*) - COUNT(teammates_signature) as missing_signature
FROM match_stats
```

#### Étape 1.2 : Créer/Adapter la fonction de calcul de signature

**Fichier** : `src/data/sync/transformers.py` ou nouveau fichier

```python
def compute_teammates_signature(
    match_json: dict[str, Any],
    my_xuid: str,
    my_team_id: int | None,
) -> str | None:
    """Calcule la signature des coéquipiers pour un match.
    
    Args:
        match_json: JSON du match depuis l'API.
        my_xuid: XUID du joueur principal.
        my_team_id: ID de l'équipe du joueur.
        
    Returns:
        Signature (XUIDs triés séparés par virgule) ou None.
    """
    players = match_json.get("Players", [])
    if not players or my_team_id is None:
        return None
    
    # Extraire les XUIDs des coéquipiers (même équipe, excluant moi)
    teammate_xuids = []
    for player in players:
        xuid = _extract_xuid(player)
        team_id = _safe_int(player.get("LastTeamId"))
        
        if xuid and team_id == my_team_id and xuid != my_xuid:
            teammate_xuids.append(xuid)
    
    if not teammate_xuids:
        return None
    
    # Trier et joindre pour créer une signature stable
    teammate_xuids.sort()
    return ",".join(teammate_xuids)
```

#### Étape 1.3 : Intégrer dans `transform_match_stats()`

**Fichier** : `src/data/sync/transformers.py`

- Ajouter l'appel à `compute_teammates_signature()` dans `transform_match_stats()`
- Ajouter `teammates_signature` au modèle `MatchStatsRow`
- Mettre à jour `_insert_match_row()` pour inclure `teammates_signature`

#### Étape 1.4 : Script de backfill pour `teammates_signature`

**Fichier** : `scripts/backfill_teammates_signature.py` (nouveau)

- Pour chaque match sans `teammates_signature` :
  - Récupérer le JSON depuis l'API (ou depuis archive si disponible)
  - Calculer la signature
  - UPDATE `match_stats`

---

### Phase 2 : Migrer vers Polars

**Objectif** : Remplacer Pandas par Polars dans `src/analysis/sessions.py`.

#### Étape 2.1 : Créer `compute_sessions_with_context_polars()`

**Fichier** : `src/analysis/sessions.py`

```python
import polars as pl

def compute_sessions_with_context_polars(
    df: pl.DataFrame,
    gap_minutes: int = DEFAULT_SESSION_GAP_MINUTES,
    cutoff_hour: int = SESSION_CUTOFF_HOUR,
    teammates_column: str | None = "teammates_signature",
) -> pl.DataFrame:
    """Version Polars de compute_sessions_with_context.
    
    Règles :
    1. Gap > gap_minutes = nouvelle session
    2. Changement de teammates_signature = nouvelle session
    3. Heure de coupure pour sessions "en cours"
    
    Args:
        df: DataFrame Polars avec colonnes start_time et optionnellement teammates_signature.
        gap_minutes: Gap maximum entre matchs.
        cutoff_hour: Heure de coupure.
        teammates_column: Nom de la colonne teammates_signature.
        
    Returns:
        DataFrame avec colonnes session_id et session_label ajoutées.
    """
    if df.is_empty():
        return df.with_columns([
            pl.lit(None).cast(pl.Int64).alias("session_id"),
            pl.lit(None).cast(pl.Utf8).alias("session_label"),
        ])
    
    # Trier par start_time
    df_sorted = df.sort("start_time")
    
    # Calculer les gaps (en secondes)
    gaps = df_sorted["start_time"].diff().dt.total_seconds().fill_null(0)
    gap_break = (gaps > (gap_minutes * 60)).cast(pl.Int8)
    
    # Changement de coéquipiers ?
    if teammates_column and teammates_column in df_sorted.columns:
        teammates_break = (
            df_sorted[teammates_column] != df_sorted[teammates_column].shift(1)
        ).cast(pl.Int8)
        teammates_break = teammates_break.fill_null(0)
    else:
        teammates_break = pl.lit(0).cast(pl.Int8)
    
    # Nouvelle session si gap OU changement de coéquipiers
    new_session = ((gap_break == 1) | (teammates_break == 1)).cast(pl.Int8)
    new_session = new_session.fill_null(1)  # Premier match = première session
    
    # Calculer session_id (cumsum)
    session_id = new_session.cumsum() - 1
    
    # Générer les labels
    session_labels = (
        df_sorted
        .with_columns(session_id.alias("_session_id"))
        .group_by("_session_id")
        .agg([
            pl.col("start_time").min().alias("start"),
            pl.col("start_time").max().alias("end"),
            pl.count().alias("count"),
        ])
        .with_columns(
            pl.format(
                "{} {}–{} ({})",
                pl.col("start").dt.strftime("%d/%m/%Y"),
                pl.col("start").dt.strftime("%H:%M"),
                pl.col("end").dt.strftime("%H:%M"),
                pl.col("count"),
            ).alias("session_label")
        )
        .select(["session_id", "session_label"])
    )
    
    # Joindre les labels
    df_result = df_sorted.with_columns(session_id.alias("session_id"))
    df_result = df_result.join(
        session_labels,
        on="session_id",
        how="left",
    )
    
    return df_result
```

#### Étape 2.2 : Adapter `cached_compute_sessions_db()` pour utiliser Polars

**Fichier** : `src/ui/cache.py`

- Charger les données avec Polars (ou convertir depuis Pandas)
- Appeler `compute_sessions_with_context_polars()`
- Retourner un DataFrame Polars (ou convertir en Pandas si nécessaire pour compatibilité UI)

---

### Phase 3 : Corriger `scripts/compute_sessions.py`

**Objectif** : Utiliser la même logique que l'UI.

#### Étape 3.1 : Refactoriser pour utiliser Polars

**Fichier** : `scripts/compute_sessions.py`

```python
import polars as pl
from src.analysis.sessions import compute_sessions_with_context_polars

def compute_sessions_for_db(
    conn: duckdb.DuckDBPyConnection,
    gap_minutes: int = 120,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Calcule et persiste les sessions avec logique avancée."""
    
    # Charger les matchs depuis DuckDB en DataFrame Polars
    df = conn.execute("""
        SELECT 
            match_id,
            start_time,
            teammates_signature
        FROM match_stats
        WHERE start_time IS NOT NULL
        ORDER BY start_time ASC
    """).pl()
    
    # Calculer les sessions avec la logique avancée
    df_with_sessions = compute_sessions_with_context_polars(
        df,
        gap_minutes=gap_minutes,
        teammates_column="teammates_signature",
    )
    
    # Persister dans match_stats
    if not dry_run:
        for row in df_with_sessions.iter_rows(named=True):
            conn.execute(
                """
                UPDATE match_stats
                SET session_id = ?, session_label = ?
                WHERE match_id = ?
                """,
                [str(row["session_id"]), row["session_label"], row["match_id"]],
            )
    
    # Rafraîchir mv_session_stats et table sessions
    # ...
```

---

### Phase 4 : Corriger `scripts/sync.py`

**Objectif** : Utiliser la logique avancée lors du sync.

#### Étape 4.1 : Identifier où les sessions sont calculées dans sync.py

**Fichier** : `scripts/sync.py` (ligne ~492)

- Remplacer `compute_sessions()` par `compute_sessions_with_context_polars()`
- S'assurer que `teammates_signature` est disponible dans le DataFrame

---

### Phase 5 : Tests et Validation

#### Étape 5.1 : Tests unitaires

**Fichier** : `tests/test_sessions_advanced.py` (nouveau)

```python
def test_compute_sessions_with_teammates_change():
    """Test que changement de coéquipiers crée une nouvelle session."""
    # Créer un DataFrame avec changement de teammates_signature
    # Vérifier que session_id change
    
def test_compute_sessions_with_gap():
    """Test que gap > gap_minutes crée une nouvelle session."""
    
def test_compute_sessions_consistency():
    """Test que backfill et UI produisent les mêmes sessions."""
```

#### Étape 5.2 : Validation sur données réelles

1. Exécuter `compute_sessions.py --all --force` avec la nouvelle logique
2. Comparer les résultats avec l'ancienne logique
3. Vérifier que les sessions sont cohérentes entre backfill et UI

---

## 📋 Checklist d'Implémentation

### Phase 1 : `teammates_signature`
- [ ] Vérifier l'état actuel de `teammates_signature`
- [ ] Créer `compute_teammates_signature()` dans `transformers.py`
- [ ] Intégrer dans `transform_match_stats()`
- [ ] Mettre à jour `MatchStatsRow` pour inclure `teammates_signature`
- [ ] Mettre à jour `_insert_match_row()` pour persister `teammates_signature`
- [ ] Créer script `backfill_teammates_signature.py`
- [ ] Exécuter le backfill pour tous les joueurs

### Phase 2 : Migration vers Polars
- [ ] Créer `compute_sessions_with_context_polars()` dans `sessions.py`
- [ ] Tester la fonction avec des données réelles
- [ ] Adapter `cached_compute_sessions_db()` pour utiliser Polars
- [ ] Vérifier la compatibilité avec l'UI (conversion Pandas si nécessaire)

### Phase 3 : Corriger `compute_sessions.py`
- [ ] Refactoriser pour utiliser Polars
- [ ] Utiliser `compute_sessions_with_context_polars()`
- [ ] Tester avec `--dry-run`
- [ ] Exécuter sur tous les joueurs avec `--force`

### Phase 4 : Corriger `sync.py`
- [ ] Identifier où les sessions sont calculées
- [ ] Remplacer par `compute_sessions_with_context_polars()`
- [ ] Tester le sync avec la nouvelle logique

### Phase 5 : Tests
- [ ] Créer tests unitaires
- [ ] Valider sur données réelles
- [ ] Comparer résultats avant/après
- [ ] Documenter les changements

---

## ⚠️ Points d'Attention

1. **Compatibilité Pandas/Polars** : L'UI utilise peut-être Pandas. Vérifier si conversion nécessaire.
2. **Performance** : Polars est plus rapide mais tester sur gros volumes.
3. **Migration des données existantes** : Les sessions déjà calculées devront être recalculées avec `--force`.
4. **`teammates_signature` NULL** : Gérer le cas où la colonne est NULL (fallback sur logique simple).

---

## 📝 Notes Techniques

### Format de `teammates_signature`

```
"2533274823110022,2533274858283686,2533274883457349"
```

- XUIDs triés par ordre croissant
- Séparés par virgule
- Exclut le joueur principal
- NULL si pas de coéquipiers ou équipe inconnue

### Ordre d'exécution recommandé

1. **Phase 1** : Compléter `teammates_signature` pour tous les matchs
2. **Phase 2** : Migrer vers Polars (fonction de calcul)
3. **Phase 3** : Corriger `compute_sessions.py`
4. **Phase 4** : Corriger `sync.py`
5. **Phase 5** : Tests et validation

---

## 🔗 Fichiers à Modifier

| Fichier | Action | Priorité |
|---------|--------|----------|
| `src/data/sync/transformers.py` | Ajouter `compute_teammates_signature()` | 🔴 Critique |
| `src/data/sync/models.py` | Ajouter `teammates_signature` à `MatchStatsRow` | 🔴 Critique |
| `src/data/sync/engine.py` | Mettre à jour `_insert_match_row()` | 🔴 Critique |
| `src/analysis/sessions.py` | Créer `compute_sessions_with_context_polars()` | 🔴 Critique |
| `src/ui/cache.py` | Adapter `cached_compute_sessions_db()` | 🔴 Critique |
| `scripts/compute_sessions.py` | Refactoriser avec Polars | 🔴 Critique |
| `scripts/sync.py` | Utiliser logique avancée | 🟡 Important |
| `scripts/backfill_teammates_signature.py` | Créer nouveau script | 🟡 Important |
| `tests/test_sessions_advanced.py` | Créer tests | 🟢 Nice to have |

---

*Plan créé le 2026-02-05*
