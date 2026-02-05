# Sprint : Plan de Récupération des Données Post-Migration

> **Date** : 2026-02-05
> **Priorité** : 🔴 Critique → 🟡 Nice to have
> **Durée estimée** : 3-5 jours de développement

---

## Vue d'ensemble

Ce sprint corrige les données manquantes après la migration SQLite → DuckDB v4.

### État actuel des données

| Table | JGtm | Madina | Choco | Daemon | État |
|-------|------|--------|-------|--------|------|
| match_stats | 451 | 955 | 219 | 18 | ✅ OK |
| medals_earned | 1278 | - | - | - | ✅ OK |
| teammates_aggregate | 853 | - | - | - | ✅ OK |
| player_match_stats | 449 | 946 | 219 | 18 | ✅ OK |
| highlight_events | 201k | 345k | 95k | 8k | ✅ OK (limité - anciens matchs non récupérables via API) |
| **xuid_aliases** | **?** | **?** | **?** | **?** | ✅ Implémenté `--force-aliases` |
| **antagonists** | **?** | **?** | **?** | **?** | ✅ Script `populate_antagonists.py` existe |
| **killer_victim_pairs** | **?** | **?** | **?** | **?** | ✅ Implémenté `--killer-victim` |
| **match_participants** | **?** | **?** | **?** | **?** | ✅ Implémenté `--participants` |
| sessions | 0 | - | - | - | 🟡 VIDE |
| career_progression | 0 | - | - | - | 🟡 VIDE |
| skill_history | 0 | - | - | - | 🟡 VIDE |

### Mise à jour 2026-02-05 (Sprint Gamertag Roster Fix)

**Implémentations terminées :**
- ✅ **match_participants** : Table créée, `extract_participants()` dans transformers.py, backfill via `--participants`
- ✅ **killer_victim_pairs** : Backfill via `--killer-victim` (utilise `compute_killer_victim_pairs()`)
- ✅ **xuid_aliases** : Backfill via `--force-aliases`
- ✅ **resolve_gamertag_batch()** : Centralisé dans `duckdb_repo.py`

**Limitation importante :**
- ⚠️ L'API Halo ne retourne plus les `highlight_events` pour les anciens matchs (~574 matchs sur 955 pour Madina97294)
- Les données killer_victim_pairs ne peuvent être calculées que sur les matchs ayant des highlight_events (381/955 pour Madina)

### Mise à jour 2026-02-05 (Récupération depuis SQLite)

**Script créé : `scripts/recover_from_sqlite.py`**

Récupère les données depuis les anciennes bases SQLite (`spnkr_gt_*.db`) :

| Joueur | match_participants | xuid_aliases |
|--------|-------------------|--------------|
| Madina97294 | 18,869 | 3,696 |
| JGtm | 4,186 | 2,257 |
| Chocoboflor | 103 | 70 |
| XxDaemonGamerxX | 159 | 78 |
| **TOTAL** | **23,317** | **6,101** |

**Commande utilisée :**
```bash
python scripts/recover_from_sqlite.py --all
```

**Couverture gamertag :**
- ~30% des XUIDs ont un gamertag connu (depuis HighlightEvents + TeammatesAggregate)
- ~70% restent sans gamertag (joueurs vus uniquement dans les 574 matchs sans highlight_events)

---

## 🔴 PRIORITÉ 1 : xuid_aliases (Critique)

### Problème
La table `xuid_aliases` est vide pour tous les joueurs. Elle devrait contenir le mapping XUID → Gamertag.

### Impact détaillé

| Feature | Fichier | Impact |
|---------|---------|--------|
| **Roster du match** | `src/ui/widgets/match_view_players.py` | ❌ Affiche des XUIDs au lieu des gamertags |
| **Némésis/Antagonistes** | `src/ui/widgets/match_view_players.py` | ❌ Noms illisibles |
| **Mes Coéquipiers** | `src/ui/pages/teammates.py` | ⚠️ Noms depuis teammates_aggregate OK, mais pas de fallback |
| **Session Trio** | `src/ui/pages/teammates.py` | ❌ Résolution des noms échoue |
| **Fonction resolve_gamertag()** | `src/data/repositories/duckdb_repo.py` | ❌ Retourne None systématiquement |

### Sources de données disponibles

1. **highlight_events** (4203 gamertags uniques pour JGtm)
   - ⚠️ Gamertags souvent corrompus (caractères NUL)
   - ✅ Contient les XUIDs corrects
   
2. **teammates_aggregate** (853 lignes pour JGtm)
   - ✅ Gamertags propres
   - ✅ XUIDs corrects
   
3. **API Halo (via nouveau sync)**
   - ✅ Gamertags propres et à jour
   - ⚠️ Nécessite des appels API

### Plan d'implémentation

#### Étape 1.1 : Backfill depuis teammates_aggregate (rapide, offline)

**Fichier** : `scripts/backfill_xuid_aliases.py` (nouveau)

