# Analyse : Optimisation de la Gestion des Matchs Partagés

> **Auteur** : Analyse IA  
> **Date** : 2026-02-14  
> **Problématique** : Duplication massive des données de matchs entre joueurs partageant des matchs communs  
> **Impact** : Appels API redondants, stockage inefficace, backfill coûteux

---

## 🎯 Problématique

### Situation Actuelle

Les joueurs qui jouent ensemble partagent un taux élevé de matchs communs :

| Joueur | Matchs Partagés avec Chocoboflor | % |
|--------|----------------------------------|---|
| Madina97294 | ~95% | 95% |
| JGtm | ~75% | 75% |
| xxdameongamerxx | ~100% | 100% |

**Inefficacités observées** :

1. ❌ **Duplication des données** : Un match_id donné est stocké N fois (une fois par joueur participant)
2. ❌ **Appels API redondants** : Si on sync Madina97294 puis Chocoboflor, on télécharge les mêmes 95% de matchs deux fois
3. ❌ **Backfill inefficace** : Impossible de savoir si les données d'un match ont déjà été récupérées pour un autre joueur
4. ❌ **Détection manquante** : Aucun mécanisme pour identifier qu'un match est déjà connu dans le système

### Architecture Actuelle (v4)

```
data/
├── warehouse/
│   └── metadata.duckdb           # Référentiels globaux
│                                  # (playlists, maps, medals_def, etc.)
└── players/
    ├── Chocoboflor/
    │   └── stats.duckdb          # TOUTES les données de ses matchs
    │       ├── match_stats       # → Duplication des matchs communs
    │       ├── match_participants # → Duplication du roster complet
    │       ├── highlight_events  # → Duplication des kills/deaths
    │       ├── medals_earned
    │       └── player_match_stats
    │
    ├── Madina97294/
    │   └── stats.duckdb          # 95% de matchs identiques à Chocoboflor
    │       ├── match_stats       # → DUPLICATION ×2
    │       ├── match_participants # → DUPLICATION ×2
    │       └── highlight_events  # → DUPLICATION ×2
    │
    └── xxdameongamerxx/
        └── stats.duckdb          # 100% de matchs identiques à Chocoboflor
            └── ...               # → DUPLICATION ×3
```

**Conséquence** : Pour un match à 8 joueurs tous trackés, les mêmes données sont stockées 8 fois !

---

## 📊 Analyse des Données par Nature

### Données Spécifiques au Joueur (À conserver dans player DB)

Ces données varient selon le point de vue du joueur :

| Table | Colonnes Spécifiques | Raison |
|-------|---------------------|--------|
| `match_stats` | `outcome`, `kills`, `deaths`, `assists`, `kda`, `accuracy`, `team_id`, `rank`, `personal_score`, `performance_score`, `session_id`, `is_with_friends` | Vision subjective du joueur |
| `medals_earned` | `count` par medal_name_id | Médailles gagnées par le joueur uniquement |
| `player_match_stats` | `team_mmr`, `enemy_mmr`, `kills_expected`, etc. | MMR spécifique au joueur |
| `teammates_aggregate` | Tout | Agrégat depuis le point de vue du joueur |
| `antagonists` | Tout | Rivalités depuis le point de vue du joueur |
| `career_progression` | Tout | Progression personnelle |

### Données Communes au Match (À mutualiser)

Ces données sont **identiques** quel que soit le joueur qui a participé au match :

| Table | Colonnes Communes | Nature |
|-------|------------------|--------|
| `match_stats` | `match_id`, `start_time`, `end_time`, `playlist_id`, `playlist_name`, `map_id`, `map_name`, `game_variant_id`, `pair_id`, `my_team_score`, `enemy_team_score`, `duration_seconds` | Métadonnées du match |
| `match_participants` | **TOUT** (roster complet) | Liste de tous les joueurs avec team, rank, score, K/D/A |
| `highlight_events` | **TOUT** (tous les kills/deaths) | Événements filmés (journal complet du match) |
| `xuid_aliases` | **TOUT** | Mapping xuid → gamertag global |

