"""Tests unitaires pour le module d'indexation des médias (Sprint 1)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import duckdb
import pytest

from src.data.media_indexer import MediaIndexer, ScanResult


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Crée une DB DuckDB temporaire pour les tests."""
    db_path = tmp_path / "test_stats.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute("""
            CREATE TABLE match_stats (
                match_id VARCHAR PRIMARY KEY,
                start_time TIMESTAMP,
                time_played_seconds INTEGER,
                xuid VARCHAR
            )
        """)
        conn.execute(
            """
            INSERT INTO match_stats (match_id, start_time, time_played_seconds, xuid)
            VALUES (?, ?, ?, ?)
            """,
            ["test_match_1", "2026-02-04 20:00:00+00:00", 720, "test_xuid_123"],
        )
        conn.commit()
    finally:
        conn.close()
    return db_path


@pytest.fixture
def temp_media_dir(tmp_path: Path) -> Path:
    """Crée un dossier temporaire avec des fichiers médias de test."""
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    (media_dir / "test_video.mp4").write_text("fake video content")
    # Image PNG valide pour les tests thumbnails (PIL requis)
    try:
        from PIL import Image

        img = Image.new("RGB", (100, 100), color="red")
        img.save(media_dir / "test_image.png", "PNG")
    except ImportError:
        (media_dir / "test_image.png").write_text("fake image content")
    return media_dir


def test_media_indexer_init(temp_db: Path) -> None:
    """Test l'initialisation de MediaIndexer."""
    indexer = MediaIndexer(temp_db)
    assert indexer.db_path == temp_db


def test_ensure_schema(temp_db: Path) -> None:
    """Test la création du schéma (Sprint 1 : status, capture_start_utc, capture_end_utc)."""
    indexer = MediaIndexer(temp_db)
    indexer.ensure_schema()

    conn = duckdb.connect(str(temp_db), read_only=True)
    try:
        tables = conn.execute(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'main' AND table_name IN ('media_files', 'media_match_associations')
            """
        ).fetchall()
        assert {row[0] for row in tables} == {"media_files", "media_match_associations"}

        columns = conn.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'main' AND table_name = 'media_files'
            """
        ).fetchall()
        col_names = {row[0] for row in columns}
        assert "status" in col_names
        assert "capture_start_utc" in col_names
        assert "capture_end_utc" in col_names
        assert "owner_xuid" not in col_names

        assoc_cols = conn.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'main' AND table_name = 'media_match_associations'
            """
        ).fetchall()
        assoc_names = {row[0] for row in assoc_cols}
        assert "map_id" in assoc_names
        assert "map_name" in assoc_names
    finally:
        conn.close()


def test_scan_and_index(temp_db: Path, temp_media_dir: Path) -> None:
    """Test le scan et l'indexation des médias."""
    indexer = MediaIndexer(temp_db)
    indexer.ensure_schema()

    result = indexer.scan_and_index(
        videos_dir=temp_media_dir,
        screens_dir=None,
        force_rescan=False,
    )

    assert isinstance(result, ScanResult)
    assert result.n_scanned >= 1
    assert result.n_new >= 1

    conn = duckdb.connect(str(temp_db), read_only=True)
    try:
        files = conn.execute(
            "SELECT file_path, kind, status FROM media_files WHERE status = 'active'"
        ).fetchall()
        assert len(files) >= 1
        video_files = [f for f in files if f[1] == "video"]
        assert len(video_files) >= 1
        assert all(f[2] == "active" for f in files)
    finally:
        conn.close()


def test_scan_incremental(temp_db: Path, temp_media_dir: Path) -> None:
    """Test que le scan incrémental ne re-traite pas les fichiers inchangés."""
    indexer = MediaIndexer(temp_db)
    indexer.ensure_schema()

    result1 = indexer.scan_and_index(
        videos_dir=temp_media_dir,
        screens_dir=None,
        force_rescan=False,
    )
    assert result1.n_new >= 1

    result2 = indexer.scan_and_index(
        videos_dir=temp_media_dir,
        screens_dir=None,
        force_rescan=False,
    )
    assert result2.n_new == 0
    assert result2.n_scanned >= 1


