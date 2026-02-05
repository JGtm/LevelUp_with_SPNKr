# Sprint : Correction Gamertags, Roster et Coéquipiers

> **Date** : 2026-02-05
> **Priorité** : 🔴 Critique
> **Impact** : Roster, Antagonistes, Mes Coéquipiers, Session Trio

---

## 🔴 Problème Racine

### 1. Gamertags corrompus dans `highlight_events`

Les gamertags proviennent du parsing des films Halo et contiennent des caractères NUL (`\x00`) et de contrôle :
```
'juan1\x00\x00\x00\x00\x00\x00\x00\x03'
'Purp8225\x00\x00\x00\x01'
'Ă\x01'  (quasi illisible)
```

### 2. Table `xuid_aliases` vide

La table `xuid_aliases` devrait contenir les gamertags propres extraits depuis `MatchStats.Players.PlayerGamertag` (API), mais elle est **vide** car :
- La migration SQLite → DuckDB n'a pas transféré les aliases
- Les syncs delta suivants n'ont trouvé aucun nouveau match
- Les DBs SQLite originales ont été supprimées

### 3. Architecture DuckDB v4 incompatible avec la logique legacy

**Legacy SQLite** : Le `ResponseBody` JSON contenait TOUS les joueurs du match
```sql
-- Fonctionne car ResponseBody contient $.Players[] avec tout le monde
SELECT json_extract(j.value, '$.PlayerId'), json_extract(j.value, '$.LastTeamId')
FROM MatchStats JOIN json_each(json_extract(ResponseBody, '$.Players')) AS j
```

**DuckDB v4** : `match_stats` ne contient QUE les stats du joueur principal (1 ligne/match)
```sql
-- NE FONCTIONNE PAS : match_stats ne contient que MES stats !
SELECT * FROM match_stats WHERE xuid = friend_xuid  -- Jamais de résultat
```

---

## 📊 État actuel des tables

| Table | État | Problème |
|-------|------|----------|
| `xuid_aliases` | ❌ Vide (0 lignes) | Jamais peuplée lors de la migration |
| `teammates_aggregate` | ✅ 853 lignes | Gamertags propres, mais pas team_id par match |
| `highlight_events` | ⚠️ 201k lignes | Gamertags corrompus (NUL chars) |
| `killer_victim_pairs` | ❌ Vide (0 lignes) | Non peuplée |
| `antagonists` | ❌ Vide (0 lignes) | Non peuplée |
| `player_match_stats` | ⚠️ 449 lignes | Que le joueur principal, pas les coéquipiers |

**Table manquante** : `match_participants` - stockerait xuid, team_id, outcome de TOUS les joueurs par match

---

## 🎯 Features impactées

| Feature | Fichier | État | Problème |
|---------|---------|------|----------|
| **Roster (dernier match)** | `match_view_players.py` | 🔴 Cassé | Gamertags illisibles, équipes mal assignées |
| **Némésis/Antagonistes** | `match_view_players.py` | 🔴 Cassé | Gamertags illisibles |
| **Mes coéquipiers** | `teammates.py` | 🔴 Cassé | `load_same_team_match_ids()` retourne vide |
| **Session trio** | `teammates.py` | 🔴 Cassé | Idem, dépend des coéquipiers |
| **Dernière session trio** | `teammates.py` | 🔴 Cassé | Idem |

---

## 📝 Plan de correction

### Phase 1 : Nouvelle table `match_participants`

**Objectif** : Restaurer la logique legacy en stockant les participants de chaque match.

#### 1.1 Créer la table dans le schéma DuckDB

**Fichier** : `src/data/sync/engine.py` (section SCHEMA)

```sql
CREATE TABLE IF NOT EXISTS match_participants (
    match_id VARCHAR NOT NULL,
    xuid VARCHAR NOT NULL,
    team_id INTEGER,
    outcome INTEGER,
    gamertag VARCHAR,
    PRIMARY KEY (match_id, xuid)
);
CREATE INDEX IF NOT EXISTS idx_participants_xuid ON match_participants(xuid);
CREATE INDEX IF NOT EXISTS idx_participants_team ON match_participants(match_id, team_id);
```

#### 1.2 Créer le transformateur `extract_participants()`

**Fichier** : `src/data/sync/transformers.py`

