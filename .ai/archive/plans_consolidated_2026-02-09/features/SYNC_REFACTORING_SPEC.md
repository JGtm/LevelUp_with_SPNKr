# Spécification : Refonte du Système de Synchronisation

> **Sprint 4.5** - Refactoring Sync API → DuckDB Direct
> Date : 2026-02-01
> Statut : Draft

---

## 1. Contexte et Objectifs

### 1.1 Situation Actuelle

Le système de synchronisation actuel utilise un pipeline multi-étapes avec plusieurs formats intermédiaires :

```
API SPNKr
    │
    ▼
scripts/spnkr_import_db.py ─────► SQLite (JSON brut)
    │                               ├── MatchStats
    │                               ├── PlayerMatchStats
    │                               ├── HighlightEvents
    │                               └── XuidAliases
    │
    ▼
scripts/sync.py ────────────────► SQLite (Cache)
    │   rebuild_match_cache()       ├── MatchCache
    │   rebuild_teammates_aggregate()└── TeammatesAggregate
    │
    ▼
scripts/migrate_to_parquet.py ──► Parquet
    │   ShadowRepository            └── match_facts/
    │
    ▼
scripts/migrate_player_to_duckdb.py ► DuckDB
                                      └── stats.duckdb
```

**Problèmes identifiés :**

1. **Pipeline trop long** : 4 étapes pour arriver à DuckDB
2. **Formats intermédiaires inutiles** : SQLite JSON → SQLite Cache → Parquet → DuckDB
3. **Duplication de logique** : Parsing JSON dans 3 fichiers différents
4. **Performance** : Reconstructions coûteuses (`rebuild_match_cache`)
5. **Maintenance** : Code dispersé dans 6+ fichiers

### 1.2 Architecture Cible

```
API SPNKr / (Future: Grunt)
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│              DuckDBSyncEngine (src/data/sync/)               │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐   │
│  │ APIClient   │─▶│ Transformers │─▶│ DuckDB Writer     │   │
│  │ (async)     │  │ (Pydantic)   │  │ (upsert direct)   │   │
│  └─────────────┘  └──────────────┘  └───────────────────┘   │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
data/players/{gamertag}/stats.duckdb
├── match_stats          (remplace MatchCache)
├── player_match_stats   (MMR/skill - nouveau)
├── highlight_events     (remplace table SQLite)
├── teammates_aggregate
├── medals_earned
├── antagonists
├── xuid_aliases         (nouveau - remplace table SQLite)
└── sync_meta            (métadonnées)

data/warehouse/metadata.duckdb
├── maps
├── playlists
├── game_variants
└── medal_definitions
```

### 1.3 Gains Attendus

| Métrique | Avant | Après | Gain |
|----------|-------|-------|------|
| Étapes de sync | 4 | 1 | -75% |
| Fichiers impliqués | 8+ | 3 | -60% |
| Parsing JSON | 3x | 1x | -66% |
| Temps sync delta | ~15-30s | ~5-10s | -60% |
| Complexité code | Élevée | Faible | -60% |

---

## 2. Points d'Intégration Existants

### 2.1 launcher.py

Le launcher utilise actuellement :

```python
# Lignes 327-421
def _run_spnkr_import(opts: RefreshOptions) -> int:
    """Exécute l'import SPNKr via subprocess."""
    cmd = [sys.executable, str(DEFAULT_IMPORTER), ...]
    proc = subprocess.Popen(cmd, ...)
```

**Impact refactoring** :
- Remplacer l'appel subprocess par import direct de `DuckDBSyncEngine`
- Supprimer la logique de fichier temporaire (tmp_db)
- Simplifier car DuckDB gère les transactions ACID

### 2.2 src/ui/sync.py

Fonctions clés actuelles :

```python
def refresh_spnkr_db_via_api(...) -> tuple[bool, str]:
    """Lance spnkr_import_db.py via subprocess."""
    
def sync_all_players(...) -> tuple[bool, str]:
    """Sync tous les joueurs d'une DB fusionnée."""
```

**Impact refactoring** :
- Remplacer par appel direct à `DuckDBSyncEngine.sync_delta()`
- Supprimer le wrapper subprocess

### 2.3 src/app/sidebar.py

```python
def render_sync_button(...) -> bool:
    """Bouton de sync dans la sidebar Streamlit."""
    ok, msg = sync_all_players(
        db_path=db_path,
        match_type=...,
        max_matches=...,
        delta=True,
    )
```