def test_scan_marks_deleted_when_file_removed(temp_db: Path, temp_media_dir: Path) -> None:
    """Test que les fichiers supprimés du disque sont marqués status='deleted'."""
    indexer = MediaIndexer(temp_db)
    indexer.ensure_schema()

    result1 = indexer.scan_and_index(
        videos_dir=temp_media_dir,
        screens_dir=None,
        force_rescan=False,
    )
    assert result1.n_new >= 1

    # Supprimer un fichier
    (temp_media_dir / "test_video.mp4").unlink()

    result2 = indexer.scan_and_index(
        videos_dir=temp_media_dir,
        screens_dir=None,
        force_rescan=False,
    )
    assert result2.n_deleted >= 1

    conn = duckdb.connect(str(temp_db), read_only=True)
    try:
        deleted = conn.execute(
            "SELECT file_path FROM media_files WHERE status = 'deleted'"
        ).fetchall()
        assert len(deleted) >= 1
    finally:
        conn.close()


def test_scan_result_has_n_deleted(temp_db: Path, temp_media_dir: Path) -> None:
    """Test que ScanResult contient n_deleted."""
    indexer = MediaIndexer(temp_db)
    indexer.ensure_schema()
    indexer.scan_and_index(videos_dir=temp_media_dir, screens_dir=None)

    result = ScanResult()
    assert hasattr(result, "n_deleted")
    assert result.n_deleted == 0


def test_scan_handles_inaccessible_directory(temp_db: Path, tmp_path: Path) -> None:
    """Test que un dossier inaccessible (ex. réseau) ne fait pas planter le scan (Sprint 6)."""
    indexer = MediaIndexer(temp_db)
    indexer.ensure_schema()
    bad_dir = tmp_path / "inaccessible"
    bad_dir.mkdir()

    with patch("src.data.media_indexer.os.walk") as m_walk:
        m_walk.side_effect = OSError(13, "Permission denied")
        result = indexer.scan_and_index(videos_dir=bad_dir, screens_dir=None)
    assert len(result.errors) >= 1
    assert (
        "inaccessible" in result.errors[0]
        or "Permission" in result.errors[0]
        or str(bad_dir) in result.errors[0]
    )
    assert result.n_scanned >= 0


def test_associate_with_matches(temp_db: Path, temp_media_dir: Path) -> None:
    """Test l'association des médias avec les matchs."""
    indexer = MediaIndexer(temp_db)
    indexer.ensure_schema()
    indexer.scan_and_index(
        videos_dir=temp_media_dir,
        screens_dir=None,
        force_rescan=False,
    )

    n_associated = indexer.associate_with_matches(tolerance_minutes=5)

    conn = duckdb.connect(str(temp_db), read_only=True)
    try:
        count = conn.execute("SELECT COUNT(*) FROM media_match_associations").fetchone()[0]
        assert count >= 0
        assert n_associated == count
    finally:
        conn.close()


def test_associate_with_matches_explicit_timestamps(tmp_path: Path) -> None:
    """Test l'association avec des timestamps explicits (epoch UTC)."""
    db_path = tmp_path / "stats.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute("""
        CREATE TABLE match_stats (
            match_id VARCHAR PRIMARY KEY,
            start_time TIMESTAMP,
            time_played_seconds INTEGER
        )
    """)
    conn.execute(
        """
        INSERT INTO match_stats (match_id, start_time, time_played_seconds)
        VALUES (?, ?::TIMESTAMP, ?)
        """,
        ["match_1", "2026-02-03 17:00:00", 720],
    )
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
            first_seen_at TIMESTAMP,
            last_scan_at TIMESTAMP,
            scan_version INTEGER DEFAULT 2
        )
    """)
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
    match_start_epoch = datetime(2026, 2, 3, 17, 0, 0, tzinfo=timezone.utc).timestamp()
    media_epoch = match_start_epoch + 120
    conn.execute(
        """
        INSERT INTO media_files (
            file_path, file_hash, file_name, file_size, file_ext, kind,
            mtime, mtime_paris_epoch, capture_end_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CAST(? AS TIMESTAMP))
        """,
        [
            str(tmp_path / "clip.mp4"),
            "abc123",
            "clip.mp4",
            1000,
            "mp4",
            "video",
            media_epoch,
            media_epoch,
            "2026-02-03 17:02:00",
        ],
    )
    conn.commit()
    conn.close()

    indexer = MediaIndexer(db_path)
    with patch.object(MediaIndexer, "_get_all_player_dbs") as mock_dbs:
        mock_dbs.return_value = [(db_path, "test_xuid")]
        n = indexer.associate_with_matches(tolerance_minutes=5)

    assert n >= 1
    conn = duckdb.connect(str(db_path), read_only=True)
    count = conn.execute("SELECT COUNT(*) FROM media_match_associations").fetchone()[0]
    conn.close()
    assert count >= 1