```python
def extract_participants(
    match_json: dict[str, Any],
) -> list[MatchParticipantRow]:
    """Extrait tous les participants d'un match (xuid, team_id, outcome, gamertag).
    
    Source : MatchStats.Players[] (JSON API propre, pas les films corrompus).
    """
    players = match_json.get("Players")
    if not isinstance(players, list):
        return []
    
    match_id = match_json.get("MatchId")
    if not match_id:
        return []
    
    rows = []
    for player in players:
        xuid = _extract_xuid(player)
        if not xuid:
            continue
        
        team_id = _safe_int(player.get("LastTeamId"))
        outcome = _safe_int(player.get("Outcome"))
        gamertag = _normalize_gamertag(player.get("PlayerGamertag") or player.get("Gamertag"))
        
        rows.append(MatchParticipantRow(
            match_id=match_id,
            xuid=xuid,
            team_id=team_id,
            outcome=outcome,
            gamertag=gamertag,
        ))
    
    return rows
```

#### 1.3 Intégrer dans le sync engine

**Fichier** : `src/data/sync/engine.py`

Dans `_process_single_match()` :
```python
# Après extract_aliases()
participant_rows = []
if options.with_participants:  # True par défaut
    participant_rows = extract_participants(stats_json)

# Dans le bloc d'insertion
if participant_rows:
    self._insert_participant_rows(participant_rows)
    result["participants"] = len(participant_rows)
```

---

### Phase 2 : Corriger les requêtes coéquipiers

#### 2.1 Réécrire `load_same_team_match_ids()`

**Fichier** : `src/data/repositories/duckdb_repo.py`

```python
def load_same_team_match_ids(self, teammate_xuid: str) -> list[str]:
    """Retourne les match_id où les deux joueurs étaient dans la même équipe.
    
    Utilise match_participants pour trouver les matchs communs.
    """
    conn = self._get_connection()
    
    # Vérifier si match_participants existe
    has_participants = self._has_table("match_participants")
    
    if has_participants:
        # Nouvelle logique avec match_participants
        result = conn.execute("""
            SELECT DISTINCT me.match_id
            FROM match_participants me
            INNER JOIN match_participants tm 
                ON me.match_id = tm.match_id 
                AND me.team_id = tm.team_id
            WHERE me.xuid = ? AND tm.xuid = ?
            ORDER BY me.match_id DESC
        """, [self._xuid, teammate_xuid])
        return [row[0] for row in result.fetchall()]
    
    # Fallback : utiliser teammates_aggregate (moins précis)
    return self._load_same_team_match_ids_fallback(teammate_xuid)
```

#### 2.2 Réécrire `load_matches_with_teammate()`

```python
def load_matches_with_teammate(self, teammate_xuid: str) -> list[FriendMatchInfo]:
    """Retourne les matchs joués avec un coéquipier avec détails.
    
    Retourne: Liste de FriendMatchInfo(match_id, my_team_id, my_outcome, 
                                        friend_team_id, friend_outcome, same_team)
    """
    conn = self._get_connection()
    
    if self._has_table("match_participants"):
        result = conn.execute("""
            SELECT 
                me.match_id,
                ms.start_time,
                ms.playlist_name,
                ms.pair_name,
                me.team_id AS my_team_id,
                me.outcome AS my_outcome,
                tm.team_id AS friend_team_id,
                tm.outcome AS friend_outcome,
                CASE WHEN me.team_id = tm.team_id THEN 1 ELSE 0 END AS same_team
            FROM match_participants me
            INNER JOIN match_participants tm ON me.match_id = tm.match_id
            INNER JOIN match_stats ms ON me.match_id = ms.match_id
            WHERE me.xuid = ? AND tm.xuid = ?
            ORDER BY ms.start_time DESC
        """, [self._xuid, teammate_xuid])
        
        return [FriendMatchInfo(...) for row in result.fetchall()]
    
    return []  # Fallback vide si table manquante
```

---

### Phase 3 : Backfill des matchs existants

#### 3.1 Ajouter options au script `backfill_data.py`

**Nouvelles options CLI** :
```bash
# Backfill participants (PRIORITAIRE)
--participants         # Extraire match_participants depuis l'API
--force-participants   # Forcer pour TOUS les matchs

# Backfill aliases (déjà existe, mais améliorer)
--aliases              # Déjà existe
--force-aliases        # Déjà existe

# Backfill killer_victim_pairs (optionnel)
--roster               # Extraire depuis highlight_events
--antagonists          # Recalculer antagonists globaux
```

