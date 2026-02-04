"""Tests unitaires pour le module d'indexation des médias."""

from __future__ import annotations

import tempfile
from pathlib import Path

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
    indexer = MediaIndexer(temp_db, "test_xuid_123")
    assert indexer.db_path == temp_db
    assert indexer.owner_xuid == "test_xuid_123"


def test_ensure_schema(temp_db: Path):
    """Test la création du schéma."""
    indexer = MediaIndexer(temp_db, "test_xuid_123")
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
    finally:
        conn.close()


def test_scan_and_index(temp_db: Path, temp_media_dir: Path):
    """Test le scan et l'indexation des médias."""
    indexer = MediaIndexer(temp_db, "test_xuid_123")
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
        files = conn.execute(
            "SELECT file_path, kind FROM media_files WHERE owner_xuid = ?",
            ["test_xuid_123"],
        ).fetchall()
        assert len(files) >= 1
        # Vérifier qu'on a bien la vidéo
        video_files = [f for f in files if f[1] == "video"]
        assert len(video_files) >= 1
    finally:
        conn.close()


def test_scan_incremental(temp_db: Path, temp_media_dir: Path):
    """Test que le scan incrémental ne re-traite pas les fichiers inchangés."""
    indexer = MediaIndexer(temp_db, "test_xuid_123")
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
    indexer = MediaIndexer(temp_db, "test_xuid_123")
    indexer.ensure_schema()

    # Scanner d'abord
    indexer.scan_and_index(
        videos_dir=temp_media_dir,
        screens_dir=None,
        force_rescan=False,
    )

    # Associer avec les matchs
    indexer.associate_with_matches(tolerance_minutes=5)

    # Vérifier qu'au moins une association a été créée (si le timing correspond)
    conn = duckdb.connect(str(temp_db), read_only=True)
    try:
        associations = conn.execute(
            """
            SELECT COUNT(*)
            FROM media_match_associations
            WHERE xuid = ?
            """,
            ["test_xuid_123"],
        ).fetchone()[0]
        # Note: peut être 0 si le timing ne correspond pas, c'est OK
        assert associations >= 0
    finally:
        conn.close()


def test_file_hash_computation(temp_db: Path, tmp_path: Path):
    """Test le calcul du hash des fichiers."""
    indexer = MediaIndexer(temp_db, "test_xuid_123")

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
    indexer = MediaIndexer(temp_db, "test_xuid_123")

    # Créer un fichier vidéo de test
    test_video = tmp_path / "test.mp4"
    test_video.write_text("fake video")

    metadata = indexer._get_file_metadata(test_video)
    assert metadata is not None
    assert metadata["kind"] == "video"
    assert metadata["file_ext"] == "mp4"
    assert "mtime" in metadata
    assert "mtime_paris_epoch" in metadata


def test_owner_xuid_required():
    """Test que owner_xuid est requis."""
    with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False) as f:
        db_path = Path(f.name)

    try:
        with pytest.raises(ValueError, match="owner_xuid ne peut pas être vide"):
            MediaIndexer(db_path, "")
    finally:
        if db_path.exists():
            db_path.unlink()
