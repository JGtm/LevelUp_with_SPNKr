#!/usr/bin/env python3
"""Script de synchronisation unifié.

Point d'entrée unique pour toutes les opérations de synchronisation :
- Import des matchs via SPNKr
- Reconstruction du cache (MatchCache)
- Téléchargement des assets (médailles, maps)
- Application des index
- Backfill des données manquantes

IMPORTANT: Toutes les données sont toujours récupérées pour chaque match :
- Stats de base (kills, deaths, assists, KDA, etc.)
- Médailles
- Personal scores
- Score de performance
- Highlight events (kills/deaths depuis les films)
- Skill/MMR (données de skill par match)
- Aliases XUID → Gamertag

Usage:
    python scripts/sync.py --help
    python scripts/sync.py --delta                    # Sync incrémentale
    python scripts/sync.py --full                     # Sync complète
    python scripts/sync.py --rebuild-cache            # Reconstruit MatchCache
    python scripts/sync.py --apply-indexes            # Applique les index optimisés
    python scripts/sync.py --delta --with-assets      # Sync + assets
    python scripts/sync.py --delta --player JGtm --with-backfill  # Sync + backfill complet
    python scripts/sync.py --delta --player JGtm --backfill-performance-scores  # Sync + scores performance
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.config import get_default_db_path  # noqa: E402
from src.ui.multiplayer import DuckDBPlayerInfo, list_duckdb_v4_players  # noqa: E402


class SQLiteForbiddenError(Exception):
    """Exception levée quand on tente d'utiliser SQLite (interdit)."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        super().__init__(f"SQLite interdit – utilisez DuckDB v4: {db_path}")


# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# =============================================================================
# Helpers
# =============================================================================


def _get_iso_now() -> str:
    """Retourne le timestamp ISO 8601 actuel (UTC)."""
    return datetime.now(timezone.utc).isoformat()


def _normalize_player_key(s: str) -> str:
    """Normalise un identifiant joueur pour comparaison."""
    return (s or "").strip().lower()


def _get_project_db_path():
    """Retourne le chemin de DB à utiliser pour le projet.

    Aligné sur le bouton Actualiser de la sidebar (sync_all_players_duckdb).
    Priorité :
    1. Si db_profiles.json existe et contient des profils → liste des joueurs depuis ce fichier.
    2. Sinon si data/players/*/stats.duckdb existe (DuckDB v4) → liste depuis le disque.
    3. Sinon retourne (get_default_db_path(), []).

    Returns:
        Tuple (db_path ou None, liste des DuckDBPlayerInfo si mode DuckDB v4).
    """
    import json

    db_profiles_path = REPO_ROOT / "db_profiles.json"
    if db_profiles_path.exists():
        try:
            with open(db_profiles_path, encoding="utf-8") as f:
                data = json.load(f)
            profiles = data.get("profiles", {})
            if profiles:
                duckdb_players: list[DuckDBPlayerInfo] = []
                for gamertag, profile in profiles.items():
                    if not isinstance(profile, dict):
                        continue
                    raw_path = profile.get("db_path", "").strip()
                    if raw_path:
                        db_path = (REPO_ROOT / raw_path).resolve()
                    else:
                        db_path = (
                            REPO_ROOT / "data" / "players" / gamertag / "stats.duckdb"
                        ).resolve()
                    if not db_path.exists():
                        continue
                    xuid = profile.get("xuid") or None
                    if isinstance(xuid, str) and not xuid.strip():
                        xuid = None
                    duckdb_players.append(
                        DuckDBPlayerInfo(
                            gamertag=gamertag,
                            db_path=db_path,
                            total_matches=0,
                            xuid=xuid,
                        )
                    )
                if duckdb_players:
                    return None, duckdb_players
        except (json.JSONDecodeError, OSError):
            pass

    duckdb_players = list_duckdb_v4_players()
    if duckdb_players:
        return None, duckdb_players
    legacy_path = get_default_db_path()
    return legacy_path, []


def _resolve_player_in_db(db_path: str, player_query: str) -> tuple[str, str | None, str | None]:
    """Résout un joueur (xuid/gamertag/label) en identifiant utilisable par SPNKr.

    Args:
        db_path: Chemin de la base (souvent la DB unifiée).
        player_query: XUID (digits) ou nom (gamertag/label).

    Returns:
        (player_id, resolved_xuid, display_label)

        - player_id: identifiant à passer à SPNKr (xuid si dispo, sinon gamertag).
        - resolved_xuid: xuid si trouvé dans la table Players.
        - display_label: label humain pour logs.
    """
    q = _normalize_player_key(player_query)
    if not q:
        return "", None, None

    # Si l'utilisateur donne directement un XUID, on n'a pas besoin de lookup.
    if q.isdigit():
        cleaned = player_query.strip()
        return cleaned, cleaned, cleaned

    # Essayer d'abord depuis db_profiles.json (pour DuckDB v4)
    xuid_from_profiles = _get_xuid_for_gamertag(player_query)
    if xuid_from_profiles:
        return xuid_from_profiles, xuid_from_profiles, player_query.strip()

    # Essayer depuis la DB DuckDB du joueur si elle existe (pour DuckDB v4)
    player_db_path = REPO_ROOT / "data" / "players" / player_query / "stats.duckdb"
    if player_db_path.exists():
        try:
            import duckdb

            conn = duckdb.connect(str(player_db_path), read_only=True)
            # Chercher dans xuid_aliases
            result = conn.execute(
                "SELECT xuid FROM xuid_aliases WHERE LOWER(gamertag) = LOWER(?) LIMIT 1",
                [player_query],
            ).fetchone()
            conn.close()
            if result and result[0]:
                xuid = str(result[0]).strip()
                return xuid, xuid, player_query.strip()
        except Exception:
            pass

    # SQLite legacy supprimé - plus de get_players_from_db

    # Fallback: considérer la query comme un gamertag (ou autre identifiant SPNKr).
    return player_query.strip(), None, player_query.strip()


