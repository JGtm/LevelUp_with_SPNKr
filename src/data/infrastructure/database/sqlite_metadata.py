"""
Store de métadonnées SQLite.
(SQLite metadata store)

HOW IT WORKS:
Gère les données "chaudes" dans SQLite :
- Profils joueurs
- Définitions de playlists/maps
- Amis
- Sessions

Ces données sont relationnelles et de faible volume.
DuckDB peut les joindre avec les faits Parquet via ATTACH.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from src.db.connection import get_connection
from src.data.domain.models.player import PlayerProfile


# Schéma SQL pour les métadonnées
METADATA_SCHEMA = """
-- =============================================================================
-- SCHÉMA SQLite : Métadonnées (données chaudes)
-- =============================================================================

-- Table des joueurs (dimension principale)
CREATE TABLE IF NOT EXISTS players (
    xuid TEXT PRIMARY KEY,
    gamertag TEXT NOT NULL,
    service_tag TEXT,
    emblem_path TEXT,
    backdrop_path TEXT,
    career_rank INTEGER DEFAULT 0,
    last_seen_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_players_gamertag ON players(gamertag);

-- Table des playlists (dimension)
CREATE TABLE IF NOT EXISTS playlists (
    asset_id TEXT PRIMARY KEY,
    version_id TEXT,
    public_name TEXT NOT NULL,
    description TEXT,
    is_ranked INTEGER DEFAULT 0,
    category TEXT,
    raw_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Table des cartes (dimension)
CREATE TABLE IF NOT EXISTS maps (
    asset_id TEXT PRIMARY KEY,
    version_id TEXT,
    public_name TEXT NOT NULL,
    description TEXT,
    thumbnail_path TEXT,
    raw_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Table des variantes de jeu (dimension)
CREATE TABLE IF NOT EXISTS game_variants (
    asset_id TEXT PRIMARY KEY,
    version_id TEXT,
    public_name TEXT NOT NULL,
    description TEXT,
    category TEXT,
    raw_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Table des amis (relation)
CREATE TABLE IF NOT EXISTS friends (
    owner_xuid TEXT NOT NULL,
    friend_xuid TEXT NOT NULL,
    friend_gamertag TEXT,
    nickname TEXT,
    added_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (owner_xuid, friend_xuid)
);

-- Table des sessions de jeu
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    xuid TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    match_count INTEGER NOT NULL,
    total_kills INTEGER DEFAULT 0,
    total_deaths INTEGER DEFAULT 0,
    total_assists INTEGER DEFAULT 0,
    avg_kda REAL,
    avg_accuracy REAL,
    performance_score REAL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_sessions_xuid ON sessions(xuid);
CREATE INDEX IF NOT EXISTS idx_sessions_start ON sessions(start_time);

-- Table de métadonnées de synchronisation
CREATE TABLE IF NOT EXISTS sync_meta (
    xuid TEXT PRIMARY KEY,
    last_sync_at TEXT,
    last_match_id TEXT,
    total_matches INTEGER DEFAULT 0,
    total_parquet_rows INTEGER DEFAULT 0,
    sync_status TEXT DEFAULT 'idle',
    error_message TEXT
);

-- Table des définitions de médailles (référentiel)
CREATE TABLE IF NOT EXISTS medal_definitions (
    name_id INTEGER PRIMARY KEY,
    name_en TEXT NOT NULL,
    name_fr TEXT,
    description_en TEXT,
    description_fr TEXT,
    difficulty TEXT,
    sprite_path TEXT
);

-- Migration tracking
CREATE TABLE IF NOT EXISTS migration_meta (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);
"""


class SQLiteMetadataStore:
    """
    Gestionnaire des métadonnées SQLite.
    (SQLite metadata manager)
    
    Gère les données relationnelles qui seront jointures avec les faits Parquet.
    """
    
    def __init__(self, db_path: str | Path) -> None:
        """
        Initialise le store de métadonnées.
        (Initialize metadata store)
        
        Args:
            db_path: Chemin vers le fichier SQLite (metadata.db)
        """
        self.db_path = Path(db_path)
        self._ensure_schema()
    
    def _ensure_schema(self) -> None:
        """
        Crée les tables si elles n'existent pas.
        (Create tables if they don't exist)
        """
        # Créer le dossier parent si nécessaire
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with get_connection(str(self.db_path)) as con:
            con.executescript(METADATA_SCHEMA)
            con.commit()
    
    def get_player(self, xuid: str) -> PlayerProfile | None:
        """
        Récupère le profil d'un joueur.
        (Get player profile)
        """
        with get_connection(str(self.db_path)) as con:
            cur = con.cursor()
            cur.execute(
                """
                SELECT xuid, gamertag, service_tag, emblem_path, backdrop_path,
                       career_rank, last_seen_at, created_at, updated_at
                FROM players
                WHERE xuid = ?
                """,
                (xuid,),
            )
            row = cur.fetchone()
            if not row:
                return None
            
            return PlayerProfile(
                xuid=row[0],
                gamertag=row[1],
                service_tag=row[2],
                emblem_path=row[3],
                backdrop_path=row[4],
                career_rank=row[5] or 0,
                last_seen_at=datetime.fromisoformat(row[6]) if row[6] else None,
                created_at=datetime.fromisoformat(row[7]) if row[7] else None,
                updated_at=datetime.fromisoformat(row[8]) if row[8] else None,
            )
    
    def upsert_player(self, profile: PlayerProfile) -> None:
        """
        Insère ou met à jour un profil joueur.
        (Insert or update player profile)
        """
        with get_connection(str(self.db_path)) as con:
            cur = con.cursor()
            cur.execute(
                """
                INSERT INTO players (xuid, gamertag, service_tag, emblem_path, 
                                    backdrop_path, career_rank, last_seen_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(xuid) DO UPDATE SET
                    gamertag = excluded.gamertag,
                    service_tag = COALESCE(excluded.service_tag, service_tag),
                    emblem_path = COALESCE(excluded.emblem_path, emblem_path),
                    backdrop_path = COALESCE(excluded.backdrop_path, backdrop_path),
                    career_rank = COALESCE(excluded.career_rank, career_rank),
                    last_seen_at = COALESCE(excluded.last_seen_at, last_seen_at),
                    updated_at = datetime('now')
                """,
                (
                    profile.xuid,
                    profile.gamertag,
                    profile.service_tag,
                    profile.emblem_path,
                    profile.backdrop_path,
                    profile.career_rank,
                    profile.last_seen_at.isoformat() if profile.last_seen_at else None,
                ),
            )
            con.commit()
    
    def get_sync_status(self, xuid: str) -> dict[str, Any]:
        """
        Récupère l'état de synchronisation pour un joueur.
        (Get sync status for a player)
        """
        with get_connection(str(self.db_path)) as con:
            cur = con.cursor()
            cur.execute(
                """
                SELECT last_sync_at, last_match_id, total_matches, 
                       total_parquet_rows, sync_status, error_message
                FROM sync_meta
                WHERE xuid = ?
                """,
                (xuid,),
            )
            row = cur.fetchone()
            if not row:
                return {
                    "last_sync_at": None,
                    "last_match_id": None,
                    "total_matches": 0,
                    "total_parquet_rows": 0,
                    "sync_status": "never",
                    "error_message": None,
                }
            
            return {
                "last_sync_at": datetime.fromisoformat(row[0]) if row[0] else None,
                "last_match_id": row[1],
                "total_matches": row[2] or 0,
                "total_parquet_rows": row[3] or 0,
                "sync_status": row[4] or "idle",
                "error_message": row[5],
            }
    
    def update_sync_status(
        self,
        xuid: str,
        *,
        last_sync_at: datetime | None = None,
        last_match_id: str | None = None,
        total_matches: int | None = None,
        total_parquet_rows: int | None = None,
        sync_status: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """
        Met à jour l'état de synchronisation.
        (Update sync status)
        """
        with get_connection(str(self.db_path)) as con:
            cur = con.cursor()
            
            # Construire la requête dynamiquement
            fields = []
            values = []
            
            if last_sync_at is not None:
                fields.append("last_sync_at = ?")
                values.append(last_sync_at.isoformat())
            if last_match_id is not None:
                fields.append("last_match_id = ?")
                values.append(last_match_id)
            if total_matches is not None:
                fields.append("total_matches = ?")
                values.append(total_matches)
            if total_parquet_rows is not None:
                fields.append("total_parquet_rows = ?")
                values.append(total_parquet_rows)
            if sync_status is not None:
                fields.append("sync_status = ?")
                values.append(sync_status)
            if error_message is not None:
                fields.append("error_message = ?")
                values.append(error_message)
            
            if not fields:
                return
            
            # Upsert
            cur.execute(
                f"""
                INSERT INTO sync_meta (xuid, {', '.join(f.split(' = ')[0] for f in fields)})
                VALUES (?, {', '.join('?' * len(values))})
                ON CONFLICT(xuid) DO UPDATE SET {', '.join(fields)}
                """,
                (xuid, *values, *values),
            )
            con.commit()
    
    def get_migration_status(self) -> dict[str, Any]:
        """
        Récupère l'état de la migration.
        (Get migration status)
        """
        with get_connection(str(self.db_path)) as con:
            cur = con.cursor()
            cur.execute("SELECT key, value FROM migration_meta")
            return {row[0]: row[1] for row in cur.fetchall()}
    
    def set_migration_status(self, key: str, value: str) -> None:
        """
        Met à jour l'état de la migration.
        (Update migration status)
        """
        with get_connection(str(self.db_path)) as con:
            cur = con.cursor()
            cur.execute(
                """
                INSERT INTO migration_meta (key, value, updated_at)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')
                """,
                (key, value),
            )
            con.commit()
