"""Fonctions de synchronisation et gestion des bases SPNKr.

Ce module contient les fonctions pour :
- Détecter et sélectionner les bases SPNKr
- Afficher l'indicateur de synchronisation
- Rafraîchir les bases via l'API
- Nettoyer les fichiers temporaires orphelins
"""

from __future__ import annotations

import os
import subprocess
import sys
import time as time_module
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import streamlit as st

from src.db import get_sync_metadata

if TYPE_CHECKING:
    pass


def pick_latest_spnkr_db_if_any(repo_root: Path | None = None) -> str:
    """Sélectionne la base SPNKr la plus récente dans data/.
    
    Args:
        repo_root: Racine du repo (déduit automatiquement si None).
        
    Returns:
        Chemin de la DB ou chaîne vide si aucune trouvée.
    """
    try:
        if repo_root is None:
            repo_root = Path(__file__).resolve().parent.parent.parent
        data_dir = repo_root / "data"
        if not data_dir.exists():
            return ""
        candidates = [p for p in data_dir.glob("spnkr*.db") if p.is_file()]
        if not candidates:
            return ""
        # On évite de sélectionner une DB vide (0 octet), ce qui bloque l'app (aucune table).
        non_empty = [p for p in candidates if p.exists() and p.stat().st_size > 0]
        non_empty.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0.0, reverse=True)
        if non_empty:
            return str(non_empty[0])
        # Fallback: si tout est vide, retourne quand même la plus récente pour debug.
        candidates.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0.0, reverse=True)
        return str(candidates[0])
    except Exception:
        return ""


def is_spnkr_db_path(db_path: str) -> bool:
    """Vérifie si un chemin correspond à une base SPNKr."""
    try:
        p = Path(db_path)
        return p.suffix.lower() == ".db" and p.name.lower().startswith("spnkr")
    except Exception:
        return False


def cleanup_orphan_tmp_dbs(repo_root: Path | None = None) -> None:
    """Nettoie les fichiers .tmp.*.db orphelins dans le dossier data/.
    
    Ces fichiers peuvent rester si un import SPNKr a été interrompu
    (crash, timeout, fermeture de l'app). On supprime ceux de plus de 1h.
    
    Args:
        repo_root: Racine du repo (déduit automatiquement si None).
    """
    if st.session_state.get("_tmp_db_cleanup_done"):
        return
    st.session_state["_tmp_db_cleanup_done"] = True
    
    try:
        if repo_root is None:
            repo_root = Path(__file__).resolve().parent.parent.parent
        data_dir = repo_root / "data"
        if not data_dir.exists():
            return
        
        now = time_module.time()
        one_hour_ago = now - 3600  # 1 heure
        
        # Pattern: *.tmp.*.db (ex: spnkr_gt_Madina.db.tmp.1234567890.12345.db)
        for tmp_file in data_dir.glob("*.tmp.*.db"):
            try:
                if tmp_file.stat().st_mtime < one_hour_ago:
                    tmp_file.unlink()
            except Exception:
                pass
        
        # Pattern alternatif: *.db.tmp.* sans extension finale
        for tmp_file in data_dir.glob("*.db.tmp.*"):
            try:
                if tmp_file.stat().st_mtime < one_hour_ago:
                    tmp_file.unlink()
            except Exception:
                pass
    except Exception:
        pass


def render_sync_indicator(db_path: str) -> None:
    """Affiche l'indicateur de dernière synchronisation dans la sidebar.
    
    Couleurs:
    - 🟢 Vert: sync < 1h
    - 🟡 Jaune: sync < 24h  
    - 🔴 Rouge: sync > 24h ou jamais
    
    Args:
        db_path: Chemin vers la base de données.
    """
    if not db_path or not os.path.exists(db_path):
        return
    
    meta = get_sync_metadata(db_path)
    last_sync = meta.get("last_sync_at")
    total_matches = meta.get("total_matches", 0)
    
    now = datetime.now(timezone.utc)
    
    if last_sync:
        delta = now - last_sync
        hours = delta.total_seconds() / 3600
        
        if hours < 1:
            minutes = int(delta.total_seconds() / 60)
            indicator = "🟢"
            time_str = f"il y a {minutes} min" if minutes > 0 else "à l'instant"
        elif hours < 24:
            indicator = "🟡"
            h = int(hours)
            time_str = f"il y a {h}h"
        else:
            indicator = "🔴"
            days = int(hours / 24)
            if days == 1:
                time_str = "il y a 1 jour"
            else:
                time_str = f"il y a {days} jours"
        
        sync_text = f"{indicator} Sync {time_str}"
    else:
        # Pas de métadonnées de sync, on utilise la date de modification du fichier
        try:
            mtime = os.path.getmtime(db_path)
            mtime_dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
            delta = now - mtime_dt
            hours = delta.total_seconds() / 3600
            
            if hours < 1:
                indicator = "🟢"
                minutes = int(delta.total_seconds() / 60)
                time_str = f"il y a {minutes} min" if minutes > 0 else "à l'instant"
            elif hours < 24:
                indicator = "🟡"
                h = int(hours)
                time_str = f"il y a {h}h"
            else:
                indicator = "🔴"
                days = int(hours / 24)
                time_str = f"il y a {days} jour{'s' if days > 1 else ''}"
            
            sync_text = f"{indicator} Modifié {time_str}"
        except Exception:
            sync_text = "🔴 Sync inconnue"
    
    # Affichage compact
    match_info = f"({total_matches} matchs)" if total_matches > 0 else ""
    st.markdown(
        f"<div style='font-size: 0.85em; color: #888; margin: 4px 0 8px 0;'>"
        f"{sync_text} {match_info}</div>",
        unsafe_allow_html=True,
    )