def _refuse_sqlite_path(db_path: str) -> None:
    """Refuse les chemins .db (SQLite). Lève SQLiteForbiddenError si applicable."""
    if db_path and db_path.strip().lower().endswith(".db"):
        raise SQLiteForbiddenError(db_path)


# =============================================================================
# Opérations de synchronisation
# =============================================================================


def _is_duckdb_path(db_path: str) -> bool:
    """Indique si le chemin pointe vers une base DuckDB (v4)."""
    return (db_path or "").endswith(".duckdb")


def apply_indexes(db_path: str) -> tuple[bool, str]:
    """Applique les index optimisés sur la base de données.

    DuckDB uniquement. Pour les fichiers .duckdb, les index sont gérés automatiquement.
    Refuse les chemins .db (SQLite).
    """
    _refuse_sqlite_path(db_path)
    if _is_duckdb_path(db_path):
        logger.info("Application des index: ignoré (DuckDB v4 gère ses propres index).")
        return True, "DuckDB: ignoré"
    return True, "OK"


def ensure_cache_tables(db_path: str) -> tuple[bool, str]:
    """Crée les tables de cache si elles n'existent pas.

    DuckDB v4 n'utilise pas ce cache (MatchCache). Refuse les chemins .db (SQLite).
    """
    _refuse_sqlite_path(db_path)
    if _is_duckdb_path(db_path):
        logger.info("Tables de cache: ignoré (DuckDB v4 n'utilise pas ce cache).")
        return True, "DuckDB: ignoré"
    return True, "OK"


def rebuild_match_cache(db_path: str, xuid: str | None = None) -> tuple[bool, str]:
    """Reconstruit le cache MatchCache depuis MatchStats.

    DuckDB v4 n'utilise pas MatchCache. Refuse les chemins .db (SQLite).
    """
    _refuse_sqlite_path(db_path)
    if _is_duckdb_path(db_path):
        logger.info("Rebuild cache: ignoré (DuckDB v4 n'utilise pas MatchCache).")
        return True, "DuckDB: ignoré"

    # Chemin ni .duckdb ni .db : refuser (seul DuckDB supporté)
    raise ValueError(
        f"Seuls les fichiers .duckdb sont supportés. Reçu: {db_path}. "
        "Migrez avec scripts/migrate_player_to_duckdb.py"
    )


def rebuild_teammates_aggregate(db_path: str) -> tuple[bool, str]:
    """Reconstruit la table TeammatesAggregate depuis MatchStats.

    DuckDB v4 n'utilise pas TeammatesAggregate (table legacy). Refuse .db (SQLite).
    """
    _refuse_sqlite_path(db_path)
    if _is_duckdb_path(db_path):
        return True, "DuckDB: ignoré (n'utilise pas TeammatesAggregate)"
    return False, "Seuls les fichiers .duckdb sont supportés"


def refresh_duckdb_materialized_views(gamertag: str | None = None) -> tuple[bool, str]:
    """Rafraîchit les vues matérialisées DuckDB après synchronisation.

    Détecte automatiquement si le joueur a une DB DuckDB et rafraîchit
    les vues matérialisées (mv_map_stats, mv_mode_category_stats, etc.).

    Args:
        gamertag: Gamertag du joueur (optionnel, None = tous les joueurs).

    Returns:
        Tuple (success, message).
    """
    try:
        from src.data.repositories.duckdb_repo import DuckDBRepository

        # Chercher les DB DuckDB des joueurs
        data_dir = REPO_ROOT / "data" / "players"
        if not data_dir.exists():
            return True, "Pas de dossier data/players (architecture legacy)"

        players_refreshed = 0
        total_rows = {}

        if gamertag:
            # Un seul joueur
            player_dirs = [data_dir / gamertag]
        else:
            # Tous les joueurs
            player_dirs = [d for d in data_dir.iterdir() if d.is_dir()]

        for player_dir in player_dirs:
            stats_db = player_dir / "stats.duckdb"
            if not stats_db.exists():
                continue

            # Lire le XUID depuis db_profiles.json ou metadata
            gt = player_dir.name
            xuid = _get_xuid_for_gamertag(gt)
            if not xuid:
                logger.warning(f"XUID non trouvé pour {gt}, skip refresh MV")
                continue

            try:
                repo = DuckDBRepository(
                    player_db_path=stats_db,
                    xuid=xuid,
                    gamertag=gt,
                    read_only=False,
                )
                results = repo.refresh_materialized_views()
                repo.close()

                players_refreshed += 1
                for table, count in results.items():
                    total_rows[table] = total_rows.get(table, 0) + count

                logger.info(f"  Vues matérialisées rafraîchies pour {gt}: {results}")
            except Exception as e:
                logger.warning(f"Erreur refresh MV pour {gt}: {e}")

        if players_refreshed == 0:
            return True, "Aucune DB DuckDB trouvée à rafraîchir"

        msg = f"Vues matérialisées rafraîchies: {players_refreshed} joueur(s), {total_rows}"
        return True, msg

    except ImportError as e:
        return True, f"DuckDB non disponible: {e}"
    except Exception as e:
        return False, f"Erreur refresh vues matérialisées: {e}"