```python
def backfill_from_teammates_aggregate(conn) -> int:
    """Peuple xuid_aliases depuis teammates_aggregate."""
    return conn.execute("""
        INSERT INTO xuid_aliases (xuid, gamertag, last_seen, source, updated_at)
        SELECT 
            teammate_xuid,
            teammate_gamertag,
            last_played,
            'teammates_aggregate',
            CURRENT_TIMESTAMP
        FROM teammates_aggregate
        WHERE teammate_gamertag IS NOT NULL 
          AND teammate_gamertag != ''
        ON CONFLICT (xuid) DO UPDATE SET
            gamertag = CASE 
                WHEN excluded.gamertag != '' THEN excluded.gamertag 
                ELSE xuid_aliases.gamertag 
            END,
            last_seen = GREATEST(xuid_aliases.last_seen, excluded.last_seen),
            updated_at = CURRENT_TIMESTAMP
    """).rowcount
```

**Commande** :
```bash
python scripts/backfill_xuid_aliases.py --all --source teammates
```

**Résultat attendu** : ~853 aliases pour JGtm (tous les coéquipiers)

#### Étape 1.2 : Backfill depuis highlight_events (plus complet, nettoyage requis)

```python
def backfill_from_highlight_events(conn) -> int:
    """Peuple xuid_aliases depuis highlight_events avec nettoyage."""
    return conn.execute("""
        INSERT INTO xuid_aliases (xuid, gamertag, last_seen, source, updated_at)
        SELECT DISTINCT
            xuid,
            -- Nettoyer les caractères non-ASCII
            regexp_replace(gamertag, '[^\\x20-\\x7E]', '', 'g') AS clean_gamertag,
            MAX(time_ms) AS last_seen,
            'highlight_events',
            CURRENT_TIMESTAMP
        FROM highlight_events
        WHERE xuid IS NOT NULL 
          AND gamertag IS NOT NULL
          AND LENGTH(regexp_replace(gamertag, '[^\\x20-\\x7E]', '', 'g')) >= 3
        GROUP BY xuid, regexp_replace(gamertag, '[^\\x20-\\x7E]', '', 'g')
        ON CONFLICT (xuid) DO NOTHING  -- Ne pas écraser les données propres
    """).rowcount
```

**Commande** :
```bash
python scripts/backfill_xuid_aliases.py --all --source highlight_events
```

**Résultat attendu** : ~4000+ aliases supplémentaires (adversaires)

#### Étape 1.3 : Backfill via API (le plus propre, mais lent)

```python
async def backfill_from_api(conn, client, match_ids: list[str]) -> int:
    """Récupère les gamertags depuis l'API pour les matchs."""
    count = 0
    for match_id in match_ids:
        stats = await client.get_match_stats(match_id)
        for player in stats.get("Players", []):
            xuid = extract_xuid(player)
            gamertag = player.get("PlayerGamertag")
            if xuid and gamertag:
                conn.execute("""
                    INSERT INTO xuid_aliases (xuid, gamertag, source, updated_at)
                    VALUES (?, ?, 'api', CURRENT_TIMESTAMP)
                    ON CONFLICT (xuid) DO UPDATE SET
                        gamertag = excluded.gamertag,
                        updated_at = CURRENT_TIMESTAMP
                """, [xuid, gamertag])
                count += 1
    return count
```

**Commande** :
```bash
python scripts/backfill_data.py --all --force-aliases
```

### Fichiers à modifier

| Fichier | Modification |
|---------|--------------|
| `scripts/backfill_xuid_aliases.py` | Créer (nouveau script) |
| `scripts/backfill_data.py` | Ajouter option `--source` |
| `src/data/sync/engine.py` | S'assurer que sync peuple xuid_aliases |

### Tests

```bash
# Vérifier le peuplement
python -c "
import duckdb
conn = duckdb.connect('data/players/JGtm/stats.duckdb')
print(conn.execute('SELECT COUNT(*) FROM xuid_aliases').fetchone())
print(conn.execute('SELECT * FROM xuid_aliases LIMIT 5').fetchdf())
"
```

### Dépendances
- Aucune dépendance externe

### Estimation
- **Implémentation** : 1-2 heures
- **Exécution backfill** : 5-10 minutes par joueur

---

## 🔴 PRIORITÉ 2 : match_participants (Critique)

### Problème
La table `match_participants` n'existe pas. Elle devrait stocker TOUS les joueurs de chaque match avec leur équipe.

### Impact détaillé

| Feature | Fichier | Impact |
|---------|---------|--------|
| **Mes Coéquipiers** | `src/ui/pages/teammates.py` | ❌ `load_same_team_match_ids()` retourne vide |
| **Session Trio** | `src/ui/pages/teammates.py` | ❌ Impossible de trouver les matchs en commun |
| **Dernière session trio** | `src/ui/pages/teammates.py` | ❌ Idem |
| **Roster avec équipes** | `src/ui/widgets/match_view_players.py` | ❌ Ne sait pas qui est dans quelle équipe |
| **Stats coéquipier** | `src/ui/pages/teammates.py` | ❌ Impossible de charger depuis sa propre DB |
| **Win rate avec ami** | Futur | ❌ Impossible de calculer |

### Architecture legacy vs v4

**Legacy SQLite** : Le `ResponseBody` JSON contenait TOUS les joueurs
```python
# Fonctionnait car ResponseBody avait $.Players[] avec tout le monde
players = json.loads(row["ResponseBody"])["Players"]
for p in players:
    team_id = p["LastTeamId"]
    outcome = p["Outcome"]
```