def test_file_hash_computation(temp_db: Path, tmp_path: Path) -> None:
    """Test le calcul du hash des fichiers."""
    indexer = MediaIndexer(temp_db)
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")
    hash1 = indexer._compute_file_hash(test_file)
    assert hash1
    test_file.write_text("modified content")
    hash2 = indexer._compute_file_hash(test_file)
    assert hash1 != hash2


def test_get_file_metadata(temp_db: Path, tmp_path: Path) -> None:
    """Test la récupération des métadonnées (capture_start_utc, capture_end_utc)."""
    indexer = MediaIndexer(temp_db)
    test_video = tmp_path / "test.mp4"
    test_video.write_text("fake video")
    metadata = indexer._get_file_metadata(test_video)
    assert metadata is not None
    assert metadata["kind"] == "video"
    assert metadata["file_ext"] == "mp4"
    assert "mtime" in metadata
    assert "capture_start_utc" in metadata
    assert "capture_end_utc" in metadata
    assert "owner_xuid" not in metadata


# =============================================================================
# Sprint 2 : Association capture ↔ match (multi-joueurs)
# =============================================================================


def test_association_closest_match_when_multiple_candidates(tmp_path: Path) -> None:
    """Test que l'association choisit le match LE PLUS PROCHE quand plusieurs candidats."""
    db_path = tmp_path / "stats.duckdb"
    conn = duckdb.connect(str(db_path))
    # 2 matchs : match_A à 17:00, match_B à 17:10 (10 min plus tard)
    conn.execute("""
        CREATE TABLE match_stats (
            match_id VARCHAR PRIMARY KEY,
            start_time TIMESTAMP,
            time_played_seconds INTEGER,
            map_id VARCHAR,
            map_name VARCHAR
        )
    """)
    conn.execute(
        """
        INSERT INTO match_stats (match_id, start_time, time_played_seconds, map_id, map_name)
        VALUES ('match_A', '2026-02-03 17:00:00', 720, 'map1', 'Aquarius'),
               ('match_B', '2026-02-03 17:10:00', 720, 'map2', 'Live Fire')
        """,
    )
    conn.execute("""
        CREATE TABLE media_files (
            file_path VARCHAR PRIMARY KEY, file_hash VARCHAR NOT NULL, file_name VARCHAR,
            file_size BIGINT, file_ext VARCHAR, kind VARCHAR,
            capture_start_utc TIMESTAMP, capture_end_utc TIMESTAMP NOT NULL,
            duration_seconds DOUBLE, title VARCHAR, thumbnail_path VARCHAR,
            mtime DOUBLE NOT NULL, mtime_paris_epoch DOUBLE,
            status VARCHAR NOT NULL DEFAULT 'active',
            first_seen_at TIMESTAMP, last_scan_at TIMESTAMP, scan_version INTEGER DEFAULT 2
        )
    """)
    conn.execute("""
        CREATE TABLE media_match_associations (
            media_path VARCHAR NOT NULL, match_id VARCHAR NOT NULL, xuid VARCHAR NOT NULL,
            match_start_time TIMESTAMP NOT NULL, map_id VARCHAR, map_name VARCHAR,
            association_confidence DOUBLE DEFAULT 1.0, associated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (media_path, match_id, xuid)
        )
    """)
    # Média à 17:02 = 2 min après match_A, 8 min avant match_B → match_A plus proche
    epoch_a = datetime(2026, 2, 3, 17, 0, 0, tzinfo=timezone.utc).timestamp()
    media_epoch = epoch_a + 120
    conn.execute(
        """
        INSERT INTO media_files (file_path, file_hash, file_name, file_size, file_ext, kind,
            mtime, mtime_paris_epoch, capture_end_utc)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CAST(? AS TIMESTAMP))
        """,
        [
            str(tmp_path / "clip.mp4"),
            "abc",
            "clip.mp4",
            1000,
            "mp4",
            "video",
            media_epoch,
            media_epoch,
            "2026-02-03 17:02:00",
        ],
    )
    conn.commit()
    conn.close()

    indexer = MediaIndexer(db_path)
    with patch.object(MediaIndexer, "_get_all_player_dbs") as mock_dbs:
        mock_dbs.return_value = [(db_path, "xuid_1")]
        indexer.associate_with_matches(tolerance_minutes=10)

    conn = duckdb.connect(str(db_path), read_only=True)
    rows = conn.execute(
        "SELECT match_id, map_name FROM media_match_associations WHERE media_path = ?",
        [str(tmp_path / "clip.mp4")],
    ).fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0][0] == "match_A"
    assert rows[0][1] == "Aquarius"