#### 3.2 Implémenter le backfill participants

```python
async def _backfill_participants(
    conn,
    client: SPNKrAPIClient,
    match_id: str,
) -> int:
    """Backfill la table match_participants pour un match."""
    stats_json = await client.get_match_stats(match_id)
    if not stats_json:
        return 0
    
    participant_rows = extract_participants(stats_json)
    return _insert_participant_rows(conn, participant_rows)
```

#### 3.3 Commandes de correction

```bash
# Étape 1 : Backfill participants (critique pour coéquipiers)
python scripts/backfill_data.py --player JGtm --participants

# Étape 2 : Backfill aliases (pour noms propres)
python scripts/backfill_data.py --player JGtm --force-aliases

# Tout en un pour tous les joueurs
python scripts/backfill_data.py --all --participants --force-aliases
```

---

### Phase 4 : Résolution centralisée des gamertags

#### 4.1 Créer `resolve_gamertag()`

**Fichier** : `src/data/repositories/duckdb_repo.py` (ou nouveau module)

```python
def resolve_gamertag(
    self,
    xuid: str,
    *,
    match_id: str | None = None,
) -> str | None:
    """Résout un XUID en gamertag avec cascade de sources.
    
    Priorité:
    1. match_participants (pour ce match spécifique)
    2. xuid_aliases (source officielle API)
    3. teammates_aggregate (historique)
    4. highlight_events (nettoyé avec extraction ASCII)
    """
    conn = self._get_connection()
    
    # 1. match_participants (si match_id fourni)
    if match_id and self._has_table("match_participants"):
        result = conn.execute(
            "SELECT gamertag FROM match_participants WHERE match_id = ? AND xuid = ?",
            [match_id, xuid]
        ).fetchone()
        if result and result[0]:
            return result[0]
    
    # 2. xuid_aliases
    result = conn.execute(
        "SELECT gamertag FROM xuid_aliases WHERE xuid = ?",
        [xuid]
    ).fetchone()
    if result and result[0]:
        return result[0]
    
    # 3. teammates_aggregate
    result = conn.execute(
        "SELECT teammate_gamertag FROM teammates_aggregate WHERE teammate_xuid = ?",
        [xuid]
    ).fetchone()
    if result and result[0]:
        return result[0]
    
    # 4. highlight_events avec extraction ASCII
    if match_id:
        result = conn.execute(
            "SELECT gamertag FROM highlight_events WHERE match_id = ? AND xuid = ? LIMIT 1",
            [match_id, xuid]
        ).fetchone()
        if result and result[0]:
            return self._extract_ascii_token(result[0])
    
    return None

def _extract_ascii_token(self, value: str) -> str | None:
    """Extrait un token ASCII plausible depuis un gamertag corrompu."""
    import re
    parts = re.findall(r'[A-Za-z0-9]+', str(value or ""))
    if not parts:
        return None
    parts.sort(key=len, reverse=True)
    token = parts[0]
    return token if len(token) >= 3 else None
```

#### 4.2 Utiliser dans `load_match_rosters()` et `load_match_gamertags()`

Remplacer les appels directs par `resolve_gamertag()`.

---

### Phase 5 : Tests et validation

#### 5.1 Script de validation

```bash
# Vérifier les tables
python -c "
import duckdb
db = duckdb.connect('data/players/JGtm/stats.duckdb', read_only=True)
for t in ['match_participants', 'xuid_aliases', 'teammates_aggregate']:
    count = db.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
    print(f'{t}: {count} lignes')
db.close()
"
```

#### 5.2 Tests fonctionnels

1. **Roster dernier match** : Vérifier noms lisibles, équipes correctes
2. **Némésis/Antagonistes** : Vérifier noms lisibles
3. **Mes coéquipiers** : Sélectionner Madina97294 + Chocoboflor, vérifier matchs trouvés
4. **Session trio** : Vérifier détection dernière session trio

---

## 📅 Ordre d'implémentation

