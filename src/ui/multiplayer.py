"""Gestion du sélecteur multi-joueurs.

Ce module fournit les fonctions pour :
- Détecter si une DB est multi-joueurs (table Players) - Legacy SQLite
- Lister les joueurs disponibles (Legacy et DuckDB v4)
- Afficher un sélecteur dans la sidebar

Architecture v4 (DuckDB):
Chaque joueur a sa propre DB dans data/players/{gamertag}/stats.duckdb.
Le sélecteur liste les dossiers joueurs disponibles.

Legacy SQLite:
Une seule DB avec table Players pour les DBs fusionnées.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import streamlit as st

from src.utils.paths import PLAYERS_DIR

if TYPE_CHECKING:
    pass


def _get_players_dir() -> Path:
    """Retourne le chemin vers data/players/."""
    return PLAYERS_DIR


def _is_duckdb_file(db_path: str) -> bool:
    """Détecte si le fichier est une base DuckDB."""
    return db_path.endswith(".duckdb")


def _get_duckdb_connection(db_path: str):
    """Retourne une connexion DuckDB."""
    import duckdb

    return duckdb.connect(db_path, read_only=True)


@dataclass
class PlayerInfo:
    """Informations sur un joueur dans une DB multi-joueurs."""

    xuid: str
    gamertag: str | None
    label: str | None
    total_matches: int
    first_match_date: str | None
    last_match_date: str | None

    @property
    def display_name(self) -> str:
        """Nom d'affichage pour le sélecteur."""
        if self.label:
            return self.label
        if self.gamertag:
            return self.gamertag
        return self.xuid[:15] + "…"

    @property
    def display_with_stats(self) -> str:
        """Nom d'affichage avec statistiques."""
        name = self.display_name
        if self.total_matches:
            return f"{name} ({self.total_matches} matchs)"
        return name


def is_multi_player_db(db_path: str) -> bool:
    """Vérifie si la DB contient une table Players (DB fusionnée).

    DuckDB v4 uniquement : chaque joueur a sa propre DB, toujours single-player.
    Retourne False (SQLite .db refusé).
    """
    if not db_path or not os.path.exists(db_path):
        return False
    # SQLite (.db) interdit - toujours False
    if db_path.strip().lower().endswith(".db"):
        return False
    # DuckDB v4 : toujours single-player
    if _is_duckdb_file(db_path):
        return False
    return False


def list_players_in_db(db_path: str) -> list[PlayerInfo]:
    """Liste les joueurs disponibles dans une DB multi-joueurs.

    DuckDB v4 uniquement : toujours single-player, retourne [].
    SQLite (.db) interdit.
    """
    if not db_path or not os.path.exists(db_path):
        return []
    # SQLite interdit, DuckDB v4 = single-player
    return []


def get_unique_xuids_from_matchstats(db_path: str) -> list[tuple[str, int]]:
    """Fallback : liste les XUIDs distincts depuis MatchStats.

    Utilisé si la table Players n'existe pas mais que la DB contient
    des matchs de plusieurs joueurs.

    Returns:
        Liste de (xuid, count) triée par count décroissant.
    """
    if not db_path or not os.path.exists(db_path):
        return []

    # DuckDB v4 : chaque DB = 1 joueur, pas de multi-xuid
    if _is_duckdb_file(db_path):
        return []
    # SQLite (.db) interdit
    return []


def render_player_selector(
    db_path: str,
    current_xuid: str,
    key: str = "player_selector",
) -> str | None:
    """Affiche un sélecteur de joueur si la DB est multi-joueurs.

    Args:
        db_path: Chemin vers la DB.
        current_xuid: XUID actuellement sélectionné.
        key: Clé Streamlit pour le widget.

    Returns:
        XUID sélectionné, ou None si pas de changement / pas multi-joueurs.
    """
    if not db_path or not is_multi_player_db(db_path):
        return None

    players = list_players_in_db(db_path)
    if len(players) <= 1:
        return None

    # Construire les options
    options = {p.xuid: p.display_with_stats for p in players}
    xuids = list(options.keys())
    labels = list(options.values())

    # Index actuel
    try:
        current_idx = xuids.index(current_xuid)
    except ValueError:
        current_idx = 0

    # Afficher le sélecteur
    st.markdown("#### 👥 Joueur")
    selected_label = st.selectbox(
        "Joueur",
        options=labels,
        index=current_idx,
        key=key,
        label_visibility="collapsed",
    )

    # Retrouver le XUID sélectionné
    try:
        selected_idx = labels.index(selected_label)
        selected_xuid = xuids[selected_idx]
    except (ValueError, IndexError):
        selected_xuid = current_xuid

    if selected_xuid != current_xuid:
        return selected_xuid

    return None