def test_association_multi_players_same_media(tmp_path: Path) -> None:
    """Test qu'une capture peut avoir plusieurs associations (une par joueur)."""
    db_a = tmp_path / "player_a" / "stats.duckdb"
    db_b = tmp_path / "player_b" / "stats.duckdb"
    db_a.parent.mkdir(parents=True)
    db_b.parent.mkdir(parents=True)

    epoch = datetime(2026, 2, 3, 17, 0, 0, tzinfo=timezone.utc).timestamp()
    media_epoch = epoch + 60
    media_path = str(tmp_path / "shared" / "clip.mp4")

    # db_a = BDD médias du joueur actuel (contient media_files + associations)
    conn = duckdb.connect(str(db_a))
    conn.execute("""
        CREATE TABLE match_stats (
            match_id VARCHAR PRIMARY KEY, start_time TIMESTAMP,
            time_played_seconds INTEGER, map_id VARCHAR, map_name VARCHAR
        )
    """)
    conn.execute(
        """
        INSERT INTO match_stats (match_id, start_time, time_played_seconds, map_id, map_name)
        VALUES ('match_a', '2026-02-03 17:00:00', 720, 'm1', 'Aquarius')
        """,
    )
    conn.execute("""
        CREATE TABLE media_files (
            file_path VARCHAR PRIMARY KEY, file_hash VARCHAR NOT NULL, file_name VARCHAR,
            file_size BIGINT, file_ext VARCHAR, kind VARCHAR,
            capture_start_utc TIMESTAMP, capture_end_utc TIMESTAMP NOT NULL,
            duration_seconds DOUBLE, title VARCHAR, thumbnail_path VARCHAR,
            mtime DOUBLE NOT NULL, mtime_paris_epoch DOUBLE,
            status VARCHAR NOT NULL DEFAULT 'active',
            first_seen_at TIMESTAMP, last_scan_at TIMESTAMP, scan_version INTEGER DEFAULT 2
        )
    """)
    conn.execute("""
        CREATE TABLE media_match_associations (
            media_path VARCHAR NOT NULL, match_id VARCHAR NOT NULL, xuid VARCHAR NOT NULL,
            match_start_time TIMESTAMP NOT NULL, map_id VARCHAR, map_name VARCHAR,
            association_confidence DOUBLE DEFAULT 1.0, associated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (media_path, match_id, xuid)
        )
    """)
    conn.execute(
        """
        INSERT INTO media_files (file_path, file_hash, file_name, file_size, file_ext, kind,
            mtime, mtime_paris_epoch, capture_end_utc)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CAST(? AS TIMESTAMP))
        """,
        [
            media_path,
            "abc",
            "clip.mp4",
            1000,
            "mp4",
            "video",
            media_epoch,
            media_epoch,
            "2026-02-03 17:01:00",
        ],
    )
    conn.commit()
    conn.close()

    # db_b = BDD autre joueur (match_stats seulement)
    conn = duckdb.connect(str(db_b))
    conn.execute("""
        CREATE TABLE match_stats (
            match_id VARCHAR PRIMARY KEY, start_time TIMESTAMP,
            time_played_seconds INTEGER, map_id VARCHAR, map_name VARCHAR
        )
    """)
    conn.execute(
        """
        INSERT INTO match_stats (match_id, start_time, time_played_seconds, map_id, map_name)
        VALUES ('match_b', '2026-02-03 17:00:00', 720, 'm1', 'Aquarius')
        """,
    )
    conn.commit()
    conn.close()

    # Utiliser db_a comme BDD médias ; les associations seront stockées ici
    indexer = MediaIndexer(db_a)
    with patch.object(MediaIndexer, "_get_all_player_dbs") as mock_dbs:
        mock_dbs.return_value = [(db_a, "xuid_a"), (db_b, "xuid_b")]
        n = indexer.associate_with_matches(tolerance_minutes=5)

    assert n >= 2
    conn = duckdb.connect(str(db_a), read_only=True)
    rows = conn.execute(
        "SELECT match_id, xuid FROM media_match_associations ORDER BY xuid"
    ).fetchall()
    conn.close()
    xuids = {r[1] for r in rows}
    assert "xuid_a" in xuids
    assert "xuid_b" in xuids