| # | Tâche | Priorité | Effort | Dépendances |
|---|-------|----------|--------|-------------|
| 1 | Phase 1.1 : Créer table `match_participants` | 🔴 Critique | Faible | - |
| 2 | Phase 1.2 : Créer `extract_participants()` | 🔴 Critique | Moyen | #1 |
| 3 | Phase 1.3 : Intégrer dans sync engine | 🔴 Critique | Faible | #2 |
| 4 | Phase 3.1-3.2 : Backfill participants | 🔴 Critique | Moyen | #3 |
| 5 | Phase 2.1-2.2 : Corriger requêtes coéquipiers | 🔴 Critique | Moyen | #4 |
| 6 | Phase 4.1 : Créer `resolve_gamertag()` | 🟡 Important | Moyen | #1 |
| 7 | Phase 4.2 : Utiliser dans rosters | 🟡 Important | Faible | #6 |
| 8 | Phase 3.3 : Backfill aliases | 🟡 Important | Faible | #3 |
| 9 | Phase 5 : Tests validation | 🟢 Standard | Faible | Tous |

---

## 🔧 Commandes finales

```bash
# 1. Après implémentation, backfill toutes les données
python scripts/backfill_data.py --player JGtm --participants --force-aliases

# 2. Pour tous les joueurs
python scripts/backfill_data.py --all --participants --force-aliases

# 3. Vérification
python scripts/diagnose_player_db.py --player JGtm --check-tables
```

---

## Phase 6 : Backfill `killer_victim_pairs` et Antagonistes

> **Objectif** : Peupler la table `killer_victim_pairs` depuis les `highlight_events` DuckDB pour alimenter les graphiques et tableaux d'antagonistes.

### 6.1 Comprendre le flux de données

```
highlight_events (kill/death)
         │
         ▼ Pairing par timestamp (±5ms)
         │
killer_victim_pairs (killer → victim, time_ms)
         │
         ▼ Agrégation par adversaire
         │
antagonists (nemesis/victim stats globales)
         │
         ▼ Visualisations
         │
antagonist_charts.py (graphiques Plotly)
```

**Tables concernées** :

| Table | Rôle | État actuel |
|-------|------|-------------|
| `highlight_events` | Events bruts (kill, death, medal...) | ✅ ~201k lignes |
| `killer_victim_pairs` | Paires killer→victim avec timestamp | ❌ Vide |
| `antagonists` | Stats agrégées par adversaire | ❌ Vide |

### 6.2 Algorithme de pairing kill/death

Les events `kill` et `death` dans `highlight_events` ont des timestamps quasi-identiques (±5ms). Le pairing consiste à joindre :

```python
# Requête SQL pour extraire les paires
SELECT 
    k.match_id,
    k.time_ms,
    k.xuid AS killer_xuid,
    k.gamertag AS killer_gamertag,
    d.xuid AS victim_xuid,
    d.gamertag AS victim_gamertag
FROM highlight_events k
JOIN highlight_events d 
    ON k.match_id = d.match_id 
    AND ABS(k.time_ms - d.time_ms) <= 5
WHERE k.event_type = 'kill' 
  AND d.event_type = 'death'
  AND k.xuid != d.xuid  -- Pas de suicide
```

**Attention** : Cette jointure peut créer des doublons si plusieurs kills/deaths ont le même timestamp. Utiliser la logique de `src/analysis/killer_victim.py:compute_killer_victim_pairs()` qui gère ce cas avec un algorithme de matching greedy.

### 6.3 Ajouter option `--killer-victim` au backfill

**Fichier** : `scripts/backfill_data.py`

```python
@click.option("--killer-victim", is_flag=True, help="Backfill killer_victim_pairs depuis highlight_events")
@click.option("--antagonists", is_flag=True, help="Recalculer la table antagonists")
async def backfill(..., killer_victim: bool, antagonists: bool):
    # ...
    if killer_victim:
        await _backfill_killer_victim_pairs(conn, player_xuid)
    
    if antagonists:
        await _backfill_antagonists(conn, player_xuid)
```

