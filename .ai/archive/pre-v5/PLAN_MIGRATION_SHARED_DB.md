# Plan de Migration : Base de Données Partagée Multi-Joueurs

> **Référence** : [ANALYSE_OPTIMISATION_MATCHS_PARTAGES.md](ANALYSE_OPTIMISATION_MATCHS_PARTAGES.md)  
> **Date** : 2026-02-14  
> **Statut** : Proposition de refactoring majeur  

---

## 🎯 Problème Identifié

**Duplication massive des données de matchs partagés entre joueurs.**

### Exemples Concrets

- Madina97294 partage **95%** de ses matchs avec Chocoboflor
- xxdameongamerxx partage **100%** de ses matchs avec Chocoboflor
- JGtm partage **75%** de ses matchs avec Chocoboflor

**Conséquence** : Pour 1 match à 8 joueurs tous trackés, les données sont stockées **8 fois** !

---

## 💡 Solution Proposée : DB Shared Centralisée

### Architecture Cible

```
data/
├── warehouse/
│   ├── metadata.duckdb              # Référentiels (existant)
│   └── shared_matches.duckdb        # ⭐ NOUVEAU
│       ├── match_registry           # Registre central
│       ├── match_participants       # Roster (1 seule fois)
│       ├── highlight_events         # Events (1 seule fois)
│       └── xuid_aliases             # Aliases globaux
│
└── players/
    ├── Chocoboflor/
    │   └── stats.duckdb
    │       ├── player_match_stats   # Stats personnelles uniquement
    │       ├── medals_earned
    │       └── teammates_aggregate
    └── ...
```

### Principe

**Données Communes** (identiques pour tous les joueurs) → `shared_matches.duckdb`
- Roster complet (`match_participants`)
- Événements filmés (`highlight_events`)
- Métadonnées du match (map, playlist, scores des équipes, etc.)

**Données Spécifiques** (vue subjective du joueur) → `players/{gt}/stats.duckdb`
- Kills/deaths/assists **du joueur**
- Médailles gagnées
- Performance score
- Session ID

---

## 📊 Gains Attendus

### Stockage

| Métrique | Avant | Après | Économie |
|----------|-------|-------|----------|
| Taille totale (4 joueurs, 1000 matchs, 90% partagés) | ~800 MB | ~250 MB | **-69%** |
| `match_participants` | 40 000 lignes | 10 000 lignes | **-75%** |
| `highlight_events` | 400 000 lignes | 100 000 lignes | **-75%** |

### API & Performance

| Opération | Avant | Après | Gain |
|-----------|-------|-------|------|
| Sync initiale 4 joueurs | 12 000 appels | 3 300 appels | **-72%** |
| Backfill 1 joueur (100 matchs, 90% partagés) | 300 appels | 30 appels | **-90%** |
| Temps de sync (estimation) | ~45 min | ~12 min | **-73%** |

---

## 🔄 Plan de Migration (5 Phases)

### Phase 1 : Infrastructure (Sprint 0) ⭐ PRIORITÉ HAUTE

**Objectif** : Créer `shared_matches.duckdb` avec le schéma complet.

**Actions** :
```sql
-- scripts/migration/create_shared_matches_db.sql
CREATE TABLE match_registry (
    match_id VARCHAR PRIMARY KEY,
    start_time TIMESTAMP NOT NULL,
    playlist_id VARCHAR,
    map_id VARCHAR,
    -- Métadonnées de backfill
    backfill_completed INTEGER DEFAULT 0,
    participants_loaded BOOLEAN DEFAULT FALSE,
    events_loaded BOOLEAN DEFAULT FALSE,
    -- Tracking
    first_sync_by VARCHAR,
    player_count SMALLINT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE match_participants (...);
CREATE TABLE highlight_events (...);
CREATE TABLE xuid_aliases (...);
```

**Livrables** :
- ✅ `data/warehouse/shared_matches.duckdb` créé
- ✅ Scripts DDL validés
- ✅ Index créés

---

### Phase 2 : Migration des Données (Sprint 1) ⭐ PRIORITÉ HAUTE

**Objectif** : Migrer les données existantes vers `shared_matches`.

**Script** : `scripts/migration/migrate_to_shared_matches.py`