def test_association_map_id_map_name_stored(tmp_path: Path) -> None:
    """Test que map_id et map_name sont bien stockés dans les associations."""
    db_path = tmp_path / "stats.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute("""
        CREATE TABLE match_stats (
            match_id VARCHAR PRIMARY KEY, start_time TIMESTAMP,
            time_played_seconds INTEGER, map_id VARCHAR, map_name VARCHAR
        )
    """)
    conn.execute(
        """
        INSERT INTO match_stats (match_id, start_time, time_played_seconds, map_id, map_name)
        VALUES ('m1', '2026-02-03 17:00:00', 720, 'uuid-aquarius', 'Aquarius')
        """,
    )
    conn.execute("""
        CREATE TABLE media_files (
            file_path VARCHAR PRIMARY KEY, file_hash VARCHAR NOT NULL, file_name VARCHAR,
            file_size BIGINT, file_ext VARCHAR, kind VARCHAR,
            capture_start_utc TIMESTAMP, capture_end_utc TIMESTAMP NOT NULL,
            duration_seconds DOUBLE, title VARCHAR, thumbnail_path VARCHAR,
            mtime DOUBLE NOT NULL, mtime_paris_epoch DOUBLE,
            status VARCHAR NOT NULL DEFAULT 'active',
            first_seen_at TIMESTAMP, last_scan_at TIMESTAMP, scan_version INTEGER DEFAULT 2
        )
    """)
    conn.execute("""
        CREATE TABLE media_match_associations (
            media_path VARCHAR NOT NULL, match_id VARCHAR NOT NULL, xuid VARCHAR NOT NULL,
            match_start_time TIMESTAMP NOT NULL, map_id VARCHAR, map_name VARCHAR,
            association_confidence DOUBLE DEFAULT 1.0, associated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (media_path, match_id, xuid)
        )
    """)
    epoch = datetime(2026, 2, 3, 17, 0, 0, tzinfo=timezone.utc).timestamp()
    conn.execute(
        """
        INSERT INTO media_files (file_path, file_hash, file_name, file_size, file_ext, kind,
            mtime, mtime_paris_epoch, capture_end_utc)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CAST(? AS TIMESTAMP))
        """,
        [
            str(tmp_path / "c.mp4"),
            "x",
            "c.mp4",
            1,
            "mp4",
            "video",
            epoch + 60,
            epoch + 60,
            "2026-02-03 17:01:00",
        ],
    )
    conn.commit()
    conn.close()

    indexer = MediaIndexer(db_path)
    with patch.object(MediaIndexer, "_get_all_player_dbs") as mock_dbs:
        mock_dbs.return_value = [(db_path, "u1")]
        indexer.associate_with_matches(tolerance_minutes=5)

    conn = duckdb.connect(str(db_path), read_only=True)
    row = conn.execute("SELECT map_id, map_name FROM media_match_associations").fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "uuid-aquarius"
    assert row[1] == "Aquarius"


# =============================================================================
# Sprint 3 : Thumbnails (vidéos + images)
# =============================================================================


def test_generate_image_thumbnails(temp_db: Path, temp_media_dir: Path) -> None:
    """Test la génération des miniatures pour les images (PIL resize)."""
    indexer = MediaIndexer(temp_db)
    indexer.ensure_schema()
    indexer.scan_and_index(videos_dir=None, screens_dir=temp_media_dir)

    gen, err = indexer.generate_thumbnails_for_new(
        videos_dir=None,
        screens_dir=temp_media_dir,
    )

    conn = duckdb.connect(str(temp_db), read_only=True)
    try:
        rows = conn.execute(
            """
            SELECT file_path, thumbnail_path FROM media_files
            WHERE kind = 'image' AND status = 'active'
            """
        ).fetchall()
        assert len(rows) >= 1
        for _path_str, thumb_path in rows:
            assert thumb_path is not None
            assert thumb_path != ""
            assert Path(thumb_path).exists()
    finally:
        conn.close()
    assert gen >= 1 or err == 0


def test_generate_thumbnails_no_ffmpeg_skips_videos(temp_db: Path, temp_media_dir: Path) -> None:
    """Test que l'absence de ffmpeg ne bloque pas (images fonctionnent quand même)."""
    indexer = MediaIndexer(temp_db)
    indexer.ensure_schema()
    indexer.scan_and_index(
        videos_dir=temp_media_dir,
        screens_dir=temp_media_dir,
    )

    with patch("scripts.generate_thumbnails.check_ffmpeg", return_value=False):
        gen, err = indexer.generate_thumbnails_for_new(
            videos_dir=temp_media_dir,
            screens_dir=temp_media_dir,
        )
    assert err == 0
    assert gen >= 1