**DuckDB v4** : `match_stats` ne contient QUE le joueur principal
```python
# NE FONCTIONNE PAS - match_stats n'a que mes stats !
# Aucune info sur les coéquipiers/adversaires
```

### Plan d'implémentation

#### Étape 2.1 : Créer le schéma de la table

**Fichier** : `src/data/sync/engine.py`

```python
# Ajouter dans SCHEMA (après highlight_events)
"""
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
"""
```

#### Étape 2.2 : Créer le modèle Pydantic

**Fichier** : `src/data/sync/models.py`

```python
class MatchParticipantRow(BaseModel):
    """Participant d'un match (stocké pour chaque joueur du match)."""
    match_id: str
    xuid: str
    team_id: int | None = None
    outcome: int | None = None  # 2=Won, 3=Lost, 4=Tied
    gamertag: str | None = None

    model_config = ConfigDict(frozen=True)
```

#### Étape 2.3 : Créer le transformateur

**Fichier** : `src/data/sync/transformers.py`

```python
def extract_participants(match_json: dict[str, Any]) -> list[MatchParticipantRow]:
    """Extrait tous les participants d'un match.
    
    Source : MatchStats.Players[] (JSON API propre).
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
        gamertag = _normalize_gamertag(player.get("PlayerGamertag"))
        
        rows.append(MatchParticipantRow(
            match_id=match_id,
            xuid=xuid,
            team_id=team_id,
            outcome=outcome,
            gamertag=gamertag,
        ))
    
    return rows
```

#### Étape 2.4 : Intégrer dans le sync engine

**Fichier** : `src/data/sync/engine.py`

```python
def _process_single_match(self, match_id: str, ...) -> dict:
    # ... code existant ...
    
    # Extraire les participants (NOUVEAU)
    participant_rows = extract_participants(stats_json)
    
    # ... insertion match_stats, medals, etc ...
    
    # Insérer les participants
    if participant_rows:
        self._insert_participant_rows(participant_rows)
        result["participants"] = len(participant_rows)
    
    return result

def _insert_participant_rows(self, rows: list[MatchParticipantRow]) -> int:
    """Insère les participants dans la table."""
    if not rows:
        return 0
    
    conn = self._get_connection()
    inserted = 0
    for row in rows:
        try:
            conn.execute("""
                INSERT INTO match_participants (match_id, xuid, team_id, outcome, gamertag)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (match_id, xuid) DO UPDATE SET
                    team_id = excluded.team_id,
                    outcome = excluded.outcome,
                    gamertag = COALESCE(excluded.gamertag, match_participants.gamertag)
            """, [row.match_id, row.xuid, row.team_id, row.outcome, row.gamertag])
            inserted += 1
        except Exception:
            pass
    return inserted
```

#### Étape 2.5 : Script de backfill

**Fichier** : `scripts/backfill_match_participants.py` (nouveau)

```python
async def backfill_participants(
    conn,
    client: SPNKrAPIClient,
    match_ids: list[str],
    progress_callback=None,
) -> dict:
    """Backfill match_participants pour les matchs existants."""
    results = {"processed": 0, "participants": 0, "errors": 0}
    
    for i, match_id in enumerate(match_ids):
        try:
            # Récupérer les stats du match depuis l'API
            stats_json = await client.get_match_stats(match_id)
            if not stats_json:
                results["errors"] += 1
                continue
            
            # Extraire et insérer les participants
            participant_rows = extract_participants(stats_json)
            for row in participant_rows:
                conn.execute("""
                    INSERT INTO match_participants (match_id, xuid, team_id, outcome, gamertag)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT (match_id, xuid) DO NOTHING
                """, [row.match_id, row.xuid, row.team_id, row.outcome, row.gamertag])
            
            results["processed"] += 1
            results["participants"] += len(participant_rows)
            
        except Exception as e:
            results["errors"] += 1
        
        if progress_callback:
            progress_callback(i + 1, len(match_ids))
    
    return results
```

**Commande** :
```bash
# Backfill pour un joueur
python scripts/backfill_match_participants.py --gamertag JGtm

# Backfill pour tous
python scripts/backfill_match_participants.py --all

# Dry-run
python scripts/backfill_match_participants.py --all --dry-run
```

#### Étape 2.6 : Mettre à jour le repository

**Fichier** : `src/data/repositories/duckdb_repo.py`

```python
def load_same_team_match_ids(self, teammate_xuid: str) -> list[str]:
    """Retourne les match_id où les deux joueurs étaient dans la même équipe."""
    conn = self._get_connection()
    
    if self._has_table("match_participants"):
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
    
    # Fallback : retourner vide si table absente
    return []

def load_match_roster(self, match_id: str) -> list[dict]:
    """Retourne tous les participants d'un match avec équipes."""
    conn = self._get_connection()
    
    if self._has_table("match_participants"):
        result = conn.execute("""
            SELECT 
                mp.xuid,
                COALESCE(xa.gamertag, mp.gamertag) as gamertag,
                mp.team_id,
                mp.outcome
            FROM match_participants mp
            LEFT JOIN xuid_aliases xa ON mp.xuid = xa.xuid
            WHERE mp.match_id = ?
            ORDER BY mp.team_id, mp.gamertag
        """, [match_id])
        return [dict(row) for row in result.fetchall()]
    
    return []
```

