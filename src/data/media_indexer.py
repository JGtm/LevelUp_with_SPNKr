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
import polars as pl

from src.utils.paths import PLAYER_DB_FILENAME, PLAYERS_DIR

logger = logging.getLogger(__name__)


def get_gamertag_from_db_path(db_path: Path | str) -> str | None:
    """Extrait le gamertag depuis data/players/{gamertag}/stats.duckdb."""
    try:
        p = Path(db_path).resolve()
        if p.name == PLAYER_DB_FILENAME:
            return p.parent.name
    except Exception:
        pass
    return None


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

    def reset_media_tables(self) -> None:
        """Vide les tables media_files et media_match_associations (schéma conservé)."""
        conn = duckdb.connect(str(self.db_path), read_only=False)
        try:
            self.ensure_schema()
            conn.execute("DELETE FROM media_match_associations")
            conn.execute("DELETE FROM media_files")
            conn.commit()
        finally:
            conn.close()

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
                # owner_xuid (legacy) : conservée si présente, on la remplit à l'INSERT
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
        videos_dir: Path | None = None,
        screens_dir: Path | None = None,
        *,
        player_captures_dir: Path | None = None,
        force_rescan: bool = False,
    ) -> ScanResult:
        """Scan delta : nouveaux, modifiés, absents → status='deleted'.

        Si player_captures_dir est fourni, on scanne ce dossier (images + vidéos).
        Sinon on utilise videos_dir et screens_dir (legacy).
        """
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

            # Nouvelle logique: un seul dossier joueur (base_dir/gamertag)
            if player_captures_dir and Path(player_captures_dir).exists():
                dirs_exts = [
                    (player_captures_dir, VIDEO_EXTENSIONS | IMAGE_EXTENSIONS),
                ]
            else:
                dirs_exts = [
                    (videos_dir, VIDEO_EXTENSIONS),
                    (screens_dir, IMAGE_EXTENSIONS),
                ]

            for media_dir, exts in dirs_exts:
                if not media_dir or not Path(media_dir).exists():
                    continue
                try:
                    walk_iter = os.walk(media_dir)
                except OSError as e:
                    result.errors.append(f"Dossier inaccessible {media_dir}: {e}")
                    logger.warning("Scan dossier %s: %s", media_dir, e)
                    continue
                for root, _dirs, files in walk_iter:
                    for name in files:
                        fp = Path(root) / name
                        if fp.suffix.lower() not in exts:
                            continue
                        result.n_scanned += 1
                        try:
                            meta = self._get_file_metadata(fp)
                        except Exception as e:
                            result.errors.append(f"Métadonnées {fp}: {e}")
                            logger.debug("Métadonnées %s: %s", fp, e)
                            continue
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

            # owner_xuid (legacy) : certaines DB l'ont encore
            has_owner_xuid = "owner_xuid" in self._get_existing_columns(conn, "media_files")
            owner_xuid_val = get_gamertag_from_db_path(self.db_path) or ""

            for meta in files_to_process:
                path_str = meta["file_path"]
                is_new = path_str not in existing
                try:
                    if is_new:
                        if has_owner_xuid:
                            conn.execute(
                                """
                                INSERT INTO media_files (
                                    file_path, file_hash, file_name, file_size, file_ext, kind,
                                    capture_start_utc, capture_end_utc, duration_seconds, title,
                                    mtime, mtime_paris_epoch, status, first_seen_at, last_scan_at,
                                    scan_version, owner_xuid
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)
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
                                    owner_xuid_val,
                                ],
                            )
                        else:
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
        for player_dir in sorted(PLAYERS_DIR.iterdir(), key=lambda p: p.name):
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

    def _get_all_player_dbs_current_first(self) -> list[tuple[Path, str]]:
        """Liste des (db_path, xuid) avec la DB courante (profil actuel) en premier."""
        all_dbs = self._get_all_player_dbs()
        current = self.db_path.resolve()
        current_first = [(p, x) for p, x in all_dbs if p.resolve() == current]
        others = [(p, x) for p, x in all_dbs if p.resolve() != current]
        return current_first + others

    def associate_with_matches(self, tolerance_minutes: int = 20) -> int:
        """Associe les médias actifs avec les matchs (multi-joueurs).

        Pour chaque média actif, on cherche le match le plus proche (dans la tolérance)
        pour **chaque DB joueur** (xuid). On peut donc avoir plusieurs associations
        pour un même média (une par joueur), via la clé primaire
        (media_path, match_id, xuid).

        Returns:
            Nombre de nouvelles associations insérées.
        """
        self.ensure_schema()
        conn_read = duckdb.connect(str(self.db_path), read_only=True)
        try:
            media_rows = conn_read.execute(
                """
                SELECT mf.file_path, COALESCE(epoch(mf.capture_end_utc), mf.mtime_paris_epoch, mf.mtime)
                FROM media_files mf
                WHERE mf.status = 'active'
                ORDER BY mf.mtime DESC
                """
            ).fetchall()
        finally:
            conn_read.close()

        if not media_rows:
            return 0

        player_dbs = self._get_all_player_dbs_current_first()
        if not player_dbs:
            player_dbs = [(self.db_path, get_gamertag_from_db_path(self.db_path) or "")]

        matches_by_xuid: dict[str, list[tuple[Any, ...]]] = {}
        for db_path, xuid in player_dbs:
            try:
                with duckdb.connect(str(db_path), read_only=True) as c:
                    try:
                        rows = c.execute(
                            """
                            SELECT match_id, start_time, time_played_seconds,
                                   COALESCE(map_id, ''), COALESCE(map_name, '')
                            FROM match_stats WHERE start_time IS NOT NULL
                            """
                        ).fetchall()
                    except Exception:
                        rows = c.execute(
                            """
                            SELECT match_id, start_time, time_played_seconds, '', ''
                            FROM match_stats WHERE start_time IS NOT NULL
                            """
                        ).fetchall()
                    matches_by_xuid[str(xuid)] = rows
            except Exception:
                matches_by_xuid[str(xuid)] = []

        tol_seconds = tolerance_minutes * 60
        conn_write = duckdb.connect(str(self.db_path), read_only=False)
        try:
            before = conn_write.execute("SELECT COUNT(*) FROM media_match_associations").fetchone()[
                0
            ]

            for media_path, mtime_epoch in media_rows:
                for xuid, matches in matches_by_xuid.items():
                    candidates: list[tuple[str, Any, Any, str, str, float]] = []
                    for row in matches:
                        match_id, st, dur = row[0], row[1], row[2]
                        map_id = row[3] if len(row) > 3 else ""
                        map_name = row[4] if len(row) > 4 else ""
                        start_epoch = _match_start_to_epoch(st)
                        if start_epoch is None:
                            continue
                        d = float(dur or 0) if dur else 12 * 60
                        end_epoch = start_epoch + d
                        if start_epoch - tol_seconds <= mtime_epoch <= end_epoch + tol_seconds:
                            dist = abs(mtime_epoch - start_epoch)
                            candidates.append((xuid, match_id, st, map_id, map_name, dist))

                    if not candidates:
                        continue
                    candidates.sort(key=lambda x: (x[5], x[1]))
                    best = candidates[0]
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
                                best[1],
                                best[0],
                                best[2],
                                best[3],
                                best[4],
                            ],
                        )
                    except Exception as e:
                        logger.warning("Association %s/%s: %s", media_path, xuid, e)
            conn_write.commit()
            after = conn_write.execute("SELECT COUNT(*) FROM media_match_associations").fetchone()[
                0
            ]
        finally:
            conn_write.close()
        return int(after - before)

    @staticmethod
    def load_media_for_ui(db_path: Path | str, current_xuid: str | None) -> pl.DataFrame:
        """Charge les médias actifs avec associations pour l'onglet Médias (Sprint 5).

        Cross-DB : « Mes captures » depuis la DB courante ; « Captures de XXX »
        depuis les autres DB dont le match_id existe dans la DB courante.
        Une seule ligne par média : priorité mine > teammate > unassigned.

        Returns:
            Polars DataFrame avec colonnes: file_path, file_name, kind, thumbnail_path,
            capture_end_utc, map_name, match_id, match_start_time, xuid, gamertag, section.
            section ∈ {'mine', 'teammate', 'unassigned'}.
        """
        db_path = Path(db_path)
        if not db_path.exists():
            return pl.DataFrame()
        try:
            MediaIndexer(db_path).ensure_schema()
        except Exception as e:
            logger.warning("load_media_for_ui ensure_schema: %s", e)
            return pl.DataFrame()

        cu = str(current_xuid or "")
        current_resolved = db_path.resolve()
        player_dbs = MediaIndexer._get_all_player_dbs()

        # 1) Match_ids du joueur courant
        match_ids_current: set[str] = set()
        try:
            with duckdb.connect(str(db_path), read_only=True) as c:
                rows = c.execute(
                    "SELECT DISTINCT match_id FROM match_stats WHERE match_id IS NOT NULL"
                ).fetchall()
                match_ids_current = {str(r[0]).strip() for r in rows if r[0]}
        except Exception:
            pass

        # 2) Charger médias DB courante (mine + unassigned)
        df_current = pl.DataFrame()
        try:
            with duckdb.connect(str(db_path), read_only=True) as c:
                tables = c.execute(
                    """
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'main' AND table_name = 'media_files'
                    """
                ).fetchall()
                if tables:
                    df_current = c.execute("""
                        SELECT
                            mf.file_path, mf.file_name, mf.kind, mf.thumbnail_path,
                            mf.capture_end_utc, mma.map_name, mma.match_id, mma.match_start_time,
                            mma.xuid
                        FROM media_files mf
                        LEFT JOIN media_match_associations mma ON mf.file_path = mma.media_path
                        WHERE mf.status = 'active'
                    """).pl()
        except Exception as e:
            logger.warning("load_media_for_ui current: %s", e)

        # 3) Charger médias des autres DB (match_id dans match_ids_current) → Captures de XXX
        dfs_teammate: list[pl.DataFrame] = []
        for pdb, _xuid in player_dbs:
            if Path(pdb).resolve() == current_resolved:
                continue
            if not match_ids_current:
                continue
            try:
                with duckdb.connect(str(pdb), read_only=True) as c:
                    tables = c.execute(
                        """
                        SELECT table_name FROM information_schema.tables
                        WHERE table_schema = 'main' AND table_name = 'media_match_associations'
                        """
                    ).fetchall()
                    if not tables:
                        continue
                    placeholders = ",".join("?" for _ in match_ids_current)
                    q = f"""
                        SELECT mf.file_path, mf.file_name, mf.kind, mf.thumbnail_path,
                               mf.capture_end_utc, mma.map_name, mma.match_id, mma.match_start_time,
                               mma.xuid
                        FROM media_files mf
                        JOIN media_match_associations mma ON mf.file_path = mma.media_path
                        WHERE mf.status = 'active' AND mma.match_id IN ({placeholders})
                    """
                    df_t = c.execute(q, list(match_ids_current)).pl()
                    if not df_t.is_empty():
                        dfs_teammate.append(df_t)
            except Exception as e:
                logger.debug("load_media_for_ui other db %s: %s", pdb, e)

        # 4) Concaténer
        if df_current.is_empty() and not dfs_teammate:
            return pl.DataFrame()
        dfs = [df_current] + dfs_teammate
        df = pl.concat(dfs) if len(dfs) > 1 else dfs[0]

        # xuid → gamertag
        xuid_to_gamertag: dict[str, str] = {}
        for pdb, xu in player_dbs:
            gamertag = Path(pdb).parent.name
            xuid_to_gamertag[str(xu)] = gamertag

        def _gamertag(u: Any) -> str:
            if u is None:
                return ""
            return xuid_to_gamertag.get(str(u), str(u))

        df = df.with_columns(
            pl.col("xuid").map_elements(_gamertag, return_dtype=pl.Utf8).alias("gamertag")
        )
        # Section: unassigned si pas de match_id, sinon mine ou teammate
        # Mine = xuid match OU gamertag match (current_xuid peut être gamertag en DuckDB v4)
        current_gamertag = get_gamertag_from_db_path(db_path) or cu
        df = df.with_columns(
            pl.when(
                pl.col("match_id").is_null()
                | (pl.col("match_id").cast(pl.Utf8).str.strip_chars() == "")
            )
            .then(pl.lit("unassigned"))
            .when((pl.col("xuid").cast(pl.Utf8) == cu) | (pl.col("gamertag") == current_gamertag))
            .then(pl.lit("mine"))
            .otherwise(pl.lit("teammate"))
            .alias("section")
        )
        # Une seule ligne par média : priorité mine > teammate > unassigned
        df = df.with_columns(
            pl.when(pl.col("section") == "mine")
            .then(0)
            .when(pl.col("section") == "teammate")
            .then(1)
            .otherwise(2)
            .alias("_section_rank")
        )
        df = df.sort(["file_path", "_section_rank", "gamertag"]).unique(
            subset=["file_path"], keep="first"
        )
        df = df.drop("_section_rank")
        return df.sort("capture_end_utc", descending=True, nulls_last=True)

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