```python
async def _backfill_killer_victim_pairs(conn, me_xuid: str) -> int:
    """Extrait les paires killer/victim depuis highlight_events.
    
    Utilise l'algorithme de pairing de src/analysis/killer_victim.py
    pour apparier les events kill/death par timestamp.
    """
    from src.analysis.killer_victim import compute_killer_victim_pairs
    
    # Charger tous les matchs avec highlight events
    matches = conn.execute("""
        SELECT DISTINCT match_id 
        FROM highlight_events 
        WHERE event_type IN ('kill', 'death')
    """).fetchall()
    
    total_pairs = 0
    
    for (match_id,) in matches:
        # Charger les events du match
        events = conn.execute("""
            SELECT event_type, time_ms, xuid, gamertag
            FROM highlight_events
            WHERE match_id = ? AND event_type IN ('kill', 'death')
            ORDER BY time_ms
        """, [match_id]).fetchall()
        
        # Convertir en dicts pour l'algorithme
        event_dicts = [
            {"event_type": e[0], "time_ms": e[1], "xuid": e[2], "gamertag": e[3]}
            for e in events
        ]
        
        # Calculer les paires avec l'algorithme validé
        pairs = compute_killer_victim_pairs(event_dicts, tolerance_ms=5)
        
        # Insérer les paires
        for p in pairs:
            conn.execute("""
                INSERT OR IGNORE INTO killer_victim_pairs
                (match_id, killer_xuid, killer_gamertag, victim_xuid, victim_gamertag, kill_count, time_ms)
                VALUES (?, ?, ?, ?, ?, 1, ?)
            """, [match_id, p.killer_xuid, p.killer_gamertag, p.victim_xuid, p.victim_gamertag, p.time_ms])
        
        total_pairs += len(pairs)
    
    return total_pairs
```

### 6.4 Mettre à jour `populate_antagonists.py`

Le script actuel cherche une DB SQLite legacy qui n'existe plus. Modifier pour utiliser DuckDB :

**Fichier** : `scripts/populate_antagonists.py`

```python
def process_player_duckdb(gamertag: str, profile: dict, *, force: bool = False) -> AggregationResult | None:
    """Version DuckDB utilisant highlight_events dans la DB du joueur."""
    db_path = profile.get("db_path")
    xuid = profile.get("xuid")
    
    conn = duckdb.connect(db_path, read_only=False)
    
    # Charger les matchs avec highlight events
    matches = conn.execute("""
        SELECT DISTINCT he.match_id, ms.start_time
        FROM highlight_events he
        JOIN match_stats ms ON he.match_id = ms.match_id
        WHERE he.event_type IN ('kill', 'death')
        ORDER BY ms.start_time DESC
    """).fetchall()
    
    match_results = []
    for match_id, start_time in matches:
        events = conn.execute("""
            SELECT event_type, time_ms, xuid, gamertag
            FROM highlight_events
            WHERE match_id = ? AND event_type IN ('kill', 'death')
        """, [match_id]).fetchall()
        
        event_dicts = [
            {"event_type": e[0], "time_ms": e[1], "xuid": e[2], "gamertag": e[3]}
            for e in events
        ]
        
        result = compute_personal_antagonists(event_dicts, me_xuid=xuid)
        if result.my_kills_total > 0 or result.my_deaths_total > 0:
            match_results.append((start_time, result))
    
    # Agréger et sauvegarder
    aggregated = aggregate_antagonists(match_results)
    # ...
```

### 6.5 Commandes de backfill

```bash
# Backfill killer_victim_pairs
python scripts/backfill_data.py --player JGtm --killer-victim

# Backfill antagonists (après killer_victim_pairs)
python scripts/populate_antagonists.py --gamertag JGtm --force

# Ou tout en un
python scripts/backfill_data.py --player JGtm --killer-victim --antagonists
```

---

## Phase 7 : Intégration des graphiques antagonistes

> Les graphiques de `src/visualization/antagonist_charts.py` sont implémentés mais pas encore intégrés dans l'UI.

### 7.1 Graphiques disponibles

| Fonction | Description | Dépendance |
|----------|-------------|------------|
| `plot_killer_victim_stacked_bars()` | Barres empilées kills/deaths par joueur | `killer_victim_pairs` |
| `plot_kd_timeseries()` | K/D par minute au cours du match | `killer_victim_pairs` |
| `plot_duel_history()` | Historique des duels vs un adversaire | `killer_victim_pairs` |
| `plot_nemesis_victim_summary()` | Indicateurs némésis/victime | `antagonists` |
| `plot_killer_victim_heatmap()` | Matrice killer vs victim | `killer_victim_pairs` |
| `plot_top_antagonists_bars()` | Top némésis et victimes | `antagonists` |

### 7.2 Exemple d'intégration dans Streamlit

