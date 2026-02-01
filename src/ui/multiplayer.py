"""Gestion du sélecteur multi-joueurs pour les DBs fusionnées.

Ce module fournit les fonctions pour :
- Détecter si une DB est multi-joueurs (table Players)
- Lister les joueurs disponibles
- Afficher un sélecteur dans la sidebar

NOTE: Dans l'architecture v4 (DuckDB), chaque joueur a sa propre DB dans
data/players/{gamertag}/stats.duckdb, donc les fonctions multi-joueurs
ne s'appliquent qu'aux DBs legacy SQLite fusionnées (halo_unified.db).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

import streamlit as st

if TYPE_CHECKING:
    pass


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