**Taille estimée de la duplication** :

- 1 match ≈ 10-20 participants (roster)
- 1 match ≈ 50-200 highlight_events
- pour 1000 matchs partagés à 95% → **950 matchs dupliqués** → ~9500 lignes participants + ~95000 events dupliqués !

---

## 🏗️ Solution Proposée : Architecture Hybride Player + Shared

### Nouvelle Structure

```
data/
├── warehouse/
│   ├── metadata.duckdb              # Référentiels (existant)
│   │   ├── playlists
│   │   ├── maps
│   │   ├── medal_definitions
│   │   └── career_ranks
│   │
│   └── shared_matches.duckdb        # ⭐ NOUVEAU : Données communes
│       ├── match_registry           # Registre central des matchs connus
│       ├── match_participants       # Roster complet de tous les matchs
│       ├── highlight_events         # Kills/deaths de tous les matchs
│       ├── xuid_aliases             # Aliases globaux
│       └── match_backfill_meta      # Métadonnées de backfill par match_id
│
└── players/
    ├── Chocoboflor/
    │   └── stats.duckdb             # Données spécifiques au joueur
    │       ├── player_match_stats   # Vue subjective + médailles
    │       │   ├── match_id (PK/FK → shared)
    │       │   ├── xuid
    │       │   ├── outcome          # (mon résultat)
    │       │   ├── team_id          # (mon équipe)
    │       │   ├── kills, deaths, assists, kda
    │       │   ├── accuracy, shots_fired, shots_hit
    │       │   ├── personal_score, performance_score
    │       │   ├── session_id
    │       │   └── ...
    │       ├── medals_earned        # Mes médailles
    │       ├── player_skill_stats   # Mon MMR
    │       ├── teammates_aggregate
    │       ├── antagonists
    │       └── career_progression
    │
    ├── Madina97294/
    │   └── stats.duckdb             # Pointe vers shared_matches pour roster/events
    └── ...
```

### Table `match_registry` (shared_matches.duckdb)

Registre central de tous les matchs connus par le système :

```sql
CREATE TABLE match_registry (
    match_id VARCHAR PRIMARY KEY,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    
    -- Métadonnées du match (communes)
    playlist_id VARCHAR,
    playlist_name VARCHAR,
    map_id VARCHAR,
    map_name VARCHAR,
    pair_id VARCHAR,
    pair_name VARCHAR,
    game_variant_id VARCHAR,
    game_variant_name VARCHAR,
    mode_category VARCHAR,
    is_ranked BOOLEAN,
    is_firefight BOOLEAN,
    duration_seconds INTEGER,
    
    -- Scores des équipes
    team_0_score SMALLINT,
    team_1_score SMALLINT,
    
    -- Métadonnées de backfill
    backfill_completed INTEGER DEFAULT 0,  -- Bitmask des données chargées
    participants_loaded BOOLEAN DEFAULT FALSE,
    events_loaded BOOLEAN DEFAULT FALSE,
    skill_loaded BOOLEAN DEFAULT FALSE,
    
    -- Tracking
    first_sync_by VARCHAR,        -- Gamertag du premier joueur ayant sync ce match
    first_sync_at TIMESTAMP,
    last_updated_at TIMESTAMP,
    player_count SMALLINT,         -- Nombre de joueurs trackés ayant ce match
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_match_registry_time ON match_registry(start_time);
CREATE INDEX idx_match_registry_playlist ON match_registry(playlist_id);
CREATE INDEX idx_match_registry_map ON match_registry(map_id);
```

### Avantages de l'Architecture Hybride

✅ **Élimination de la duplication** :
- `match_participants` : stocké 1 seule fois au lieu de N fois
- `highlight_events` : stocké 1 seule fois au lieu de N fois
- Économie d'espace : ~80-90% pour les joueurs partageant beaucoup de matchs