```python
# Dans src/ui/pages/match_view.py
from src.visualization.antagonist_charts import (
    plot_killer_victim_stacked_bars,
    plot_kd_timeseries,
)
from src.data.repositories.factory import get_repository_from_profile

def render_antagonist_charts(match_id: str, gamertag: str):
    """Affiche les graphiques d'antagonistes pour un match."""
    repo = get_repository_from_profile(gamertag)
    
    # Vérifier si des données existent
    if not repo.has_killer_victim_pairs():
        st.info("Graphiques indisponibles. Lancez le backfill avec --killer-victim.")
        return
    
    # Charger les paires pour ce match
    pairs_df = repo.load_killer_victim_pairs_as_polars(match_id=match_id)
    
    if not pairs_df.is_empty():
        # Barres empilées
        fig1 = plot_killer_victim_stacked_bars(pairs_df, match_id=match_id)
        st.plotly_chart(fig1, use_container_width=True)
        
        # Timeseries K/D (si on a le xuid)
        from src.analysis.killer_victim import compute_kd_timeseries_by_minute_polars
        xuid = repo._xuid
        ts_df = compute_kd_timeseries_by_minute_polars(pairs_df, xuid)
        fig2 = plot_kd_timeseries(ts_df)
        st.plotly_chart(fig2, use_container_width=True)
```

### 7.3 Intégration dans l'onglet "Antagonistes"

Créer une nouvelle page ou section dans `match_view.py` :

```python
def render_antagonists_tab():
    """Onglet complet des antagonistes."""
    st.header("Mes Antagonistes")
    
    repo = get_current_repo()
    
    # Résumé global
    summary = repo.compute_antagonists_summary_polars(top_n=5)
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Top Némésis")
        for nem in summary["nemeses"]:
            st.metric(nem["killer_gamertag"], f"{nem['times_killed_by']} morts")
    
    with col2:
        st.subheader("Top Victimes")
        for vic in summary["victims"]:
            st.metric(vic["victim_gamertag"], f"{vic['times_killed']} kills")
    
    # Graphiques
    fig = plot_top_antagonists_bars(summary["nemeses"], summary["victims"])
    st.plotly_chart(fig, use_container_width=True)
```

---

## 📁 Fichiers à modifier

| Fichier | Modifications |
|---------|---------------|
| `src/data/sync/engine.py` | Ajouter table `match_participants`, intégrer extraction |
| `src/data/sync/transformers.py` | Ajouter `extract_participants()` |
| `src/data/sync/models.py` | Ajouter `MatchParticipantRow` |
| `src/data/repositories/duckdb_repo.py` | Corriger requêtes coéquipiers, ajouter `resolve_gamertag()` |
| `scripts/backfill_data.py` | Ajouter options `--participants`, `--killer-victim`, `--antagonists` |
| `scripts/populate_antagonists.py` | Adapter pour DuckDB (plus de SQLite legacy) |
| `src/ui/pages/match_view.py` | Intégrer graphiques antagonistes |
| `src/ui/cache.py` | Adapter `cached_friend_matches_df()` si nécessaire |

---

## ✅ Critères de succès

### Tables et données
- [ ] `match_participants` contient ~8 joueurs par match (4v4)
- [ ] `xuid_aliases` contient les gamertags propres
- [ ] `killer_victim_pairs` contient les paires killer→victim avec timestamps
- [ ] `antagonists` contient les stats agrégées par adversaire

### Fonctionnalités UI
- [ ] "Mes coéquipiers" trouve les matchs avec Madina97294/Chocoboflor
- [ ] "Session trio" détecte la dernière session à trois
- [ ] Roster du dernier match affiche des noms lisibles
- [ ] Némésis affiche un nom lisible

### Graphiques antagonistes
- [ ] Barres empilées killer/victim fonctionnelles
- [ ] Timeseries K/D par minute fonctionnelle
- [ ] Heatmap killer-victim fonctionnelle
- [ ] Top antagonistes affichés correctement

---

## 📚 Documentation pour les IA : Créer des graphiques avec les données de frags

> Cette section documente comment utiliser les données `killer_victim_pairs` pour créer de nouveaux graphiques ou tableaux.

### Architecture des données de frags

