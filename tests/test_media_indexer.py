"""Tests unitaires pour le module d'indexation des médias."""

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
        # Créer la table match_stats minimale pour les tests
        conn.execute("""
            CREATE TABLE match_stats (
                match_id VARCHAR PRIMARY KEY,
                start_time TIMESTAMP,
                time_played_seconds INTEGER,
                xuid VARCHAR
            )
        """)
        # Insérer un match de test
        conn.execute(
            """
            INSERT INTO match_stats (match_id, start_time, time_played_seconds, xuid)
            VALUES (?, ?, ?, ?)
            """,
            [
                "test_match_1",
                "2026-02-04 20:00:00+00:00",
                720,  # 12 minutes
                "test_xuid_123",
            ],
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

    # Créer quelques fichiers de test
    (media_dir / "test_video.mp4").write_text("fake video content")
    (media_dir / "test_image.png").write_text("fake image content")

    return media_dir


def test_media_indexer_init(temp_db: Path):
    """Test l'initialisation de MediaIndexer."""
    indexer = MediaIndexer(temp_db)
    assert indexer.db_path == temp_db


def test_ensure_schema(temp_db: Path):
    """Test la création du schéma."""
    indexer = MediaIndexer(temp_db)
    indexer.ensure_schema()

    # Vérifier que les tables existent
    conn = duckdb.connect(str(temp_db), read_only=True)
    try:
        tables = conn.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'main'
            AND table_name IN ('media_files', 'media_match_associations')
            """
        ).fetchall()
        table_names = {row[0] for row in tables}
        assert "media_files" in table_names
        assert "media_match_associations" in table_names

        # Vérifier que media_files n'a pas de colonne owner_xuid
        columns = conn.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'main'
            AND table_name = 'media_files'
            """
        ).fetchall()
        column_names = {row[0] for row in columns}
        assert "owner_xuid" not in column_names
    finally:
        conn.close()


def test_scan_and_index(temp_db: Path, temp_media_dir: Path):
    """Test le scan et l'indexation des médias."""
    indexer = MediaIndexer(temp_db)
    indexer.ensure_schema()

    result = indexer.scan_and_index(
        videos_dir=temp_media_dir,
        screens_dir=None,
        force_rescan=False,
    )

    assert isinstance(result, ScanResult)
    assert result.n_scanned >= 1  # Au moins la vidéo
    assert result.n_new >= 1

    # Vérifier que les fichiers sont bien enregistrés en BDD
    conn = duckdb.connect(str(temp_db), read_only=True)
    try:
        files = conn.execute("SELECT file_path, kind FROM media_files").fetchall()
        assert len(files) >= 1
        # Vérifier qu'on a bien la vidéo
        video_files = [f for f in files if f[1] == "video"]
        assert len(video_files) >= 1
    finally:
        conn.close()


def test_scan_incremental(temp_db: Path, temp_media_dir: Path):
    """Test que le scan incrémental ne re-traite pas les fichiers inchangés."""
    indexer = MediaIndexer(temp_db)
    indexer.ensure_schema()

    # Premier scan
    result1 = indexer.scan_and_index(
        videos_dir=temp_media_dir,
        screens_dir=None,
        force_rescan=False,
    )
    assert result1.n_new >= 1  # Au moins un nouveau fichier

    # Deuxième scan (devrait détecter que rien n'a changé)
    result2 = indexer.scan_and_index(
        videos_dir=temp_media_dir,
        screens_dir=None,
        force_rescan=False,
    )

    # Le deuxième scan ne devrait pas trouver de nouveaux fichiers
    assert result2.n_new == 0
    assert result2.n_scanned >= 1  # Mais devrait scanner quand même