✅ **Détection intelligente des matchs connus** :
```python
# Avant sync/backfill
match_id = "abc-123"
registry_row = conn.execute(
    "SELECT backfill_completed, participants_loaded, events_loaded 
     FROM shared_matches.match_registry WHERE match_id = ?", 
    (match_id,)
).fetchone()

if registry_row:
    # Match déjà connu !
    if registry_row['participants_loaded']:
        # Skip téléchargement du roster
        pass
    if registry_row['events_loaded']:
        # Skip téléchargement des highlight events
        pass
```

✅ **Optimisation des appels API** :
```python
# Si Chocoboflor sync le match abc-123 :
# → Télécharge + stocke dans shared_matches.duckdb
# → Marque participants_loaded=True, events_loaded=True

# Quand Madina97294 sync ensuite :
# → Détecte que le match existe déjà
# → Récupère SEULEMENT ses stats personnelles (kills, deaths, medals)
# → Réutilise les participants/events depuis shared_matches
# → ÉCONOMIE : 2 appels API évités (/stats OK, /film et /participants skip)
```

✅ **Backfill intelligent** :
```python
# Avant : backfill re-télécharge tout pour chaque joueur
# Après : vérifie d'abord match_registry
def backfill_missing_data(player: str):
    missing_matches = get_matches_missing_data(player)
    
    for match_id in missing_matches:
        registry = get_match_registry(match_id)
        
        if registry and registry['events_loaded']:
            # Les events existent déjà, juste copier depuis shared
            copy_events_from_shared(match_id, player)
        else:
            # Télécharger + stocker dans shared pour tous
            events = api.get_highlight_events(match_id)
            store_events_in_shared(match_id, events)
            mark_events_loaded(match_id)
```

---

## 🔄 Flux de Synchronisation Optimisé

### Sync Delta d'un Joueur

```python
async def sync_player_delta(gamertag: str, xuid: str):
    """Sync incrémentale avec détection des matchs partagés."""
    
    # 1. Récupérer l'historique du joueur
    history = await api.get_match_history(gamertag)
    
    for item in history:
        match_id = item.match_id
        
        # 2. Vérifier si le match existe déjà dans le registre central
        shared_conn = get_shared_matches_connection()
        registry = shared_conn.execute(
            "SELECT * FROM match_registry WHERE match_id = ?",
            (match_id,)
        ).fetchone()
        
        if registry:
            # ✅ Match déjà connu !
            logger.info(f"Match {match_id} déjà dans le registre central")
            
            # 3a. Récupérer SEULEMENT les stats personnelles du joueur
            stats = await api.get_match_stats(match_id)
            player_stats = extract_player_specific_stats(stats, xuid)
            
            # 3b. Insérer dans la DB du joueur
            player_conn = get_player_connection(gamertag)
            player_conn.execute("""
                INSERT OR REPLACE INTO player_match_stats
                (match_id, xuid, outcome, kills, deaths, assists, ...)
                VALUES (?, ?, ?, ...)
            """, player_stats)
            
            # 3c. Backfill sélectif si des données manquent dans shared
            if not registry['participants_loaded']:
                participants = extract_participants(stats)
                store_participants_in_shared(match_id, participants)
                
            if not registry['events_loaded']:
                events = await api.get_highlight_events(match_id)
                store_events_in_shared(match_id, events)
            
            # 3d. Incrémenter player_count dans le registre
            shared_conn.execute("""
                UPDATE match_registry 
                SET player_count = player_count + 1,
                    last_updated_at = CURRENT_TIMESTAMP
                WHERE match_id = ?
            """, (match_id,))
            
        else:
            # ⭐ Nouveau match jamais vu
            logger.info(f"Nouveau match {match_id}, sync complète")
            
            # 4a. Télécharger toutes les données
            stats = await api.get_match_stats(match_id)
            events = await api.get_highlight_events(match_id)
            skill = await api.get_skill_stats(match_id, xuids)
            
            # 4b. Stocker les données communes dans shared_matches
            match_common = extract_match_common_data(stats)
            shared_conn.execute("""
                INSERT INTO match_registry 
                (match_id, start_time, playlist_id, map_id, ..., 
                 first_sync_by, first_sync_at, player_count)
                VALUES (?, ?, ?, ?, ..., ?, CURRENT_TIMESTAMP, 1)
            """, (*match_common, gamertag))
            
            participants = extract_participants(stats)
            store_participants_in_shared(match_id, participants)
            store_events_in_shared(match_id, events)
            
            # 4c. Stocker les données personnelles dans player DB
            player_stats = extract_player_specific_stats(stats, xuid)
            store_player_stats(gamertag, player_stats)
```