**Impact refactoring** :
- Interface identique (tuple[bool, str])
- Juste changer l'implémentation interne de `sync_all_players()`

### 2.4 scripts/sync.py (CLI)

Point d'entrée CLI unifié :

```bash
python scripts/sync.py --delta --player Chocoboflor
python scripts/sync.py --full --max-matches 500
```

**Impact refactoring** :
- Garder l'interface CLI identique
- Remplacer les appels internes par `DuckDBSyncEngine`

---

## 3. Nouveau Module `src/data/sync/`

### 3.1 Structure

```
src/data/sync/
├── __init__.py
├── engine.py           # DuckDBSyncEngine (orchestrateur)
├── api_client.py       # Wrapper SPNKr (async)
├── transformers.py     # API JSON → DuckDB rows
├── delta.py            # Logique sync incrémentale
├── assets.py           # Import maps, playlists, variants
└── models.py           # SyncResult, SyncOptions, etc.
```

### 3.2 Interface `DuckDBSyncEngine`

```python
# src/data/sync/engine.py

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Any

import duckdb


@dataclass
class SyncOptions:
    """Options de synchronisation."""
    match_type: str = "matchmaking"
    max_matches: int = 200
    with_highlight_events: bool = True
    with_skill: bool = True
    with_aliases: bool = True
    with_assets: bool = True
    requests_per_second: int = 5
    parallel_matches: int = 3


@dataclass
class SyncResult:
    """Résultat d'une synchronisation."""
    matches_inserted: int = 0
    matches_updated: int = 0
    highlight_events_inserted: int = 0
    skill_records_inserted: int = 0
    aliases_updated: int = 0
    assets_imported: int = 0
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    
    @property
    def success(self) -> bool:
        """True si la sync a réussi (même partiellement)."""
        return self.matches_inserted > 0 or len(self.errors) == 0
    
    def to_message(self) -> str:
        """Message de résumé pour l'UI."""
        if not self.success:
            return f"❌ Sync échouée: {', '.join(self.errors[:2])}"
        parts = []
        if self.matches_inserted > 0:
            parts.append(f"{self.matches_inserted} nouveaux matchs")
        if self.aliases_updated > 0:
            parts.append(f"{self.aliases_updated} aliases")
        if not parts:
            parts.append("Déjà à jour")
        return f"✅ {', '.join(parts)}"


class DuckDBSyncEngine:
    """Moteur de synchronisation API → DuckDB unifié.
    
    Gère tout le pipeline en une seule étape :
    1. Fetch depuis l'API SPNKr
    2. Transformation Pydantic
    3. Upsert direct dans DuckDB
    4. Mise à jour des agrégats
    
    Thread-safe via lock asyncio pour les écritures DB.
    """
    
    def __init__(
        self,
        player_db_path: Path | str,
        *,
        xuid: str,
        gamertag: str,
        metadata_db_path: Path | str | None = None,
    ) -> None:
        """
        Args:
            player_db_path: Chemin vers stats.duckdb du joueur.
            xuid: XUID du joueur.
            gamertag: Gamertag pour l'identification API.
            metadata_db_path: Chemin vers metadata.duckdb (auto-détecté si None).
        """
        self._player_db_path = Path(player_db_path)
        self._xuid = xuid
        self._gamertag = gamertag
        self._metadata_db_path = self._resolve_metadata_path(metadata_db_path)
        
        self._connection: duckdb.DuckDBPyConnection | None = None
        self._logger = logging.getLogger(__name__)
    
    async def sync_delta(
        self,
        options: SyncOptions | None = None,
        *,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> SyncResult:
        """Synchronisation incrémentale (nouveaux matchs uniquement).
        
        S'arrête dès qu'un match déjà connu est rencontré.
        Optimal pour les synchronisations régulières (< 10s).
        
        Args:
            options: Options de sync (défauts si None).
            progress_callback: Callback (current, total) pour progression.
        
        Returns:
            SyncResult avec les détails.
        """
        ...
    
    async def sync_full(
        self,
        options: SyncOptions | None = None,
        *,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> SyncResult:
        """Synchronisation complète (tous les matchs).
        
        Continue même si des matchs existent déjà (mise à jour).
        Utile pour backfill de données manquantes.
        
        Args:
            options: Options de sync (défauts si None).
            progress_callback: Callback (current, total) pour progression.
        
        Returns:
            SyncResult avec les détails.
        """
        ...
    
    async def sync_assets(self) -> int:
        """Synchronise les assets (maps, playlists) dans metadata.duckdb.
        
        Returns:
            Nombre d'assets importés/mis à jour.
        """
        ...
    
    def refresh_aggregates(self) -> dict[str, int]:
        """Recalcule les tables d'agrégats après sync.
        
        Met à jour :
        - teammates_aggregate
        - antagonists (si highlight_events disponibles)
        - Vues matérialisées (mv_*)
        
        Returns:
            Dict table_name → rows_affected.
        """
        ...
    
    def get_sync_status(self) -> dict[str, Any]:
        """Retourne l'état de la dernière synchronisation.
        
        Returns:
            Dict avec last_sync_at, total_matches, etc.
        """
        ...
    
    def close(self) -> None:
        """Ferme la connexion DuckDB."""
        ...
```

