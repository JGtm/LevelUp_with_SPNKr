#!/usr/bin/env python3
"""Génère des thumbnails animés (GIF) pour les vidéos du dossier configuré.

Ce script :
1. Lit la configuration depuis app_settings.json (media_videos_dir)
2. Scanne les vidéos existantes
3. Génère un GIF animé de 3-5 secondes pour chaque vidéo
4. Stocke les GIFs dans un sous-dossier 'thumbs' du dossier vidéos

Prérequis : ffmpeg doit être installé et accessible dans le PATH.

Usage:
    python scripts/generate_thumbnails.py
    python scripts/generate_thumbnails.py --watch  # Mode surveillance continue
    python scripts/generate_thumbnails.py --videos-dir /path/to/videos
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Extensions vidéo supportées
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mkv", ".mov", ".avi"}

# Paramètres du GIF
GIF_WIDTH = 320  # Largeur du GIF en pixels
GIF_FPS = 10  # Images par seconde
GIF_DURATION = 4  # Durée en secondes (extrait du milieu de la vidéo)


def get_repo_root() -> Path:
    """Retourne la racine du repo."""
    return Path(__file__).resolve().parent.parent


def load_videos_dir_from_settings() -> str | None:
    """Charge le dossier vidéos depuis app_settings.json."""
    settings_path = get_repo_root() / "app_settings.json"
    if not settings_path.exists():
        return None

    try:
        with open(settings_path, encoding="utf-8") as f:
            settings = json.load(f)
        return settings.get("media_videos_dir")
    except (json.JSONDecodeError, OSError):
        return None


def check_ffmpeg() -> bool:
    """Vérifie que ffmpeg est disponible."""
    return shutil.which("ffmpeg") is not None


def get_video_duration(video_path: Path) -> float | None:
    """Récupère la durée d'une vidéo en secondes."""
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
                str(video_path),
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


def generate_thumbnail_gif(
    video_path: Path,
    output_path: Path,
    *,
    width: int = GIF_WIDTH,
    fps: int = GIF_FPS,
    duration: float = GIF_DURATION,
) -> bool:
    """Génère un GIF animé à partir d'une vidéo.

    Args:
        video_path: Chemin vers la vidéo source.
        output_path: Chemin de sortie pour le GIF.
        width: Largeur du GIF en pixels.
        fps: Images par seconde.
        duration: Durée de l'extrait en secondes.

    Returns:
        True si le GIF a été généré avec succès.
    """
    # Obtenir la durée de la vidéo
    video_duration = get_video_duration(video_path)

    # Calculer le point de départ (milieu de la vidéo)
    if video_duration and video_duration > duration * 2:
        start_time = (video_duration - duration) / 2
    else:
        start_time = 0

    # Créer le dossier de sortie si nécessaire
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Générer le GIF avec ffmpeg
    # -ss : point de départ
    # -t : durée
    # -vf : filtres vidéo (redimensionner, générer palette pour qualité)
    # La méthode en 2 passes donne une meilleure qualité de couleur
    palette_path = output_path.with_suffix(".palette.png")

    try:
        # Passe 1 : générer la palette
        result1 = subprocess.run(
            [
                "ffmpeg",
                "-y",  # Écraser sans demander
                "-ss",
                str(start_time),
                "-t",
                str(duration),
                "-i",
                str(video_path),
                "-vf",
                f"fps={fps},scale={width}:-1:flags=lanczos,palettegen",
                str(palette_path),
            ],
            capture_output=True,
            timeout=120,
        )

        if result1.returncode != 0:
            # Fallback : méthode simple sans palette
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    str(start_time),
                    "-t",
                    str(duration),
                    "-i",
                    str(video_path),
                    "-vf",
                    f"fps={fps},scale={width}:-1:flags=lanczos",
                    str(output_path),
                ],
                capture_output=True,
                timeout=120,
            )
            return result.returncode == 0

        # Passe 2 : générer le GIF avec la palette
        result2 = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                str(start_time),
                "-t",
                str(duration),
                "-i",
                str(video_path),
                "-i",
                str(palette_path),
                "-lavfi",
                f"fps={fps},scale={width}:-1:flags=lanczos [x]; [x][1:v] paletteuse",
                str(output_path),
            ],
            capture_output=True,
            timeout=120,
        )

        return result2.returncode == 0

    except subprocess.TimeoutExpired:
        print(f"  Timeout lors de la génération de {output_path.name}")
        return False
    except Exception as e:
        print(f"  Erreur: {e}")
        return False
    finally:
        # Nettoyer la palette temporaire
        if palette_path.exists():
            try:
                palette_path.unlink()
            except Exception:
                pass


def get_thumbnail_path(video_path: Path, thumbs_dir: Path) -> Path:
    """Génère le chemin du thumbnail pour une vidéo.

    Utilise un hash du chemin complet pour éviter les collisions.
    """
    # Hash du chemin pour unicité
    path_hash = hashlib.md5(str(video_path).encode()).hexdigest()[:12]
    stem = video_path.stem[:50]  # Limiter la longueur du nom
    return thumbs_dir / f"{stem}_{path_hash}.gif"


