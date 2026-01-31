"""
Moteur de requête DuckDB.
(DuckDB query engine)

HOW IT WORKS:
1. DuckDB est utilisé comme moteur de requête principal (read-only sur les faits)
2. Il peut "attacher" une base SQLite pour joindre les métadonnées
3. Il lit directement les fichiers Parquet partitionnés
4. Les requêtes SQL peuvent combiner SQLite et Parquet de manière transparente

Exemple d'utilisation:
    engine = DuckDBEngine(warehouse_path="data/warehouse")
    engine.attach_sqlite("data/warehouse/metadata.db", "meta")
    
    # Jointure entre SQLite (players) et Parquet (match_facts)
    df = engine.query('''
        SELECT p.gamertag, AVG(m.kda) as avg_kda
        FROM read_parquet('data/warehouse/match_facts/**/*.parquet') m
        JOIN meta.players p ON m.xuid = p.xuid
        GROUP BY p.gamertag
    ''')
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import duckdb

from src.models import MatchRow


class DuckDBEngine:
    """
    Moteur de requête DuckDB pour l'architecture hybride.
    (DuckDB query engine for hybrid architecture)
    
    Permet :
    - Requêtes SQL sur fichiers Parquet
    - Attachement de bases SQLite
    - Jointures entre Parquet et SQLite
    - Agrégations haute performance
    """
    
    def __init__(
        self,
        warehouse_path: str | Path,
        *,
        read_only: bool = True,
        memory_limit: str = "512MB",
        threads: int | None = None,
    ) -> None:
        """
        Initialise le moteur DuckDB.
        (Initialize DuckDB engine)
        
        Args:
            warehouse_path: Chemin vers le dossier warehouse
            read_only: Si True, connexion en lecture seule
            memory_limit: Limite mémoire pour DuckDB
            threads: Nombre de threads (None = auto)
        """
        self.warehouse_path = Path(warehouse_path)
        self.read_only = read_only
        self._connection: duckdb.DuckDBPyConnection | None = None
        self._attached_dbs: dict[str, str] = {}  # alias -> path
        
        # Configuration DuckDB
        self._memory_limit = memory_limit
        self._threads = threads
    
    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        """
        Retourne une connexion DuckDB (créée à la demande).
        (Returns a DuckDB connection, created on demand)
        """
        if self._connection is None:
            # Connexion en mémoire pour les requêtes
            self._connection = duckdb.connect(":memory:")
            
            # Configuration pour performance
            self._connection.execute(f"SET memory_limit = '{self._memory_limit}'")
            if self._threads:
                self._connection.execute(f"SET threads = {self._threads}")
            
            # Configuration pour Parquet
            self._connection.execute("SET enable_object_cache = true")
        
        return self._connection
    
    def attach_sqlite(self, db_path: str | Path, alias: str = "meta") -> None:
        """
        Attache une base SQLite pour les jointures.
        (Attach a SQLite database for joins)
        
        Args:
            db_path: Chemin vers le fichier SQLite
            alias: Alias pour accéder aux tables (ex: meta.players)
        """
        db_path = Path(db_path)
        if not db_path.exists():
            raise FileNotFoundError(f"SQLite database not found: {db_path}")
        
        conn = self._get_connection()
        
        # Détacher si déjà attaché
        if alias in self._attached_dbs:
            conn.execute(f"DETACH DATABASE {alias}")
        
        # Attacher la base SQLite
        conn.execute(f"ATTACH DATABASE '{db_path}' AS {alias} (TYPE SQLITE, READ_ONLY)")
        self._attached_dbs[alias] = str(db_path)
    
    def query(self, sql: str, params: tuple | None = None) -> list[dict[str, Any]]:
        """
        Exécute une requête SQL et retourne les résultats.
        (Execute SQL query and return results)
        
        Args:
            sql: Requête SQL (peut utiliser read_parquet, tables attachées, etc.)
            params: Paramètres optionnels pour la requête
            
        Returns:
            Liste de dictionnaires (une ligne = un dict)
        """
        conn = self._get_connection()
        if params:
            result = conn.execute(sql, params)
        else:
            result = conn.execute(sql)
        
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
        
        return [dict(zip(columns, row)) for row in rows]
    
    def query_df(self, sql: str, params: tuple | None = None):
        """
        Exécute une requête SQL et retourne un DataFrame Polars.
        (Execute SQL query and return Polars DataFrame)
        """
        conn = self._get_connection()
        if params:
            result = conn.execute(sql, params)
        else:
            result = conn.execute(sql)
        
        return result.pl()  # Retourne un Polars DataFrame
    
    def get_parquet_path(self, table: str, xuid: str | None = None) -> str:
        """
        Construit le chemin Parquet avec pattern glob.
        (Build Parquet path with glob pattern)
        
        Args:
            table: Nom de la table (match_facts, medals, etc.)
            xuid: Optionnel, filtre par joueur
            
        Returns:
            Chemin avec pattern glob pour read_parquet()
        """
        base_path = self.warehouse_path / table
        
        if xuid:
            # Parquet partitionné par joueur
            return str(base_path / f"player={xuid}" / "**" / "*.parquet")
        else:
            # Tous les joueurs
            return str(base_path / "**" / "*.parquet")
    
    def load_matches(
        self,
        xuid: str,
        *,
        playlist_filter: str | None = None,
        map_filter: str | None = None,
        limit: int | None = None,
    ) -> list[MatchRow]:
        """
        Charge les matchs depuis Parquet.
        (Load matches from Parquet)
        
        Équivalent à load_matches() mais depuis Parquet via DuckDB.
        """
        parquet_path = self.get_parquet_path("match_facts", xuid)
        
        # Vérifier si des fichiers Parquet existent
        if not list(self.warehouse_path.glob(f"match_facts/player={xuid}/**/*.parquet")):
            return []
        
        where_clauses = ["xuid = ?"]
        params = [xuid]
        
        if playlist_filter:
            where_clauses.append("playlist_id = ?")
            params.append(playlist_filter)
        
        if map_filter:
            where_clauses.append("map_id = ?")
            params.append(map_filter)
        
        where_sql = " AND ".join(where_clauses)
        limit_sql = f"LIMIT {limit}" if limit else ""
        
        sql = f"""
            SELECT 
                match_id, start_time, map_id, map_name,
                playlist_id, playlist_name,
                game_variant_id, game_variant_name,
                outcome, team_id as last_team_id,
                kda, max_killing_spree, headshot_kills,
                avg_life_seconds as average_life_seconds,
                time_played_seconds, kills, deaths, assists, accuracy,
                my_team_score, enemy_team_score,
                team_mmr, enemy_mmr
            FROM read_parquet('{parquet_path}')
            WHERE {where_sql}
            ORDER BY start_time ASC
            {limit_sql}
        """
        
        rows = self.query(sql, tuple(params))
        
        return [
            MatchRow(
                match_id=r["match_id"],
                start_time=r["start_time"],
                map_id=r.get("map_id"),
                map_name=r.get("map_name"),
                playlist_id=r.get("playlist_id"),
                playlist_name=r.get("playlist_name"),
                map_mode_pair_id=None,
                map_mode_pair_name=None,
                game_variant_id=r.get("game_variant_id"),
                game_variant_name=r.get("game_variant_name"),
                outcome=r.get("outcome"),
                last_team_id=r.get("last_team_id"),
                kda=r.get("kda"),
                max_killing_spree=r.get("max_killing_spree"),
                headshot_kills=r.get("headshot_kills"),
                average_life_seconds=r.get("average_life_seconds"),
                time_played_seconds=r.get("time_played_seconds"),
                kills=r.get("kills", 0),
                deaths=r.get("deaths", 0),
                assists=r.get("assists", 0),
                accuracy=r.get("accuracy"),
                my_team_score=r.get("my_team_score"),
                enemy_team_score=r.get("enemy_team_score"),
                team_mmr=r.get("team_mmr"),
                enemy_mmr=r.get("enemy_mmr"),
            )
            for r in rows
        ]
    
    def get_kd_evolution_by_weapon(
        self,
        xuid: str,
        last_n_matches: int = 500,
    ) -> list[dict[str, Any]]:
        """
        Exemple de requête analytique complexe.
        (Example of complex analytical query)
        
        Calcule l'évolution du ratio K/D moyen par arme sur les N derniers matchs.
        Note: Requiert les données d'armes dans weapon_stats (à implémenter).
        """
        # TODO: Implémenter quand les données d'armes seront disponibles
        # Pour l'instant, retourne une liste vide
        return []
    
    def close(self) -> None:
        """Ferme la connexion DuckDB. (Close DuckDB connection)"""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
            self._attached_dbs.clear()
    
    def __enter__(self) -> DuckDBEngine:
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()