### Économie d'Appels API

**Scénario** : Sync de 4 joueurs (Chocoboflor, Madina97294, JGtm, xxdameongamerxx)  
**Matchs** : 1000 matchs partagés à 90%

| Système | API Calls | Détail |
|---------|-----------|--------|
| **Actuel** | 12 000 | 4 joueurs × 1000 matchs × 3 endpoints (stats, events, participants) |
| **Optimisé** | ~3 300 | 1000 matchs × 3 (premier joueur) + 3 × 100 matchs uniques × 3 + 3 × 900 matchs × 1 (stats seulement) |
| **Économie** | **-72%** | **8 700 appels économisés** |

---

## 📋 Plan de Migration

### Phase 1 : Création de l'Infrastructure Shared (Sprint 0)

**Objectifs** :
- ✅ Créer `data/warehouse/shared_matches.duckdb`
- ✅ Définir le schéma `match_registry`, `match_participants`, `highlight_events`
- ✅ Créer les index et contraintes

**Livrables** :
```sql
-- scripts/migration/create_shared_matches_db.sql
CREATE DATABASE IF NOT EXISTS shared_matches;

-- Table principale
CREATE TABLE match_registry ( ... );

-- Tables de données communes
CREATE TABLE match_participants ( ... );
CREATE TABLE highlight_events ( ... );
CREATE TABLE xuid_aliases ( ... );
```

### Phase 2 : Migration des Données Existantes (Sprint 1)

**Script** : `scripts/migration/migrate_to_shared_matches.py`

```python
def migrate_player_to_shared(gamertag: str):
    """Migre les données d'un joueur vers shared_matches."""
    
    player_db = f"data/players/{gamertag}/stats.duckdb"
    shared_db = "data/warehouse/shared_matches.duckdb"
    
    conn_player = duckdb.connect(player_db, read_only=True)
    conn_shared = duckdb.connect(shared_db)
    
    # 1. Extraire les matchs du joueur
    matches = conn_player.execute("""
        SELECT 
            match_id, start_time, end_time,
            playlist_id, map_id, game_variant_id,
            ...
        FROM match_stats
    """).pl()
    
    # 2. Pour chaque match
    for match_row in matches.iter_rows(named=True):
        match_id = match_row['match_id']
        
        # 2a. Vérifier si déjà dans shared
        exists = conn_shared.execute(
            "SELECT 1 FROM match_registry WHERE match_id = ?",
            (match_id,)
        ).fetchone()
        
        if not exists:
            # 2b. Insérer dans match_registry
            conn_shared.execute("""
                INSERT INTO match_registry (
                    match_id, start_time, playlist_id, map_id, ...,
                    first_sync_by, first_sync_at, player_count
                ) VALUES (?, ?, ?, ...)
            """, (match_id, ..., gamertag, ..., 1))
            
            # 2c. Copier match_participants
            participants = conn_player.execute("""
                SELECT * FROM match_participants 
                WHERE match_id = ?
            """, (match_id,)).pl()
            
            conn_shared.execute("""
                INSERT INTO match_participants SELECT * FROM participants
            """)
            
            # 2d. Copier highlight_events
            events = conn_player.execute("""
                SELECT * FROM highlight_events 
                WHERE match_id = ?
            """, (match_id,)).pl()
            
            conn_shared.execute("""
                INSERT INTO highlight_events SELECT * FROM events
            """)
        else:
            # Match déjà migré, incrémenter player_count
            conn_shared.execute("""
                UPDATE match_registry 
                SET player_count = player_count + 1
                WHERE match_id = ?
            """, (match_id,))
    
    conn_player.close()
    conn_shared.commit()
    conn_shared.close()
```

