"""Module d'indexation des médias et association avec les matchs.

Ce module gère :
- Le scan incrémental des dossiers de médias
- L'association automatique média → match via proximité temporelle (multi-joueurs)
- La génération de thumbnails pour les nouveaux contenus

Note: Les médias n'ont plus de propriétaire unique. Les associations se font
via media_match_associations pour tous les joueurs ayant un match correspondant.
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb

from src.utils.paths import PLAYER_DB_FILENAME, PLAYERS_DIR

logger = logging.getLogger(__name__)


def _match_start_to_epoch(start_time: datetime | str | float) -> float | None:
    """Convertit start_time (DB/API) en epoch seconds pour comparaison avec mtime_paris_epoch.

    L'API et le sync stockent start_time en UTC. DuckDB peut retourner un datetime naïf
    (sans timezone) = UTC. On convertit en epoch UTC pour comparer avec les mtime des fichiers.
    """
    try:
        if isinstance(start_time, int | float):
            return float(start_time)
        if isinstance(start_time, datetime):
            dt = start_time
        elif isinstance(start_time, str):
            if start_time.endswith("Z"):
                dt = datetime.fromisoformat(start_time[:-1] + "+00:00")
            elif "+" in start_time or start_time.count("-") > 2:
                dt = datetime.fromisoformat(start_time)
            else:
                dt = datetime.fromisoformat(start_time + "+00:00")
        else:
            return None
        # Datetime naïf depuis DuckDB = UTC (convention API/sync)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return None


# Extensions supportées
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mkv", ".mov", ".avi"}


@dataclass
class ScanResult:
    """Résultat d'un scan de médias."""

    n_scanned: int = 0
    n_new: int = 0
    n_updated: int = 0
    n_associated: int = 0
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class MediaIndexer:
    """Gère l'indexation des médias et l'association avec les matchs.

    Les médias sont indexés sans propriétaire unique. Les associations se font
    automatiquement avec tous les joueurs ayant un match correspondant.
    """

    def __init__(self, db_path: Path | None = None):
        """Initialise l'indexeur.

        Args:
            db_path: Chemin vers une DB DuckDB pour le stockage des médias.
                    Si None, utilise la première DB trouvée dans data/players/.
                    Note: Les médias sont stockés dans une seule DB mais associés
                    à tous les joueurs via media_match_associations.
        """
        if db_path:
            self.db_path = Path(db_path)
        else:
            # Auto-détection : utiliser la première DB trouvée
            if not PLAYERS_DIR.exists():
                raise ValueError("Aucune DB joueur trouvée dans data/players/")
            for player_dir in PLAYERS_DIR.iterdir():
                if player_dir.is_dir():
                    db_file = player_dir / PLAYER_DB_FILENAME
                    if db_file.exists():
                        self.db_path = db_file
                        break
            if not hasattr(self, "db_path") or not self.db_path.exists():
                raise ValueError("Aucune DB joueur valide trouvée")

    def _get_existing_columns(self, conn: duckdb.DuckDBPyConnection, table: str) -> set[str]:
        """Récupère les colonnes existantes d'une table."""
        try:
            cols = conn.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'main'
                AND table_name = ?
                """,
                [table],
            ).fetchall()
            return {row[0] for row in cols}
        except Exception:
            return set()

    def ensure_schema(self) -> None:
        """Crée les tables si elles n'existent pas et migre si nécessaire."""
        try:
            conn = duckdb.connect(str(self.db_path), read_only=False)
            try:
                # Vérifier si les tables existent
                tables = conn.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'main'
                    AND table_name IN ('media_files', 'media_match_associations')
                    """
                ).fetchall()

                existing_tables = {row[0] for row in tables}

                # Migration: supprimer owner_xuid si la table existe avec l'ancien schéma
                if "media_files" in existing_tables:
                    existing_cols = self._get_existing_columns(conn, "media_files")
                    if "owner_xuid" in existing_cols:
                        logger.info(
                            "Migration: suppression de la colonne owner_xuid de media_files"
                        )
                        try:
                            # Supprimer l'index d'abord si il existe
                            import contextlib

                            with contextlib.suppress(Exception):
                                conn.execute("DROP INDEX IF EXISTS idx_media_owner")
                            # Essayer de supprimer la colonne directement
                            try:
                                conn.execute("ALTER TABLE media_files DROP COLUMN owner_xuid")
                                conn.commit()
                                logger.info("✅ Migration réussie: colonne owner_xuid supprimée")
                            except Exception as drop_error:
                                # Si DROP COLUMN échoue, recréer la table sans owner_xuid
                                logger.warning(
                                    f"DROP COLUMN échoué ({drop_error}), recréation de la table..."
                                )
                                # Sauvegarder les données existantes (sans owner_xuid)
                                conn.execute(
                                    """
                                    CREATE TABLE media_files_new (
                                        file_path VARCHAR PRIMARY KEY,
                                        file_hash VARCHAR NOT NULL,
                                        file_name VARCHAR NOT NULL,
                                        file_size BIGINT NOT NULL,
                                        file_ext VARCHAR NOT NULL,
                                        kind VARCHAR NOT NULL,
                                        mtime DOUBLE NOT NULL,
                                        mtime_paris_epoch DOUBLE NOT NULL,
                                        thumbnail_path VARCHAR,
                                        thumbnail_generated_at TIMESTAMP,
                                        first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                        last_scan_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                        scan_version INTEGER DEFAULT 1
                                    )
                                    """
                                )
                                # Copier les données (sans owner_xuid)
                                conn.execute(
                                    """
                                    INSERT INTO media_files_new
                                    SELECT
                                        file_path, file_hash, file_name, file_size, file_ext, kind,
                                        mtime, mtime_paris_epoch, thumbnail_path, thumbnail_generated_at,
                                        first_seen_at, last_scan_at, scan_version
                                    FROM media_files
                                    """
                                )
                                # Supprimer l'ancienne table et renommer
                                conn.execute("DROP TABLE media_files")
                                conn.execute("ALTER TABLE media_files_new RENAME TO media_files")
                                # Recréer les index
                                conn.execute(
                                    "CREATE INDEX IF NOT EXISTS idx_media_mtime ON media_files(mtime_paris_epoch DESC)"
                                )
                                conn.execute(
                                    "CREATE INDEX IF NOT EXISTS idx_media_kind ON media_files(kind)"
                                )
                                conn.execute(
                                    "CREATE INDEX IF NOT EXISTS idx_media_hash ON media_files(file_hash)"
                                )
                                conn.commit()
                                logger.info("✅ Migration réussie: table recréée sans owner_xuid")
                        except Exception as e:
                            logger.error(
                                f"❌ Erreur lors de la migration (colonne owner_xuid): {e}",
                                exc_info=True,
                            )
                            # Si la migration échoue complètement, on continue quand même
                            # L'utilisateur devra peut-être supprimer manuellement la colonne

                # Créer media_files si nécessaire
                if "media_files" not in existing_tables:
                    conn.execute("""
                        CREATE TABLE media_files (
                            file_path VARCHAR PRIMARY KEY,
                            file_hash VARCHAR NOT NULL,
                            file_name VARCHAR NOT NULL,
                            file_size BIGINT NOT NULL,
                            file_ext VARCHAR NOT NULL,
                            kind VARCHAR NOT NULL,
                            mtime DOUBLE NOT NULL,
                            mtime_paris_epoch DOUBLE NOT NULL,
                            thumbnail_path VARCHAR,
                            thumbnail_generated_at TIMESTAMP,
                            first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            last_scan_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            scan_version INTEGER DEFAULT 1
                        )
                    """)
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_media_mtime ON media_files(mtime_paris_epoch DESC)"
                    )
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_media_kind ON media_files(kind)")
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_media_hash ON media_files(file_hash)"
                    )
                    logger.info("Table media_files créée")

                # Créer media_match_associations si nécessaire
                if "media_match_associations" not in existing_tables:
                    conn.execute("""
                        CREATE TABLE media_match_associations (
                            media_path VARCHAR NOT NULL,
                            match_id VARCHAR NOT NULL,
                            xuid VARCHAR NOT NULL,
                            match_start_time TIMESTAMP NOT NULL,
                            association_confidence DOUBLE DEFAULT 1.0,
                            associated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            PRIMARY KEY (media_path, match_id, xuid)
                        )
                    """)
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_assoc_media ON media_match_associations(media_path)"
                    )
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_assoc_match ON media_match_associations(match_id, xuid)"
                    )
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_assoc_xuid ON media_match_associations(xuid)"
                    )
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_assoc_time ON media_match_associations(match_start_time DESC)"
                    )
                    logger.info("Table media_match_associations créée")

                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"Erreur lors de la création du schéma: {e}", exc_info=True)
            raise

    def _compute_file_hash(self, file_path: Path) -> str:
        """Calcule le hash MD5 d'un fichier."""
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.warning(f"Impossible de calculer le hash de {file_path}: {e}")
            return ""

    def _get_file_metadata(self, file_path: Path) -> dict[str, Any] | None:
        """Récupère les métadonnées d'un fichier."""
        try:
            if not file_path.exists():
                return None

            stat = file_path.stat()
            ext = file_path.suffix.lower()
            kind = (
                "video"
                if ext in VIDEO_EXTENSIONS
                else "image"
                if ext in IMAGE_EXTENSIONS
                else "unknown"
            )

            if kind == "unknown":
                return None

            # Timestamp système : st_mtime est toujours en epoch UTC (POSIX).
            # On le garde tel quel pour l'association (comparaison avec start_time en UTC).
            mtime_sys = float(stat.st_mtime)
            mtime_paris_epoch = mtime_sys

            return {
                "file_path": str(file_path.resolve()),
                "file_name": file_path.name,
                "file_size": stat.st_size,
                "file_ext": ext.lstrip("."),
                "kind": kind,
                "mtime": mtime_sys,
                "mtime_paris_epoch": mtime_paris_epoch,
            }
        except Exception as e:
            logger.warning(f"Erreur lors de la lecture de {file_path}: {e}")
            return None

    def scan_and_index(
        self,
        videos_dir: Path | None,
        screens_dir: Path | None,
        *,
        force_rescan: bool = False,
    ) -> ScanResult:
        """Scanne les dossiers et met à jour l'index en BDD.

        Args:
            videos_dir: Dossier des vidéos.
            screens_dir: Dossier des captures d'écran.
            force_rescan: Si True, re-scanner tous les fichiers même s'ils existent déjà.

        Returns:
            ScanResult avec statistiques du scan.
        """
        self.ensure_schema()

        result = ScanResult()
        now = datetime.now()

        # Récupérer les fichiers déjà indexés pour comparaison
        conn = duckdb.connect(str(self.db_path), read_only=False)
        try:
            existing_files = {}
            if not force_rescan:
                existing = conn.execute(
                    "SELECT file_path, file_hash, mtime FROM media_files"
                ).fetchall()
                existing_files = {row[0]: {"hash": row[1], "mtime": row[2]} for row in existing}

            # Scanner les dossiers
            files_to_process: list[dict[str, Any]] = []

            for media_dir, exts in [
                (videos_dir, VIDEO_EXTENSIONS),
                (screens_dir, IMAGE_EXTENSIONS),
            ]:
                if not media_dir or not Path(media_dir).exists():
                    continue

                media_path = Path(media_dir)
                for root, _dirs, files in os.walk(media_path):
                    for filename in files:
                        file_path = Path(root) / filename
                        ext = file_path.suffix.lower()

                        if ext not in exts:
                            continue

                        result.n_scanned += 1

                        # Récupérer métadonnées
                        metadata = self._get_file_metadata(file_path)
                        if not metadata:
                            continue

                        file_path_str = str(file_path.resolve())

                        # Vérifier si nouveau ou modifié
                        if file_path_str in existing_files:
                            existing = existing_files[file_path_str]
                            # Calculer hash seulement si nécessaire
                            if (
                                not force_rescan
                                and abs(metadata["mtime"] - existing["mtime"]) < 1.0
                            ):
                                continue  # Pas de changement

                        # Calculer hash
                        file_hash = self._compute_file_hash(file_path)
                        if not file_hash:
                            result.errors.append(
                                f"Impossible de calculer hash pour {file_path_str}"
                            )
                            continue

                        metadata["file_hash"] = file_hash
                        files_to_process.append(metadata)

            # Insérer/mettre à jour en BDD
            for metadata in files_to_process:
                file_path_str = metadata["file_path"]
                is_new = file_path_str not in existing_files

                try:
                    conn.execute(
                        """
                        INSERT INTO media_files (
                            file_path, file_hash, file_name, file_size, file_ext, kind,
                            mtime, mtime_paris_epoch, last_scan_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT (file_path) DO UPDATE SET
                            file_hash = EXCLUDED.file_hash,
                            file_size = EXCLUDED.file_size,
                            mtime = EXCLUDED.mtime,
                            mtime_paris_epoch = EXCLUDED.mtime_paris_epoch,
                            last_scan_at = EXCLUDED.last_scan_at
                        """,
                        [
                            file_path_str,
                            metadata["file_hash"],
                            metadata["file_name"],
                            metadata["file_size"],
                            metadata["file_ext"],
                            metadata["kind"],
                            metadata["mtime"],
                            metadata["mtime_paris_epoch"],
                            now,
                        ],
                    )

                    if is_new:
                        result.n_new += 1
                    else:
                        result.n_updated += 1

                except Exception as e:
                    result.errors.append(f"Erreur insertion {file_path_str}: {e}")
                    logger.error(f"Erreur insertion média: {e}", exc_info=True)

            conn.commit()
            logger.info(
                f"Scan terminé: {result.n_scanned} fichiers scannés, "
                f"{result.n_new} nouveaux, {result.n_updated} mis à jour"
            )

        finally:
            conn.close()

        return result

    @staticmethod
    def _get_all_player_dbs() -> list[tuple[Path, str]]:
        """Récupère toutes les DBs joueurs avec leurs XUIDs.

        Returns:
            Liste de tuples (db_path, xuid) pour chaque joueur.
        """
        player_dbs = []
        if not PLAYERS_DIR.exists():
            return player_dbs

        for player_dir in PLAYERS_DIR.iterdir():
            if not player_dir.is_dir():
                continue

            db_path = player_dir / PLAYER_DB_FILENAME
            if not db_path.exists():
                continue

            # Essayer de récupérer le XUID depuis sync_meta
            xuid = None
            try:
                conn = duckdb.connect(str(db_path), read_only=True)
                try:
                    result = conn.execute(
                        "SELECT value FROM sync_meta WHERE key = 'xuid'"
                    ).fetchone()
                    if result:
                        xuid = result[0]
                except Exception:
                    pass
                finally:
                    conn.close()
            except Exception:
                pass

            # Si pas de XUID dans sync_meta, utiliser le gamertag comme fallback
            if not xuid:
                xuid = player_dir.name  # Gamertag comme fallback

            player_dbs.append((db_path, xuid))

        return player_dbs

    def associate_with_matches(
        self,
        tolerance_minutes: int = 5,
    ) -> int:
        """Associe les médias non associés avec les matchs de TOUS les joueurs.

        Parcourt toutes les DBs joueurs et crée des associations pour chaque joueur
        ayant un match correspondant au média.

        Args:
            tolerance_minutes: Tolérance en minutes pour l'association temporelle.

        Returns:
            Nombre total d'associations créées (peut être > nombre de médias si multi-joueurs).
        """
        self.ensure_schema()

        # Corriger une fois les médias indexés avec l'ancienne logique (mtime_paris_epoch ≠ mtime)
        conn_fix = duckdb.connect(str(self.db_path), read_only=False)
        try:
            conn_fix.execute(
                "UPDATE media_files SET mtime_paris_epoch = mtime WHERE mtime_paris_epoch != mtime"
            )
            conn_fix.commit()
        except Exception:
            pass
        finally:
            conn_fix.close()

        # Récupérer tous les médias non associés depuis la DB centrale
        conn_read = duckdb.connect(str(self.db_path), read_only=True)
        try:
            unassociated = conn_read.execute(
                """
                SELECT
                    mf.file_path,
                    mf.mtime_paris_epoch
                FROM media_files mf
                WHERE NOT EXISTS (
                    SELECT 1 FROM media_match_associations mma
                    WHERE mma.media_path = mf.file_path
                )
                ORDER BY mf.mtime_paris_epoch DESC
                """
            ).fetchall()

            if not unassociated:
                logger.info("Aucun média non associé trouvé")
                return 0

            logger.info(f"{len(unassociated)} média(s) non associé(s) à traiter")

        finally:
            conn_read.close()

        # Parcourir toutes les DBs joueurs
        player_dbs = self._get_all_player_dbs()
        if not player_dbs:
            logger.warning("Aucune DB joueur trouvée pour l'association")
            return 0

        logger.info(f"Parcours de {len(player_dbs)} DB(s) joueur(s) pour l'association")

        tol_seconds = tolerance_minutes * 60
        total_associations = 0

        # Connexion pour les insertions (réutilisée pour toutes les associations)
        # Quand la DB joueur = DB médias, on réutilise cette connexion pour éviter
        # "Can't open same database file with different configuration"
        conn_write = duckdb.connect(str(self.db_path), read_only=False)
        try:
            for player_db_path, player_xuid in player_dbs:
                try:
                    # Réutiliser conn_write si on lit la même DB (évite double connexion DuckDB)
                    if player_db_path.resolve() == self.db_path.resolve():
                        player_conn = conn_write
                    else:
                        player_conn = duckdb.connect(str(player_db_path), read_only=True)

                    try:
                        # Récupérer les fenêtres temporelles des matchs de ce joueur
                        match_windows = player_conn.execute(
                            """
                            SELECT
                                match_id,
                                start_time,
                                time_played_seconds
                            FROM match_stats
                            WHERE start_time IS NOT NULL
                            ORDER BY start_time DESC
                            """
                        ).fetchall()

                        if not match_windows:
                            continue  # Pas de matchs pour ce joueur

                        # Pour chaque média non associé, chercher des matchs correspondants
                        for media_path, mtime_epoch in unassociated:
                            best_matches = []  # Peut avoir plusieurs matchs dans la fenêtre

                            for match_id, start_time, time_played in match_windows:
                                try:
                                    # start_time en DB = UTC ; convertir en epoch pour comparaison
                                    start_epoch = _match_start_to_epoch(start_time)
                                    if start_epoch is None:
                                        continue

                                    duration = float(time_played or 0) if time_played else 12 * 60
                                    end_epoch = start_epoch + duration

                                    window_start = start_epoch - tol_seconds
                                    window_end = end_epoch + tol_seconds

                                    if window_start <= mtime_epoch <= window_end:
                                        distance = abs(mtime_epoch - start_epoch)
                                        best_matches.append((match_id, start_time, distance))

                                except Exception as e:
                                    logger.debug(f"Erreur traitement match {match_id}: {e}")
                                    continue

                            # Créer une association pour chaque match correspondant
                            if best_matches:
                                # Trier par distance et prendre le meilleur (ou tous si plusieurs très proches)
                                best_matches.sort(key=lambda x: x[2])
                                for match_id, start_time, _distance in best_matches:
                                    try:
                                        conn_write.execute(
                                            """
                                            INSERT INTO media_match_associations (
                                                media_path, match_id, xuid, match_start_time, association_confidence
                                            ) VALUES (?, ?, ?, ?, ?)
                                            ON CONFLICT (media_path, match_id, xuid) DO NOTHING
                                            """,
                                            [media_path, match_id, player_xuid, start_time, 1.0],
                                        )
                                        total_associations += 1
                                    except Exception as e:
                                        logger.warning(
                                            f"Erreur association {media_path} → {match_id} (joueur {player_xuid}): {e}"
                                        )

                    finally:
                        if player_conn is not conn_write:
                            player_conn.close()

                except Exception as e:
                    logger.warning(f"Erreur lecture DB joueur {player_db_path}: {e}")
                    continue

            # Commit toutes les associations
            conn_write.commit()

            # Vérifier s'il reste des médias non associés
            remaining_unassociated = conn_write.execute(
                """
                SELECT COUNT(*)
                FROM media_files mf
                WHERE NOT EXISTS (
                    SELECT 1 FROM media_match_associations mma
                    WHERE mma.media_path = mf.file_path
                )
                """
            ).fetchone()[0]

            if remaining_unassociated > 0:
                logger.warning(
                    f"{remaining_unassociated} média(s) non associé(s) - "
                    "vérifier la tolérance temporelle ou la synchronisation des matchs"
                )

            logger.info(
                f"{total_associations} association(s) créée(s) pour {len(unassociated)} média(s)"
            )

        finally:
            conn_write.close()

        return total_associations

    def generate_thumbnails_for_new(
        self,
        videos_dir: Path,
        *,
        max_concurrent: int = 2,  # noqa: ARG002
    ) -> tuple[int, int]:
        """Génère les thumbnails pour les vidéos sans thumbnail.

        Args:
            videos_dir: Dossier contenant les vidéos.
            max_concurrent: Nombre maximum de générations simultanées (non utilisé pour l'instant).

        Returns:
            Tuple (generated, errors).
        """
        if not videos_dir or not videos_dir.exists():
            return 0, 0

        # Importer les fonctions du script existant
        try:
            from scripts.generate_thumbnails import (
                check_ffmpeg,
                generate_thumbnail_gif,
                get_thumbnail_path,
            )
        except ImportError as e:
            logger.warning(
                f"Impossible d'importer generate_thumbnails: {e} - vérifier que le module existe"
            )
            return 0, 0

        # Vérifier que ffmpeg est disponible
        if not check_ffmpeg():
            logger.warning(
                "ffmpeg n'est pas disponible - génération thumbnails ignorée. "
                "Installez ffmpeg pour générer les thumbnails automatiquement."
            )
            return 0, 0

        self.ensure_schema()

        conn = duckdb.connect(str(self.db_path), read_only=False)
        try:
            # Récupérer les vidéos sans thumbnail
            videos_without_thumb = conn.execute(
                """
                SELECT file_path, file_name
                FROM media_files
                WHERE kind = 'video'
                    AND (thumbnail_path IS NULL OR thumbnail_path = '')
                ORDER BY mtime_paris_epoch DESC
                """
            ).fetchall()

            if not videos_without_thumb:
                logger.info("Aucune vidéo sans thumbnail à générer")
                return 0, 0

            thumbs_dir = videos_dir / "thumbs"
            thumbs_dir.mkdir(exist_ok=True)

            generated = 0
            errors = 0

            for file_path_str, file_name in videos_without_thumb:
                video_path = Path(file_path_str)

                # Vérifier que le fichier existe toujours
                if not video_path.exists():
                    logger.warning(f"Fichier vidéo introuvable: {video_path}")
                    continue

                # Générer le chemin du thumbnail
                thumb_path = get_thumbnail_path(video_path, thumbs_dir)

                # Vérifier si déjà généré (au cas où)
                if thumb_path.exists():
                    # Mettre à jour en BDD
                    try:
                        conn.execute(
                            "UPDATE media_files SET thumbnail_path = ?, thumbnail_generated_at = CURRENT_TIMESTAMP WHERE file_path = ?",
                            [str(thumb_path), file_path_str],
                        )
                        generated += 1
                        continue
                    except Exception as e:
                        logger.warning(f"Erreur mise à jour thumbnail {file_path_str}: {e}")

                # Générer le thumbnail
                logger.info(f"Génération thumbnail pour: {file_name}")
                try:
                    if generate_thumbnail_gif(video_path, thumb_path):
                        # Mettre à jour en BDD
                        conn.execute(
                            "UPDATE media_files SET thumbnail_path = ?, thumbnail_generated_at = CURRENT_TIMESTAMP WHERE file_path = ?",
                            [str(thumb_path), file_path_str],
                        )
                        generated += 1
                        logger.info(f"  OK: {thumb_path.name}")
                    else:
                        errors += 1
                        logger.warning(f"  ERREUR: échec génération pour {file_name}")
                except Exception as e:
                    errors += 1
                    logger.error(f"Erreur génération thumbnail {file_name}: {e}", exc_info=True)

            conn.commit()
            logger.info(
                f"Génération thumbnails terminée: {generated} généré(s), {errors} erreur(s)"
            )

        finally:
            conn.close()

        return generated, errors
