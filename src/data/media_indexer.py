"""Module d'indexation des médias et association avec les matchs.

Ce module gère :
- Le scan incrémental des dossiers de médias
- L'association automatique média → match via proximité temporelle
- La génération de thumbnails pour les nouveaux contenus
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb

from src.ui.formatting import paris_epoch_seconds

logger = logging.getLogger(__name__)

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
    """Gère l'indexation des médias et l'association avec les matchs."""

    def __init__(self, db_path: Path, owner_xuid: str):
        """Initialise l'indexeur.

        Args:
            db_path: Chemin vers la DB DuckDB du joueur.
            owner_xuid: XUID du propriétaire des médias (ex: JGtm).
        """
        self.db_path = Path(db_path)
        self.owner_xuid = str(owner_xuid).strip()
        if not self.owner_xuid:
            raise ValueError("owner_xuid ne peut pas être vide")

    def ensure_schema(self) -> None:
        """Crée les tables si elles n'existent pas."""
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
                            owner_xuid VARCHAR NOT NULL,
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
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_media_owner ON media_files(owner_xuid)"
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

            # Timestamp système
            mtime_sys = float(stat.st_mtime)

            # Convertir en epoch seconds Paris
            dt_sys = datetime.fromtimestamp(mtime_sys)
            mtime_paris_epoch = paris_epoch_seconds(dt_sys) or mtime_sys

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
                    "SELECT file_path, file_hash, mtime FROM media_files WHERE owner_xuid = ?",
                    [self.owner_xuid],
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
                        metadata["owner_xuid"] = self.owner_xuid
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
                            owner_xuid, mtime, mtime_paris_epoch, last_scan_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                            metadata["owner_xuid"],
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

    def associate_with_matches(
        self,
        tolerance_minutes: int = 5,
    ) -> int:
        """Associe les médias non associés avec les matchs.

        Args:
            tolerance_minutes: Tolérance en minutes pour l'association temporelle.

        Returns:
            Nombre de médias associés.
        """
        self.ensure_schema()

        conn = duckdb.connect(str(self.db_path), read_only=False)
        try:
            # Récupérer les fenêtres temporelles des matchs
            # Note: Dans DuckDB v4, chaque DB est pour un seul joueur, donc pas besoin de filtrer par xuid
            match_windows = conn.execute(
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
                logger.warning("Aucun match trouvé pour l'association")
                return 0

            # Récupérer les médias non associés
            unassociated = conn.execute(
                """
                SELECT
                    mf.file_path,
                    mf.mtime_paris_epoch
                FROM media_files mf
                LEFT JOIN media_match_associations mma
                    ON mf.file_path = mma.media_path
                    AND mf.owner_xuid = mma.xuid
                WHERE mf.owner_xuid = ?
                    AND mma.media_path IS NULL
                ORDER BY mf.mtime_paris_epoch DESC
                """,
                [self.owner_xuid],
            ).fetchall()

            if not unassociated:
                logger.info("Aucun média non associé trouvé")
                return 0

            tol_seconds = tolerance_minutes * 60
            n_associated = 0

            for media_path, mtime_epoch in unassociated:
                # Trouver le match le plus proche
                best_match = None
                best_distance = float("inf")

                for match_id, start_time, time_played in match_windows:
                    try:
                        # Convertir start_time en epoch seconds Paris
                        if isinstance(start_time, str):
                            # Gérer format ISO avec/sans timezone
                            if start_time.endswith("Z"):
                                dt_start = datetime.fromisoformat(start_time[:-1] + "+00:00")
                            elif "+" in start_time or start_time.count("-") > 2:
                                dt_start = datetime.fromisoformat(start_time)
                            else:
                                # Format naïf, supposé UTC
                                dt_start = datetime.fromisoformat(start_time + "+00:00")
                        else:
                            dt_start = start_time

                        # Convertir en epoch seconds Paris
                        start_epoch = paris_epoch_seconds(dt_start)
                        if start_epoch is None:
                            continue  # Skip si conversion échoue

                        # Calculer fin du match
                        duration = (
                            float(time_played or 0) if time_played else 12 * 60
                        )  # 12 min par défaut
                        end_epoch = start_epoch + duration

                        # Fenêtre avec tolérance
                        window_start = start_epoch - tol_seconds
                        window_end = end_epoch + tol_seconds

                        # Vérifier si média dans la fenêtre
                        if window_start <= mtime_epoch <= window_end:
                            distance = abs(mtime_epoch - start_epoch)
                            if distance < best_distance:
                                best_distance = distance
                                best_match = (match_id, start_time)

                    except Exception as e:
                        logger.warning(f"Erreur traitement match {match_id}: {e}")
                        continue

                # Associer si match trouvé
                if best_match:
                    match_id, start_time = best_match
                    try:
                        conn.execute(
                            """
                            INSERT INTO media_match_associations (
                                media_path, match_id, xuid, match_start_time, association_confidence
                            ) VALUES (?, ?, ?, ?, ?)
                            ON CONFLICT (media_path, match_id, xuid) DO NOTHING
                            """,
                            [media_path, match_id, self.owner_xuid, start_time, 1.0],
                        )
                        n_associated += 1
                    except Exception as e:
                        logger.warning(f"Erreur association {media_path} → {match_id}: {e}")

            conn.commit()

            # Vérifier s'il reste des médias non associés (erreur selon l'utilisateur)
            remaining_unassociated = conn.execute(
                """
                SELECT COUNT(*)
                FROM media_files mf
                LEFT JOIN media_match_associations mma
                    ON mf.file_path = mma.media_path
                    AND mf.owner_xuid = mma.xuid
                WHERE mf.owner_xuid = ?
                    AND mma.media_path IS NULL
                """,
                [self.owner_xuid],
            ).fetchone()[0]

            if remaining_unassociated > 0:
                logger.warning(
                    f"{remaining_unassociated} média(s) non associé(s) - "
                    "vérifier la tolérance temporelle ou la synchronisation des matchs"
                )

            logger.info(f"{n_associated} média(s) associé(s) à des matchs")

        finally:
            conn.close()

        return n_associated

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
        except ImportError:
            logger.warning(
                "Impossible d'importer generate_thumbnails - vérifier que ffmpeg est installé"
            )
            return 0, 0

        # Vérifier que ffmpeg est disponible
        if not check_ffmpeg():
            logger.warning("ffmpeg n'est pas disponible - génération thumbnails ignorée")
            return 0, 0

        self.ensure_schema()

        conn = duckdb.connect(str(self.db_path), read_only=False)
        try:
            # Récupérer les vidéos sans thumbnail
            videos_without_thumb = conn.execute(
                """
                SELECT file_path, file_name
                FROM media_files
                WHERE owner_xuid = ?
                    AND kind = 'video'
                    AND (thumbnail_path IS NULL OR thumbnail_path = '')
                ORDER BY mtime_paris_epoch DESC
                """,
                [self.owner_xuid],
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