### Fichiers à modifier/créer

| Fichier | Action |
|---------|--------|
| `src/data/sync/engine.py` | Modifier - Ajouter schéma + insertion |
| `src/data/sync/models.py` | Modifier - Ajouter MatchParticipantRow |
| `src/data/sync/transformers.py` | Modifier - Ajouter extract_participants |
| `src/data/repositories/duckdb_repo.py` | Modifier - Ajouter méthodes |
| `scripts/backfill_match_participants.py` | Créer (nouveau) |

### Tests

```python
# Test unitaire
def test_extract_participants():
    match_json = {
        "MatchId": "test-123",
        "Players": [
            {"PlayerId": "xuid(123)", "LastTeamId": 0, "Outcome": 2, "PlayerGamertag": "Player1"},
            {"PlayerId": "xuid(456)", "LastTeamId": 1, "Outcome": 3, "PlayerGamertag": "Player2"},
        ]
    }
    rows = extract_participants(match_json)
    assert len(rows) == 2
    assert rows[0].team_id == 0
    assert rows[1].team_id == 1
```

### Dépendances
- Dépend de la Priorité 1 (xuid_aliases) pour la résolution des noms

### Estimation
- **Implémentation** : 3-4 heures
- **Backfill** : 30-60 minutes par joueur (appels API)

---

## 🔴 PRIORITÉ 3 : killer_victim_pairs (Important)

### Problème
La table `killer_victim_pairs` est vide. Elle devrait stocker qui a tué qui dans chaque match.

### Impact détaillé

| Feature | Fichier | Impact |
|---------|---------|--------|
| **Widget Némésis** | `src/ui/widgets/match_view_players.py` | ❌ Pas de données pour calculer le némésis |
| **Widget Souffre-douleur** | `src/ui/widgets/match_view_players.py` | ❌ Idem |
| **Statistiques de duel** | Futur | ❌ Impossible |
| **Heatmap des kills** | Futur | ❌ Impossible |

### Source de données

Les `highlight_events` contiennent les événements de type `Kill` et `Death` :
```json
{
    "event_type": "Kill",
    "xuid": "2533274823110022",  // Killer
    "time_ms": 45000
}
{
    "event_type": "Death", 
    "xuid": "2533274858283686",  // Victim
    "time_ms": 45000  // Même timestamp = même événement
}
```

### Plan d'implémentation

#### Étape 3.1 : Vérifier le schéma existant

Le schéma existe déjà dans `engine.py` :
```sql
CREATE TABLE IF NOT EXISTS killer_victim_pairs (
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
```

#### Étape 3.2 : Algorithme d'extraction

**Fichier** : `scripts/backfill_killer_victim_pairs.py`

```python
def extract_killer_victim_pairs_from_events(
    conn,
    match_id: str,
    my_xuid: str,
    tolerance_ms: int = 5,
) -> list[dict]:
    """Extrait les paires killer/victim depuis highlight_events.
    
    Algorithme :
    1. Récupérer tous les Kill et Death du match
    2. Pour chaque Kill, trouver le Death correspondant (même time_ms ± tolérance)
    3. Créer une paire (killer_xuid, victim_xuid)
    """
    # Récupérer les events
    events = conn.execute("""
        SELECT event_type, xuid, gamertag, time_ms
        FROM highlight_events
        WHERE match_id = ?
          AND event_type IN ('Kill', 'Death')
        ORDER BY time_ms
    """, [match_id]).fetchall()
    
    kills = [e for e in events if e[0] == 'Kill']
    deaths = [e for e in events if e[0] == 'Death']
    
    pairs = []
    used_deaths = set()
    
    for kill in kills:
        killer_xuid = kill[1]
        killer_gamertag = kill[2]
        kill_time = kill[3]
        
        # Trouver la mort correspondante
        for i, death in enumerate(deaths):
            if i in used_deaths:
                continue
            
            victim_xuid = death[1]
            death_time = death[3]
            
            # Même timestamp ± tolérance
            if abs(kill_time - death_time) <= tolerance_ms:
                # Éviter auto-kill (suicide)
                if killer_xuid != victim_xuid:
                    pairs.append({
                        "match_id": match_id,
                        "killer_xuid": killer_xuid,
                        "killer_gamertag": killer_gamertag,
                        "victim_xuid": victim_xuid,
                        "victim_gamertag": death[2],
                        "time_ms": kill_time,
                    })
                    used_deaths.add(i)
                    break
    
    return pairs
```

#### Étape 3.3 : Script de backfill complet

**Commande existante** :
```bash
python scripts/backfill_killer_victim_pairs.py --gamertag JGtm
python scripts/backfill_killer_victim_pairs.py --all
```

### Fichiers à modifier

| Fichier | Action |
|---------|--------|
| `scripts/backfill_killer_victim_pairs.py` | Vérifier/améliorer |
| `src/analysis/killer_victim.py` | Utiliser les données |