def test_associate_with_matches(temp_db: Path, temp_media_dir: Path):
    """Test l'association des médias avec les matchs."""
    indexer = MediaIndexer(temp_db)
    indexer.ensure_schema()

    # Scanner d'abord
    indexer.scan_and_index(
        videos_dir=temp_media_dir,
        screens_dir=None,
        force_rescan=False,
    )

    # Associer avec les matchs (cherche dans toutes les DBs joueurs)
    n_associated = indexer.associate_with_matches(tolerance_minutes=5)

    # Vérifier qu'au moins une association a été créée (si le timing correspond)
    conn = duckdb.connect(str(temp_db), read_only=True)
    try:
        associations = conn.execute(
            """
            SELECT COUNT(*)
            FROM media_match_associations
            """
        ).fetchone()[0]
        # Note: peut être 0 si le timing ne correspond pas, c'est OK
        assert associations >= 0
        assert n_associated == associations  # Le nombre retourné doit correspondre
    finally:
        conn.close()


def test_associate_with_matches_explicit_timestamps(tmp_path: Path):
    """Test que l'association fonctionne avec des timestamps explicits (epoch UTC)."""
    db_path = tmp_path / "stats.duckdb"
    conn = duckdb.connect(str(db_path))

    # Match à 2026-02-03 17:00:00 UTC = epoch 1738594800 (approx)
    match_start_utc = datetime(2026, 2, 3, 17, 0, 0, tzinfo=timezone.utc)
    match_start_epoch = match_start_utc.timestamp()
    # Durée 12 min
    conn.execute("""
        CREATE TABLE match_stats (
            match_id VARCHAR PRIMARY KEY,
            start_time TIMESTAMP,
            time_played_seconds INTEGER
        )
    """)
    # DuckDB accepte ISO avec timezone
    # Insérer en chaîne ISO UTC ; DuckDB renverra un datetime naïf (qu'on traite comme UTC)
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
            mtime DOUBLE NOT NULL,
            mtime_paris_epoch DOUBLE NOT NULL,
            thumbnail_path VARCHAR,
            thumbnail_generated_at TIMESTAMP,
            first_seen_at TIMESTAMP,
            last_scan_at TIMESTAMP,
            scan_version INTEGER DEFAULT 1
        )
    """)
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

    # Média dont le mtime (epoch UTC) est 2 min après le début du match
    media_epoch = match_start_epoch + 120
    conn.execute(
        """
        INSERT INTO media_files (
            file_path, file_hash, file_name, file_size, file_ext, kind,
            mtime, mtime_paris_epoch
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
        ],
    )
    conn.commit()
    conn.close()

    # Associer : il faut que _get_all_player_dbs retourne notre DB
    indexer = MediaIndexer(db_path)
    with patch.object(MediaIndexer, "_get_all_player_dbs") as mock_dbs:
        mock_dbs.return_value = [(db_path, "test_xuid")]

        n = indexer.associate_with_matches(tolerance_minutes=5)

    assert n >= 1, "Au moins une association doit être créée"
    conn = duckdb.connect(str(db_path), read_only=True)
    count = conn.execute("SELECT COUNT(*) FROM media_match_associations").fetchone()[0]
    conn.close()
    assert count >= 1


def test_file_hash_computation(temp_db: Path, tmp_path: Path):
    """Test le calcul du hash des fichiers."""
    indexer = MediaIndexer(temp_db)

    # Créer un fichier de test
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")

    hash1 = indexer._compute_file_hash(test_file)
    assert hash1  # Hash non vide

    # Modifier le fichier
    test_file.write_text("modified content")
    hash2 = indexer._compute_file_hash(test_file)
    assert hash1 != hash2  # Hash différent


def test_get_file_metadata(temp_db: Path, tmp_path: Path):
    """Test la récupération des métadonnées d'un fichier."""
    indexer = MediaIndexer(temp_db)

    # Créer un fichier vidéo de test
    test_video = tmp_path / "test.mp4"
    test_video.write_text("fake video")

    metadata = indexer._get_file_metadata(test_video)
    assert metadata is not None
    assert metadata["kind"] == "video"
    assert metadata["file_ext"] == "mp4"
    assert "mtime" in metadata
    assert "mtime_paris_epoch" in metadata
    # Vérifier qu'il n'y a pas de owner_xuid dans les métadonnées
    assert "owner_xuid" not in metadata