def refresh_spnkr_db_via_api(
    *,
    db_path: str,
    player: str,
    match_type: str,
    max_matches: int,
    rps: int,
    with_highlight_events: bool = True,
    with_aliases: bool = True,
    delta: bool = False,
    timeout_seconds: int = 180,
    repo_root: Path | None = None,
) -> tuple[bool, str]:
    """Rafraîchit une DB SPNKr en appelant scripts/spnkr_import_db.py.

    Retourne (ok, message) pour affichage UI.
    
    Args:
        db_path: Chemin vers la DB cible.
        player: Gamertag ou XUID du joueur.
        match_type: Type de matchs (all, matchmaking, custom, local).
        max_matches: Nombre maximum de matchs à récupérer.
        rps: Requêtes par seconde.
        with_highlight_events: Activer les highlight events (défaut: True).
        with_aliases: Activer le refresh des aliases (défaut: True).
        delta: Mode delta - s'arrête dès qu'un match connu est rencontré (défaut: False).
        timeout_seconds: Timeout en secondes (défaut: 180).
        repo_root: Racine du repo (déduit automatiquement si None).
        
    Returns:
        Tuple (succès, message).
    """
    if repo_root is None:
        repo_root = Path(__file__).resolve().parent.parent.parent
    importer = repo_root / "scripts" / "spnkr_import_db.py"
    if not importer.exists():
        return False, f"Script introuvable: {importer}"

    p = (player or "").strip()
    if not p:
        return False, "Aucun joueur pour SPNKr (gamertag ou XUID)."

    mt = (match_type or "matchmaking").strip().lower()
    if mt not in {"all", "matchmaking", "custom", "local"}:
        mt = "matchmaking"

    target = str(db_path)
    # IMPORTANT: on n'écrit jamais directement dans la DB cible.
    # Si l'import crashe/timeout, SQLite peut laisser un fichier vide/corrompu.
    tmp = f"{target}.tmp.{uuid.uuid4().hex}.db"
    
    # Pour le mode delta: copier la DB existante vers tmp pour que --resume
    # trouve les matchs déjà connus (sinon existing_match_ids serait vide)
    if delta and os.path.exists(target):
        import shutil
        try:
            shutil.copy2(target, tmp)
        except Exception as e:
            return False, f"Impossible de copier la DB pour mode delta: {e}"

    cmd = [
        sys.executable,
        str(importer),
        "--out-db",
        str(tmp),
        "--player",
        p,
        "--match-type",
        mt,
        "--max-matches",
        str(int(max_matches)),
        "--requests-per-second",
        str(int(rps)),
        "--resume",
    ]
    # Highlight events et aliases sont activés par défaut côté import
    # On n'ajoute les flags --no-* que si explicitement désactivés
    if not with_highlight_events:
        cmd.append("--no-highlight-events")
    if not with_aliases:
        cmd.append("--no-aliases")
    # Mode delta: arrêt dès match connu (sync rapide)
    if delta:
        cmd.append("--delta")

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=int(timeout_seconds),
        )
    except subprocess.TimeoutExpired:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        return False, f"Timeout après {timeout_seconds}s (import SPNKr trop long)."
    except Exception as e:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        return False, f"Erreur au lancement de l'import SPNKr: {e}"

    if int(proc.returncode) != 0:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        tail = (proc.stderr or proc.stdout or "").strip()
        if len(tail) > 1200:
            tail = tail[-1200:]
        return False, f"Import SPNKr en échec (code={proc.returncode}).\n{tail}".strip()

    # Remplace la DB cible uniquement si le tmp semble valide (non vide).
    try:
        if not os.path.exists(tmp) or os.path.getsize(tmp) <= 0:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass
            return False, "Import SPNKr terminé mais DB temporaire vide (annulé)."
        os.makedirs(str(Path(target).resolve().parent), exist_ok=True)
        os.replace(tmp, target)
    except Exception as e:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        return False, f"Import SPNKr OK mais remplacement de la DB a échoué: {e}"

    return True, "DB SPNKr rafraîchie."