### Estimation
- **Implémentation** : 1 heure (script existe déjà)
- **Exécution** : 5-15 minutes par joueur (local, pas d'API)

---

## 🔴 PRIORITÉ 4 : antagonists (Important)

### Problème
La table `antagonists` est vide. Elle devrait contenir les stats agrégées de némésis/victimes.

### Impact détaillé

| Feature | Fichier | Impact |
|---------|---------|--------|
| **Section Antagonistes** | `src/ui/pages/home.py` | ❌ Widget vide |
| **Top Killer (qui m'a le plus tué)** | `src/ui/widgets/antagonists.py` | ❌ Pas de données |
| **Top Victim (qui j'ai le plus tué)** | `src/ui/widgets/antagonists.py` | ❌ Pas de données |
| **Net kills par adversaire** | Futur | ❌ Impossible |

### Plan d'implémentation

#### Étape 4.1 : Schéma existant

```sql
CREATE TABLE IF NOT EXISTS antagonists (
    opponent_xuid VARCHAR PRIMARY KEY,
    opponent_gamertag VARCHAR,
    times_killed INTEGER DEFAULT 0,      -- Fois où je l'ai tué
    times_killed_by INTEGER DEFAULT 0,   -- Fois où il m'a tué
    matches_against INTEGER DEFAULT 0,
    last_encounter TIMESTAMP,
    net_kills INTEGER GENERATED ALWAYS AS (times_killed - times_killed_by) STORED
);
```

#### Étape 4.2 : Script de calcul

**Fichier** : `scripts/compute_antagonists.py` (nouveau ou existant)

```python
def compute_antagonists_from_kvp(conn, my_xuid: str) -> int:
    """Calcule les antagonists depuis killer_victim_pairs."""
    
    # Vider et recalculer
    conn.execute("DELETE FROM antagonists")
    
    # Calculer depuis killer_victim_pairs
    return conn.execute("""
        INSERT INTO antagonists (
            opponent_xuid, 
            opponent_gamertag, 
            times_killed, 
            times_killed_by, 
            matches_against,
            last_encounter
        )
        WITH my_kills AS (
            SELECT 
                victim_xuid as opponent_xuid,
                victim_gamertag as opponent_gamertag,
                COUNT(*) as times_killed,
                COUNT(DISTINCT match_id) as matches_as_killer,
                MAX(created_at) as last_kill
            FROM killer_victim_pairs
            WHERE killer_xuid = ?
            GROUP BY victim_xuid, victim_gamertag
        ),
        my_deaths AS (
            SELECT 
                killer_xuid as opponent_xuid,
                killer_gamertag as opponent_gamertag,
                COUNT(*) as times_killed_by,
                COUNT(DISTINCT match_id) as matches_as_victim,
                MAX(created_at) as last_death
            FROM killer_victim_pairs
            WHERE victim_xuid = ?
            GROUP BY killer_xuid, killer_gamertag
        )
        SELECT 
            COALESCE(k.opponent_xuid, d.opponent_xuid) as opponent_xuid,
            COALESCE(k.opponent_gamertag, d.opponent_gamertag) as opponent_gamertag,
            COALESCE(k.times_killed, 0) as times_killed,
            COALESCE(d.times_killed_by, 0) as times_killed_by,
            COALESCE(k.matches_as_killer, 0) + COALESCE(d.matches_as_victim, 0) as matches_against,
            GREATEST(k.last_kill, d.last_death) as last_encounter
        FROM my_kills k
        FULL OUTER JOIN my_deaths d ON k.opponent_xuid = d.opponent_xuid
    """, [my_xuid, my_xuid]).rowcount
```

**Commande** :
```bash
python scripts/compute_antagonists.py --gamertag JGtm
python scripts/compute_antagonists.py --all
```

### Dépendances
- **Dépend de** : Priorité 3 (killer_victim_pairs doit être peuplé)
- **Dépend de** : Priorité 1 (xuid_aliases pour les gamertags)

### Estimation
- **Implémentation** : 1-2 heures
- **Exécution** : < 1 minute par joueur (calcul local)

---

## 🟠 PRIORITÉ 5 : maps dans metadata (Moyen)

### Problème
La table `maps` dans `metadata.duckdb` est vide (0 lignes).

### Impact détaillé

| Feature | Fichier | Impact |
|---------|---------|--------|
| **Résolution nom de carte** | `src/data/sync/transformers.py` | ⚠️ Fallback sur PublicName de l'API |
| **Filtre par carte** | `src/ui/pages/*.py` | ⚠️ Utilise les noms des matchs (OK) |
| **Stats par carte** | `mv_map_stats` | ⚠️ Fonctionne car utilise map_name de match_stats |
| **Thumbnails des cartes** | `src/ui/widgets/` | ⚠️ Matching par nom approximatif |

### Plan d'implémentation

#### Étape 5.1 : Script d'ingestion

**Fichier** : `scripts/ingest_halo_data.py`

```python
async def ingest_maps(client: SPNKrAPIClient, conn) -> int:
    """Ingère les définitions de cartes depuis l'API."""
    maps_data = await client.get_maps()  # ou get_map_variants()
    
    count = 0
    for map_info in maps_data:
        asset_id = map_info.get("AssetId")
        version_id = map_info.get("VersionId")
        public_name = map_info.get("PublicName")
        description = map_info.get("Description")
        
        conn.execute("""
            INSERT INTO maps (asset_id, version_id, public_name, description, created_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT (asset_id) DO UPDATE SET
                public_name = excluded.public_name,
                description = excluded.description
        """, [asset_id, version_id, public_name, description])
        count += 1
    
    return count
```

#### Étape 5.2 : Alternative - Extraction depuis match_stats

```python
def extract_maps_from_match_stats(meta_conn, player_conns: list) -> int:
    """Extrait les cartes uniques depuis les match_stats de tous les joueurs."""
    
    all_maps = set()
    for conn in player_conns:
        result = conn.execute("""
            SELECT DISTINCT map_id, map_name
            FROM match_stats
            WHERE map_id IS NOT NULL AND map_name IS NOT NULL
        """)
        for row in result.fetchall():
            all_maps.add((row[0], row[1]))
    
    count = 0
    for map_id, map_name in all_maps:
        meta_conn.execute("""
            INSERT INTO maps (asset_id, public_name, created_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT (asset_id) DO NOTHING
        """, [map_id, map_name])
        count += 1
    
    return count
```

**Commande** :
```bash
# Depuis l'API
python scripts/ingest_halo_data.py --maps

# Depuis les données existantes
python scripts/ingest_halo_data.py --maps --from-match-stats
```

### Estimation
- **Implémentation** : 1 heure
- **Exécution** : < 5 minutes

---

## 🟠 PRIORITÉ 6 : players et friends dans metadata (Moyen)

### Problème
Les tables `players` et `friends` dans `metadata.duckdb` sont vides.

### Impact détaillé

| Feature | Impact |
|---------|--------|
| **Liste des joueurs connus** | ⚠️ Pas de registre global |
| **Liste d'amis** | ⚠️ Pas de filtrage par amis possible |
| **Suggestions de coéquipiers** | ⚠️ Pas de données |

### Plan d'implémentation

#### Étape 6.1 : Peupler players depuis les profils

```python
def sync_players_from_profiles(meta_conn, profiles: dict) -> int:
    """Synchronise les joueurs depuis db_profiles.json."""
    count = 0
    for gamertag, profile in profiles.items():
        meta_conn.execute("""
            INSERT INTO players (xuid, gamertag, last_seen_at, created_at)
            VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (xuid) DO UPDATE SET
                gamertag = excluded.gamertag,
                last_seen_at = CURRENT_TIMESTAMP
        """, [profile["xuid"], gamertag])
        count += 1
    return count
```

#### Étape 6.2 : Peupler friends depuis l'API Xbox

```python
async def sync_friends(client, meta_conn, owner_xuid: str) -> int:
    """Synchronise la liste d'amis depuis l'API Xbox."""
    friends = await client.get_friends(owner_xuid)
    
    count = 0
    for friend in friends:
        meta_conn.execute("""
            INSERT INTO friends (owner_xuid, friend_xuid, friend_gamertag, added_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT (owner_xuid, friend_xuid) DO UPDATE SET
                friend_gamertag = excluded.friend_gamertag
        """, [owner_xuid, friend["xuid"], friend["gamertag"]])
        count += 1
    
    return count
```

### Estimation
- **Implémentation** : 1-2 heures
- **Exécution** : < 5 minutes

---

## 🟡 PRIORITÉ 7 : sessions (Nice to have)

### Problème
La table `sessions` est vide. Les sessions groupent les matchs consécutifs en "sessions de jeu".

### Impact détaillé

| Feature | Impact |
|---------|--------|
| **Vue par session** | ⚠️ Pas de regroupement des matchs |
| **Stats de session** | ⚠️ mv_session_stats vide |
| **Performance par session** | ⚠️ Pas de tendance |
| **"Dernière session"** | ⚠️ Retourne tous les matchs récents |

### Plan d'implémentation

#### Algorithme de détection des sessions

```python
def compute_sessions(conn, session_gap_minutes: int = 30) -> int:
    """Calcule les sessions basées sur les gaps entre matchs.
    
    Règle : Si > 30 min entre deux matchs, nouvelle session.
    """
    # Récupérer les matchs triés
    matches = conn.execute("""
        SELECT match_id, start_time
        FROM match_stats
        ORDER BY start_time
    """).fetchall()
    
    sessions = []
    current_session = {"start": None, "end": None, "matches": []}
    
    for match_id, start_time in matches:
        if current_session["end"] is None:
            # Premier match
            current_session["start"] = start_time
            current_session["end"] = start_time
            current_session["matches"].append(match_id)
        else:
            gap = (start_time - current_session["end"]).total_seconds() / 60
            if gap > session_gap_minutes:
                # Nouvelle session
                sessions.append(current_session)
                current_session = {
                    "start": start_time,
                    "end": start_time,
                    "matches": [match_id]
                }
            else:
                # Même session
                current_session["end"] = start_time
                current_session["matches"].append(match_id)
    
    if current_session["matches"]:
        sessions.append(current_session)
    
    # Insérer les sessions
    for i, session in enumerate(sessions):
        session_id = f"session_{i+1}"
        conn.execute("""
            INSERT INTO sessions (session_id, start_time, end_time, match_count)
            VALUES (?, ?, ?, ?)
        """, [session_id, session["start"], session["end"], len(session["matches"])])
        
        # Mettre à jour les matchs
        for match_id in session["matches"]:
            conn.execute("""
                UPDATE match_stats SET session_id = ? WHERE match_id = ?
            """, [session_id, match_id])
    
    return len(sessions)
```

**Commande** :
```bash
python scripts/compute_sessions.py --gamertag JGtm --gap-minutes 30
python scripts/compute_sessions.py --all
```

### Estimation
- **Implémentation** : 2 heures
- **Exécution** : < 1 minute par joueur

---

## 🟡 PRIORITÉ 8 : career_progression et skill_history (Nice to have)

### Problème
Les tables `career_progression` et `skill_history` sont vides.

### Impact détaillé

| Feature | Impact |
|---------|--------|
| **Graphique de progression** | ⚠️ Pas d'historique |
| **Rang actuel** | ⚠️ Doit appeler l'API à chaque fois |
| **Historique MMR** | ⚠️ Pas de tendance |
| **Graphique CSR** | ⚠️ Pas de données |

### Plan d'implémentation

#### Étape 8.1 : Synchroniser career_progression

```python
async def sync_career_progression(client, conn, xuid: str) -> dict:
    """Synchronise la progression de carrière depuis l'API."""
    career = await client.get_career_rank(xuid)
    
    if career:
        conn.execute("""
            INSERT INTO career_progression (
                xuid, rank, rank_name, rank_tier, 
                current_xp, xp_for_next_rank, xp_total,
                is_max_rank, recorded_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, [
            xuid,
            career.get("Rank"),
            career.get("RankName"),
            career.get("TierName"),
            career.get("CurrentXp"),
            career.get("XpForNextRank"),
            career.get("TotalXp"),
            career.get("IsMaxRank", False),
        ])
        return {"success": True}
    
    return {"success": False}
```

#### Étape 8.2 : Synchroniser skill_history

```python
async def sync_skill_history(client, conn, xuid: str, playlist_id: str) -> dict:
    """Synchronise l'historique de skill pour une playlist."""
    skill = await client.get_playlist_csr(xuid, playlist_id)
    
    if skill:
        conn.execute("""
            INSERT INTO skill_history (
                playlist_id, recorded_at, csr, tier, division, matches_played
            )
            VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?, ?)
            ON CONFLICT (playlist_id, recorded_at) DO NOTHING
        """, [
            playlist_id,
            skill.get("Csr"),
            skill.get("Tier"),
            skill.get("Division"),
            skill.get("MatchesPlayed"),
        ])
        return {"success": True}
    
    return {"success": False}
```

**Commandes** :
```bash
# Sync carrière
python scripts/sync.py --gamertag JGtm --with-career

# Sync skill (toutes les playlists ranked)
python scripts/sync.py --gamertag JGtm --with-skill

# Tout en un
python scripts/sync.py --all --with-career --with-skill
```

### Estimation
- **Implémentation** : 2-3 heures
- **Exécution** : 1-2 minutes par joueur (appels API)

---

## 📋 Résumé des tâches

| # | Tâche | Priorité | Effort | Dépendances | État |
|---|-------|----------|--------|-------------|------|
| 1 | Backfill xuid_aliases | 🔴 Critique | 2h | Aucune | ✅ Implémenté |
| 1b | Résoudre XUIDs manquants via API | 🔴 Critique | 1h | #1 | ✅ Implémenté |
| 2 | Créer + backfill match_participants | 🔴 Critique | 4h | #1 | ✅ Implémenté |
| 3 | Backfill killer_victim_pairs | 🔴 Important | 1h | Aucune | ✅ Implémenté |
| 4 | Compute antagonists | 🔴 Important | 2h | #3 | ✅ Script existe |
| 5 | Ingérer maps dans metadata | 🟠 Moyen | 1h | Aucune | 🔲 À faire |
| 6 | Peupler players/friends | 🟠 Moyen | 2h | Aucune | 🔲 À faire |
| 7 | Compute sessions | 🟡 Nice to have | 2h | Aucune | 🔲 À faire |
| 8 | Sync career + skill history | 🟡 Nice to have | 3h | Aucune | 🔲 À faire |

**Total estimé** : 17-20 heures de développement
**Progression** : 5/9 tâches implémentées (code)

---

## 🚀 Ordre d'exécution recommandé

### Scripts existants confirmés

| Script | Existe | Options disponibles |
|--------|--------|---------------------|
| `backfill_data.py` | ✅ | `--force-aliases`, `--participants`, `--killer-victim`, `--all-data` |
| `backfill_killer_victim_pairs.py` | ✅ | `--gamertag`, `--all`, `--force` |
| `populate_antagonists.py` | ✅ | `--gamertag`, `--all`, `--force` |
| `resolve_missing_gamertags.py` | ✅ | `--gamertag`, `--all`, `--limit`, `--dry-run` |
| `recover_from_sqlite.py` | ✅ | `--gamertag`, `--all`, `--dry-run` |
| `sync.py` | ✅ | Calcule les sessions automatiquement |
| `ingest_halo_data.py` | ✅ | Pour les référentiels |
| `diagnose_migration_gaps.py` | ✅ | `--all`, `--json` |

### Commandes à exécuter (dans l'ordre)

```bash
# ============================================
# JOUR 1 - CRITIQUES (offline possible)
# ============================================

# 1. Backfill xuid_aliases depuis les données existantes
#    (extrait depuis highlight_events et teammates_aggregate)
python scripts/backfill_data.py --all --force-aliases

# 2. Backfill killer_victim_pairs depuis highlight_events
#    (calcule les paires killer/victim)
python scripts/backfill_killer_victim_pairs.py --all

# 3. Calculer les antagonists depuis killer_victim_pairs
python scripts/populate_antagonists.py --all --force

# ============================================
# JOUR 2 - IMPORTANTS (nécessite API)
# ============================================

# 4. Backfill match_participants (récupère les participants via API)
#    ⚠️ ATTENTION: Fait des appels API pour chaque match !
#    Pour ~450 matchs = ~15-30 minutes par joueur
python scripts/backfill_data.py --player JGtm --participants
python scripts/backfill_data.py --player Madina97294 --participants
python scripts/backfill_data.py --player Chocoboflor --participants
python scripts/backfill_data.py --player XxDaemonGamerxX --participants

# Ou pour tous en une commande (plus long)
python scripts/backfill_data.py --all --participants

# 5. Ingérer les référentiels (maps, playlists, etc.)
python scripts/ingest_halo_data.py

# ============================================
# JOUR 3 - NICE TO HAVE
# ============================================

# 6. Sync avec calcul de sessions (sessions calculées automatiquement)
#    Note: sync.py appelle compute_sessions() automatiquement
python scripts/sync.py --delta --gamertag JGtm

# 7. Sync avec career progression et skill history
python scripts/sync.py --delta --gamertag JGtm --with-career --with-skill

# ============================================
# VALIDATION FINALE
# ============================================

# Vérifier l'état après les corrections
python scripts/diagnose_migration_gaps.py --all

# Rapport JSON détaillé
python scripts/diagnose_migration_gaps.py --all --json --output .ai/diagnostics/POST_RECOVERY_REPORT.json
```

### Temps d'exécution estimés

| Étape | Commande | Durée estimée | API ? |
|-------|----------|---------------|-------|
| 1 | force-aliases | 5-10 min | Non |
| 2 | killer_victim_pairs | 5-15 min | Non |
| 3 | antagonists | 1-2 min | Non |
| 4 | participants | 30-60 min/joueur | **Oui** |
| 5 | ingest_halo_data | 2-5 min | Oui |
| 6 | sync sessions | 2-5 min | Oui |
| 7 | career+skill | 2-5 min | Oui |

**Total** : ~2-3 heures pour tous les joueurs

---

## ✅ Critères de succès

| Table | Cible |
|-------|-------|
| xuid_aliases | > 1000 entrées par joueur |
| match_participants | = matchs × ~8 joueurs |
| killer_victim_pairs | > 0 entrées |
| antagonists | > 100 entrées par joueur |
| maps | > 20 entrées |
| sessions | > 0 entrées |
| career_progression | ≥ 1 entrée par joueur |
| skill_history | ≥ 1 entrée par playlist ranked |

---

---

## 📝 Mise à jour 2026-02-05 : Résolution XUIDs via API SPNKr

### Nouveau script : `resolve_missing_gamertags.py`

Script créé pour résoudre les XUIDs manquants dans `xuid_aliases` via l'API SPNKr.

**Fonctionnalités :**
- Utilise `client.profile.get_users_by_id()` pour résoudre XUIDs → gamertags en batch
- Gestion du rate limiting (429) avec retry automatique
- Filtrage des XUIDs invalides (données corrompues)
- Support `.env.local` pour les credentials OAuth Azure

**Usage :**
```bash
# Dry-run pour voir les XUIDs manquants
python scripts/resolve_missing_gamertags.py --all --dry-run

# Résoudre pour un joueur
python scripts/resolve_missing_gamertags.py --gamertag Madina97294

# Résoudre pour tous (attention: rate limiting)
python scripts/resolve_missing_gamertags.py --all

# Limiter le nombre de XUIDs
python scripts/resolve_missing_gamertags.py --gamertag Madina97294 --limit 100
```

**Résultats du 2026-02-05 :**

| Joueur | XUIDs manquants | Statut |
|--------|-----------------|--------|
| Chocoboflor | 0 | ✅ Complet |
| JGtm | 0 | ✅ Complet |
| Madina97294 | ~8600 | 🔄 Rate limited |
| XxDaemonGamerxX | ~8 (invalides) | ⚠️ Données corrompues |

**Limitations API :**
- L'API profile est fortement rate-limited (~1 req/sec)
- Pour 8600 XUIDs avec batches de 20 : ~430 requêtes × 3s = ~20 minutes
- Nécessite une exécution progressive avec pauses

**Prérequis :**
- Fichier `.env.local` avec credentials OAuth Azure :
  ```
  SPNKR_AZURE_CLIENT_ID=...
  SPNKR_AZURE_CLIENT_SECRET=...
  SPNKR_OAUTH_REFRESH_TOKEN=...
  ```

---

*Document créé le 2026-02-05*
*Dernière mise à jour : 2026-02-05 (ajout resolve_missing_gamertags.py)*