def _get_xuid_for_gamertag(gamertag: str) -> str | None:
    """Récupère le XUID d'un joueur depuis db_profiles.json."""
    import json

    profiles_path = REPO_ROOT / "db_profiles.json"
    if not profiles_path.exists():
        return None

    try:
        with open(profiles_path) as f:
            data = json.load(f)

        # db_profiles.json a la structure: {"profiles": {"JGtm": {"xuid": "...", ...}}}
        profiles_dict = data.get("profiles", {})
        if not isinstance(profiles_dict, dict):
            return None

        # Chercher directement par clé (gamertag)
        gamertag_lower = gamertag.lower()
        for key, profile in profiles_dict.items():
            if isinstance(profile, dict):
                # Vérifier si la clé correspond
                if key.lower() == gamertag_lower:
                    return profile.get("xuid")
                # Vérifier dans les valeurs du profil
                if profile.get("gamertag", "").lower() == gamertag_lower:
                    return profile.get("xuid")
                if profile.get("waypoint_player", "").lower() == gamertag_lower:
                    return profile.get("xuid")

        return None
    except Exception:
        return None


def _get_profile_for_gamertag(gamertag: str) -> dict | None:
    """Retourne le profil brut db_profiles.json pour un gamertag (case-insensitive)."""
    import json

    profiles_path = REPO_ROOT / "db_profiles.json"
    if not profiles_path.exists():
        return None

    try:
        with open(profiles_path, encoding="utf-8") as f:
            data = json.load(f)

        profiles_dict = data.get("profiles", {})
        if not isinstance(profiles_dict, dict):
            return None

        gamertag_lower = gamertag.lower()
        for key, profile in profiles_dict.items():
            if not isinstance(profile, dict):
                continue
            if key.lower() == gamertag_lower:
                return profile
            if str(profile.get("gamertag", "")).lower() == gamertag_lower:
                return profile
            if str(profile.get("waypoint_player", "")).lower() == gamertag_lower:
                return profile

        return None
    except Exception:
        return None


