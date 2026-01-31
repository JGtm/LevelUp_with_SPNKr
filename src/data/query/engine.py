"""
Moteur de requête DuckDB unifié.
(Unified DuckDB query engine)

HOW IT WORKS:
Ce moteur encapsule toutes les opérations DuckDB et fournit :
1. Attachement automatique de la base SQLite metadata
2. Construction de chemins Parquet avec partitionnement
3. Exécution de requêtes SQL avec retour typé
4. Gestion du cache et des optimisations

Le moteur peut être utilisé directement pour des requêtes ad-hoc
ou via les classes de haut niveau (AnalyticsQueries, TrendAnalyzer).

Exemple de requête avec jointure SQLite + Parquet:
    engine = QueryEngine("data/warehouse")
    
    # DuckDB joint automatiquement SQLite (meta.players) et Parquet (match_facts)
    result = engine.execute('''
        SELECT 
            p.gamertag,
            AVG(m.kda) as avg_kda,
            COUNT(*) as matches
        FROM match_facts m
        JOIN meta.players p ON m.xuid = p.xuid
        GROUP BY p.gamertag
        ORDER BY avg_kda DESC
    ''', xuid="1234567890")
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal, overload

import duckdb
import polars as pl

from src.models import MatchRow


logger = logging.getLogger(__name__)


class QueryEngine:
    """
    Moteur de requête DuckDB pour l'architecture hybride.
    (DuckDB query engine for hybrid architecture)
    
    Fournit une interface unifiée pour :
    - Requêtes SQL sur Parquet
    - Jointures avec SQLite (metadata)
    - Agrégations analytiques haute performance
    """
    
    def __init__(
        self,
        warehouse_path: str | Path,
        *,
        memory_limit: str = "1GB",
        threads: int | None = None,
    ) -> None:
        """
        Initialise le moteur de requête.
        (Initialize query engine)
        
        Args:
            warehouse_path: Chemin vers le dossier warehouse
            memory_limit: Limite mémoire DuckDB (défaut: 1GB)
            threads: Nombre de threads (None = auto-detect)
        """
        self.warehouse_path = Path(warehouse_path)
        self._memory_limit = memory_limit
        self._threads = threads
        self._connection: duckdb.DuckDBPyConnection | None = None
        self._metadata_attached = False
        
        # Vérifier que le warehouse existe
        if not self.warehouse_path.exists():
            logger.warning(f"Warehouse non trouvé: {self.warehouse_path}")
    
    @property
    def connection(self) -> duckdb.DuckDBPyConnection:
        """
        Retourne la connexion DuckDB (lazy loading).
        (Return DuckDB connection with lazy loading)
        """
        if self._connection is None:
            self._connection = self._create_connection()
        return self._connection
    
    def _create_connection(self) -> duckdb.DuckDBPyConnection:
        """
        Crée et configure une connexion DuckDB.
        (Create and configure a DuckDB connection)
        """
        conn = duckdb.connect(":memory:")
        
        # Configuration pour performance
        conn.execute(f"SET memory_limit = '{self._memory_limit}'")
        if self._threads:
            conn.execute(f"SET threads = {self._threads}")
        
        # Optimisations pour Parquet
        conn.execute("SET enable_object_cache = true")
        conn.execute("SET enable_progress_bar = false")
        
        # Attacher la base SQLite metadata si elle existe
        metadata_db = self.warehouse_path / "metadata.db"
        if metadata_db.exists():
            conn.execute(
                f"ATTACH DATABASE '{metadata_db}' AS meta (TYPE SQLITE, READ_ONLY)"
            )
            self._metadata_attached = True
            logger.debug(f"SQLite metadata attachée: {metadata_db}")
        
        return conn
    
    def get_parquet_glob(
        self,
        table: str,
        xuid: str | None = None,
        year: int | None = None,
        month: int | None = None,
    ) -> str:
        """
        Construit le pattern glob pour les fichiers Parquet.
        (Build glob pattern for Parquet files)
        
        Args:
            table: Nom de la table (match_facts, medals, etc.)
            xuid: Optionnel, filtre par joueur
            year: Optionnel, filtre par année
            month: Optionnel, filtre par mois
            
        Returns:
            Pattern glob pour read_parquet()
        """
        parts = [str(self.warehouse_path / table)]
        
        if xuid:
            parts.append(f"player={xuid}")
        else:
            parts.append("player=*")
        
        if year:
            parts.append(f"year={year}")
        else:
            parts.append("year=*")
        
        if month:
            parts.append(f"month={month:02d}")
        else:
            parts.append("month=*")
        
        parts.append("*.parquet")
        
        return "/".join(parts)
    
    def has_data(self, table: str, xuid: str | None = None) -> bool:
        """
        Vérifie si des données Parquet existent.
        (Check if Parquet data exists)
        """
        table_path = self.warehouse_path / table
        if not table_path.exists():
            return False
        
        if xuid:
            player_path = table_path / f"player={xuid}"
            if not player_path.exists():
                return False
            return bool(list(player_path.glob("**/*.parquet")))
        
        return bool(list(table_path.glob("**/*.parquet")))
    
    @overload
    def execute(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
        *,
        return_type: Literal["list"] = "list",
    ) -> list[dict[str, Any]]: ...
    
    @overload
    def execute(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
        *,
        return_type: Literal["polars"],
    ) -> pl.DataFrame: ...
    
    @overload
    def execute(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
        *,
        return_type: Literal["raw"],
    ) -> duckdb.DuckDBPyRelation: ...
    
    def execute(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
        *,
        return_type: Literal["list", "polars", "raw"] = "list",
    ) -> list[dict[str, Any]] | pl.DataFrame | duckdb.DuckDBPyRelation:
        """
        Exécute une requête SQL et retourne les résultats.
        (Execute SQL query and return results)
        
        Args:
            sql: Requête SQL (peut contenir des placeholders $var)
            params: Paramètres pour les placeholders
            return_type: Format de retour ("list", "polars", "raw")
            
        Returns:
            Résultats selon le return_type spécifié
            
        Exemple:
            # Avec placeholders
            result = engine.execute(
                "SELECT * FROM match_facts WHERE xuid = $xuid LIMIT $limit",
                {"xuid": "123", "limit": 10}
            )
        """
        conn = self.connection
        
        # Préparer les paramètres
        if params:
            # DuckDB utilise $name pour les paramètres nommés
            for key, value in params.items():
                conn.execute(f"SET VARIABLE {key} = {repr(value)}")
        
        try:
            result = conn.execute(sql)
            
            if return_type == "raw":
                return result
            elif return_type == "polars":
                return result.pl()
            else:  # "list"
                columns = [desc[0] for desc in result.description]
                rows = result.fetchall()
                return [dict(zip(columns, row)) for row in rows]
        finally:
            # Nettoyer les variables
            if params:
                for key in params:
                    try:
                        conn.execute(f"RESET VARIABLE {key}")
                    except Exception:
                        pass
    
    def execute_with_parquet(
        self,
        sql_template: str,
        table: str,
        xuid: str,
        *,
        params: dict[str, Any] | None = None,
        return_type: Literal["list", "polars"] = "list",
    ) -> list[dict[str, Any]] | pl.DataFrame:
        """
        Exécute une requête SQL avec remplacement automatique de la table Parquet.
        (Execute SQL with automatic Parquet table replacement)
        
        Le placeholder {table} est remplacé par read_parquet('...').
        
        Args:
            sql_template: Template SQL avec {table} comme placeholder
            table: Nom de la table Parquet
            xuid: XUID du joueur
            params: Paramètres additionnels
            
        Exemple:
            result = engine.execute_with_parquet(
                "SELECT * FROM {table} WHERE kills > 10 ORDER BY start_time DESC",
                table="match_facts",
                xuid="1234567890"
            )
        """
        if not self.has_data(table, xuid):
            return [] if return_type == "list" else pl.DataFrame()
        
        parquet_glob = self.get_parquet_glob(table, xuid)
        sql = sql_template.replace("{table}", f"read_parquet('{parquet_glob}')")
        
        return self.execute(sql, params, return_type=return_type)  # type: ignore
    
    def query_match_facts(
        self,
        xuid: str,
        *,
        select: str = "*",
        where: str | None = None,
        order_by: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Requête simplifiée sur la table match_facts.
        (Simplified query on match_facts table)
        
        Args:
            xuid: XUID du joueur
            select: Colonnes à sélectionner
            where: Clause WHERE optionnelle
            order_by: Clause ORDER BY optionnelle
            limit: Limite de résultats
            
        Exemple:
            # Derniers 100 matchs gagnés
            wins = engine.query_match_facts(
                xuid="123",
                select="match_id, start_time, kills, deaths",
                where="outcome = 2",
                order_by="start_time DESC",
                limit=100
            )
        """
        parts = [f"SELECT {select}", "FROM {table}"]
        
        if where:
            parts.append(f"WHERE {where}")
        if order_by:
            parts.append(f"ORDER BY {order_by}")
        if limit:
            parts.append(f"LIMIT {limit}")
        
        sql = " ".join(parts)
        return self.execute_with_parquet(sql, "match_facts", xuid)  # type: ignore
    
    def query_with_metadata_join(
        self,
        sql_template: str,
        xuid: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Requête avec jointure automatique sur les métadonnées SQLite.
        (Query with automatic join on SQLite metadata)
        
        Placeholders disponibles:
        - {match_facts} : Table des faits de match
        - {medals} : Table des médailles
        - {players} : meta.players (SQLite)
        - {playlists} : meta.playlists (SQLite)
        - {maps} : meta.maps (SQLite)
        
        Exemple:
            result = engine.query_with_metadata_join('''
                SELECT 
                    p.gamertag,
                    pl.public_name as playlist,
                    AVG(m.kda) as avg_kda
                FROM {match_facts} m
                JOIN {players} p ON m.xuid = p.xuid
                LEFT JOIN {playlists} pl ON m.playlist_id = pl.asset_id
                GROUP BY p.gamertag, pl.public_name
            ''', xuid="123")
        """
        if not self._metadata_attached:
            logger.warning("SQLite metadata non attachée, jointures limitées")
        
        # Remplacer les placeholders
        sql = sql_template
        
        if "{match_facts}" in sql:
            if self.has_data("match_facts", xuid):
                parquet_glob = self.get_parquet_glob("match_facts", xuid)
                sql = sql.replace("{match_facts}", f"read_parquet('{parquet_glob}')")
            else:
                logger.warning("Pas de données match_facts")
                return []
        
        if "{medals}" in sql:
            if self.has_data("medals", xuid):
                parquet_glob = self.get_parquet_glob("medals", xuid)
                sql = sql.replace("{medals}", f"read_parquet('{parquet_glob}')")
            else:
                sql = sql.replace("{medals}", "(SELECT NULL as match_id LIMIT 0)")
        
        # Placeholders SQLite
        sql = sql.replace("{players}", "meta.players")
        sql = sql.replace("{playlists}", "meta.playlists")
        sql = sql.replace("{maps}", "meta.maps")
        sql = sql.replace("{game_variants}", "meta.game_variants")
        sql = sql.replace("{medal_definitions}", "meta.medal_definitions")
        
        return self.execute(sql, params)  # type: ignore
    
    def to_match_rows(self, results: list[dict[str, Any]]) -> list[MatchRow]:
        """
        Convertit les résultats de requête en MatchRow.
        (Convert query results to MatchRow)
        """
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
                last_team_id=r.get("team_id") or r.get("last_team_id"),
                kda=r.get("kda"),
                max_killing_spree=r.get("max_killing_spree"),
                headshot_kills=r.get("headshot_kills"),
                average_life_seconds=r.get("avg_life_seconds"),
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
            for r in results
        ]
    
    def close(self) -> None:
        """Ferme la connexion DuckDB. (Close DuckDB connection)"""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
            self._metadata_attached = False
    
    def __enter__(self) -> QueryEngine:
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