### 3.3 Interface `APIClient`

```python
# src/data/sync/api_client.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator


@dataclass
class MatchHistoryItem:
    """Item de l'historique des matchs."""
    match_id: str
    start_time: str
    # ... autres champs minimaux


@dataclass 
class MatchData:
    """Données complètes d'un match (stats + skill + events)."""
    match_id: str
    stats_json: dict[str, Any]
    skill_json: dict[str, Any] | None
    highlight_events: list[dict[str, Any]]


class SPNKrAPIClient:
    """Client API SPNKr asynchrone.
    
    Encapsule HaloInfiniteClient de SPNKr avec :
    - Gestion automatique des tokens
    - Rate limiting configurable
    - Retry avec backoff exponentiel
    - Cache HTTP optionnel pour assets
    """
    
    def __init__(
        self,
        *,
        requests_per_second: int = 5,
    ) -> None:
        ...
    
    async def get_match_history(
        self,
        player: str,
        *,
        match_type: str = "matchmaking",
        start: int = 0,
        count: int = 25,
    ) -> list[MatchHistoryItem]:
        """Récupère l'historique des matchs."""
        ...
    
    async def get_match_data(
        self,
        match_id: str,
        xuids: list[int],
        *,
        with_skill: bool = True,
        with_highlight_events: bool = True,
    ) -> MatchData:
        """Récupère les données complètes d'un match."""
        ...
    
    async def get_asset(
        self,
        asset_type: str,
        asset_id: str,
        version_id: str,
    ) -> dict[str, Any] | None:
        """Récupère un asset (map, playlist, variant)."""
        ...
    
    async def batch_resolve_xuids(
        self,
        xuids: list[int],
    ) -> dict[int, str]:
        """Résout des XUIDs en gamertags."""
        ...
```

### 3.4 Transformers

```python
# src/data/sync/transformers.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class MatchStatsRow:
    """Ligne pour la table match_stats."""
    match_id: str
    start_time: datetime
    playlist_id: str | None
    playlist_name: str | None
    map_id: str | None
    map_name: str | None
    pair_id: str | None
    pair_name: str | None
    game_variant_id: str | None
    game_variant_name: str | None
    outcome: int | None
    team_id: int | None
    kills: int
    deaths: int
    assists: int
    kda: float | None
    accuracy: float | None
    headshot_kills: int | None
    max_killing_spree: int | None
    time_played_seconds: int | None
    avg_life_seconds: float | None
    my_team_score: int | None
    enemy_team_score: int | None
    team_mmr: float | None
    enemy_mmr: float | None


@dataclass
class PlayerMatchStatsRow:
    """Ligne pour la table player_match_stats (MMR/skill)."""
    match_id: str
    xuid: str
    team_id: int | None
    team_mmr: float | None
    enemy_mmr: float | None
    kills_expected: float | None
    kills_stddev: float | None
    deaths_expected: float | None
    deaths_stddev: float | None


@dataclass
class HighlightEventRow:
    """Ligne pour la table highlight_events."""
    match_id: str
    event_type: str
    time_ms: int
    xuid: str | None
    gamertag: str | None
    type_hint: int | None
    raw_json: str  # JSON complet pour données additionnelles


def transform_match_stats(
    match_json: dict[str, Any],
    xuid: str,
) -> MatchStatsRow | None:
    """Transforme le JSON API en row match_stats."""
    ...


def transform_skill_stats(
    skill_json: dict[str, Any],
    match_id: str,
    xuid: str,
) -> PlayerMatchStatsRow | None:
    """Transforme le JSON skill en row player_match_stats."""
    ...


def transform_highlight_events(
    events: list[Any],
    match_id: str,
) -> list[HighlightEventRow]:
    """Transforme les highlight events en rows."""
    ...


def extract_aliases(
    match_json: dict[str, Any],
) -> dict[str, str]:
    """Extrait les pairs XUID → Gamertag d'un match."""
    ...
```

