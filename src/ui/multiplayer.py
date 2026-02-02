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


def _get_sqlite_connection(db_path: str):
    """Retourne une connexion SQLite."""
    import sqlite3

    return sqlite3.connect(db_path)


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

    Dans l'architecture v4 (DuckDB), chaque joueur a sa propre DB,
    donc cette fonction retourne False pour les fichiers .duckdb.
    """
    if not db_path or not os.path.exists(db_path):
        return False

    # Les DBs DuckDB v4 sont toujours single-player
    if _is_duckdb_file(db_path):
        return False

    try:
        con = _get_sqlite_connection(db_path)
        cur = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Players'")
        result = cur.fetchone() is not None
        con.close()
        return result
    except Exception:
        return False


def list_players_in_db(db_path: str) -> list[PlayerInfo]:
    """Liste les joueurs disponibles dans une DB multi-joueurs.

    Returns:
        Liste triée par nombre de matchs (décroissant).
    """
    if not db_path or not os.path.exists(db_path):
        return []

    # Les DBs DuckDB v4 sont single-player, pas de table Players
    if _is_duckdb_file(db_path):
        return []

    players: list[PlayerInfo] = []
    try:
        con = _get_sqlite_connection(db_path)
        cur = con.execute("""
            SELECT xuid, gamertag, label, total_matches,
                   first_match_date, last_match_date
            FROM Players
            ORDER BY total_matches DESC
        """)
        for row in cur.fetchall():
            players.append(
                PlayerInfo(
                    xuid=row[0],
                    gamertag=row[1],
                    label=row[2],
                    total_matches=row[3] or 0,
                    first_match_date=row[4],
                    last_match_date=row[5],
                )
            )
        con.close()
    except Exception:
        pass
    return players


def get_unique_xuids_from_matchstats(db_path: str) -> list[tuple[str, int]]:
    """Fallback : liste les XUIDs distincts depuis MatchStats.

    Utilisé si la table Players n'existe pas mais que la DB contient
    des matchs de plusieurs joueurs.

    Returns:
        Liste de (xuid, count) triée par count décroissant.
    """
    if not db_path or not os.path.exists(db_path):
        return []

    xuids: list[tuple[str, int]] = []

    # Pour DuckDB, lire depuis match_stats
    if _is_duckdb_file(db_path):
        try:
            con = _get_duckdb_connection(db_path)
            result = con.execute("""
                SELECT xuid, COUNT(*) as cnt
                FROM match_stats
                GROUP BY xuid
                ORDER BY cnt DESC
            """).fetchall()
            xuids = [(str(row[0]), row[1]) for row in result if row[0]]
            con.close()
        except Exception:
            pass
        return xuids

    # Pour SQLite, essayer MatchCache puis MatchStats
    try:
        con = _get_sqlite_connection(db_path)
        try:
            cur = con.execute("""
                SELECT xuid, COUNT(*) as cnt
                FROM MatchCache
                GROUP BY xuid
                ORDER BY cnt DESC
            """)
            xuids = [(row[0], row[1]) for row in cur.fetchall()]
        except Exception:
            cur = con.execute("""
                SELECT DISTINCT XUID
                FROM MatchStats
            """)
            xuids = [(row[0], 0) for row in cur.fetchall() if row[0]]
        con.close()
    except Exception:
        pass
    return xuids


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
    """Récupère le nom d'affichage d'un joueur depuis la table Players.

    Pour les DBs DuckDB v4, retourne None car il n'y a pas de table Players
    (chaque joueur a sa propre DB identifiée par le nom du dossier).
    """
    if not db_path or not xuid or not os.path.exists(db_path):
        return None

    # Les DBs DuckDB v4 n'ont pas de table Players
    if _is_duckdb_file(db_path):
        return None

    try:
        con = _get_sqlite_connection(db_path)
        cur = con.execute("SELECT label, gamertag FROM Players WHERE xuid = ?", (xuid,))
        row = cur.fetchone()
        con.close()
        if row:
            return row[0] or row[1] or None
    except Exception:
        pass
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
            # Compter les matchs
            result = con.execute("SELECT COUNT(*) FROM match_stats").fetchone()
            total_matches = result[0] if result else 0
            # Récupérer le XUID depuis sync_meta si disponible
            try:
                result = con.execute("SELECT value FROM sync_meta WHERE key = 'xuid'").fetchone()
                xuid = result[0] if result else None
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
            # Récupérer le XUID du nouveau joueur si disponible
            new_xuid = None
            try:
                con = _get_duckdb_connection(new_db_path)
                result = con.execute("SELECT value FROM sync_meta WHERE key = 'xuid'").fetchone()
                new_xuid = result[0] if result else None
                con.close()
            except Exception:
                pass
            return new_db_path, new_xuid
        return None, None

    # Cas 2: Legacy SQLite multi-joueurs
    new_xuid = render_player_selector(db_path, current_xuid, key=key)
    if new_xuid:
        return None, new_xuid

    return None, None