def scan_and_generate(videos_dir: Path, *, force: bool = False) -> tuple[int, int]:
    """Scanne le dossier et génère les thumbnails manquants.

    Args:
        videos_dir: Dossier contenant les vidéos.
        force: Si True, régénère tous les thumbnails.

    Returns:
        Tuple (nombre généré, nombre d'erreurs).
    """
    if not videos_dir.exists():
        print(f"Dossier vidéos introuvable: {videos_dir}")
        return 0, 0

    thumbs_dir = videos_dir / "thumbs"
    thumbs_dir.mkdir(exist_ok=True)

    videos = [
        f for f in videos_dir.iterdir() if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS
    ]

    if not videos:
        print(f"Aucune vidéo trouvée dans {videos_dir}")
        return 0, 0

    print(f"Trouvé {len(videos)} vidéo(s) dans {videos_dir}")

    generated = 0
    errors = 0

    for video in videos:
        thumb_path = get_thumbnail_path(video, thumbs_dir)

        if thumb_path.exists() and not force:
            continue

        print(f"Génération du thumbnail pour: {video.name}")
        if generate_thumbnail_gif(video, thumb_path):
            generated += 1
            print(f"  OK: {thumb_path.name}")
        else:
            errors += 1
            print("  ERREUR: échec de la génération")

    return generated, errors


def watch_mode(videos_dir: Path, interval: int = 30) -> None:
    """Mode surveillance continue avec polling.

    Args:
        videos_dir: Dossier à surveiller.
        interval: Intervalle entre les scans en secondes.
    """
    print(f"Mode surveillance (polling): {videos_dir}")
    print(f"Intervalle: {interval}s (Ctrl+C pour arrêter)")

    while True:
        generated, errors = scan_and_generate(videos_dir)
        if generated > 0 or errors > 0:
            print(f"Scan terminé: {generated} généré(s), {errors} erreur(s)")
        time.sleep(interval)


def daemon_mode(videos_dir: Path) -> None:
    """Mode daemon avec watchdog (surveillance temps réel).

    Utilise inotify (Linux) ou FSEvents (macOS) pour détecter
    les nouveaux fichiers instantanément.

    Args:
        videos_dir: Dossier à surveiller.
    """
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler, FileCreatedEvent
    except ImportError:
        print("ERREUR: watchdog n'est pas installé.")
        print("Installez-le avec: pip install watchdog")
        print("Fallback sur le mode polling...")
        watch_mode(videos_dir, interval=30)
        return

    thumbs_dir = videos_dir / "thumbs"
    thumbs_dir.mkdir(exist_ok=True)

    class VideoHandler(FileSystemEventHandler):
        """Handler pour les événements de création de fichiers vidéo."""

        def on_created(self, event: FileCreatedEvent) -> None:
            if event.is_directory:
                return

            file_path = Path(event.src_path)
            if file_path.suffix.lower() not in VIDEO_EXTENSIONS:
                return

            # Attendre que le fichier soit complètement écrit
            print(f"Nouveau fichier détecté: {file_path.name}")
            time.sleep(2)  # Attendre 2s pour s'assurer que l'écriture est terminée

            # Vérifier que le fichier existe toujours et a une taille > 0
            if not file_path.exists() or file_path.stat().st_size == 0:
                print(f"  Fichier incomplet ou supprimé, ignoré.")
                return

            thumb_path = get_thumbnail_path(file_path, thumbs_dir)
            if thumb_path.exists():
                print(f"  Thumbnail existe déjà: {thumb_path.name}")
                return

            print(f"  Génération du thumbnail...")
            if generate_thumbnail_gif(file_path, thumb_path):
                print(f"  OK: {thumb_path.name}")
            else:
                print("  ERREUR: échec de la génération")

    # Scanner les fichiers existants d'abord
    print(f"Scan initial de {videos_dir}...")
    generated, errors = scan_and_generate(videos_dir)
    print(f"Scan initial terminé: {generated} généré(s), {errors} erreur(s)")

    # Démarrer la surveillance
    event_handler = VideoHandler()
    observer = Observer()
    observer.schedule(event_handler, str(videos_dir), recursive=False)
    observer.start()

    print(f"\nMode daemon (watchdog): {videos_dir}")
    print("Surveillance temps réel active (Ctrl+C pour arrêter)")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nArrêt du daemon...")
        observer.stop()
    observer.join()
    print("Daemon arrêté.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Génère des thumbnails GIF animés pour les vidéos."
    )
    parser.add_argument(
        "--videos-dir",
        type=str,
        help="Dossier contenant les vidéos (par défaut: depuis app_settings.json)",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Mode surveillance continue",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Intervalle de scan en mode watch (secondes)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Régénérer tous les thumbnails même s'ils existent",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Mode daemon avec watchdog (surveillance temps réel)",
    )

    args = parser.parse_args()

    # Vérifier ffmpeg
    if not check_ffmpeg():
        print("ERREUR: ffmpeg n'est pas installé ou n'est pas dans le PATH.")
        print("Installez ffmpeg: https://ffmpeg.org/download.html")
        return 1

    # Déterminer le dossier vidéos
    videos_dir: str | None = args.videos_dir
    if not videos_dir:
        videos_dir = load_videos_dir_from_settings()

    if not videos_dir:
        print("ERREUR: Aucun dossier vidéos configuré.")
        print("Utilisez --videos-dir ou configurez media_videos_dir dans app_settings.json")
        return 1

    videos_path = Path(videos_dir)
    if not videos_path.exists():
        print(f"ERREUR: Dossier introuvable: {videos_path}")
        return 1

    if args.daemon:
        try:
            daemon_mode(videos_path)
        except KeyboardInterrupt:
            print("\nArrêt demandé.")
            return 0
    elif args.watch:
        try:
            watch_mode(videos_path, interval=args.interval)
        except KeyboardInterrupt:
            print("\nArrêt demandé.")
            return 0
    else:
        generated, errors = scan_and_generate(videos_path, force=args.force)
        print(f"\nTerminé: {generated} thumbnail(s) généré(s), {errors} erreur(s)")
        return 1 if errors > 0 else 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
