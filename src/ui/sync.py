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
    """Vérifie si un chemin correspond à une base SPNKr ou fusionnée multi-joueurs."""
    try:
        p = Path(db_path)
        if p.suffix.lower() != ".db":
            return False
        # DB SPNKr classique (spnkr_*.db)
        if p.name.lower().startswith("spnkr"):
            return True
        # DB fusionnée (halo_*.db ou autre avec table Players)
        if p.name.lower().startswith("halo"):
            return True
        return False
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
    _ = meta.get("total_matches", 0)  # noqa: F841 - Pour usage futur

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
            time_str = "il y a 1 jour" if days == 1 else f"il y a {days} jours"

        _ = f"{indicator} Sync {time_str}"  # noqa: F841 - Pour usage futur
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

            _ = f"{indicator} Modifié {time_str}"  # noqa: F841 - Pour usage futur
        except Exception:
            pass  # Sync inconnue

    # Affichage compact
    # match_info = f"({total_matches} matchs)" if total_matches > 0 else ""
    # st.markdown(
    #     f"<div style='font-size: 0.85em; color: #888; margin: 4px 0 8px 0;'>"
    #     f"{sync_text} {match_info}</div>",
    #     unsafe_allow_html=True,
    # )


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

    Écrit directement dans la DB cible avec --resume (pas de copie temporaire).

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

    # Écriture directe dans la DB avec --resume (pas de copie temporaire)
    # Le script gère déjà l'ajout incrémental sans supprimer les données existantes
    cmd = [
        sys.executable,
        str(importer),
        "--out-db",
        target,
        "--player",
        p,
        "--match-type",
        mt,
        "--max-matches",
        str(int(max_matches)),
        "--requests-per-second",
        str(int(rps)),
        "--resume",  # Crucial: ne pas supprimer les données existantes
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
        return False, f"Timeout après {timeout_seconds}s (import SPNKr trop long)."
    except Exception as e:
        return False, f"Erreur au lancement de l'import SPNKr: {e}"

    if int(proc.returncode) != 0:
        tail = (proc.stderr or proc.stdout or "").strip()
        if len(tail) > 1200:
            tail = tail[-1200:]
        return False, f"Import SPNKr en échec (code={proc.returncode}).\n{tail}".strip()

    # Sync réussie
    return True, f"Sync OK pour {p}"


def sync_all_players(
    *,
    db_path: str,
    match_type: str = "matchmaking",
    max_matches: int = 200,
    rps: int = 5,
    with_highlight_events: bool = True,
    with_aliases: bool = True,
    delta: bool = True,
    timeout_seconds: int = 120,
) -> tuple[bool, str]:
    """Synchronise tous les joueurs d'une DB fusionnée (table Players).

    Si la DB n'a pas de table Players, tente de déduire le joueur depuis le nom.

    Returns:
        Tuple (succès_global, message_résumé).
    """
    from src.db import get_players_from_db, infer_spnkr_player_from_db_path

    players = get_players_from_db(db_path)

    if not players:
        # Fallback: DB mono-joueur, on déduit depuis le nom
        single_player = infer_spnkr_player_from_db_path(db_path) or ""
        if not single_player:
            return False, "Aucun joueur trouvé dans la DB."
        players = [{"xuid": "", "gamertag": single_player, "label": single_player}]

    results: list[tuple[str, bool, str]] = []

    for p in players:
        # Utiliser XUID si disponible, sinon gamertag
        player_id = str(p.get("xuid") or p.get("gamertag") or "").strip()
        player_label = str(p.get("label") or p.get("gamertag") or player_id).strip()

        if not player_id:
            continue

        ok, msg = refresh_spnkr_db_via_api(
            db_path=db_path,
            player=player_id,
            match_type=match_type,
            max_matches=max_matches,
            rps=rps,
            with_highlight_events=with_highlight_events,
            with_aliases=with_aliases,
            delta=delta,
            timeout_seconds=timeout_seconds,
        )
        results.append((player_label, ok, msg))

    if not results:
        return False, "Aucun joueur à synchroniser."

    # Résumé
    success_count = sum(1 for _, ok, _ in results if ok)
    total = len(results)

    if success_count == total:
        return (
            True,
            f"✅ {total} joueur{'s' if total > 1 else ''} synchronisé{'s' if total > 1 else ''}.",
        )
    elif success_count > 0:
        failed = [label for label, ok, _ in results if not ok]
        return True, f"⚠️ {success_count}/{total} OK. Échec: {', '.join(failed)}"
    else:
        errors = [f"{label}: {msg}" for label, ok, msg in results if not ok]
        return False, "❌ Échec pour tous les joueurs.\n" + "\n".join(errors[:3])


# =============================================================================
# Fonctions de synchronisation DuckDB (nouveau pipeline)
# =============================================================================


def get_player_duckdb_path(gamertag: str, repo_root: Path | None = None) -> Path | None:
    """Retourne le chemin vers stats.duckdb d'un joueur si existant.

    Args:
        gamertag: Gamertag du joueur.
        repo_root: Racine du repo (déduit automatiquement si None).

    Returns:
        Path vers stats.duckdb ou None si non trouvé.
    """
    if repo_root is None:
        repo_root = Path(__file__).resolve().parent.parent.parent

    player_dir = repo_root / "data" / "players" / gamertag
    stats_db = player_dir / "stats.duckdb"

    if stats_db.exists():
        return stats_db
    return None


def is_duckdb_player(gamertag: str, repo_root: Path | None = None) -> bool:
    """Vérifie si un joueur utilise l'architecture DuckDB v4.

    Args:
        gamertag: Gamertag du joueur.
        repo_root: Racine du repo.

    Returns:
        True si le joueur a une DB DuckDB.
    """
    return get_player_duckdb_path(gamertag, repo_root) is not None


async def sync_player_duckdb_async(
    gamertag: str,
    xuid: str,
    *,
    delta: bool = True,
    match_type: str = "matchmaking",
    max_matches: int = 200,
    with_highlight_events: bool = True,
    with_skill: bool = True,
    with_aliases: bool = True,
    repo_root: Path | None = None,
) -> tuple[bool, str]:
    """Synchronise un joueur via le nouveau pipeline DuckDB (async).

    Args:
        gamertag: Gamertag du joueur.
        xuid: XUID du joueur.
        delta: Mode delta (True) ou full (False).
        match_type: Type de matchs.
        max_matches: Nombre max de matchs.
        with_highlight_events: Récupérer les highlight events.
        with_skill: Récupérer les stats skill/MMR.
        with_aliases: Mettre à jour les aliases.
        repo_root: Racine du repo.

    Returns:
        Tuple (success, message).
    """
    if repo_root is None:
        repo_root = Path(__file__).resolve().parent.parent.parent

    player_db_path = get_player_duckdb_path(gamertag, repo_root)
    if player_db_path is None:
        return False, f"DB DuckDB non trouvée pour {gamertag}"

    try:
        from src.data.sync import DuckDBSyncEngine, SyncOptions

        engine = DuckDBSyncEngine(
            player_db_path=player_db_path,
            xuid=xuid,
            gamertag=gamertag,
        )

        options = SyncOptions(
            match_type=match_type,
            max_matches=max_matches,
            with_highlight_events=with_highlight_events,
            with_skill=with_skill,
            with_aliases=with_aliases,
        )

        if delta:
            result = await engine.sync_delta(options)
        else:
            result = await engine.sync_full(options)

        engine.close()

        return result.success, result.to_message()

    except Exception as e:
        return False, f"Erreur sync DuckDB: {e}"


def sync_player_duckdb(
    gamertag: str,
    xuid: str,
    *,
    delta: bool = True,
    match_type: str = "matchmaking",
    max_matches: int = 200,
    with_highlight_events: bool = True,
    with_skill: bool = True,
    with_aliases: bool = True,
    repo_root: Path | None = None,
) -> tuple[bool, str]:
    """Synchronise un joueur via le nouveau pipeline DuckDB (sync wrapper).

    Wrapper synchrone autour de sync_player_duckdb_async().

    Args:
        gamertag: Gamertag du joueur.
        xuid: XUID du joueur.
        delta: Mode delta (True) ou full (False).
        match_type: Type de matchs.
        max_matches: Nombre max de matchs.
        with_highlight_events: Récupérer les highlight events.
        with_skill: Récupérer les stats skill/MMR.
        with_aliases: Mettre à jour les aliases.
        repo_root: Racine du repo.

    Returns:
        Tuple (success, message).
    """
    import asyncio

    return asyncio.run(
        sync_player_duckdb_async(
            gamertag=gamertag,
            xuid=xuid,
            delta=delta,
            match_type=match_type,
            max_matches=max_matches,
            with_highlight_events=with_highlight_events,
            with_skill=with_skill,
            with_aliases=with_aliases,
            repo_root=repo_root,
        )
    )


def sync_player_auto(
    gamertag: str,
    xuid: str,
    *,
    db_path: str | None = None,
    delta: bool = True,
    match_type: str = "matchmaking",
    max_matches: int = 200,
    with_highlight_events: bool = True,
    with_aliases: bool = True,
    timeout_seconds: int = 300,
    repo_root: Path | None = None,
) -> tuple[bool, str]:
    """Synchronise un joueur en détectant automatiquement le mode.

    Utilise DuckDB si le joueur a une DB v4, sinon fallback sur SPNKr legacy.

    Args:
        gamertag: Gamertag du joueur.
        xuid: XUID du joueur.
        db_path: Chemin DB legacy (pour fallback).
        delta: Mode delta (True) ou full (False).
        match_type: Type de matchs.
        max_matches: Nombre max de matchs.
        with_highlight_events: Récupérer les highlight events.
        with_aliases: Mettre à jour les aliases.
        timeout_seconds: Timeout pour le mode legacy.
        repo_root: Racine du repo.

    Returns:
        Tuple (success, message).
    """
    # Priorité 1: DuckDB v4
    if is_duckdb_player(gamertag, repo_root):
        return sync_player_duckdb(
            gamertag=gamertag,
            xuid=xuid,
            delta=delta,
            match_type=match_type,
            max_matches=max_matches,
            with_highlight_events=with_highlight_events,
            with_skill=True,
            with_aliases=with_aliases,
            repo_root=repo_root,
        )

    # Fallback: SPNKr legacy
    if db_path:
        return refresh_spnkr_db_via_api(
            db_path=db_path,
            player=xuid or gamertag,
            match_type=match_type,
            max_matches=max_matches,
            rps=5,
            with_highlight_events=with_highlight_events,
            with_aliases=with_aliases,
            delta=delta,
            timeout_seconds=timeout_seconds,
            repo_root=repo_root,
        )

    return False, f"Aucune DB trouvée pour {gamertag}"