**Ordre de migration** :
1. **Chocoboflor** (base de référence, le plus de matchs)
2. **Madina97294** (95% partagés → peu d'ajouts)
3. **JGtm** (75% partagés)
4. **xxdameongamerxx** (100% partagés → 0 ajout théorique)

**Logique** :
```python
for gamertag in ["Chocoboflor", "Madina97294", "JGtm", "xxdameongamerxx"]:
    for match in get_player_matches(gamertag):
        if match_id not in shared_registry:
            # Nouveau match → insérer tout
            insert_into_shared(match_id, participants, events)
            set_first_sync_by(gamertag)
        else:
            # Match déjà connu → juste incrémenter player_count
            increment_player_count(match_id)
```

**Validation** :
```sql
SELECT 
    COUNT(*) as total_matches,
    AVG(player_count) as avg_players_per_match,
    SUM(CASE WHEN player_count > 1 THEN 1 ELSE 0 END) as shared_matches
FROM match_registry;

-- Résultat attendu :
-- total_matches: ~1050 (vs 4000 dupliqués avant)
-- avg_players_per_match: ~3.8
-- shared_matches: ~950 (90%)
```

---

### Phase 3 : Refactoring Sync Engine (Sprint 2) ⭐ PRIORITÉ HAUTE

**Objectif** : Adapter `src/data/sync/engine.py` pour détecter les matchs partagés.

**Modifications** :

```python
class DuckDBSyncEngine:
    def __init__(self, ..., shared_db_path: str = "data/warehouse/shared_matches.duckdb"):
        self._shared_connection = None
    
    async def _process_single_match(self, client, match_id, options):
        # 1. Vérifier dans shared_matches
        registry = self._get_shared_connection().execute(
            "SELECT * FROM match_registry WHERE match_id = ?", 
            (match_id,)
        ).fetchone()
        
        if registry:
            # ✅ Match connu → sync allégée
            return await self._process_known_match(match_id, registry, options)
        else:
            # ⭐ Nouveau match → sync complète
            return await self._process_new_match(match_id, options)
    
    async def _process_known_match(self, match_id, registry, options):
        """Optimisé : récupère SEULEMENT les stats personnelles."""
        
        # 1. API call minimal (stats seulement)
        stats_json = await client.get_match_stats(match_id)
        
        # 2. Extraire données personnelles
        player_stats = extract_player_specific_stats(stats_json, self._xuid)
        
        # 3. Insérer dans player DB
        self._insert_player_match_stats(player_stats)
        
        # 4. Backfill sélectif si nécessaire
        if not registry['participants_loaded']:
            participants = extract_participants(stats_json)
            self._insert_participants_to_shared(participants)
        
        if not registry['events_loaded'] and options.with_highlight_events:
            events = await client.get_highlight_events(match_id)
            self._insert_events_to_shared(events)
        
        # 5. Incrémenter player_count
        self._shared_connection.execute(
            "UPDATE match_registry SET player_count = player_count + 1 WHERE match_id = ?",
            (match_id,)
        )
```

**Impact** :
- ✅ Économie de 2 appels API par match partagé (events + participants)
- ✅ Pour Madina97294 (95% partagés) : **285 appels évités** sur 300 matchs

---

### Phase 4 : Adaptation Repository (Sprint 3)

**Objectif** : Adapter `DuckDBRepository` pour lire depuis `shared_matches`.

**Modifications** :

```python
class DuckDBRepository:
    def _get_connection(self):
        if self._connection is None:
            self._connection = duckdb.connect(self._player_db_path)
            
            # ATTACH metadata (existant)
            self._connection.execute(
                f"ATTACH '{self._metadata_db_path}' AS meta (READ_ONLY)"
            )
            
            # ⭐ ATTACH shared_matches
            self._connection.execute(
                f"ATTACH '{self._shared_db_path}' AS shared (READ_ONLY)"
            )
        
        return self._connection
    
    def load_match_participants(self, match_id: str):
        """Lecture depuis shared.match_participants."""
        return self._connection.execute("""
            SELECT * FROM shared.match_participants
            WHERE match_id = ?
        """, (match_id,)).pl()
    
    def load_highlight_events(self, match_id: str):
        """Lecture depuis shared.highlight_events."""
        return self._connection.execute("""
            SELECT * FROM shared.highlight_events
            WHERE match_id = ?
        """, (match_id,)).pl()
```

**Impact** :
- ✅ Transparence totale pour l'UI (aucune modification nécessaire)
- ✅ Les queries existantes fonctionnent via ATTACH

---

### Phase 5 : Nettoyage (Sprint 4)

**Objectif** : Supprimer les tables redondantes des player DBs.

**Actions** :
```python
# scripts/migration/cleanup_player_tables.py
def cleanup_player_db(gamertag: str):
    # ⚠️ BACKUP avant suppression
    backup()
    
    # Supprimer les tables migrées
    conn.execute("DROP TABLE IF EXISTS match_participants")
    conn.execute("DROP TABLE IF EXISTS highlight_events")
    conn.execute("DROP TABLE IF EXISTS xuid_aliases")
    
    # Optionnel : Créer des VIEWs de compatibilité
    conn.execute("""
        CREATE VIEW match_participants AS 
        SELECT * FROM shared.match_participants 
        WHERE match_id IN (SELECT match_id FROM player_match_stats)
    """)
```

**Impact** :
- ✅ Réduction de ~60-70% de la taille des player DBs
- ✅ Simplification du schéma

---

## ⚠️ Points d'Attention

### 1. Migration Progressive

**Risque** : Migrer tous les joueurs simultanément peut causer des incohérences.

**Solution** : Migrer 1 joueur à la fois, valider, puis continuer.

### 2. Compatibilité Ascendante

**Problème** : Le code existant cherche `match_participants` dans player DB.

**Solution** : Créer des VIEWs de compatibilité :
```sql
CREATE VIEW match_participants AS 
SELECT * FROM shared.match_participants 
WHERE match_id IN (SELECT match_id FROM player_match_stats);
```

### 3. Concurrence

**Scénario** : Sync simultanée de 2 joueurs sur le même match.

**Solution** : Utiliser `INSERT OR IGNORE` et atomicité des `UPDATE`.

---

## 📋 Checklist de Validation

Après chaque phase, vérifier :

### Phase 1 (Infrastructure)
- [ ] `shared_matches.duckdb` créé et accessible
- [ ] Toutes les tables existent
- [ ] Index créés
- [ ] Permissions correctes

### Phase 2 (Migration)
- [ ] Tous les matchs de Chocoboflor migrés
- [ ] `player_count` correct dans `match_registry`
- [ ] Pas de duplications dans `match_participants`
- [ ] Pas de perte de données

### Phase 3 (Sync Engine)
- [ ] Détection des matchs partagés fonctionnelle
- [ ] Sync allégée pour matchs connus
- [ ] Sync complète pour nouveaux matchs
- [ ] Bitmask `backfill_completed` mis à jour

### Phase 4 (Repository)
- [ ] ATTACH fonctionne correctement
- [ ] Queries de lecture depuis shared OK
- [ ] Pas de régression UI
- [ ] Performance acceptable

### Phase 5 (Nettoyage)
- [ ] Backups créés avant suppression
- [ ] Tables supprimées
- [ ] VIEWs de compatibilité créées
- [ ] UI fonctionne toujours

---

## 🚀 Recommandation Finale

**Implémenter en priorité Phases 1-3** pour bénéficier immédiatement :
- ✅ **-72% d'appels API** sur les prochaines syncs
- ✅ **-69% d'espace disque** pour les nouveaux matchs
- ✅ Détection intelligente des matchs partagés

**Effort estimé** : 
- Phase 1 : 1-2 jours (création schéma + scripts)
- Phase 2 : 2-3 jours (migration + validation)
- Phase 3 : 3-4 jours (refactoring + tests)
- **Total Phases 1-3 : ~1.5-2 semaines**

**ROI** : Récupération de l'investissement dès la première sync complète post-migration (économie de 70% du temps et des appels API).

---

## 📚 Références

- [Analyse Complète](ANALYSE_OPTIMISATION_MATCHS_PARTAGES.md) : Détails techniques complets
- [DATA_ARCHITECTURE.md](../docs/DATA_ARCHITECTURE.md) : Architecture actuelle
- [SQL_SCHEMA.md](../docs/SQL_SCHEMA.md) : Schémas DuckDB
- [SYNC_GUIDE.md](../docs/SYNC_GUIDE.md) : Guide de synchronisation