def test_generate_thumbnails_empty_dirs(temp_db: Path) -> None:
    """Test que generate_thumbnails_for_new avec dossiers vides/invalides retourne (0, 0)."""
    indexer = MediaIndexer(temp_db)
    indexer.ensure_schema()

    gen, err = indexer.generate_thumbnails_for_new(
        videos_dir=None,
        screens_dir=None,
    )
    assert gen == 0
    assert err == 0


def test_get_image_thumbnail_path() -> None:
    """Test le chemin du thumbnail image."""
    from src.data.media_indexer import _get_image_thumbnail_path

    thumbs = Path("/tmp/thumbs")
    p = Path("/media/screenshot.png")
    thumb = _get_image_thumbnail_path(p, thumbs)
    assert thumb.parent == thumbs
    assert thumb.suffix == ".png"
    assert "screenshot" in thumb.name

    p2 = Path("/media/photo.jpg")
    thumb2 = _get_image_thumbnail_path(p2, thumbs)
    assert thumb2.suffix == ".jpg"


def test_association_search_all_player_dbs(tmp_path: Path) -> None:
    """Test que la recherche s'effectue dans toutes les BDD joueurs (pas seulement la courante)."""
    db_current = tmp_path / "current" / "stats.duckdb"
    db_other = tmp_path / "other" / "stats.duckdb"
    db_current.parent.mkdir(parents=True)
    db_other.parent.mkdir(parents=True)

    epoch = datetime(2026, 2, 3, 17, 0, 0, tzinfo=timezone.utc).timestamp()
    media_epoch = epoch + 120

    # BDD courante : media + associations, match_stats VIDE (pas de match pour ce joueur)
    conn = duckdb.connect(str(db_current))
    conn.execute(
        "CREATE TABLE match_stats (match_id VARCHAR PRIMARY KEY, start_time TIMESTAMP, time_played_seconds INTEGER)"
    )
    conn.execute("""
        CREATE TABLE media_files (
            file_path VARCHAR PRIMARY KEY, file_hash VARCHAR NOT NULL, file_name VARCHAR,
            file_size BIGINT, file_ext VARCHAR, kind VARCHAR,
            capture_start_utc TIMESTAMP, capture_end_utc TIMESTAMP NOT NULL,
            duration_seconds DOUBLE, title VARCHAR, thumbnail_path VARCHAR,
            mtime DOUBLE NOT NULL, mtime_paris_epoch DOUBLE,
            status VARCHAR NOT NULL DEFAULT 'active',
            first_seen_at TIMESTAMP, last_scan_at TIMESTAMP, scan_version INTEGER DEFAULT 2
        )
    """)
    conn.execute("""
        CREATE TABLE media_match_associations (
            media_path VARCHAR NOT NULL, match_id VARCHAR NOT NULL, xuid VARCHAR NOT NULL,
            match_start_time TIMESTAMP NOT NULL, map_id VARCHAR, map_name VARCHAR,
            association_confidence DOUBLE DEFAULT 1.0, associated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (media_path, match_id, xuid)
        )
    """)
    media_path = str(tmp_path / "c.mp4")
    conn.execute(
        """
        INSERT INTO media_files (file_path, file_hash, file_name, file_size, file_ext, kind,
            mtime, mtime_paris_epoch, capture_end_utc)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CAST(? AS TIMESTAMP))
        """,
        [
            media_path,
            "x",
            "c.mp4",
            1,
            "mp4",
            "video",
            media_epoch,
            media_epoch,
            "2026-02-03 17:02:00",
        ],
    )
    conn.commit()
    conn.close()

    # BDD autre joueur : a un match qui correspond
    conn = duckdb.connect(str(db_other))
    conn.execute("""
        CREATE TABLE match_stats (
            match_id VARCHAR PRIMARY KEY, start_time TIMESTAMP, time_played_seconds INTEGER
        )
    """)
    conn.execute(
        """
        INSERT INTO match_stats (match_id, start_time, time_played_seconds)
        VALUES ('match_other', '2026-02-03 17:00:00', 720)
        """,
    )
    conn.commit()
    conn.close()

    indexer = MediaIndexer(db_current)
    with patch.object(MediaIndexer, "_get_all_player_dbs") as mock_dbs:
        mock_dbs.return_value = [(db_current, "xuid_current"), (db_other, "xuid_other")]
        n = indexer.associate_with_matches(tolerance_minutes=5)

    assert n >= 1
    conn = duckdb.connect(str(db_current), read_only=True)
    rows = conn.execute("SELECT match_id, xuid FROM media_match_associations").fetchall()
    conn.close()
    assert any(r[1] == "xuid_other" for r in rows)