def _load_db_profiles_json() -> dict:
    """Charge db_profiles.json ou retourne un squelette par défaut."""
    import json

    profiles_path = REPO_ROOT / "db_profiles.json"
    if not profiles_path.exists():
        return {
            "version": "2.1",
            "warehouse_path": "data/warehouse",
            "metadata_db": "data/warehouse/metadata.duckdb",
            "profiles": {},
        }

    with open(profiles_path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("db_profiles.json invalide (root non-objet)")
    if not isinstance(data.get("profiles", {}), dict):
        data["profiles"] = {}
    return data


def _save_db_profiles_json(data: dict) -> None:
    """Écrit db_profiles.json de façon déterministe (UTF-8, indent)."""
    import json

    profiles_path = REPO_ROOT / "db_profiles.json"
    with open(profiles_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _find_profile_key_case_insensitive(profiles_dict: dict, key: str) -> str | None:
    """Retourne la clé existante correspondant à key (case-insensitive)."""
    target = _normalize_player_key(key)
    if not target:
        return None
    for k in profiles_dict:
        if _normalize_player_key(str(k)) == target:
            return str(k)
    return None


def _run_async(coro, *, timeout_seconds: int = 20):
    """Exécute un coroutine en contexte sync (CLI).

    Sur certains environnements (ex: si déjà dans une boucle), on bascule
    sur un thread.
    """
    import asyncio
    import concurrent.futures

    try:
        return asyncio.run(coro)
    except RuntimeError as e:
        msg = str(e)
        if "asyncio.run() cannot be called" not in msg:
            raise
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(lambda: asyncio.run(coro))
            return fut.result(timeout=float(timeout_seconds) + 30.0)


def _resolve_gamertag_from_xuid_via_spnkr(xuid: str) -> str | None:
    """Résout un XUID vers un gamertag via SPNKr (si tokens disponibles)."""

    async def _run() -> str | None:
        try:
            from src.data.sync.api_client import SPNKrAPIClient
        except ImportError:
            return None

        x = str(xuid or "").strip()
        if not x.isdigit():
            return None

        async with SPNKrAPIClient(requests_per_second=2) as api_client:
            resp = await api_client.client.profile.get_users_by_id([x])
            users = resp.data if hasattr(resp, "data") else await resp.parse()
            if not users:
                return None
            user = users[0]
            gt = str(getattr(user, "gamertag", "") or "").strip()
            return gt or None

    try:
        return _run_async(_run(), timeout_seconds=20)
    except Exception:
        return None


def add_player_profile(player_input: str) -> tuple[str, str | None]:
    """Ajoute/MAJ un joueur dans db_profiles.json.

    Args:
        player_input: Gamertag ou XUID.

    Returns:
        (profile_key, xuid)
        - profile_key: clé utilisée dans db_profiles.json (gamertag canonique si résolu, sinon input)
        - xuid: xuid résolu si dispo
    """
    raw = str(player_input or "").strip()
    if not raw:
        raise ValueError("--add-player: valeur vide")

    # Rejeter les valeurs invalides (MagicMock, caractères spéciaux, etc.)
    import re

    if "MagicMock" in raw or not re.match(r"^[\w\s\-]{1,50}$", raw):
        raise ValueError(
            f"--add-player: valeur invalide '{raw[:60]}'. "
            "Attendu : un gamertag alphanumérique ou un XUID numérique."
        )

    xuid: str | None = None
    canonical_key: str | None = None

    if raw.isdigit():
        xuid = raw
        canonical_key = _resolve_gamertag_from_xuid_via_spnkr(xuid) or raw
    else:
        # Résolution gamertag -> xuid via SPNKr (meilleur effort)
        try:
            from src.ui.profile_api import fetch_xuid_via_spnkr

            xuid_resolved, canonical_gt = fetch_xuid_via_spnkr(gamertag=raw)
            xuid = str(xuid_resolved or "").strip() or None
            canonical_key = str(canonical_gt or "").strip() or raw
        except Exception:
            # On accepte quand même l'ajout (mais le pipeline DuckDB pourra fallback legacy)
            canonical_key = raw
            xuid = None

    canonical_key = str(canonical_key or raw).strip()
    if not canonical_key:
        raise ValueError("Impossible de déterminer un identifiant joueur")

    data = _load_db_profiles_json()
    profiles = data.setdefault("profiles", {})
    if not isinstance(profiles, dict):
        raise ValueError("db_profiles.json invalide: profiles n'est pas un objet")

    existing_key = _find_profile_key_case_insensitive(profiles, canonical_key)
    final_key = existing_key or canonical_key
    existing_profile = profiles.get(final_key) if isinstance(profiles.get(final_key), dict) else {}

    default_db_path = f"data/players/{final_key}/stats.duckdb"
    db_path = str(existing_profile.get("db_path") or "").strip() or default_db_path

    new_profile = {
        **(existing_profile if isinstance(existing_profile, dict) else {}),
        "db_path": db_path,
        "waypoint_player": str(existing_profile.get("waypoint_player") or canonical_key).strip()
        or canonical_key,
    }
    if xuid:
        new_profile["xuid"] = xuid
    else:
        # Ne pas écraser un xuid existant avec du vide
        if "xuid" not in new_profile:
            new_profile["xuid"] = ""

    profiles[final_key] = new_profile
    _save_db_profiles_json(data)

    # Créer le dossier joueur + un fichier stats.duckdb vide.
    # (Le pipeline DuckDB et src.ui.sync.sync_player_duckdb exigent que le fichier existe.)
    try:
        player_dir = REPO_ROOT / "data" / "players" / final_key
        player_dir.mkdir(parents=True, exist_ok=True)
        db_file = player_dir / "stats.duckdb"
        if not db_file.exists():
            try:
                import duckdb

                conn = duckdb.connect(str(db_file))
                conn.close()
            except Exception:
                # Fallback minimal: créer le fichier pour satisfaire les checks d'existence.
                db_file.touch(exist_ok=True)
    except Exception:
        pass

    return final_key, xuid


def rebuild_medals_aggregate(db_path: str) -> tuple[bool, str]:
    """Reconstruit la table MedalsAggregate depuis MatchStats.

    DuckDB v4 n'utilise pas MedalsAggregate (table legacy). Refuse .db (SQLite).
    """
    _refuse_sqlite_path(db_path)
    if _is_duckdb_path(db_path):
        return True, "DuckDB: ignoré (n'utilise pas MedalsAggregate)"
    return False, "Seuls les fichiers .duckdb sont supportés"


def sync_delta(
    db_path: str,
    *,
    player: str | None = None,
    match_type: str = "matchmaking",
    max_matches: int = 200,
    with_highlight_events: bool = True,
    with_aliases: bool = True,
    force_duckdb: bool = False,
) -> tuple[bool, str]:
    """Effectue une synchronisation incrémentale via SPNKr.

    Utilise automatiquement le nouveau pipeline DuckDB (Sprint 4.7) si le joueur
    a une DB DuckDB v4. Sinon, fallback sur le pipeline legacy.

    IMPORTANT: Toutes les données sont toujours récupérées (highlights, skill, aliases, médailles).
    Les paramètres with_highlight_events et with_aliases sont conservés pour compatibilité
    mais sont toujours forcés à True.

    Args:
        db_path: Chemin vers la base de données.
        player: Joueur à synchroniser (gamertag ou XUID).
        match_type: Type de matchs à récupérer.
        max_matches: Nombre maximum de matchs.
        with_highlight_events: Ignoré (toujours True).
        with_aliases: Ignoré (toujours True).
        force_duckdb: Forcer l'utilisation du pipeline DuckDB.

    Returns:
        Tuple (success, message).
    """
    # Forcer la récupération de toutes les données
    with_highlight_events = True
    with_aliases = True

    logger.info("Synchronisation incrémentale (delta)...")

    # Essayer le nouveau pipeline DuckDB si applicable
    if player:
        duckdb_result = _try_sync_duckdb(
            player=player,
            db_path=db_path,
            delta=True,
            match_type=match_type,
            max_matches=max_matches,
            with_highlight_events=with_highlight_events,
            with_aliases=with_aliases,
            force=force_duckdb,
        )
        if duckdb_result is not None:
            return duckdb_result

    # Fallback: pipeline legacy
    try:
        from src.ui.sync import refresh_spnkr_db_via_api, sync_all_players

        resolved_xuid: str | None = None
        if player:
            player_id, resolved_xuid, display_label = _resolve_player_in_db(db_path, player)
            if not player_id:
                return False, "Aucun joueur fourni via --player."
            logger.info(f"Sync delta pour: {display_label or player_id}")
            ok, msg = refresh_spnkr_db_via_api(
                db_path=db_path,
                player=player_id,
                match_type=match_type,
                max_matches=max_matches,
                rps=5,
                with_highlight_events=with_highlight_events,
                with_aliases=with_aliases,
                delta=True,
                timeout_seconds=300,
            )
        else:
            ok, msg = sync_all_players(
                db_path=db_path,
                match_type=match_type,
                max_matches=max_matches,
                with_highlight_events=with_highlight_events,
                with_aliases=with_aliases,
                delta=True,
                timeout_seconds=300,
            )

        if ok:
            logger.info(msg)
            # Rebuild cache avec les nouvelles données
            cache_ok, cache_msg = rebuild_match_cache(db_path, xuid=resolved_xuid)
            if cache_ok:
                logger.info(f"Cache mis à jour: {cache_msg}")
            else:
                logger.warning(f"Cache non mis à jour: {cache_msg}")

            # Rafraîchir les vues matérialisées DuckDB (Sprint 4.1.6)
            if player:
                _, resolved_xuid, display_label = _resolve_player_in_db(db_path, player)
                gamertag_for_mv = display_label
            else:
                gamertag_for_mv = None
            mv_ok, mv_msg = refresh_duckdb_materialized_views(gamertag_for_mv)
            if mv_ok:
                logger.info(f"Vues matérialisées: {mv_msg}")
            else:
                logger.warning(f"Vues matérialisées: {mv_msg}")
        else:
            logger.error(msg)

        return ok, msg

    except ImportError as e:
        msg = f"SPNKr non disponible: {e}"
        logger.error(msg)
        return False, msg
    except Exception as e:
        msg = f"Erreur lors de la synchronisation: {e}"
        logger.error(msg)
        return False, msg


def _try_sync_duckdb(
    player: str,
    db_path: str,
    *,
    delta: bool,
    match_type: str,
    max_matches: int,
    with_highlight_events: bool,
    with_aliases: bool,
    force: bool = False,
) -> tuple[bool, str] | None:
    """Essaie de synchroniser via le nouveau pipeline DuckDB.

    Force toujours with_highlight_events=True, with_skill=True, with_aliases=True.

    Returns:
        Tuple (success, message) si DuckDB utilisé, None sinon.
    """
    # Forcer la récupération de toutes les données
    with_highlight_events = True
    with_aliases = True
    try:
        from src.ui.sync import is_duckdb_player, sync_player_duckdb

        # Résoudre le joueur
        player_id, resolved_xuid, display_label = _resolve_player_in_db(db_path, player)
        gamertag = display_label or player

        # Vérifier si le joueur a une DB DuckDB (ou au moins un profil v4)
        has_duckdb_profile = _get_profile_for_gamertag(gamertag) is not None
        if not force and not is_duckdb_player(gamertag) and not has_duckdb_profile:
            return None

        if not resolved_xuid:
            logger.warning(f"XUID non trouvé pour {gamertag}, fallback legacy")
            return None

        mode = "delta" if delta else "full"
        logger.info(f"[DuckDB] Sync {mode} pour {gamertag} via nouveau pipeline")

        ok, msg = sync_player_duckdb(
            gamertag=gamertag,
            xuid=resolved_xuid,
            delta=delta,
            match_type=match_type,
            max_matches=max_matches,
            with_highlight_events=with_highlight_events,
            with_skill=True,
            with_aliases=with_aliases,
        )

        if ok:
            logger.info(f"[DuckDB] {msg}")
        else:
            logger.error(f"[DuckDB] {msg}")

        return ok, msg

    except ImportError:
        # Module sync pas disponible, fallback legacy
        return None
    except Exception as e:
        logger.warning(f"[DuckDB] Erreur: {e}, fallback legacy")
        return None


def sync_full(
    db_path: str,
    *,
    player: str | None = None,
    match_type: str = "matchmaking",
    max_matches: int = 1000,
    with_highlight_events: bool = True,
    with_aliases: bool = True,
    force_duckdb: bool = False,
) -> tuple[bool, str]:
    """Effectue une synchronisation complète via SPNKr.

    Utilise automatiquement le nouveau pipeline DuckDB (Sprint 4.7) si le joueur
    a une DB DuckDB v4. Sinon, fallback sur le pipeline legacy.

    IMPORTANT: Toutes les données sont toujours récupérées (highlights, skill, aliases, médailles).
    Les paramètres with_highlight_events et with_aliases sont conservés pour compatibilité
    mais sont toujours forcés à True.

    Args:
        db_path: Chemin vers la base de données.
        player: Joueur à synchroniser (gamertag ou XUID).
        match_type: Type de matchs à récupérer.
        max_matches: Nombre maximum de matchs.
        with_highlight_events: Ignoré (toujours True).
        with_aliases: Ignoré (toujours True).
        force_duckdb: Forcer l'utilisation du pipeline DuckDB.

    Returns:
        Tuple (success, message).
    """
    # Forcer la récupération de toutes les données
    with_highlight_events = True
    with_aliases = True

    logger.info("Synchronisation complète...")

    # Essayer le nouveau pipeline DuckDB si applicable
    if player:
        duckdb_result = _try_sync_duckdb(
            player=player,
            db_path=db_path,
            delta=False,
            match_type=match_type,
            max_matches=max_matches,
            with_highlight_events=with_highlight_events,
            with_aliases=with_aliases,
            force=force_duckdb,
        )
        if duckdb_result is not None:
            return duckdb_result

    # Fallback: pipeline legacy
    try:
        from src.ui.sync import refresh_spnkr_db_via_api, sync_all_players

        resolved_xuid: str | None = None
        if player:
            player_id, resolved_xuid, display_label = _resolve_player_in_db(db_path, player)
            if not player_id:
                return False, "Aucun joueur fourni via --player."
            logger.info(f"Sync full pour: {display_label or player_id}")
            ok, msg = refresh_spnkr_db_via_api(
                db_path=db_path,
                player=player_id,
                match_type=match_type,
                max_matches=max_matches,
                rps=5,
                with_highlight_events=with_highlight_events,
                with_aliases=with_aliases,
                delta=False,
                timeout_seconds=600,
            )
        else:
            ok, msg = sync_all_players(
                db_path=db_path,
                match_type=match_type,
                max_matches=max_matches,
                with_highlight_events=with_highlight_events,
                with_aliases=with_aliases,
                delta=False,
                timeout_seconds=600,
            )

        if ok:
            logger.info(msg)
            # Rebuild cache avec les nouvelles données
            cache_ok, cache_msg = rebuild_match_cache(db_path, xuid=resolved_xuid)
            if cache_ok:
                logger.info(f"Cache mis à jour: {cache_msg}")
            else:
                logger.warning(f"Cache non mis à jour: {cache_msg}")

            # Rafraîchir les vues matérialisées DuckDB (Sprint 4.1.6)
            if player:
                _, resolved_xuid, display_label = _resolve_player_in_db(db_path, player)
                gamertag_for_mv = display_label
            else:
                gamertag_for_mv = None
            mv_ok, mv_msg = refresh_duckdb_materialized_views(gamertag_for_mv)
            if mv_ok:
                logger.info(f"Vues matérialisées: {mv_msg}")
            else:
                logger.warning(f"Vues matérialisées: {mv_msg}")
        else:
            logger.error(msg)

        return ok, msg

    except ImportError as e:
        msg = f"SPNKr non disponible: {e}"
        logger.error(msg)
        return False, msg
    except Exception as e:
        msg = f"Erreur lors de la synchronisation: {e}"
        logger.error(msg)
        return False, msg


def migrate_to_parquet(
    db_path: str,
    *,
    xuid: str | None = None,
    warehouse_path: str | None = None,
) -> tuple[bool, str]:
    """@deprecated Migration vers Parquet n'est plus nécessaire depuis v4.

    Depuis l'architecture v4, seul DuckDB est utilisé.
    Utilisez scripts/migrate_to_duckdb.py pour migrer depuis SQLite legacy.

    Args:
        db_path: Ignoré
        xuid: Ignoré
        warehouse_path: Ignoré

    Returns:
        Tuple (True, message d'avertissement).
    """
    msg = (
        "Migration Parquet dépréciée depuis v4. "
        "Utilisez scripts/migrate_to_duckdb.py pour migrer vers DuckDB."
    )
    logger.warning(msg)
    return True, msg


def download_assets(db_path: str) -> tuple[bool, str]:
    """Télécharge les assets manquants (médailles, maps).

    Args:
        db_path: Chemin vers la base de données.

    Returns:
        Tuple (success, message).
    """
    logger.info("Téléchargement des assets...")

    try:
        from src.ui.medals import download_missing_medal_icons

        # Télécharger les icônes de médailles manquantes
        downloaded = download_missing_medal_icons(db_path)

        msg = f"Assets téléchargés: {downloaded} médailles"
        logger.info(msg)
        return True, msg

    except ImportError as e:
        msg = f"Module assets non disponible: {e}"
        logger.warning(msg)
        return True, msg  # Non bloquant
    except Exception as e:
        msg = f"Erreur lors du téléchargement des assets: {e}"
        logger.error(msg)
        return False, msg


def print_stats(db_path: str, player: str | None = None) -> None:
    """Affiche les statistiques de la base de données.

    Si player est fourni et que c'est un joueur DuckDB v4, affiche les stats
    de sa DB spécifique au lieu de la DB unifiée.
    """
    # Détecter si c'est un joueur DuckDB v4
    actual_db_path = db_path

    if player:
        try:
            from src.ui.sync import get_player_duckdb_path

            duckdb_path = get_player_duckdb_path(player)
            if duckdb_path and duckdb_path.exists():
                actual_db_path = str(duckdb_path)
                logger.info(f"=== Statistiques DuckDB pour {player} ===")
            else:
                logger.info("=== Statistiques de la base de données ===")
        except ImportError:
            logger.info("=== Statistiques de la base de données ===")
    else:
        logger.info("=== Statistiques de la base de données ===")

    # Refuser SQLite (.db) - uniquement DuckDB supporté
    try:
        _refuse_sqlite_path(actual_db_path)
    except SQLiteForbiddenError as e:
        logger.error(str(e))
        return

    try:
        import duckdb

        conn = duckdb.connect(actual_db_path, read_only=True)

        tables = [
            ("match_stats", "Matchs"),
            ("player_match_stats", "Stats joueur"),
            ("highlight_events", "Highlight events"),
            ("xuid_aliases", "Alias XUID"),
            ("medals_earned", "Médailles"),
        ]

        for table, label in tables:
            try:
                result = conn.execute(
                    f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '{table}'"
                ).fetchone()
                if result and result[0] > 0:
                    count_result = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                    count = count_result[0] if count_result else 0
                    logger.info(f"  {label}: {count:,}")
                else:
                    logger.info(f"  {label}: (table absente)")
            except Exception:
                logger.info(f"  {label}: (erreur)")

        conn.close()

        # Taille du fichier
        size_mb = os.path.getsize(actual_db_path) / (1024 * 1024)
        logger.info(f"  Taille: {size_mb:.2f} MB")

    except Exception as e:
        logger.error(f"Erreur lors de la lecture des stats: {e}")


# =============================================================================
# Point d'entrée
# =============================================================================


def main() -> int:
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Script de synchronisation unifié pour OpenSpartan Graph\n\n"
        "IMPORTANT: Toutes les données sont toujours récupérées pour chaque match :\n"
        "  - Stats de base, medailles, personal scores, score de performance\n"
        "  - Highlight events, skill/MMR, aliases XUID -> Gamertag",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python scripts/sync.py --delta                    # Sync incrémentale
    python scripts/sync.py --delta --player Chocoboflor # Sync delta d'un seul joueur
    python scripts/sync.py --add-player JGtm          # Ajoute/MAJ un profil joueur (gamertag)
    python scripts/sync.py --add-player 2533...       # Ajoute/MAJ un profil joueur (XUID)
  python scripts/sync.py --full --max-matches 500   # Sync complète (500 matchs)
    python scripts/sync.py --full --player Madina97294 # Sync full d'un seul joueur
  python scripts/sync.py --rebuild-cache            # Reconstruit le cache
  python scripts/sync.py --apply-indexes            # Applique les index
  python scripts/sync.py --delta --with-assets      # Sync + téléchargement assets
  python scripts/sync.py --delta --player JGtm --with-backfill  # Sync + backfill complet (toutes données)
  python scripts/sync.py --delta --player JGtm --backfill-performance-scores  # Sync + calcul scores performance
  python scripts/sync.py --stats                    # Affiche les statistiques
        """,
    )

    # Base de données
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Chemin vers la base de données (défaut: auto-détection)",
    )

    parser.add_argument(
        "--player",
        type=str,
        default=None,
        help="Sync d'un seul joueur (XUID, gamertag ou label de la table Players)",
    )

    parser.add_argument(
        "--add-player",
        type=str,
        default=None,
        help="Ajoute/MAJ un profil dans db_profiles.json (accepte XUID ou gamertag)",
    )

    # Modes de synchronisation
    sync_group = parser.add_mutually_exclusive_group()
    sync_group.add_argument(
        "--delta",
        action="store_true",
        help="Synchronisation incrémentale (nouveaux matchs uniquement)",
    )
    sync_group.add_argument(
        "--full",
        action="store_true",
        help="Synchronisation complète",
    )

    # Options de sync
    parser.add_argument(
        "--match-type",
        type=str,
        default="matchmaking",
        choices=["matchmaking", "custom", "all"],
        help="Type de matchs à synchroniser",
    )
    parser.add_argument(
        "--max-matches",
        type=int,
        default=200,
        help="Nombre maximum de matchs à récupérer",
    )
    # Note: Les options --no-highlight-events et --no-aliases ont été supprimées.
    # Toutes les données (highlights, skill, aliases) sont maintenant toujours récupérées.

    # Opérations de maintenance
    parser.add_argument(
        "--rebuild-cache",
        action="store_true",
        help="Reconstruit le cache MatchCache",
    )
    parser.add_argument(
        "--apply-indexes",
        action="store_true",
        help="Applique les index optimisés",
    )
    parser.add_argument(
        "--with-assets",
        action="store_true",
        help="Télécharge les assets manquants",
    )
    parser.add_argument(
        "--with-backfill",
        action="store_true",
        help="Effectue un backfill complet des données manquantes après la synchronisation (toutes les données)",
    )
    parser.add_argument(
        "--backfill-performance-scores",
        action="store_true",
        help="Calcule les scores de performance manquants après la synchronisation",
    )
    parser.add_argument(
        "--migrate-parquet",
        action="store_true",
        help="Migre les données vers Parquet après synchronisation",
    )
    parser.add_argument(
        "--warehouse",
        type=str,
        default=None,
        help="Chemin vers le warehouse Parquet (défaut: data/warehouse)",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Affiche les statistiques de la DB",
    )

    # Verbosité
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Mode verbeux",
    )

    args = parser.parse_args()

    # Configuration du logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Ajout/MAJ de joueur (db_profiles.json)
    if args.add_player:
        try:
            profile_key, resolved_xuid = add_player_profile(args.add_player)
            logger.info(
                f"Profil joueur ajouté/MAJ: {profile_key}"
                + (f" (xuid={resolved_xuid})" if resolved_xuid else "")
            )

            if args.player and _normalize_player_key(args.player) != _normalize_player_key(
                profile_key
            ):
                logger.error(
                    f"Conflit: --player={args.player} et --add-player={args.add_player} ne pointent pas vers le même joueur"
                )
                return 1

            # Si on veut enchaîner un sync, on force --player sur la clé ajoutée.
            if not args.player:
                args.player = profile_key

            # Si pas de mode sync/maintenance demandé, on s'arrête ici.
            if not (
                args.delta
                or args.full
                or args.rebuild_cache
                or args.apply_indexes
                or args.stats
                or args.with_assets
                or args.with_backfill
                or args.backfill_performance_scores
                or args.migrate_parquet
            ):
                return 0
        except Exception as e:
            logger.error(f"Erreur --add-player: {e}")
            return 1

    # Déterminer le chemin de la DB (ou la liste des joueurs DuckDB v4)
    db_path = args.db
    duckdb_players = []
    if not db_path:
        db_path, duckdb_players = _get_project_db_path()
        # Si on a des joueurs DuckDB v4, on travaille avec eux
        if duckdb_players and not db_path:
            if args.player:
                # Un seul joueur demandé: prendre sa DB
                gt = args.player.strip()
                for p in duckdb_players:
                    if (p.gamertag or "").strip().lower() == gt.lower():
                        db_path = str(p.db_path)
                        break
                if not db_path:
                    # Joueur non trouvé dans la liste mais peut-être que le dossier existe
                    player_db = REPO_ROOT / "data" / "players" / gt / "stats.duckdb"
                    if player_db.exists():
                        db_path = str(player_db)
                if not db_path:
                    # Dernier fallback: profil présent dans db_profiles.json même si DB absente
                    profile = _get_profile_for_gamertag(gt)
                    if isinstance(profile, dict):
                        raw_path = str(profile.get("db_path", "")).strip()
                        if raw_path:
                            db_path = str((REPO_ROOT / raw_path).resolve())
                        else:
                            db_path = str(
                                (REPO_ROOT / "data" / "players" / gt / "stats.duckdb").resolve()
                            )
                if not db_path:
                    logger.error(f"Joueur DuckDB v4 introuvable: {args.player}")
                    return 1
            else:
                # Sync tous les joueurs DuckDB v4: on garde db_path à None pour l'instant
                pass

    if not db_path and not duckdb_players:
        db_path = get_default_db_path()

    if not db_path and not duckdb_players:
        logger.error(
            "Aucune base de données trouvée. "
            "Utilisez --db <chemin> ou assurez-vous que data/players/<gamertag>/stats.duckdb existe."
        )
        return 1

    # Mode "sync tous les joueurs DuckDB v4" (sans --player)
    if duckdb_players and not args.player and (args.delta or args.full):
        logger.info(f"Sync de {len(duckdb_players)} joueur(s) DuckDB v4")
        success = True
        for i, pinfo in enumerate(duckdb_players, 1):
            logger.info(f"[{i}/{len(duckdb_players)}] {pinfo.gamertag}")
            ok, msg = (
                sync_delta(
                    str(pinfo.db_path),
                    player=pinfo.gamertag,
                    match_type=args.match_type,
                    max_matches=args.max_matches,
                    with_highlight_events=True,
                    with_aliases=True,
                )
                if args.delta
                else sync_full(
                    str(pinfo.db_path),
                    player=pinfo.gamertag,
                    match_type=args.match_type,
                    max_matches=args.max_matches,
                    with_highlight_events=True,
                    with_aliases=True,
                )
            )
            if not ok:
                success = False
                logger.error(f"  {msg}")
            else:
                logger.info(f"  {msg}")
        if args.stats:
            for pinfo in duckdb_players:
                print_stats(str(pinfo.db_path), player=pinfo.gamertag)
        return 0 if success else 1

    if not db_path:
        # Stats seules pour tous les joueurs DuckDB v4
        if duckdb_players and args.stats:
            for pinfo in duckdb_players:
                print_stats(str(pinfo.db_path), player=pinfo.gamertag)
            return 0
        logger.error("Aucune base de données à utiliser.")
        return 1

    if not os.path.exists(db_path):
        can_bootstrap_player_db = bool(
            args.player and (args.delta or args.full) and db_path.lower().endswith(".duckdb")
        )
        if can_bootstrap_player_db:
            logger.info(f"Base joueur absente, initialisation au premier sync: {db_path}")
        else:
            logger.error(f"Base de données introuvable: {db_path}")
            return 1

    # Refuser SQLite (.db) - uniquement DuckDB supporté
    try:
        _refuse_sqlite_path(db_path)
    except SQLiteForbiddenError as e:
        logger.error(str(e))
        return 1

    logger.info(f"Base de données: {db_path}")

    # Exécuter les opérations demandées
    success = True

    # Statistiques seules
    if args.stats:
        print_stats(db_path, player=args.player)
        return 0

    # Vérifier/créer les tables de cache (ignoré pour DuckDB v4)
    ok, msg = ensure_cache_tables(db_path)
    if not ok:
        logger.error(msg)
        success = False

    # Appliquer les index (ignoré pour DuckDB v4)
    if args.apply_indexes or args.delta or args.full:
        ok, msg = apply_indexes(db_path)
        if not ok:
            success = False

    # Synchronisation
    # Toutes les données sont toujours récupérées (highlights, skill, aliases)
    if args.delta:
        ok, msg = sync_delta(
            db_path,
            player=args.player,
            match_type=args.match_type,
            max_matches=args.max_matches,
            with_highlight_events=True,  # Toujours activé
            with_aliases=True,  # Toujours activé
        )
        if not ok:
            success = False

    elif args.full:
        ok, msg = sync_full(
            db_path,
            player=args.player,
            match_type=args.match_type,
            max_matches=args.max_matches,
            with_highlight_events=True,  # Toujours activé
            with_aliases=True,  # Toujours activé
        )
        if not ok:
            success = False

    # Reconstruction du cache
    if args.rebuild_cache:
        resolved_xuid = None
        if args.player:
            _, resolved_xuid, display_label = _resolve_player_in_db(db_path, args.player)
            if resolved_xuid:
                logger.info(f"Rebuild cache ciblé pour: {display_label or resolved_xuid}")
        ok, msg = rebuild_match_cache(db_path, xuid=resolved_xuid)
        if not ok:
            success = False

    # Téléchargement des assets
    if args.with_assets:
        ok, msg = download_assets(db_path)
        if not ok:
            success = False

    # Backfill des données manquantes après sync
    if args.with_backfill or args.backfill_performance_scores:
        if not args.player:
            logger.warning(
                "--with-backfill nécessite --player. "
                "Utilisez scripts/backfill_data.py --all pour backfill tous les joueurs."
            )
        else:
            logger.info("Backfill des données manquantes après synchronisation...")
            try:
                import asyncio

                from scripts.backfill_data import backfill_player_data

                # Déterminer les options de backfill
                if args.with_backfill:
                    # Backfill complet (toutes les données)
                    backfill_kwargs = {
                        "dry_run": False,
                        "max_matches": None,
                        "requests_per_second": 5,
                        "all_data": True,
                    }
                else:
                    # Backfill uniquement les scores de performance
                    backfill_kwargs = {
                        "dry_run": False,
                        "max_matches": None,
                        "requests_per_second": 5,
                        "performance_scores": True,
                    }

                result = asyncio.run(backfill_player_data(args.player, **backfill_kwargs))

                logger.info("\n=== Résumé Backfill ===")
                logger.info(f"Matchs vérifiés: {result['matches_checked']}")
                logger.info(f"Matchs avec données manquantes: {result['matches_missing_data']}")
                if result.get("medals_inserted", 0) > 0:
                    logger.info(f"Médailles insérées: {result['medals_inserted']}")
                if result.get("events_inserted", 0) > 0:
                    logger.info(f"Events insérés: {result['events_inserted']}")
                if result.get("skill_inserted", 0) > 0:
                    logger.info(f"Skill inséré: {result['skill_inserted']}")
                if result.get("personal_scores_inserted", 0) > 0:
                    logger.info(f"Personal scores insérés: {result['personal_scores_inserted']}")
                if result.get("performance_scores_inserted", 0) > 0:
                    logger.info(
                        f"Scores de performance calculés: {result['performance_scores_inserted']}"
                    )
                if result.get("aliases_inserted", 0) > 0:
                    logger.info(f"Aliases insérés: {result['aliases_inserted']}")

            except ImportError as e:
                logger.warning(f"Impossible d'importer backfill_data: {e}")
            except Exception as e:
                logger.error(f"Erreur lors du backfill: {e}")
                success = False

    # Migration vers Parquet (dépréciée depuis v4)
    if args.migrate_parquet:
        logger.warning(
            "--migrate-parquet est déprécié depuis v4. "
            "Utilisez scripts/migrate_to_duckdb.py pour migrer vers DuckDB."
        )

    # Afficher les stats finales
    if args.delta or args.full or args.rebuild_cache:
        print_stats(db_path, player=args.player)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