```
┌─────────────────────────────────────────────────────────────────┐
│                    highlight_events (source)                     │
│  - event_type: 'kill' | 'death' | 'medal' | 'mode'              │
│  - time_ms: timestamp depuis début match (ex: 45230)            │
│  - xuid: identifiant Xbox du joueur concerné                    │
│  - gamertag: nom du joueur (peut être corrompu !)               │
│  - match_id: UUID du match                                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │ Pairing kill/death (±5ms)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                  killer_victim_pairs (intermédiaire)             │
│  - match_id: UUID du match                                       │
│  - killer_xuid, killer_gamertag: qui a tué                      │
│  - victim_xuid, victim_gamertag: qui est mort                   │
│  - time_ms: timestamp du frag                                   │
│  - kill_count: 1 (un row par frag)                              │
└───────────────────────────┬─────────────────────────────────────┘
                            │ Agrégation par adversaire
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    antagonists (agrégé global)                   │
│  - opponent_xuid, opponent_gamertag                             │
│  - times_killed: combien de fois je l'ai tué (total)            │
│  - times_killed_by: combien de fois il m'a tué (total)          │
│  - matches_against: nombre de matchs en opposition              │
│  - last_encounter: date du dernier match                        │
└─────────────────────────────────────────────────────────────────┘
```

### Modules clés à utiliser

| Module | Rôle | Fonctions principales |
|--------|------|----------------------|
| `src/analysis/killer_victim.py` | Algorithmes de pairing et analyse | `compute_killer_victim_pairs()`, `compute_personal_antagonists()`, `compute_kd_timeseries_by_minute_polars()` |
| `src/analysis/antagonists.py` | Agrégation sur plusieurs matchs | `aggregate_antagonists()`, `AntagonistEntry` |
| `src/visualization/antagonist_charts.py` | Graphiques Plotly | `plot_killer_victim_stacked_bars()`, `plot_kd_timeseries()`, `plot_killer_victim_heatmap()` |
| `src/data/repositories/duckdb_repo.py` | Accès aux données | `load_killer_victim_pairs_as_polars()`, `compute_antagonists_summary_polars()` |

### Exemple 1 : Créer un graphique de K/D cumulé par match

```python
import polars as pl
from src.data.repositories.factory import get_repository_from_profile
from src.visualization.theme import apply_halo_plot_style
import plotly.graph_objects as go

def plot_kd_cumulative_by_match(gamertag: str, last_n_matches: int = 20) -> go.Figure:
    """Graphique du K/D cumulé sur les N derniers matchs."""
    repo = get_repository_from_profile(gamertag)
    
    # Charger les paires killer/victim
    pairs_df = repo.load_killer_victim_pairs_as_polars(limit=10000)
    me_xuid = repo._xuid
    
    # Agréger par match
    my_kills = (
        pairs_df
        .filter(pl.col("killer_xuid") == me_xuid)
        .group_by("match_id")
        .agg(pl.col("kill_count").sum().alias("kills"))
    )
    
    my_deaths = (
        pairs_df
        .filter(pl.col("victim_xuid") == me_xuid)
        .group_by("match_id")
        .agg(pl.col("kill_count").sum().alias("deaths"))
    )
    
    # Joindre et calculer le net K/D
    kd_by_match = (
        my_kills
        .join(my_deaths, on="match_id", how="outer")
        .with_columns([
            pl.col("kills").fill_null(0),
            pl.col("deaths").fill_null(0),
        ])
        .with_columns((pl.col("kills") - pl.col("deaths")).alias("net_kd"))
        .with_columns(pl.col("net_kd").cum_sum().alias("cumulative_kd"))
        .tail(last_n_matches)
    )
    
    # Créer le graphique
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(range(len(kd_by_match))),
        y=kd_by_match["cumulative_kd"].to_list(),
        mode="lines+markers",
        line={"color": "#00ff00" if kd_by_match["cumulative_kd"][-1] >= 0 else "#ff4444"},
    ))
    
    return apply_halo_plot_style(fig, title="K/D Cumulé par Match")
```

### Exemple 2 : Tableau des duels contre un adversaire spécifique

```python
def get_duel_history(gamertag: str, opponent_gamertag: str) -> pl.DataFrame:
    """Retourne l'historique des duels contre un adversaire."""
    repo = get_repository_from_profile(gamertag)
    pairs_df = repo.load_killer_victim_pairs_as_polars()
    me_xuid = repo._xuid
    
    # Trouver le xuid de l'adversaire
    opponent_xuid = (
        pairs_df
        .filter(pl.col("killer_gamertag").str.to_lowercase() == opponent_gamertag.lower())
        .select("killer_xuid")
        .unique()
        .item()
    )
    
    # Utiliser la fonction d'analyse existante
    from src.analysis.killer_victim import compute_duel_history_polars
    return compute_duel_history_polars(pairs_df, me_xuid, opponent_xuid)
```

### Exemple 3 : Heatmap des interactions killer-victim sur un match