def test_load_media_for_ui(temp_db: Path) -> None:
    """Test load_media_for_ui (Sprint 5) : colonnes et section mine/teammate/unassigned."""
    import polars as pl

    indexer = MediaIndexer(temp_db)
    indexer.ensure_schema()
    conn = duckdb.connect(str(temp_db), read_only=False)
    try:
        conn.execute(
            """
            INSERT INTO media_files (
                file_path, file_hash, file_name, file_size, file_ext, kind,
                capture_start_utc, capture_end_utc, duration_seconds, title,
                mtime, status, scan_version
            ) VALUES
                ('/path/a.png', 'h1', 'a.png', 100, 'png', 'image', NULL, '2026-02-07 12:00:00', NULL, NULL, 1.0, 'active', 2),
                ('/path/b.png', 'h2', 'b.png', 200, 'png', 'image', NULL, '2026-02-07 11:00:00', NULL, NULL, 2.0, 'active', 2)
            """
        )
        conn.execute(
            """
            INSERT INTO media_match_associations (media_path, match_id, xuid, match_start_time, map_name)
            VALUES ('/path/a.png', 'match_1', 'xuid_me', '2026-02-07 11:55:00', 'Aquarius')
            """
        )
        conn.commit()
    finally:
        conn.close()

    with patch.object(MediaIndexer, "_get_all_player_dbs") as mock_dbs:
        mock_dbs.return_value = [(temp_db, "xuid_me")]
        df = MediaIndexer.load_media_for_ui(temp_db, "xuid_me")

    assert isinstance(df, pl.DataFrame)
    assert not df.is_empty()
    required = {
        "file_path",
        "file_name",
        "kind",
        "map_name",
        "match_id",
        "xuid",
        "gamertag",
        "section",
    }
    assert required.issubset(df.columns)
    mine = df.filter(pl.col("section") == "mine")
    unassigned = df.filter(pl.col("section") == "unassigned")
    assert len(mine) >= 1
    assert len(unassigned) >= 1
    assert mine.filter(pl.col("file_path") == "/path/a.png").height == 1
    assert unassigned.filter(pl.col("file_path") == "/path/b.png").height == 1
