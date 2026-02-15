"""Visualisation heatmap d'impact des coéquipiers (Sprint 12).

Génère une heatmap montrant les événements clés par joueur/match :
- 🟢 First Blood (Premier sang)
- 🟡 Clutch Finisher (Finisseur)
- 🔴 Last Casualty (Boulet)

Et un tableau de ranking "Taquinerie" avec MVP et Boulet du groupe.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import plotly.graph_objects as go
import polars as pl

from src.analysis.friends_impact import ImpactEvent
from src.config import HALO_COLORS
from src.visualization.theme import apply_halo_plot_style

if TYPE_CHECKING:
    pass

# Couleurs pour les événements d'impact
IMPACT_COLORS = {
    "first_blood": "#2ecc71",  # Vert
    "clutch_finisher": "#f39c12",  # Or/Orange
    "last_casualty": "#e74c3c",  # Rouge
    "none": "rgba(100, 100, 100, 0.1)",  # Gris transparent
}

# Labels d'événements (FR)
EVENT_LABELS = {
    "first_blood": "Premier Sang 🟢",
    "clutch_finisher": "Finisseur 🟡",
    "last_casualty": "Boulet 🔴",
}


def plot_friends_impact_heatmap(
    impact_matrix: pl.DataFrame,
    *,
    title: str | None = None,
    max_matches: int = 50,
    height: int | None = None,
) -> go.Figure:
    """Crée une heatmap des événements d'impact par joueur et match.

    Args:
        impact_matrix: DataFrame Polars avec colonnes :
            - match_id, gamertag, event_type, event_value
        title: Titre optionnel.
        max_matches: Nombre maximum de matchs à afficher.
        height: Hauteur optionnelle.

    Returns:
        Figure Plotly avec la heatmap.
    """
    colors = HALO_COLORS.as_dict()

    if impact_matrix.is_empty():
        fig = go.Figure()
        fig.add_annotation(
            text="Aucun événement d'impact à afficher",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"size": 14, "color": colors.get("slate", "#64748b")},
        )
        fig.update_layout(height=height or 300)
        return apply_halo_plot_style(fig, title=title, height=height)

    # Récupérer les valeurs uniques
    gamertags = sorted(impact_matrix["gamertag"].unique().to_list())
    match_ids = impact_matrix["match_id"].unique().to_list()

    # Limiter le nombre de matchs
    if len(match_ids) > max_matches:
        # Prendre les plus récents (on suppose triés par date descendante)
        match_ids = match_ids[:max_matches]
        impact_matrix = impact_matrix.filter(pl.col("match_id").is_in(match_ids))

    n_matches = len(match_ids)
    n_players = len(gamertags)

    if n_matches == 0 or n_players == 0:
        fig = go.Figure()
        fig.update_layout(height=height or 300)
        return apply_halo_plot_style(fig, title=title, height=height)

    # Pivoter pour créer la matrice Z
    # Créer une matrice 2D : gamertags (Y) × match_ids (X)
    z_matrix = []
    text_matrix = []

    for gamertag in gamertags:
        z_row = []
        text_row = []

        player_events = impact_matrix.filter(pl.col("gamertag") == gamertag)

        for match_id in match_ids:
            match_event = player_events.filter(pl.col("match_id") == match_id)

            if match_event.is_empty() or match_event["event_type"][0] is None:
                z_row.append(0)
                text_row.append("")
            else:
                event_type = match_event["event_type"][0]
                event_value = match_event["event_value"][0]
                z_row.append(event_value)
                text_row.append(EVENT_LABELS.get(event_type, ""))

        z_matrix.append(z_row)
        text_matrix.append(text_row)

    # Créer la colorscale custom pour -1, 0, 1, 2
    # Normaliser sur l'échelle [-1, 2] -> [0, 1]
    # -1 (boulet) = 0.0 -> rouge
    # 0 (rien) = 0.33 -> gris
    # 1 (FB) = 0.66 -> vert
    # 2 (clutch) = 1.0 -> or
    colorscale = [
        [0.0, IMPACT_COLORS["last_casualty"]],  # -1
        [0.33, IMPACT_COLORS["none"]],  # 0
        [0.66, IMPACT_COLORS["first_blood"]],  # 1
        [1.0, IMPACT_COLORS["clutch_finisher"]],  # 2
    ]

    # Labels des matchs (afficher index ou raccourci)
    match_labels = [f"#{i + 1}" for i in range(n_matches)]

    fig = go.Figure(
        data=go.Heatmap(
            z=z_matrix,
            x=match_labels,
            y=gamertags,
            text=text_matrix,
            texttemplate="%{text}",
            textfont={"size": 9},
            colorscale=colorscale,
            zmin=-1,
            zmax=2,
            showscale=False,
            hovertemplate=("<b>%{y}</b><br>" "Match %{x}<br>" "%{text}<extra></extra>"),
        )
    )

    # Calculer la hauteur dynamique
    calc_height = height or max(300, 50 * n_players + 100)

    fig.update_layout(
        height=calc_height,
        margin={"l": 120, "r": 40, "t": 60 if title else 30, "b": 50},
        xaxis_title="Matchs récents →",
        yaxis_title="",
    )
    fig.update_yaxes(autorange="reversed")  # Premier en haut

    return apply_halo_plot_style(fig, title=title, height=calc_height)


def build_impact_ranking_df(
    scores: dict[str, int],
    first_blood_counts: dict[str, int] | None = None,
    clutch_counts: dict[str, int] | None = None,
    casualty_counts: dict[str, int] | None = None,
) -> pl.DataFrame:
    """Construit un DataFrame de ranking pour le tableau de taquinerie.

    Args:
        scores: Dict {gamertag: score_total}.
        first_blood_counts: Nombre de FB par joueur (optionnel).
        clutch_counts: Nombre de Clutch par joueur (optionnel).
        casualty_counts: Nombre de Boulet par joueur (optionnel).

    Returns:
        DataFrame avec colonnes : rang, gamertag, score, fb, clutch, boulet, badge.
    """
    if not scores:
        return pl.DataFrame(
            schema={
                "rang": pl.Int64,
                "gamertag": pl.Utf8,
                "score": pl.Int64,
                "fb": pl.Int64,
                "clutch": pl.Int64,
                "boulet": pl.Int64,
                "badge": pl.Utf8,
            }
        )

    first_blood_counts = first_blood_counts or {}
    clutch_counts = clutch_counts or {}
    casualty_counts = casualty_counts or {}

    # Trier par score décroissant
    sorted_players = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    rows = []
    for rank, (gamertag, score) in enumerate(sorted_players, start=1):
        badge = ""
        if rank == 1:
            badge = "🏆 MVP"
        elif rank == len(sorted_players) and score < 0:
            badge = "🍌 Boulet"
        elif rank == len(sorted_players):
            badge = "📉 Dernier"

        rows.append(
            {
                "rang": rank,
                "gamertag": gamertag,
                "score": score,
                "fb": first_blood_counts.get(gamertag, 0),
                "clutch": clutch_counts.get(gamertag, 0),
                "boulet": casualty_counts.get(gamertag, 0),
                "badge": badge,
            }
        )

    return pl.DataFrame(rows)


def count_events_by_player(
    events: dict[str, ImpactEvent],
) -> dict[str, int]:
    """Compte le nombre d'événements par joueur.

    Args:
        events: Dict {match_id: ImpactEvent}.

    Returns:
        Dict {gamertag: count}.
    """
    counts: dict[str, int] = {}
    for event in events.values():
        gamertag = event.gamertag
        counts[gamertag] = counts.get(gamertag, 0) + 1
    return counts


def render_impact_summary_stats(
    first_bloods: dict[str, ImpactEvent],
    clutch_finishers: dict[str, ImpactEvent],
    last_casualties: dict[str, ImpactEvent],
) -> dict[str, int]:
    """Calcule les statistiques résumées des événements d'impact.

    Args:
        first_bloods: Dict des premiers kills.
        clutch_finishers: Dict des finisseurs.
        last_casualties: Dict des boulets.

    Returns:
        Dict avec total_fb, total_clutch, total_casualty, total_matches.
    """
    # Compter les matchs uniques
    all_match_ids = (
        set(first_bloods.keys()) | set(clutch_finishers.keys()) | set(last_casualties.keys())
    )

    return {
        "total_fb": len(first_bloods),
        "total_clutch": len(clutch_finishers),
        "total_casualty": len(last_casualties),
        "total_matches": len(all_match_ids),
    }