**Ordre de migration** :
1. Chocoboflor (base de référence, le plus de matchs)
2. Madina97294 (95% partagés → peu d'ajouts)
3. JGtm (75% partagés)
4. xxdameongamerxx (100% partagés → 0 ajout)

**Validation** :
```sql
-- Statistiques post-migration
SELECT 
    COUNT(*) as total_matches,
    SUM(player_count) as total_participations,
    AVG(player_count) as avg_players_per_match,
    SUM(CASE WHEN player_count > 1 THEN 1 ELSE 0 END) as shared_matches
FROM match_registry;

-- Résultat attendu :
-- total_matches: ~1050 (au lieu de 4000 dupliqués)
-- avg_players_per_match: ~3.8
-- shared_matches: ~950 (90% partagés)
```

### Phase 3 : Refactoring du Sync Engine (Sprint 2)

**Modifications dans `src/data/sync/engine.py`** :

```python
class DuckDBSyncEngine:
    def __init__(
        self,
        player_db_path: str,
        xuid: str,
        gamertag: str,
        *,
        shared_db_path: str = "data/warehouse/shared_matches.duckdb",  # ⭐ NOUVEAU
    ):
        self._player_db_path = Path(player_db_path)
        self._shared_db_path = Path(shared_db_path)  # ⭐ NOUVEAU
        self._player_connection = None
        self._shared_connection = None  # ⭐ NOUVEAU
    
    def _get_shared_connection(self) -> duckdb.DuckDBPyConnection:
        """Connexion à shared_matches.duckdb."""
        if self._shared_connection is None:
            self._shared_connection = duckdb.connect(str(self._shared_db_path))
        return self._shared_connection
    
    async def _process_single_match(
        self,
        client: SPNKrAPIClient,
        match_id: str,
        options: SyncOptions,
    ) -> dict[str, Any]:
        """Version optimisée avec détection des matchs partagés."""
        
        # 1. Vérifier dans shared_matches
        shared_conn = self._get_shared_connection()
        registry = shared_conn.execute(
            "SELECT * FROM match_registry WHERE match_id = ?",
            (match_id,)
        ).fetchone()
        
        if registry:
            # Match connu → sync allégée
            return await self._process_known_match(
                client, match_id, registry, options
            )
        else:
            # Nouveau match → sync complète
            return await self._process_new_match(
                client, match_id, options
            )
    
    async def _process_known_match(
        self,
        client: SPNKrAPIClient,
        match_id: str,
        registry: dict,
        options: SyncOptions,
    ) -> dict[str, Any]:
        """Traite un match déjà connu (optimisé)."""
        
        logger.info(f"Match {match_id} déjà connu, sync allégée")
        
        # 1. Télécharger SEULEMENT les stats (pas events/participants)
        stats_json = await client.get_match_stats(match_id)
        
        # 2. Extraire données personnelles du joueur
        player_stats = transform_player_match_stats(stats_json, self._xuid)
        
        # 3. Insérer dans player DB
        player_conn = self._get_player_connection()
        self._insert_player_match_stats(player_stats)
        
        # 4. Backfill sélectif si données manquantes dans shared
        if not registry['participants_loaded']:
            participants = extract_participants(stats_json)
            self._insert_participants_to_shared(match_id, participants)
        
        if not registry['events_loaded'] and options.with_highlight_events:
            events = await client.get_highlight_events(match_id)
            self._insert_events_to_shared(match_id, events)
        
        # 5. Mettre à jour le registre
        shared_conn = self._get_shared_connection()
        shared_conn.execute("""
            UPDATE match_registry 
            SET player_count = player_count + 1,
                last_updated_at = CURRENT_TIMESTAMP
            WHERE match_id = ?
        """, (match_id,))
        
        return {"inserted": True, "mode": "known_match"}
    
    async def _process_new_match(
        self,
        client: SPNKrAPIClient,
        match_id: str,
        options: SyncOptions,
    ) -> dict[str, Any]:
        """Traite un nouveau match (sync complète)."""
        
        logger.info(f"Nouveau match {match_id}, sync complète")
        
        # 1. Télécharger toutes les données
        stats_json = await client.get_match_stats(match_id)
        events = []
        if options.with_highlight_events:
            events = await client.get_highlight_events(match_id)
        
        # 2. Extraire et stocker dans shared_matches
        match_common = transform_match_common_data(stats_json)
        participants = extract_participants(stats_json)
        
        shared_conn = self._get_shared_connection()
        
        # 2a. Registre
        shared_conn.execute("""
            INSERT INTO match_registry (
                match_id, start_time, end_time,
                playlist_id, map_id, ...,
                first_sync_by, first_sync_at, player_count,
                participants_loaded, events_loaded
            ) VALUES (?, ?, ?, ..., ?, CURRENT_TIMESTAMP, 1, TRUE, ?)
        """, (*match_common, self._gamertag, len(events) > 0))
        
        # 2b. Participants
        self._insert_participants_to_shared(match_id, participants)
        
        # 2c. Events
        if events:
            self._insert_events_to_shared(match_id, events)
        
        # 3. Stocker données personnelles dans player DB
        player_stats = transform_player_match_stats(stats_json, self._xuid)
        self._insert_player_match_stats(player_stats)
        
        return {"inserted": True, "mode": "new_match"}
```

### Phase 4 : Adaptation de DuckDBRepository (Sprint 3)

**Modifications dans `src/data/repositories/duckdb_repo.py`** :

```python
class DuckDBRepository:
    def __init__(
        self,
        player_db_path: str | Path,
        xuid: str,
        *,
        metadata_db_path: str | Path | None = None,
        shared_db_path: str | Path | None = None,  # ⭐ NOUVEAU
        gamertag: str | None = None,
        read_only: bool = True,
    ):
        # ...
        self._shared_db_path = Path(shared_db_path) if shared_db_path else (
            self._player_db_path.parent.parent.parent / "warehouse" / "shared_matches.duckdb"
        )
    
    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        """Connexion avec ATTACH des DBs shared et metadata."""
        if self._connection is None:
            self._connection = duckdb.connect(
                str(self._player_db_path),
                read_only=self._read_only,
            )
            
            # Attach metadata (existant)
            if self._metadata_db_path.exists():
                self._connection.execute(
                    f"ATTACH DATABASE '{self._metadata_db_path}' AS meta (READ_ONLY)"
                )
            
            # ⭐ NOUVEAU : Attach shared_matches
            if self._shared_db_path.exists():
                self._connection.execute(
                    f"ATTACH DATABASE '{self._shared_db_path}' AS shared (READ_ONLY)"
                )
        
        return self._connection
    
    def load_matches(
        self,
        *,
        limit: int | None = None,
        offset: int = 0,
        filters: dict | None = None,
    ) -> pl.DataFrame:
        """Charge les matchs avec JOIN sur shared pour roster/events."""
        
        conn = self._get_connection()
        
        # ⭐ JOIN player_match_stats + shared.match_registry
        query = """
            SELECT 
                p.match_id,
                p.xuid,
                p.outcome,
                p.kills,
                p.deaths,
                p.assists,
                p.kda,
                p.accuracy,
                p.personal_score,
                p.performance_score,
                -- Données communes depuis shared
                s.start_time,
                s.end_time,
                s.playlist_id,
                s.playlist_name,
                s.map_id,
                s.map_name,
                s.mode_category,
                s.team_0_score,
                s.team_1_score
            FROM player_match_stats p
            LEFT JOIN shared.match_registry s ON s.match_id = p.match_id
        """
        
        # Filtres, ORDER BY, LIMIT...
        if filters:
            query += self._build_where_clause(filters)
        
        query += " ORDER BY s.start_time DESC"
        
        if limit:
            query += f" LIMIT {limit} OFFSET {offset}"
        
        return conn.execute(query).pl()
    
    def load_match_participants(
        self,
        match_id: str,
    ) -> pl.DataFrame:
        """Charge le roster complet depuis shared_matches."""
        
        conn = self._get_connection()
        
        # ⭐ Lecture directe depuis shared.match_participants
        return conn.execute("""
            SELECT 
                p.match_id,
                p.xuid,
                p.team_id,
                p.outcome,
                p.rank,
                p.score,
                p.kills,
                p.deaths,
                p.assists,
                COALESCE(p.gamertag, a.gamertag) as gamertag
            FROM shared.match_participants p
            LEFT JOIN shared.xuid_aliases a ON a.xuid = p.xuid
            WHERE p.match_id = ?
            ORDER BY p.rank ASC
        """, (match_id,)).pl()
    
    def load_highlight_events(
        self,
        match_id: str,
    ) -> pl.DataFrame:
        """Charge les events depuis shared_matches."""
        
        conn = self._get_connection()
        
        # ⭐ Lecture depuis shared.highlight_events
        return conn.execute("""
            SELECT * FROM shared.highlight_events
            WHERE match_id = ?
            ORDER BY time_ms ASC
        """, (match_id,)).pl()
```

### Phase 5 : Nettoyage des Tables Player (Sprint 4)

**Script** : `scripts/migration/cleanup_player_tables.py`

```python
def cleanup_player_db(gamertag: str):
    """Supprime les tables redondantes après migration vers shared."""
    
    db_path = f"data/players/{gamertag}/stats.duckdb"
    conn = duckdb.connect(db_path)
    
    # ⚠️ BACKUP avant suppression
    backup_path = f"backups/{gamertag}_pre_cleanup_{datetime.now():%Y%m%d}.duckdb"
    shutil.copy2(db_path, backup_path)
    
    # Supprimer les tables migrées vers shared
    conn.execute("DROP TABLE IF EXISTS match_participants")
    conn.execute("DROP TABLE IF EXISTS highlight_events")
    conn.execute("DROP TABLE IF EXISTS xuid_aliases")  # Maintenant global
    
    # Renommer match_stats → player_match_stats (si nécessaire)
    # et ne garder que les colonnes spécifiques au joueur
    
    conn.commit()
    conn.close()
    
    logger.info(f"Nettoyage de {gamertag} terminé, backup: {backup_path}")
```

---

## 📈 Gains Attendus

### Stockage

| Métrique | Avant | Après | Économie |
|----------|-------|-------|----------|
| **Taille totale** (4 joueurs, 1000 matchs, 90% partagés) | ~800 MB | ~250 MB | **-69%** |
| **match_participants** | 4 × 10 000 lignes = 40k | 10 000 lignes | **-75%** |
| **highlight_events** | 4 × 100 000 lignes = 400k | 100 000 lignes | **-75%** |

### Performance API

| Opération | Avant | Après | Gain |
|-----------|-------|-------|------|
| **Sync initiale 4 joueurs** | 12 000 appels | 3 300 appels | **-72%** |
| **Backfill 1 joueur** (100 matchs, 90% partagés) | 300 appels | 30 appels | **-90%** |
| **Temps de sync** (estimation) | ~45 min | ~12 min | **-73%** |

### Maintenabilité

✅ **Détection globale des matchs** : `SELECT * FROM match_registry WHERE match_id = ?`  
✅ **Audit de complétude** : Savoir quelles données ont été backfill pour un match donné  
✅ **Stats cross-joueurs** : Facilite les analyses de groupe ("Combien de matchs ensemble ?")  
✅ **Extensibilité** : Ajouter de nouveaux joueurs ne duplique plus les données existantes

---

## ⚠️ Points d'Attention

### Complexité de Migration

**Risque** : Migration manuelle de milliers de matchs peut être longue et sujette aux erreurs.

**Mitigation** :
1. Scripts de migration automatisés avec validation
2. Migration progressive (joueur par joueur)
3. Backups systématiques avant chaque étape
4. Tests de cohérence post-migration

### Gestion des Conflits

**Scénario** : Deux joueurs synchronisent le même match simultanément.

**Solution** :
```python
# Utiliser INSERT OR IGNORE pour match_registry
conn.execute("""
    INSERT OR IGNORE INTO match_registry (match_id, ...)
    VALUES (?, ...)
""")

# Incrémenter player_count de manière atomique
conn.execute("""
    UPDATE match_registry 
    SET player_count = player_count + 1
    WHERE match_id = ? AND NOT EXISTS (
        SELECT 1 FROM player_match_registry 
        WHERE match_id = ? AND xuid = ?
    )
""", (match_id, match_id, xuid))
```

### Compatibilité Ascendante

**Problème** : Le code existant s'attend à trouver `match_participants` dans la DB joueur.

**Solution** :
```python
# Créer des VIEWs de compatibilité dans player DB
CREATE VIEW match_participants AS 
SELECT * FROM shared.match_participants 
WHERE match_id IN (SELECT match_id FROM player_match_stats);

CREATE VIEW highlight_events AS
SELECT * FROM shared.highlight_events
WHERE match_id IN (SELECT match_id FROM player_match_stats);
```

---

## 🎯 Recommandations

### Priorité Haute (Implémenter Maintenant)

1. ✅ **Phase 1** : Créer l'infrastructure `shared_matches.duckdb`
2. ✅ **Phase 2** : Migrer les données existantes (commencer par Chocoboflor)
3. ✅ **Phase 3** : Adapter `DuckDBSyncEngine` pour détecter les matchs partagés

**Impact** : Économie immédiate de 70% sur les prochaines syncs.

### Priorité Moyenne (Après Stabilisation)

4. ✅ **Phase 4** : Refactoring de `DuckDBRepository` pour utiliser les VIEWs shared
5. ✅ **Phase 5** : Nettoyage des tables player (après validation)

**Impact** : Réduction de la taille des DBs, simplification du code.

### Optionnel (Amélioration Continue)

6. 🔄 **Monitoring** : Dashboard de stats sur le taux de partage de matchs
7. 🔄 **Optimisation** : Compression Parquet pour les archives shared anciennes
8. 🔄 **Analyse** : Identifier les "hubs" (joueurs avec le plus de matchs partagés)

---

## 📝 Conclusion

L'architecture actuelle (v4) duplique massivement les données de matchs partagés entre joueurs, générant :
- **Surconsommation de stockage** (~800 MB pour 4 joueurs → 250 MB après optimisation)
- **Appels API redondants** (12 000 appels → 3 300 après optimisation)
- **Backfill inefficace** (impossible de détecter les données déjà chargées)

La solution proposée — **architecture hybride Player + Shared** — introduit un registre central des matchs (`shared_matches.duckdb`) qui :
1. ✅ Élimine la duplication des données communes (roster, events, assets)
2. ✅ Permet la détection intelligente des matchs déjà connus
3. ✅ Optimise les appels API (économie de 70-90%)
4. ✅ Facilite le backfill sélectif

**Gains attendus** :
- **-69% d'espace disque**
- **-72% d'appels API**
- **-73% de temps de sync**

**Effort estimé** : 4 sprints (création infra + migration + refactoring + nettoyage)

**Recommandation** : Implémenter en priorité les Phases 1-3 pour bénéficier immédiatement des gains sur les prochaines synchronisations.

---

**Prochaines étapes** :
1. Valider l'approche avec l'équipe
2. Créer les scripts de migration Phase 1
3. Tester sur un joueur pilote (Chocoboflor)
4. Déployer progressivement sur les autres joueurs