---

## 4. Schéma DuckDB Étendu

### 4.1 Nouvelles Tables dans `stats.duckdb`

```sql
-- Table player_match_stats (MMR/skill par match)
-- Remplace la lecture depuis PlayerMatchStats SQLite
CREATE TABLE IF NOT EXISTS player_match_stats (
    match_id VARCHAR PRIMARY KEY,
    xuid VARCHAR NOT NULL,
    team_id TINYINT,
    team_mmr FLOAT,
    enemy_mmr FLOAT,
    kills_expected FLOAT,
    kills_stddev FLOAT,
    deaths_expected FLOAT,
    deaths_stddev FLOAT,
    assists_expected FLOAT,
    assists_stddev FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table highlight_events (kills, deaths depuis les films)
-- Remplace la table SQLite HighlightEvents
CREATE TABLE IF NOT EXISTS highlight_events (
    id INTEGER PRIMARY KEY,
    match_id VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL,
    time_ms INTEGER,
    xuid VARCHAR,
    gamertag VARCHAR,
    type_hint INTEGER,
    raw_json VARCHAR,
    UNIQUE(match_id, event_type, time_ms, xuid)
);
CREATE INDEX IF NOT EXISTS idx_highlight_match ON highlight_events(match_id);

-- Table xuid_aliases (correspondances XUID → Gamertag)
-- Remplace la table SQLite XuidAliases
CREATE TABLE IF NOT EXISTS xuid_aliases (
    xuid VARCHAR PRIMARY KEY,
    gamertag VARCHAR NOT NULL,
    last_seen TIMESTAMP,
    source VARCHAR,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_aliases_gamertag ON xuid_aliases(gamertag);

-- Table sync_meta (métadonnées de synchronisation)
CREATE TABLE IF NOT EXISTS sync_meta (
    key VARCHAR PRIMARY KEY,
    value VARCHAR,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 4.2 Nouvelles Tables dans `metadata.duckdb`

```sql
-- Maps (remplace SQLite Maps)
CREATE TABLE IF NOT EXISTS maps (
    asset_id VARCHAR PRIMARY KEY,
    version_id VARCHAR,
    public_name VARCHAR,
    description VARCHAR,
    raw_json VARCHAR,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Playlists (remplace SQLite Playlists)
CREATE TABLE IF NOT EXISTS playlists (
    asset_id VARCHAR PRIMARY KEY,
    version_id VARCHAR,
    public_name VARCHAR,
    description VARCHAR,
    raw_json VARCHAR,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Game Variants
CREATE TABLE IF NOT EXISTS game_variants (
    asset_id VARCHAR PRIMARY KEY,
    version_id VARCHAR,
    public_name VARCHAR,
    description VARCHAR,
    raw_json VARCHAR,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Map Mode Pairs
CREATE TABLE IF NOT EXISTS map_mode_pairs (
    asset_id VARCHAR PRIMARY KEY,
    version_id VARCHAR,
    public_name VARCHAR,
    map_asset_id VARCHAR,
    variant_asset_id VARCHAR,
    raw_json VARCHAR,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 5. Décisions Architecturales

### 5.1 Parquet : Conserver ou Supprimer ?

**Analyse :**

| Aspect | Parquet | DuckDB |
|--------|---------|--------|
| Performance lecture | Excellente (colonnar) | Excellente (OLAP natif) |
| Performance écriture | Append-only (partitions) | ACID avec upsert |
| Transactions | Non | Oui |
| Requêtes SQL | Via DuckDB de toute façon | Natif |
| Taille fichier | Plus compact (compression) | Légèrement plus gros |
| Portabilité | Excellente (format ouvert) | Bonne |
| Maintenance | Gestion des partitions | Une seule DB |

**Recommandation :**

Parquet n'est **plus nécessaire comme format intermédiaire** car :
1. DuckDB lit nativement les fichiers Parquet si besoin
2. On n'a plus de flux SQLite → Parquet → DuckDB
3. DuckDB offre les mêmes perfs analytiques avec les transactions en plus

**Conserver Parquet uniquement pour :**
- **Export/Backup** : Archivage annuel des données (cold storage)
- **Interopérabilité** : Partage de données avec d'autres outils

**Action** :
- Supprimer `scripts/migrate_to_parquet.py` du workflow automatique
- Garder une commande `scripts/export_to_parquet.py` pour archivage manuel
- Supprimer `ShadowRepository` après migration complète

### 5.2 DB Unifiée vs Multi-Joueurs

**Analyse :**

| Aspect | Une DB par joueur | DB unifiée |
|--------|-------------------|------------|
| Isolation des données | Parfaite | Nécessite filtrage par XUID |
| Performance sync | Localisée | Lock global potentiel |
| Taille fichier | Petite par joueur | Grande (cumulée) |
| Sauvegarde/restore | Simple par joueur | Tout ou rien |
| Requêtes cross-player | Impossible directement | Facile |
| Maintenance | Plus de fichiers | Un seul fichier |

**Recommandation : Une DB par joueur**

Raisons :
1. **Réactivité** : La sync d'un joueur n'impacte pas les autres
2. **Parallélisation** : Sync simultanée de plusieurs joueurs possible
3. **DuckDB supporte ATTACH** : Requêtes cross-player possibles si besoin
4. **Sauvegarde granulaire** : Backup/restore d'un joueur sans toucher les autres

**Action** : Conserver le modèle `data/players/{gamertag}/stats.duckdb`

### 5.3 Migration des Données Historiques

**Décision (confirmée)** : On récupère TOUT

**Plan de migration :**

1. **Match Stats** : Déjà migrées via `migrate_player_to_duckdb.py`
2. **Highlight Events** : À migrer depuis `HighlightEvents` SQLite
3. **Player Match Stats (MMR)** : À migrer depuis `PlayerMatchStats` SQLite
4. **XUIDs Aliases** : À migrer depuis `XuidAliases` SQLite

**Script** : Créer `scripts/migrate_all_to_duckdb.py` qui :
- Migre toutes les tables d'un joueur en une seule commande
- Vérifie l'intégrité après migration
- Met à jour les métadonnées

---

## 6. Plan d'Implémentation

### Sprint 4.5.1 : Core Sync Engine (2-3 jours)

| Tâche | Fichier | Priorité |
|-------|---------|----------|
| Créer structure `src/data/sync/` | `__init__.py`, `models.py` | P0 |
| Implémenter `SPNKrAPIClient` | `api_client.py` | P0 |
| Implémenter transformers | `transformers.py` | P0 |
| Implémenter `DuckDBSyncEngine` | `engine.py` | P0 |
| Tests unitaires | `tests/test_sync_engine.py` | P0 |

### Sprint 4.5.2 : Intégration (1-2 jours)

| Tâche | Fichier | Priorité |
|-------|---------|----------|
| Adapter `scripts/sync.py` | CLI → DuckDBSyncEngine | P0 |
| Adapter `src/ui/sync.py` | Wrapper simplifié | P0 |
| Adapter `launcher.py` | Import direct (plus de subprocess) | P0 |
| Tests d'intégration | `tests/test_sync_integration.py` | P1 |

### Sprint 4.5.3 : Migration Historique (1 jour)

| Tâche | Fichier | Priorité |
|-------|---------|----------|
| Script migration HighlightEvents | `scripts/migrate_highlight_events.py` | P1 |
| Script migration PlayerMatchStats | `scripts/migrate_player_match_stats.py` | P1 |
| Script migration XuidAliases | Inclus dans les précédents | P1 |
| Script unifié | `scripts/migrate_all_to_duckdb.py` | P1 |

### Sprint 4.5.4 : Nettoyage (1 jour)

| Tâche | Fichier | Priorité |
|-------|---------|----------|
| Marquer obsolète | `src/db/loaders.py`, `loaders_cached.py` | P2 |
| Supprimer du workflow auto | `migrate_to_cache.py`, `migrate_to_parquet.py` | P2 |
| MAJ documentation | `ARCHITECTURE_ROADMAP.md`, `thought_log.md` | P2 |
| Supprimer ShadowRepository | `src/data/repositories/shadow.py` | P2 |

---

## 7. Rétrocompatibilité

### 7.1 Interface CLI (scripts/sync.py)

```bash
# Avant et après : IDENTIQUE
python scripts/sync.py --delta --player Chocoboflor
python scripts/sync.py --full --max-matches 500
python scripts/sync.py --rebuild-cache  # Ignoré (plus nécessaire)
```

### 7.2 Interface UI (render_sync_button)

```python
# Avant
ok, msg = sync_all_players(db_path=..., delta=True, ...)

# Après : IDENTIQUE
ok, msg = sync_all_players(db_path=..., delta=True, ...)
# L'implémentation interne change, pas l'interface
```

### 7.3 Launcher (launcher.py)

```python
# Avant (subprocess)
def _run_spnkr_import(opts: RefreshOptions) -> int:
    cmd = [sys.executable, str(DEFAULT_IMPORTER), ...]
    proc = subprocess.Popen(cmd, ...)

# Après (import direct)
async def _run_sync(opts: RefreshOptions) -> int:
    engine = DuckDBSyncEngine(...)
    result = await engine.sync_delta(...)
    return 0 if result.success else 1
```

**Fallback** : Si `stats.duckdb` n'existe pas, on lance la migration depuis SQLite puis la sync.

---

## 8. Tests

### 8.1 Tests Unitaires

```python
# tests/test_sync_engine.py

def test_transform_match_stats():
    """Vérifie la transformation JSON → MatchStatsRow."""
    
def test_transform_skill_stats():
    """Vérifie la transformation skill JSON → PlayerMatchStatsRow."""
    
def test_extract_aliases():
    """Vérifie l'extraction des aliases depuis un match."""
    
def test_sync_delta_stops_on_known_match():
    """Vérifie que sync_delta s'arrête au premier match connu."""
    
def test_sync_full_continues_on_known_match():
    """Vérifie que sync_full continue même avec des matchs connus."""
```

### 8.2 Tests d'Intégration

```python
# tests/test_sync_integration.py

def test_sync_delta_e2e():
    """Test end-to-end d'une sync delta avec mock API."""
    
def test_sync_updates_aggregates():
    """Vérifie que refresh_aggregates() met à jour les tables."""
    
def test_launcher_sync_command():
    """Vérifie que le launcher sync fonctionne."""
```

---

## 9. Métriques de Succès

| Métrique | Seuil | Mesure |
|----------|-------|--------|
| Temps sync delta (100 matchs) | < 10s | Benchmark |
| Temps sync full (1000 matchs) | < 60s | Benchmark |
| Couverture tests | > 80% | pytest-cov |
| Erreurs sync | < 1% | Logs production |
| Taille code sync | -50% | LOC avant/après |

---

## 10. Risques et Mitigations

| Risque | Impact | Mitigation |
|--------|--------|------------|
| Régression UI sync | Élevé | Tests E2E, période de shadow mode |
| Perte de données migration | Critique | Backup avant migration, validation checksums |
| Rate limiting API | Moyen | Retry exponentiel, cache HTTP |
| DuckDB lock contention | Moyen | WAL mode, transactions courtes |

---

## 11. Phase 5 : Comparaison SPNKr vs Grunt

> À réaliser après ce refactoring

### Points de comparaison prévus

| Critère | À évaluer |
|---------|-----------|
| Stabilité | Taux d'erreurs, uptime |
| Performance | Latence, rate limits |
| Complétude données | Champs disponibles |
| Authentification | Complexité, durée tokens |
| Maintenance | Fréquence updates lib |

**Action** : Créer `docs/API_COMPARISON.md` avec benchmark détaillé.

---

## Annexe A : Fichiers Obsolètes Post-Migration

```
À SUPPRIMER du workflow automatique :
├── scripts/migrate_to_cache.py      # Plus de cache SQLite
├── scripts/migrate_to_parquet.py    # Parquet optionnel
└── src/data/repositories/shadow.py  # Bridge legacy → hybrid

À DÉPRÉCIER (warning, pas suppression immédiate) :
├── src/db/loaders.py                # Remplacé par DuckDBRepository
├── src/db/loaders_cached.py         # Idem
└── src/data/repositories/legacy.py  # Idem

À CONSERVER pour migration one-shot :
├── scripts/migrate_player_to_duckdb.py
└── scripts/migrate_all_to_duckdb.py  # Nouveau
```

---

## Annexe B : Mapping Fichiers Avant → Après

| Avant | Après | Notes |
|-------|-------|-------|
| `scripts/spnkr_import_db.py` | `src/data/sync/api_client.py` | Logique API réutilisée |
| `scripts/sync.py` | `src/data/sync/engine.py` + CLI wrapper | Simplifié |
| `src/ui/sync.py` | Wrapper vers `DuckDBSyncEngine` | Interface conservée |
| `src/db/loaders.py` | `DuckDBRepository.load_matches()` | Déjà fait |
| `rebuild_match_cache()` | Plus nécessaire | DuckDB = source unique |
| `rebuild_teammates_aggregate()` | `engine.refresh_aggregates()` | Inclus dans sync |

---

*Document généré le 2026-02-01 - Sprint 4.5 Planning*
