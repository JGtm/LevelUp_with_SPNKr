"""Module d'indexation des médias – Onglet Médias (Sprint 1+).

Gère :
- Scan delta des dossiers configurés
- Schéma media_files (capture_start_utc, capture_end_utc, duration_seconds, title, status)
- Association média ↔ match (Sprint 2)
- Thumbnails (Sprint 3)

Chaque joueur a sa propre BDD : data/players/{gamertag}/stats.duckdb
"""

from __future__ import annotations

import hashlib
import logging
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb

from src.utils.paths import PLAYER_DB_FILENAME, PLAYERS_DIR

logger = logging.getLogger(__name__)

# Extensions supportées
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mkv", ".mov", ".avi"}

# Version du schéma pour migrations
SCAN_VERSION = 2


def _match_start_to_epoch(start_time: datetime | str | float) -> float | None:
    """Convertit start_time (DB/API) en epoch seconds."""
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
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return None


def _get_video_duration(file_path: Path) -> float | None:
    """Récupère la durée d'une vidéo via ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(file_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception:
        pass
    return None


def _get_image_exif_datetime(file_path: Path) -> datetime | None:
    """Récupère DateTimeOriginal ou CreateDate depuis EXIF (PIL)."""
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS
    except ImportError:
        return None

    try:
        with Image.open(file_path) as img:
            exif = img.getexif()
            if not exif:
                return None
            for tag_id, value in exif.items():
                if TAGS.get(tag_id) in ("DateTimeOriginal", "DateTime", "CreateDate") and value:
                    s = str(value).strip()
                    if " " in s:
                        date_part, time_part = s.split(" ", 1)
                        s = date_part.replace(":", "-") + " " + time_part
                    try:
                        return datetime.fromisoformat(s.replace(":", "-", 2))
                    except ValueError:
                        pass
    except Exception:
        pass
    return None


@dataclass
class ScanResult:
    """Résultat d'un scan de médias."""

    n_scanned: int = 0
    n_new: int = 0
    n_updated: int = 0
    n_deleted: int = 0
    n_associated: int = 0
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class MediaIndexer:
    """Gère l'indexation des médias (scan delta, schéma v2)."""

    def __init__(self, db_path: Path | None = None):
        if db_path:
            self.db_path = Path(db_path)
        else:
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
        try:
            cols = conn.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = 'main' AND table_name = ?
                """,
                [table],
            ).fetchall()
            return {row[0] for row in cols}
        except Exception:
            return set()

    def ensure_schema(self) -> None:
        """Crée ou migre le schéma media_files et media_match_associations."""
        conn = duckdb.connect(str(self.db_path), read_only=False)
        try:
            tables = conn.execute(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'main'
                AND table_name IN ('media_files', 'media_match_associations')
                """
            ).fetchall()
            existing_tables = {row[0] for row in tables}

            # media_files : schéma v2 (Sprint 1)
            if "media_files" in existing_tables:
                cols = self._get_existing_columns(conn, "media_files")
                migrations = []
                if "capture_start_utc" not in cols:
                    migrations.append(
                        (
                            "capture_start_utc",
                            "ALTER TABLE media_files ADD COLUMN capture_start_utc TIMESTAMP",
                        )
                    )
                if "capture_end_utc" not in cols:
                    migrations.append(
                        (
                            "capture_end_utc",
                            "ALTER TABLE media_files ADD COLUMN capture_end_utc TIMESTAMP",
                        )
                    )
                if "duration_seconds" not in cols:
                    migrations.append(
                        (
                            "duration_seconds",
                            "ALTER TABLE media_files ADD COLUMN duration_seconds DOUBLE",
                        )
                    )
                if "title" not in cols:
                    migrations.append(("title", "ALTER TABLE media_files ADD COLUMN title VARCHAR"))
                if "status" not in cols:
                    migrations.append(
                        (
                            "status",
                            "ALTER TABLE media_files ADD COLUMN status VARCHAR DEFAULT 'active'",
                        )
                    )
                if "mtime_paris_epoch" not in cols and "mtime" in cols:
                    migrations.append(
                        (
                            "mtime_paris_epoch",
                            "ALTER TABLE media_files ADD COLUMN mtime_paris_epoch DOUBLE",
                        )
                    )
                for _name, sql in migrations:
                    try:
                        conn.execute(sql)
                        conn.commit()
                    except Exception as e:
                        logger.warning("Migration %s: %s", _name, e)
                try:
                    conn.execute("UPDATE media_files SET status = 'active' WHERE status IS NULL")
                    conn.execute(
                        "UPDATE media_files SET mtime_paris_epoch = mtime WHERE mtime_paris_epoch IS NULL"
                    )
                    conn.commit()
                except Exception:
                    pass
            else:
                conn.execute("""
                    CREATE TABLE media_files (
                        file_path VARCHAR PRIMARY KEY,
                        file_hash VARCHAR NOT NULL,
                        file_name VARCHAR NOT NULL,
                        file_size BIGINT NOT NULL,
                        file_ext VARCHAR NOT NULL,
                        kind VARCHAR NOT NULL,
                        capture_start_utc TIMESTAMP,
                        capture_end_utc TIMESTAMP NOT NULL,
                        duration_seconds DOUBLE,
                        title VARCHAR,
                        thumbnail_path VARCHAR,
                        mtime DOUBLE NOT NULL,
                        mtime_paris_epoch DOUBLE,
                        status VARCHAR NOT NULL DEFAULT 'active',
                        first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_scan_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        scan_version INTEGER DEFAULT 2
                    )
                """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_media_mtime ON media_files(mtime DESC)"
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_media_status ON media_files(status)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_media_kind ON media_files(kind)")
                conn.commit()

            # media_match_associations : map_id, map_name
            if "media_match_associations" in existing_tables:
                cols = self._get_existing_columns(conn, "media_match_associations")
                if "map_id" not in cols:
                    try:
                        conn.execute(
                            "ALTER TABLE media_match_associations ADD COLUMN map_id VARCHAR"
                        )
                        conn.commit()
                    except Exception:
                        pass
                if "map_name" not in cols:
                    try:
                        conn.execute(
                            "ALTER TABLE media_match_associations ADD COLUMN map_name VARCHAR"
                        )
                        conn.commit()
                    except Exception:
                        pass
            else:
                conn.execute("""
                    CREATE TABLE media_match_associations (
                        media_path VARCHAR NOT NULL,
                        match_id VARCHAR NOT NULL,
                        xuid VARCHAR NOT NULL,
                        match_start_time TIMESTAMP NOT NULL,
                        map_id VARCHAR,
                        map_name VARCHAR,
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
                conn.commit()
        finally:
            conn.close()

    def _compute_file_hash(self, file_path: Path) -> str:
        try:
            h = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    h.update(chunk)
            return h.hexdigest()
        except Exception as e:
            logger.warning("Hash %s: %s", file_path, e)
            return ""

    def _get_file_metadata(self, file_path: Path) -> dict[str, Any] | None:
        """Récupère les métadonnées (capture_start_utc, capture_end_utc, duration_seconds, title)."""
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

            mtime = float(stat.st_mtime)
            capture_end_utc = datetime.fromtimestamp(mtime, tz=timezone.utc)
            capture_start_utc: datetime | None = None
            duration_seconds: float | None = None
            title: str | None = None

            if kind == "video":
                duration_seconds = _get_video_duration(file_path)
                if duration_seconds is not None and duration_seconds > 0:
                    capture_start_utc = datetime.fromtimestamp(
                        mtime - duration_seconds, tz=timezone.utc
                    )
                else:
                    capture_start_utc = capture_end_utc
            else:
                exif_dt = _get_image_exif_datetime(file_path)
                if exif_dt:
                    if exif_dt.tzinfo is None:
                        exif_dt = exif_dt.replace(tzinfo=timezone.utc)
                    capture_end_utc = exif_dt
                    capture_start_utc = exif_dt
                else:
                    capture_start_utc = capture_end_utc

            return {
                "file_path": str(file_path.resolve()),
                "file_name": file_path.name,
                "file_size": stat.st_size,
                "file_ext": ext.lstrip("."),
                "kind": kind,
                "mtime": mtime,
                "capture_start_utc": capture_start_utc,
                "capture_end_utc": capture_end_utc,
                "duration_seconds": duration_seconds,
                "title": title,
            }
        except Exception as e:
            logger.warning("Métadonnées %s: %s", file_path, e)
            return None

    def scan_and_index(
        self,
        videos_dir: Path | None,
        screens_dir: Path | None,
        *,
        force_rescan: bool = False,
    ) -> ScanResult:
        """Scan delta : nouveaux, modifiés, absents → status='deleted'."""
        self.ensure_schema()
        result = ScanResult()
        now = datetime.now()

        conn = duckdb.connect(str(self.db_path), read_only=False)
        try:
            existing = {}
            if not force_rescan:
                rows = conn.execute(
                    "SELECT file_path, file_hash, mtime FROM media_files WHERE status != 'deleted'"
                ).fetchall()
                existing = {row[0]: {"hash": row[1], "mtime": row[2]} for row in rows}

            paths_on_disk: set[str] = set()
            files_to_process: list[dict[str, Any]] = []

            for media_dir, exts in [
                (videos_dir, VIDEO_EXTENSIONS),
                (screens_dir, IMAGE_EXTENSIONS),
            ]:
                if not media_dir or not Path(media_dir).exists():
                    continue
                for root, _dirs, files in os.walk(media_dir):
                    for name in files:
                        fp = Path(root) / name
                        if fp.suffix.lower() not in exts:
                            continue
                        result.n_scanned += 1
                        meta = self._get_file_metadata(fp)
                        if not meta:
                            continue
                        path_str = meta["file_path"]
                        paths_on_disk.add(path_str)
                        if path_str in existing:
                            ex = existing[path_str]
                            if not force_rescan and abs(meta["mtime"] - ex["mtime"]) < 1.0:
                                continue
                        h = self._compute_file_hash(fp)
                        if not h:
                            result.errors.append(f"Hash impossible: {path_str}")
                            continue
                        meta["file_hash"] = h
                        files_to_process.append(meta)

            for meta in files_to_process:
                path_str = meta["file_path"]
                is_new = path_str not in existing
                try:
                    if is_new:
                        conn.execute(
                            """
                            INSERT INTO media_files (
                                file_path, file_hash, file_name, file_size, file_ext, kind,
                                capture_start_utc, capture_end_utc, duration_seconds, title,
                                mtime, mtime_paris_epoch, status, first_seen_at, last_scan_at, scan_version
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
                            """,
                            [
                                path_str,
                                meta["file_hash"],
                                meta["file_name"],
                                meta["file_size"],
                                meta["file_ext"],
                                meta["kind"],
                                meta["capture_start_utc"],
                                meta["capture_end_utc"],
                                meta["duration_seconds"],
                                meta["title"],
                                meta["mtime"],
                                meta["mtime"],
                                now,
                                now,
                                SCAN_VERSION,
                            ],
                        )
                        result.n_new += 1
                    else:
                        conn.execute(
                            """
                            UPDATE media_files SET
                                file_hash = ?, file_size = ?, capture_start_utc = ?,
                                capture_end_utc = ?, duration_seconds = ?, title = ?,
                                mtime = ?, mtime_paris_epoch = ?, status = 'active',
                                last_scan_at = ?
                            WHERE file_path = ?
                            """,
                            [
                                meta["file_hash"],
                                meta["file_size"],
                                meta["capture_start_utc"],
                                meta["capture_end_utc"],
                                meta["duration_seconds"],
                                meta["title"],
                                meta["mtime"],
                                meta["mtime"],
                                now,
                                path_str,
                            ],
                        )
                        result.n_updated += 1
                except Exception as e:
                    result.errors.append(f"Insert {path_str}: {e}")
                    logger.error("Insert média: %s", e, exc_info=True)

            # Marquer deleted les fichiers absents du disque
            for path_str in existing:
                if path_str not in paths_on_disk:
                    try:
                        conn.execute(
                            "UPDATE media_files SET status = 'deleted' WHERE file_path = ?",
                            [path_str],
                        )
                        result.n_deleted += 1
                    except Exception as e:
                        result.errors.append(f"Delete {path_str}: {e}")

            conn.commit()
            logger.info(
                "Scan: %d scannés, %d nouveaux, %d modifiés, %d supprimés",
                result.n_scanned,
                result.n_new,
                result.n_updated,
                result.n_deleted,
            )
        finally:
            conn.close()

        return result

    @staticmethod
    def _get_all_player_dbs() -> list[tuple[Path, str]]:
        player_dbs = []
        if not PLAYERS_DIR.exists():
            return player_dbs
        for player_dir in PLAYERS_DIR.iterdir():
            if not player_dir.is_dir():
                continue
            db_path = player_dir / PLAYER_DB_FILENAME
            if not db_path.exists():
                continue
            xuid = None
            try:
                c = duckdb.connect(str(db_path), read_only=True)
                try:
                    r = c.execute("SELECT value FROM sync_meta WHERE key = 'xuid'").fetchone()
                    if r:
                        xuid = r[0]
                except Exception:
                    pass
                finally:
                    c.close()
            except Exception:
                pass
            if not xuid:
                xuid = player_dir.name
            player_dbs.append((db_path, xuid))
        return player_dbs

    def associate_with_matches(self, tolerance_minutes: int = 5) -> int:
        """Associe les médias actifs non associés avec les matchs (Sprint 2)."""
        self.ensure_schema()
        conn_read = duckdb.connect(str(self.db_path), read_only=True)
        try:
            unassociated = conn_read.execute(
                """
                SELECT mf.file_path, COALESCE(mf.mtime_paris_epoch, mf.mtime)
                FROM media_files mf
                WHERE mf.status = 'active'
                AND NOT EXISTS (
                    SELECT 1 FROM media_match_associations mma
                    WHERE mma.media_path = mf.file_path
                )
                ORDER BY mf.mtime DESC
                """
            ).fetchall()
        finally:
            conn_read.close()

        if not unassociated:
            return 0

        player_dbs = self._get_all_player_dbs()
        if not player_dbs:
            return 0

        tol_seconds = tolerance_minutes * 60
        total = 0
        conn_write = duckdb.connect(str(self.db_path), read_only=False)
        try:
            for player_db_path, player_xuid in player_dbs:
                try:
                    pc = (
                        conn_write
                        if player_db_path.resolve() == self.db_path.resolve()
                        else duckdb.connect(str(player_db_path), read_only=True)
                    )
                    try:
                        try:
                            matches = pc.execute(
                                """
                                SELECT match_id, start_time, time_played_seconds,
                                       COALESCE(map_id, ''), COALESCE(map_name, '')
                                FROM match_stats WHERE start_time IS NOT NULL
                                """
                            ).fetchall()
                        except Exception:
                            matches = pc.execute(
                                """
                                SELECT match_id, start_time, time_played_seconds, '', ''
                                FROM match_stats WHERE start_time IS NOT NULL
                                """
                            ).fetchall()
                        if not matches:
                            continue
                        for media_path, mtime_epoch in unassociated:
                            best: list[tuple[Any, Any, str, str, float]] = []
                            for row in matches:
                                match_id, st, dur = row[0], row[1], row[2]
                                map_id = row[3] if len(row) > 3 else ""
                                map_name = row[4] if len(row) > 4 else ""
                                start_epoch = _match_start_to_epoch(st)
                                if start_epoch is None:
                                    continue
                                d = float(dur or 0) if dur else 12 * 60
                                end_epoch = start_epoch + d
                                if (
                                    start_epoch - tol_seconds
                                    <= mtime_epoch
                                    <= end_epoch + tol_seconds
                                ):
                                    best.append(
                                        (
                                            match_id,
                                            st,
                                            map_id,
                                            map_name,
                                            abs(mtime_epoch - start_epoch),
                                        )
                                    )
                            if best:
                                best.sort(key=lambda x: x[4])
                                match_id, start_time, map_id, map_name, _ = best[0]
                                try:
                                    conn_write.execute(
                                        """
                                        INSERT INTO media_match_associations
                                        (media_path, match_id, xuid, match_start_time, map_id, map_name, association_confidence)
                                        VALUES (?, ?, ?, ?, ?, ?, 1.0)
                                        ON CONFLICT (media_path, match_id, xuid) DO NOTHING
                                        """,
                                        [
                                            media_path,
                                            match_id,
                                            player_xuid,
                                            start_time,
                                            map_id,
                                            map_name,
                                        ],
                                    )
                                    total += 1
                                except Exception as e:
                                    logger.warning("Association %s: %s", media_path, e)
                    finally:
                        if pc is not conn_write:
                            pc.close()
                except Exception as e:
                    logger.warning("DB %s: %s", player_db_path, e)
            conn_write.commit()
        finally:
            conn_write.close()
        return total

    def generate_thumbnails_for_new(
        self,
        videos_dir: Path | None = None,
        screens_dir: Path | None = None,
        *,
        max_concurrent: int = 2,  # noqa: ARG002
    ) -> tuple[int, int]:
        """Génère les thumbnails vidéo (GIF) et image (miniatures) – Sprint 3.

        Args:
            videos_dir: Dossier des vidéos.
            screens_dir: Dossier des captures d'écran.
            max_concurrent: Non utilisé.

        Returns:
            (generated, errors)
        """
        total_gen = 0
        total_err = 0

        # Vidéos : GIF animé via ffmpeg
        if videos_dir and videos_dir.exists():
            gen, err = self._generate_video_thumbnails(videos_dir)
            total_gen += gen
            total_err += err

        # Images : miniatures dédiées via PIL
        if screens_dir and screens_dir.exists():
            gen, err = self._generate_image_thumbnails(screens_dir)
            total_gen += gen
            total_err += err

        return total_gen, total_err

    def _generate_video_thumbnails(self, videos_dir: Path) -> tuple[int, int]:
        """Génère les thumbnails GIF pour les vidéos."""
        try:
            from scripts.generate_thumbnails import (
                check_ffmpeg,
                generate_thumbnail_gif,
                get_thumbnail_path,
            )
        except ImportError:
            return 0, 0
        if not check_ffmpeg():
            return 0, 0
        self.ensure_schema()
        conn = duckdb.connect(str(self.db_path), read_only=False)
        try:
            videos = conn.execute(
                """
                SELECT file_path, file_name FROM media_files
                WHERE kind = 'video' AND status = 'active'
                AND (thumbnail_path IS NULL OR thumbnail_path = '')
                ORDER BY mtime DESC
                """
            ).fetchall()
            if not videos:
                return 0, 0
            thumbs_dir = videos_dir / "thumbs"
            thumbs_dir.mkdir(exist_ok=True)
            generated = errors = 0
            for path_str, _fname in videos:
                p = Path(path_str)
                if not p.exists():
                    continue
                thumb = get_thumbnail_path(p, thumbs_dir)
                if thumb.exists():
                    conn.execute(
                        "UPDATE media_files SET thumbnail_path = ? WHERE file_path = ?",
                        [str(thumb), path_str],
                    )
                    generated += 1
                    continue
                try:
                    if generate_thumbnail_gif(p, thumb):
                        conn.execute(
                            "UPDATE media_files SET thumbnail_path = ? WHERE file_path = ?",
                            [str(thumb), path_str],
                        )
                        generated += 1
                    else:
                        errors += 1
                except Exception:
                    errors += 1
            conn.commit()
        finally:
            conn.close()
        return generated, errors

    def _generate_image_thumbnails(self, screens_dir: Path) -> tuple[int, int]:
        """Génère les miniatures pour les images (redimensionnement)."""
        import importlib.util

        if importlib.util.find_spec("PIL") is None:
            return 0, 0
        self.ensure_schema()
        conn = duckdb.connect(str(self.db_path), read_only=False)
        try:
            images = conn.execute(
                """
                SELECT file_path, file_name FROM media_files
                WHERE kind = 'image' AND status = 'active'
                AND (thumbnail_path IS NULL OR thumbnail_path = '')
                ORDER BY mtime DESC
                """
            ).fetchall()
            if not images:
                return 0, 0
            thumbs_dir = screens_dir / "thumbs"
            thumbs_dir.mkdir(exist_ok=True)
            generated = errors = 0
            max_width = 320
            for path_str, _fname in images:
                p = Path(path_str)
                if not p.exists():
                    continue
                thumb = _get_image_thumbnail_path(p, thumbs_dir)
                if thumb.exists():
                    conn.execute(
                        "UPDATE media_files SET thumbnail_path = ? WHERE file_path = ?",
                        [str(thumb), path_str],
                    )
                    generated += 1
                    continue
                try:
                    if _generate_image_thumbnail(p, thumb, max_width=max_width):
                        conn.execute(
                            "UPDATE media_files SET thumbnail_path = ? WHERE file_path = ?",
                            [str(thumb), path_str],
                        )
                        generated += 1
                    else:
                        errors += 1
                except Exception:
                    errors += 1
            conn.commit()
        finally:
            conn.close()
        return generated, errors


def _get_image_thumbnail_path(image_path: Path, thumbs_dir: Path) -> Path:
    """Chemin du thumbnail pour une image (miniature dédiée)."""
    path_hash = hashlib.md5(str(image_path.resolve()).encode()).hexdigest()[:12]
    stem = image_path.stem[:50]
    ext = image_path.suffix.lower()
    out_ext = ".jpg" if ext in {".jpg", ".jpeg"} else ".png"
    return thumbs_dir / f"{stem}_{path_hash}{out_ext}"


def _generate_image_thumbnail(
    image_path: Path,
    output_path: Path,
    *,
    max_width: int = 320,
) -> bool:
    """Génère une miniature pour une image (PIL resize)."""
    try:
        from PIL import Image
    except ImportError:
        return False
    try:
        with Image.open(image_path) as img:
            img.load()
            w, h = img.size
            if w <= max_width and h <= max_width:
                ratio = 1.0
            elif w >= h:
                ratio = max_width / w
            else:
                ratio = max_width / h
            new_w = max(1, int(w * ratio))
            new_h = max(1, int(h * ratio))
            resample = getattr(Image.Resampling, "LANCZOS", Image.LANCZOS)
            thumb = img.resize((new_w, new_h), resample)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if output_path.suffix.lower() in {".jpg", ".jpeg"}:
                thumb.save(output_path, "JPEG", quality=85, optimize=True)
            else:
                thumb.save(output_path, "PNG", optimize=True)
            return output_path.exists()
    except Exception:
        return False