```python
from src.visualization.antagonist_charts import plot_killer_victim_heatmap
from src.analysis.killer_victim import killer_victim_matrix_polars

def render_match_heatmap(gamertag: str, match_id: str):
    """Affiche la heatmap killer-victim pour un match."""
    repo = get_repository_from_profile(gamertag)
    pairs_df = repo.load_killer_victim_pairs_as_polars(match_id=match_id)
    
    if pairs_df.is_empty():
        st.warning("Pas de données killer/victim pour ce match")
        return
    
    # Créer la matrice pivot
    matrix_df = killer_victim_matrix_polars(pairs_df)
    
    # Afficher
    fig = plot_killer_victim_heatmap(matrix_df, title=f"Interactions - Match {match_id[:8]}")
    st.plotly_chart(fig, use_container_width=True)
```

### Bonnes pratiques pour les graphiques

1. **Toujours vérifier si les données existent** :
   ```python
   if not repo.has_killer_victim_pairs():
       st.info("Lancez le backfill avec: python scripts/backfill_data.py --killer-victim")
       return
   ```

2. **Utiliser le style Halo pour les graphiques** :
   ```python
   from src.visualization.theme import apply_halo_plot_style
   fig = apply_halo_plot_style(fig, title="Mon Titre", height=400)
   ```

3. **Gérer les gamertags corrompus** :
   ```python
   # Préférer les gamertags de match_participants ou xuid_aliases
   clean_gamertag = repo.resolve_gamertag(xuid, match_id=match_id)
   ```

4. **Palette de couleurs Halo** :
   ```python
   from src.visualization.antagonist_charts import COLORS
   # COLORS["kills"] = "#00ff00" (vert)
   # COLORS["deaths"] = "#ff4444" (rouge)
   # COLORS["nemesis"] = "#ff6600" (orange)
   ```

### Requêtes SQL utiles

```sql
-- Top 10 adversaires les plus tués
SELECT victim_gamertag, SUM(kill_count) as total_kills
FROM killer_victim_pairs
WHERE killer_xuid = '{me_xuid}'
GROUP BY victim_gamertag
ORDER BY total_kills DESC
LIMIT 10;

-- K/D par map
SELECT ms.map_name, 
       SUM(CASE WHEN kv.killer_xuid = '{me_xuid}' THEN kv.kill_count ELSE 0 END) as kills,
       SUM(CASE WHEN kv.victim_xuid = '{me_xuid}' THEN kv.kill_count ELSE 0 END) as deaths
FROM killer_victim_pairs kv
JOIN match_stats ms ON kv.match_id = ms.match_id
GROUP BY ms.map_name
ORDER BY kills DESC;

-- Évolution du K/D dans le temps (par semaine)
SELECT DATE_TRUNC('week', ms.start_time) as week,
       SUM(CASE WHEN kv.killer_xuid = '{me_xuid}' THEN kv.kill_count ELSE 0 END) as kills,
       SUM(CASE WHEN kv.victim_xuid = '{me_xuid}' THEN kv.kill_count ELSE 0 END) as deaths
FROM killer_victim_pairs kv
JOIN match_stats ms ON kv.match_id = ms.match_id
GROUP BY week
ORDER BY week;
```

### Schéma complet des tables

```sql
-- Table killer_victim_pairs
CREATE TABLE killer_victim_pairs (
    id INTEGER PRIMARY KEY,
    match_id VARCHAR NOT NULL,
    killer_xuid VARCHAR NOT NULL,
    killer_gamertag VARCHAR,
    victim_xuid VARCHAR NOT NULL,
    victim_gamertag VARCHAR,
    kill_count INTEGER DEFAULT 1,
    time_ms INTEGER,            -- Timestamp dans le match
    is_validated BOOLEAN,       -- Si vérifié contre stats officielles
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index recommandés
CREATE INDEX idx_kvp_match ON killer_victim_pairs(match_id);
CREATE INDEX idx_kvp_killer ON killer_victim_pairs(killer_xuid);
CREATE INDEX idx_kvp_victim ON killer_victim_pairs(victim_xuid);

-- Table antagonists (agrégé)
CREATE TABLE antagonists (
    opponent_xuid VARCHAR PRIMARY KEY,
    opponent_gamertag VARCHAR,
    times_killed INTEGER DEFAULT 0,
    times_killed_by INTEGER DEFAULT 0,
    matches_against INTEGER DEFAULT 0,
    last_encounter TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);
```