def get_player_display_name(db_path: str, xuid: str) -> str | None:
    """Récupère le nom d'affichage d'un joueur.

    DuckDB v4 : pas de table Players (chaque joueur = une DB). Retourne None.
    SQLite (.db) interdit.
    """
    if not db_path or not xuid or not os.path.exists(db_path):
        return None
    if _is_duckdb_file(db_path):
        return None
    # SQLite (.db) interdit
    return None


# =============================================================================
# Architecture DuckDB v4 - Sélecteur multi-joueurs
# =============================================================================


@dataclass
class DuckDBPlayerInfo:
    """Informations sur un joueur DuckDB v4."""

    gamertag: str
    db_path: Path
    total_matches: int
    xuid: str | None = None

    @property
    def display_with_stats(self) -> str:
        """Nom d'affichage avec statistiques."""
        if self.total_matches:
            return f"{self.gamertag} ({self.total_matches} matchs)"
        return f"{self.gamertag} (0 matchs)"


def list_duckdb_v4_players() -> list[DuckDBPlayerInfo]:
    """Liste les joueurs depuis data/players/*/stats.duckdb.

    Returns:
        Liste triée par nombre de matchs (décroissant).
    """
    players_dir = _get_players_dir()
    players: list[DuckDBPlayerInfo] = []

    if not players_dir.exists():
        return players

    for player_dir in sorted(players_dir.iterdir()):
        if not player_dir.is_dir():
            continue

        db_path = player_dir / "stats.duckdb"
        if not db_path.exists():
            continue

        gamertag = player_dir.name
        total_matches = 0
        xuid = None

        try:
            con = _get_duckdb_connection(str(db_path))
            # Compter les matchs avec fallback intelligent
            # Chaîne de priorité : player_match_enrichment → match_stats → player_match_stats
            # Si une table existe mais est vide (0), on essaie la suivante
            total_matches = 0

            # Tentative 1 : player_match_enrichment (v5)
            try:
                result = con.execute("SELECT COUNT(*) FROM player_match_enrichment").fetchone()
                total_matches = result[0] if result else 0
            except Exception:
                pass

            # Tentative 2 : match_stats (v4) si player_match_enrichment vide ou absente
            if total_matches == 0:
                try:
                    result = con.execute("SELECT COUNT(*) FROM match_stats").fetchone()
                    total_matches = result[0] if result else 0
                except Exception:
                    pass

            # Tentative 3 : player_match_stats (legacy v3) si tout le reste vide
            if total_matches == 0:
                try:
                    result = con.execute("SELECT COUNT(*) FROM player_match_stats").fetchone()
                    total_matches = result[0] if result else 0
                except Exception:
                    pass

            # Récupérer le XUID avec fallback intelligent
            # 1. sync_meta (v5) → 2. player_match_stats (v3/v4) → 3. xuid_aliases
            try:
                result = con.execute("SELECT value FROM sync_meta WHERE key = 'xuid'").fetchone()
                if result and result[0] and str(result[0]).strip():
                    xuid = str(result[0]).strip()
            except Exception:
                pass

            if not xuid:
                try:
                    result = con.execute(
                        "SELECT DISTINCT xuid FROM player_match_stats WHERE xuid IS NOT NULL LIMIT 1"
                    ).fetchone()
                    if result and result[0] and str(result[0]).strip():
                        xuid = str(result[0]).strip()
                except Exception:
                    pass

            if not xuid:
                try:
                    result = con.execute(
                        "SELECT xuid FROM xuid_aliases WHERE gamertag = ? LIMIT 1", [gamertag]
                    ).fetchone()
                    if result and result[0] and str(result[0]).strip():
                        xuid = str(result[0]).strip()
                except Exception:
                    pass
            con.close()
        except Exception:
            pass

        players.append(
            DuckDBPlayerInfo(
                gamertag=gamertag,
                db_path=db_path,
                total_matches=total_matches,
                xuid=xuid,
            )
        )

    # Trier par nombre de matchs décroissant
    players.sort(key=lambda p: p.total_matches, reverse=True)
    return players


