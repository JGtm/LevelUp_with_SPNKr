"""Moteur de calcul et d'agrégation des citations H5G.

Ce module fournit ``CitationEngine``, classe responsable de :

- Charger les règles de mapping depuis ``citation_mappings`` (metadata.duckdb).
- Calculer les citations pour un match donné.
- Agréger les résultats depuis ``match_citations`` (player stats.duckdb).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import duckdb
import polars as pl

from src.analysis.citations.custom_rules import CUSTOM_FUNCTIONS

logger = logging.getLogger(__name__)


class CitationEngine:
    """Moteur de calcul des citations stockées en DuckDB.

    Chaque instance travaille sur la DB d'un joueur donné et charge
    les référentiels depuis ``metadata.duckdb`` (ATTACHé en ``meta``).

    En mode V5, les tables ``medals_earned`` et ``match_stats`` (via
    ``match_participants`` / ``match_registry``) sont lues depuis
    ``shared_matches.duckdb`` (ATTACHé en ``shared``).

    Args:
        db_path: Chemin vers ``stats.duckdb`` du joueur.
        xuid: XUID du joueur.
        metadata_db_path: Chemin vers ``metadata.duckdb``.  Si ``None``,
            dérivé automatiquement de *db_path*.
        shared_db_path: Chemin vers ``shared_matches.duckdb``.  Si ``None``,
            auto-détecté. Passez ``False`` pour désactiver.
        conn: Connexion DuckDB partagée (réutilisée si fournie).
    """

    def __init__(
        self,
        db_path: str | Path,
        xuid: str,
        *,
        metadata_db_path: str | Path | None = None,
        shared_db_path: str | Path | None | bool = None,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> None:
        self._db_path = Path(db_path)
        self._xuid = xuid
        self._shared_conn = conn  # Connexion partagée (réutilisée si fournie)

        if metadata_db_path is not None:
            self._metadata_db_path = Path(metadata_db_path)
        else:
            # Convention: data/players/{gt}/stats.duckdb → data/warehouse/metadata.duckdb
            self._metadata_db_path = (
                self._db_path.parent.parent.parent / "warehouse" / "metadata.duckdb"
            )

        # Auto-détection shared_matches.duckdb (V5)
        if shared_db_path is False:
            self._shared_db_path: Path | None = None
        elif shared_db_path is not None:
            self._shared_db_path = Path(shared_db_path)  # type: ignore[arg-type]
        else:
            candidate = self._db_path.parent.parent.parent / "warehouse" / "shared_matches.duckdb"
            self._shared_db_path = candidate if candidate.exists() else None

        self._mappings: dict[str, dict[str, Any]] | None = None
        self._attached_shared: bool = False

    # ------------------------------------------------------------------
    # Connexion helper
    # ------------------------------------------------------------------

    def _read_conn(self) -> tuple[duckdb.DuckDBPyConnection, bool]:
        """Retourne une connexion lecture et indique si elle a été créée.

        Si une connexion partagée est disponible, la retourne (owned=False).
        Sinon, ouvre une nouvelle connexion read-only (owned=True) et
        ATTACH ``shared_matches.duckdb`` si disponible.
        """
        if self._shared_conn is not None:
            return self._shared_conn, False
        conn = duckdb.connect(str(self._db_path), read_only=True)
        # ATTACH shared_matches.duckdb pour lecture V5
        if self._shared_db_path is not None and self._shared_db_path.exists():
            try:
                conn.execute(f"ATTACH '{self._shared_db_path}' AS shared (READ_ONLY)")
            except Exception as e:
                err = str(e).lower()
                if "already" not in err and "conflict" not in err:
                    logger.debug("Impossible d'attacher shared: %s", e)
        return conn, True

    @property
    def has_shared(self) -> bool:
        """Indique si shared_matches.duckdb est configuré et existe."""
        return self._shared_db_path is not None and self._shared_db_path.exists()

    def _conn_has_shared(self, conn: duckdb.DuckDBPyConnection) -> bool:
        """Vérifie si la connexion a le catalog 'shared' attaché."""
        try:
            result = conn.execute(
                "SELECT COUNT(*) FROM information_schema.schemata " "WHERE catalog_name = 'shared'"
            ).fetchone()
            return bool(result and result[0] > 0)
        except Exception:
            return False

    def _shared_has_table(self, conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
        """Vérifie si une table existe dans le catalog shared."""
        try:
            result = conn.execute(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_catalog = 'shared' AND table_name = ?",
                [table_name],
            ).fetchone()
            return bool(result and result[0] > 0)
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Mappings
    # ------------------------------------------------------------------

    def load_mappings(self) -> dict[str, dict[str, Any]]:
        """Charge les mappings depuis ``citation_mappings`` dans metadata.duckdb.

        Returns:
            Dict ``{citation_name_norm: {mapping fields…}}``.
        """
        if self._mappings is not None:
            return self._mappings

        meta_path = self._metadata_db_path
        if not meta_path.exists():
            logger.warning("metadata.duckdb introuvable : %s", meta_path)
            self._mappings = {}
            return self._mappings

        conn = duckdb.connect(str(meta_path), read_only=True)
        try:
            # Vérifier que la table existe
            exists = conn.execute(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_name = 'citation_mappings'"
            ).fetchone()[0]
            if not exists:
                logger.warning("Table citation_mappings absente dans %s", meta_path)
                self._mappings = {}
                return self._mappings

            rows = conn.execute(
                "SELECT citation_name_norm, citation_name_display, mapping_type, "
                "medal_id, medal_ids, stat_name, award_name, award_category, "
                "custom_function, confidence, notes "
                "FROM citation_mappings"
                # SUPPRIMÉ : WHERE enabled IS NOT FALSE
                # On charge TOUTES les citations pour l'affichage UI
            ).fetchall()

            columns = [
                "citation_name_norm",
                "citation_name_display",
                "mapping_type",
                "medal_id",
                "medal_ids",
                "stat_name",
                "award_name",
                "award_category",
                "custom_function",
                "confidence",
                "notes",
            ]
            self._mappings = {}
            for row in rows:
                d = dict(zip(columns, row, strict=False))
                norm = d.pop("citation_name_norm")
                self._mappings[norm] = d
            return self._mappings
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Calcul par match
    # ------------------------------------------------------------------

    def compute_citation_for_match(
        self,
        mapping: dict[str, Any],
        *,
        match_medals: dict[int, int] | None = None,
        match_stats: dict[str, Any] | None = None,
        match_awards: dict[str, int] | None = None,
        df_match: pl.DataFrame | None = None,
    ) -> int:
        """Calcule la valeur d'une citation pour un match.

        Args:
            mapping: Dictionnaire de mapping (issu de ``load_mappings``).
            match_medals: ``{medal_name_id: count}`` pour ce match.
            match_stats: Dict des stats du match (kills, deaths, …).
            match_awards: ``{award_name: count}`` pour ce match.
            df_match: Ligne DataFrame du match (pour fonctions custom).

        Returns:
            Valeur calculée (0 si non applicable).
        """
        mtype = mapping.get("mapping_type", "")

        if mtype == "medal":
            medal_id = mapping.get("medal_id")
            if medal_id is not None and match_medals:
                return match_medals.get(int(medal_id), 0)
            return 0

        if mtype == "stat":
            stat_name = mapping.get("stat_name", "")
            if stat_name and match_stats:
                try:
                    return int(match_stats.get(stat_name, 0) or 0)
                except (TypeError, ValueError):
                    return 0
            return 0

        if mtype == "award":
            award_name = mapping.get("award_name", "")
            if award_name and match_awards:
                return match_awards.get(award_name, 0)
            return 0

        if mtype == "custom":
            func_name = mapping.get("custom_function", "")
            func = CUSTOM_FUNCTIONS.get(func_name)
            if func is None:
                logger.warning("Fonction custom introuvable : %s", func_name)
                return 0
            try:
                return func(df=df_match, awards=match_awards)
            except TypeError:
                # Certaines fonctions n'acceptent que df
                try:
                    return func(df_match) if df_match is not None else 0
                except Exception:
                    return 0

        return 0

    def compute_all_for_match(
        self,
        match_id: str,  # noqa: ARG002 — conservé pour cohérence API
        *,
        match_medals: dict[int, int] | None = None,
        match_stats: dict[str, Any] | None = None,
        match_awards: dict[str, int] | None = None,
        df_match: pl.DataFrame | None = None,
    ) -> dict[str, int]:
        """Calcule toutes les citations pour un match.

        Returns:
            Dict sparse ``{citation_name_norm: value}`` (valeurs > 0 uniquement).
        """
        mappings = self.load_mappings()
        results: dict[str, int] = {}

        for norm_name, mapping in mappings.items():
            value = self.compute_citation_for_match(
                mapping,
                match_medals=match_medals,
                match_stats=match_stats,
                match_awards=match_awards,
                df_match=df_match,
            )
            if value > 0:
                results[norm_name] = value

        return results

    # ------------------------------------------------------------------
    # Agrégation depuis match_citations
    # ------------------------------------------------------------------

    def aggregate_citations(
        self,
        citation_names: list[str] | None = None,
        match_ids: list[str] | None = None,
    ) -> dict[str, int]:
        """Agrège les valeurs depuis la table ``match_citations``.

        Args:
            citation_names: Noms normalisés à agréger. ``None`` = tous.
            match_ids: Filtrer par matchs. ``None`` = tous.

        Returns:
            ``{citation_name_norm: total}``.
        """
        if not self._db_path.exists() and self._shared_conn is None:
            return {}

        conn, owned = self._read_conn()
        try:
            # Vérifier que la table existe
            exists = conn.execute(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_name = 'match_citations'"
            ).fetchone()[0]
            if not exists:
                return {}

            # Construire la requête dynamiquement
            conditions: list[str] = []
            params: list[Any] = []

            if citation_names is not None:
                placeholders = ", ".join(["?"] * len(citation_names))
                conditions.append(f"citation_name_norm IN ({placeholders})")
                params.extend(citation_names)

            if match_ids is not None:
                placeholders = ", ".join(["?"] * len(match_ids))
                conditions.append(f"match_id IN ({placeholders})")
                params.extend(match_ids)

            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

            rows = conn.execute(
                f"SELECT citation_name_norm, SUM(value) as total "
                f"FROM match_citations "
                f"{where} "
                f"GROUP BY citation_name_norm",
                params,
            ).fetchall()

            return {row[0]: int(row[1]) for row in rows}
        finally:
            if owned:
                conn.close()

    # ------------------------------------------------------------------
    # Helpers pour charger les données d'un match
    # ------------------------------------------------------------------

    def load_match_medals(self, match_id: str) -> dict[int, int]:
        """Charge les médailles d'un match.

        En V5, lit depuis ``shared.medals_earned`` (filtré par xuid).
        Sinon, lit depuis la table locale ``medals_earned``.

        Returns:
            ``{medal_name_id: count}``.
        """
        if not self._db_path.exists() and self._shared_conn is None:
            return {}

        conn, owned = self._read_conn()
        try:
            # V5 : lire depuis shared.medals_earned si disponible
            if self._conn_has_shared(conn) and self._shared_has_table(conn, "medals_earned"):
                rows = conn.execute(
                    "SELECT medal_name_id, count FROM shared.medals_earned "
                    "WHERE match_id = ? AND xuid = ?",
                    [match_id, self._xuid],
                ).fetchall()
                return {int(row[0]): int(row[1]) for row in rows}

            # V4 : lire depuis la table locale
            rows = conn.execute(
                "SELECT medal_name_id, count FROM medals_earned WHERE match_id = ?",
                [match_id],
            ).fetchall()
            return {int(row[0]): int(row[1]) for row in rows}
        except Exception:
            return {}
        finally:
            if owned:
                conn.close()

    def load_match_stats(self, match_id: str) -> dict[str, Any]:
        """Charge les stats d'un match.

        En V5, joint ``shared.match_participants`` et ``shared.match_registry``.
        Sinon, lit depuis la table locale ``match_stats``.

        Returns:
            Dict avec les colonnes de stats pour ce match.
        """
        if not self._db_path.exists() and self._shared_conn is None:
            return {}

        conn, owned = self._read_conn()
        try:
            # V5 : lire depuis shared.match_participants + match_registry
            if self._conn_has_shared(conn) and self._shared_has_table(conn, "match_participants"):
                result = conn.execute(
                    "SELECT p.*, r.map_name, r.playlist, r.game_variant, "
                    "r.match_start_date "
                    "FROM shared.match_participants p "
                    "LEFT JOIN shared.match_registry r ON p.match_id = r.match_id "
                    "WHERE p.match_id = ? AND p.xuid = ?",
                    [match_id, self._xuid],
                )
                row = result.fetchone()
                if row is not None:
                    columns = [desc[0] for desc in result.description]
                    return dict(zip(columns, row, strict=False))

            # V4 : lire depuis la table locale match_stats
            result = conn.execute(
                "SELECT * FROM match_stats WHERE match_id = ?",
                [match_id],
            )
            row = result.fetchone()
            if row is None:
                return {}
            columns = [desc[0] for desc in result.description]
            return dict(zip(columns, row, strict=False))
        except Exception:
            return {}
        finally:
            if owned:
                conn.close()

    def load_match_awards(self, match_id: str) -> dict[str, int]:
        """Charge les awards d'un match depuis ``personal_score_awards``.

        Returns:
            ``{award_name: total_count}``.
        """
        if not self._db_path.exists() and self._shared_conn is None:
            return {}

        conn, owned = self._read_conn()
        try:
            # Vérifier que la table existe
            exists = conn.execute(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_name = 'personal_score_awards'"
            ).fetchone()[0]
            if not exists:
                return {}

            rows = conn.execute(
                "SELECT award_name, SUM(award_count) "
                "FROM personal_score_awards "
                "WHERE match_id = ? "
                "GROUP BY award_name",
                [match_id],
            ).fetchall()
            return {str(row[0]): int(row[1]) for row in rows}
        except Exception:
            return {}
        finally:
            if owned:
                conn.close()

    def load_match_df(self, match_id: str) -> pl.DataFrame:
        """Charge un match comme DataFrame Polars (1 ligne).

        En V5, joint ``shared.match_participants`` + ``shared.match_registry``.
        Utile pour les fonctions custom qui attendent un DataFrame.
        """
        if not self._db_path.exists() and self._shared_conn is None:
            return pl.DataFrame()

        conn, owned = self._read_conn()
        try:
            # V5 : lire depuis shared
            if self._conn_has_shared(conn) and self._shared_has_table(conn, "match_participants"):
                result = conn.execute(
                    "SELECT p.*, r.map_name, r.playlist, r.game_variant, "
                    "r.match_start_date "
                    "FROM shared.match_participants p "
                    "LEFT JOIN shared.match_registry r ON p.match_id = r.match_id "
                    "WHERE p.match_id = ? AND p.xuid = ?",
                    [match_id, self._xuid],
                )
                try:
                    df = result.pl()
                    if len(df) > 0:
                        return df
                except Exception:
                    columns = [desc[0] for desc in result.description]
                    rows = result.fetchall()
                    if rows:
                        return pl.DataFrame(
                            {col: [row[i] for row in rows] for i, col in enumerate(columns)}
                        )

            # V4 : lire depuis match_stats local
            result = conn.execute(
                "SELECT * FROM match_stats WHERE match_id = ?",
                [match_id],
            )
            try:
                return result.pl()
            except Exception:
                columns = [desc[0] for desc in result.description]
                rows = result.fetchall()
                if not rows:
                    return pl.DataFrame()
                return pl.DataFrame(
                    {col: [row[i] for row in rows] for i, col in enumerate(columns)}
                )
        except Exception:
            return pl.DataFrame()
        finally:
            if owned:
                conn.close()

    # ------------------------------------------------------------------
    # Méthode haut-niveau : calcul complet pour un match
    # ------------------------------------------------------------------

    def compute_and_store_for_match(
        self,
        match_id: str,
        *,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> int:
        """Charge les données, calcule et insère les citations pour 1 match.

        Args:
            match_id: Identifiant du match.
            conn: Connexion ouverte en écriture (optionnelle, en crée une sinon).

        Returns:
            Nombre de citations insérées.
        """
        # Charger les données nécessaires
        match_medals = self.load_match_medals(match_id)
        match_stats = self.load_match_stats(match_id)
        match_awards = self.load_match_awards(match_id)
        df_match = self.load_match_df(match_id)

        # Calculer les citations
        citations = self.compute_all_for_match(
            match_id,
            match_medals=match_medals,
            match_stats=match_stats,
            match_awards=match_awards,
            df_match=df_match,
        )

        if not citations:
            return 0

        # Insérer dans match_citations
        own_conn = conn is None
        if own_conn:
            if self._shared_conn is not None:
                conn = self._shared_conn
                own_conn = False
            else:
                conn = duckdb.connect(str(self._db_path))

        try:
            for norm_name, value in citations.items():
                conn.execute(
                    "INSERT OR REPLACE INTO match_citations "
                    "(match_id, citation_name_norm, value) VALUES (?, ?, ?)",
                    [match_id, norm_name, value],
                )
            return len(citations)
        finally:
            if own_conn:
                conn.close()

    # ------------------------------------------------------------------
    # Méthode haut-niveau : agrégation compatible UI
    # ------------------------------------------------------------------

    def aggregate_for_display(
        self,
        match_ids: list[str] | None = None,
    ) -> dict[str, int]:
        """Agrège toutes les citations pour affichage UI.

        Wrapper simplifié de ``aggregate_citations`` sans filtrage par nom.

        Args:
            match_ids: Filtrer par matchs. ``None`` = tous.

        Returns:
            ``{citation_name_norm: total}``.
        """
        return self.aggregate_citations(citation_names=None, match_ids=match_ids)