def is_duckdb_v4_path(db_path: str) -> bool:
    """Vérifie si le chemin est une DB joueur DuckDB v4.

    Détecte si le chemin correspond au pattern data/players/{gamertag}/stats.duckdb.
    """
    if not db_path:
        return False

    try:
        p = Path(db_path).resolve()
        # Vérifier le pattern: .../data/players/{gamertag}/stats.duckdb
        if p.name == "stats.duckdb" and p.parent.parent.name == "players":
            return True
    except Exception:
        pass

    return False


def get_gamertag_from_duckdb_v4_path(db_path: str) -> str | None:
    """Extrait le gamertag depuis un chemin DuckDB v4.

    Args:
        db_path: Chemin vers stats.duckdb

    Returns:
        Gamertag ou None si le chemin n'est pas valide.
    """
    if not db_path:
        return None

    try:
        p = Path(db_path).resolve()
        if p.name == "stats.duckdb":
            return p.parent.name
    except Exception:
        pass

    return None


def render_duckdb_v4_player_selector(
    current_db_path: str,
    key: str = "duckdb_v4_player_selector",
) -> str | None:
    """Affiche un sélecteur de joueur pour l'architecture DuckDB v4.

    Args:
        current_db_path: Chemin vers la DB actuelle.
        key: Clé Streamlit pour le widget.

    Returns:
        Nouveau db_path si changement, None sinon.
    """
    players = list_duckdb_v4_players()

    if len(players) <= 1:
        # Un seul joueur ou aucun, pas besoin de sélecteur
        return None

    # Trouver le joueur actuel
    current_gamertag = get_gamertag_from_duckdb_v4_path(current_db_path)

    # Construire les options
    options = {str(p.db_path): p.display_with_stats for p in players}
    db_paths = list(options.keys())
    labels = list(options.values())

    # Index actuel
    try:
        current_idx = next(i for i, p in enumerate(players) if p.gamertag == current_gamertag)
    except StopIteration:
        current_idx = 0

    # Afficher le sélecteur
    st.markdown("#### 👥 Joueur")
    selected_label = st.selectbox(
        "Joueur",
        options=labels,
        index=current_idx,
        key=key,
        label_visibility="collapsed",
    )

    # Retrouver le db_path sélectionné
    try:
        selected_idx = labels.index(selected_label)
        selected_db_path = db_paths[selected_idx]
    except (ValueError, IndexError):
        return None

    # Vérifier si changement
    try:
        if Path(selected_db_path).resolve() != Path(current_db_path).resolve():
            return selected_db_path
    except Exception:
        pass

    return None


def render_player_selector_unified(
    db_path: str,
    current_xuid: str,
    key: str = "player_selector",
) -> tuple[str | None, str | None]:
    """Sélecteur de joueur unifié (Legacy SQLite + DuckDB v4).

    Cette fonction détecte automatiquement l'architecture et affiche
    le sélecteur approprié.

    Args:
        db_path: Chemin vers la DB actuelle.
        current_xuid: XUID actuellement sélectionné.
        key: Clé Streamlit pour le widget.

    Returns:
        Tuple (new_db_path, new_xuid):
        - new_db_path: Nouveau chemin DB si changement (DuckDB v4), None sinon
        - new_xuid: Nouveau XUID si changement (Legacy), None sinon
    """
    if not db_path:
        return None, None

    # Cas 1: Architecture DuckDB v4
    if is_duckdb_v4_path(db_path):
        new_db_path = render_duckdb_v4_player_selector(db_path, key=f"{key}_v4")
        if new_db_path:
            # Récupérer le XUID du nouveau joueur avec fallback intelligent
            new_xuid = None
            try:
                from src.ui.cache_loaders import _resolve_player_xuid

                resolved = _resolve_player_xuid(new_db_path)
                if resolved:
                    new_xuid = resolved
            except Exception:
                pass
            return new_db_path, new_xuid
        return None, None

    # Cas 2: Legacy SQLite multi-joueurs
    new_xuid = render_player_selector(db_path, current_xuid, key=key)
    if new_xuid:
        return None, new_xuid

    return None, None
