"""Graphiques pour visualisation des antagonistes (némésis/souffre-douleur).

Sprint 5 - Visualisations Plotly pour :
- Barres empilées killer-victim
- Timeseries K/D par minute
- Heatmap de duels
- Graphiques de tendance

Références :
- src/analysis/killer_victim.py : Fonctions d'analyse Polars
- src/visualization/theme.py : Style Halo pour les graphiques
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Import conditionnel de Polars
try:
    import polars as pl

    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False
    pl = None  # type: ignore

from src.visualization.theme import apply_halo_plot_style

if TYPE_CHECKING:
    pass


# =============================================================================
# Configuration des couleurs
# =============================================================================

# Couleurs Halo pour les graphiques d'antagonistes
COLORS = {
    "kills": "#00ff00",  # Vert néon - Mes kills
    "deaths": "#ff4444",  # Rouge - Mes morts
    "nemesis": "#ff6600",  # Orange - Némésis
    "victim": "#00aaff",  # Bleu - Victime
    "neutral": "#888888",  # Gris - Neutre
    "positive_kd": "#00ff00",  # Vert - K/D positif
    "negative_kd": "#ff4444",  # Rouge - K/D négatif
    "team_alpha": "#00aaff",  # Bleu équipe
    "team_bravo": "#ff6600",  # Orange équipe
    "highlight": "#ffd700",  # Or - Highlight
}

# Palette de couleurs pour les joueurs (jusqu'à 12)
PLAYER_COLORS = [
    "#00ff00",
    "#ff4444",
    "#00aaff",
    "#ff6600",
    "#aa00ff",
    "#ffff00",
    "#00ffaa",
    "#ff00aa",
    "#aaffaa",
    "#ffaaaa",
    "#aaaaff",
    "#ffaaff",
]


# =============================================================================
# Graphiques principaux
# =============================================================================


def plot_killer_victim_stacked_bars(
    pairs_df: pl.DataFrame,
    match_id: str | None = None,
    *,
    me_xuid: str | None = None,
    title: str = "Interactions Killer-Victim",
    height: int = 400,
) -> go.Figure:
    """Graphique barres empilées killer-victim avec Polars.

    Affiche pour chaque joueur le nombre de fois qu'il a tué et été tué
    par les autres joueurs du match.

    Args:
        pairs_df: DataFrame Polars avec colonnes killer_xuid, killer_gamertag,
                  victim_xuid, victim_gamertag, kill_count.
        match_id: Si fourni, filtre pour ce match uniquement.
        me_xuid: XUID du joueur principal (pour highlight).
        title: Titre du graphique.
        height: Hauteur en pixels.

    Returns:
        Figure Plotly avec les barres empilées.
    """
    if not POLARS_AVAILABLE:
        raise ImportError("Polars requis pour cette fonction")

    fig = go.Figure()

    if pairs_df.is_empty():
        fig.add_annotation(
            text="Aucune donnée disponible",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"size": 16, "color": COLORS["neutral"]},
        )
        return apply_halo_plot_style(fig, title=title, height=height)

    # Filtrer par match si spécifié
    filtered_df = pairs_df
    if match_id:
        filtered_df = filtered_df.filter(pl.col("match_id") == match_id)

    if filtered_df.is_empty():
        fig.add_annotation(
            text="Aucune donnée pour ce match",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"size": 16, "color": COLORS["neutral"]},
        )
        return apply_halo_plot_style(fig, title=title, height=height)

    # Calculer les kills par joueur (comme tueur)
    kills_by_player = (
        filtered_df.group_by("killer_gamertag")
        .agg(pl.col("kill_count").sum().alias("kills"))
        .sort("kills", descending=True)
    )

    # Calculer les morts par joueur (comme victime)
    deaths_by_player = filtered_df.group_by("victim_gamertag").agg(
        pl.col("kill_count").sum().alias("deaths")
    )

    # Joindre les données
    # Récupérer tous les gamertags uniques
    all_killers = set(kills_by_player["killer_gamertag"].to_list())
    all_victims = set(deaths_by_player["victim_gamertag"].to_list())
    all_players = sorted(all_killers | all_victims)

    # Préparer les données pour le graphique
    player_data = []
    for player in all_players:
        kills = 0
        deaths = 0

        kills_row = kills_by_player.filter(pl.col("killer_gamertag") == player)
        if len(kills_row) > 0:
            kills = kills_row["kills"].item()

        deaths_row = deaths_by_player.filter(pl.col("victim_gamertag") == player)
        if len(deaths_row) > 0:
            deaths = deaths_row["deaths"].item()

        player_data.append(
            {
                "gamertag": player,
                "kills": kills,
                "deaths": deaths,
                "net": kills - deaths,
            }
        )

    # Trier par net kills
    player_data.sort(key=lambda x: x["net"], reverse=True)

    gamertags = [p["gamertag"] for p in player_data]
    kills_values = [p["kills"] for p in player_data]
    deaths_values = [-p["deaths"] for p in player_data]  # Négatif pour affichage

    # Ajouter les barres de kills
    fig.add_trace(
        go.Bar(
            name="Kills",
            y=gamertags,
            x=kills_values,
            orientation="h",
            marker={"color": COLORS["kills"]},
            hovertemplate="<b>%{y}</b><br>Kills: %{x}<extra></extra>",
        )
    )

    # Ajouter les barres de morts (négatives)
    fig.add_trace(
        go.Bar(
            name="Morts",
            y=gamertags,
            x=deaths_values,
            orientation="h",
            marker={"color": COLORS["deaths"]},
            hovertemplate="<b>%{y}</b><br>Morts: %{customdata}<extra></extra>",
            customdata=[abs(d) for d in deaths_values],
        )
    )

    # Mise en forme
    fig.update_layout(
        barmode="relative",
        xaxis_title="Kills / Morts",
        yaxis_title="Joueur",
        showlegend=True,
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "center",
            "x": 0.5,
        },
    )

    # Ajouter une ligne verticale à 0
    fig.add_vline(x=0, line_width=1, line_color=COLORS["neutral"])

    return apply_halo_plot_style(fig, title=title, height=height)


def plot_kd_timeseries(
    timeseries_df: pl.DataFrame,
    *,
    title: str = "K/D par minute",
    show_cumulative: bool = True,
    height: int = 350,
) -> go.Figure:
    """Graphique timeseries du K/D par minute.

    Affiche l'évolution du K/D au cours du match, minute par minute.

    Args:
        timeseries_df: DataFrame Polars avec colonnes minute, kills, deaths,
                       net_kd, cumulative_net_kd (depuis compute_kd_timeseries_by_minute_polars).
        title: Titre du graphique.
        show_cumulative: Si True, affiche aussi la courbe cumulative.
        height: Hauteur en pixels.

    Returns:
        Figure Plotly avec la timeseries.
    """
    if not POLARS_AVAILABLE:
        raise ImportError("Polars requis pour cette fonction")

    fig = go.Figure()

    if timeseries_df.is_empty():
        fig.add_annotation(
            text="Aucune donnée disponible",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"size": 16, "color": COLORS["neutral"]},
        )
        return apply_halo_plot_style(fig, title=title, height=height)

    minutes = timeseries_df["minute"].to_list()
    kills = timeseries_df["kills"].to_list()
    deaths = timeseries_df["deaths"].to_list()
    timeseries_df["net_kd"].to_list()

    # Barres pour kills par minute
    fig.add_trace(
        go.Bar(
            name="Kills",
            x=minutes,
            y=kills,
            marker={"color": COLORS["kills"], "opacity": 0.7},
            hovertemplate="Min %{x}<br>Kills: %{y}<extra></extra>",
        )
    )

    # Barres pour morts par minute (négatif)
    fig.add_trace(
        go.Bar(
            name="Morts",
            x=minutes,
            y=[-d for d in deaths],
            marker={"color": COLORS["deaths"], "opacity": 0.7},
            hovertemplate="Min %{x}<br>Morts: %{customdata}<extra></extra>",
            customdata=deaths,
        )
    )

    # Ligne de K/D net cumulatif
    if show_cumulative and "cumulative_net_kd" in timeseries_df.columns:
        cumulative = timeseries_df["cumulative_net_kd"].to_list()

        # Couleur basée sur la valeur finale
        final_color = COLORS["positive_kd"] if cumulative[-1] >= 0 else COLORS["negative_kd"]

        fig.add_trace(
            go.Scatter(
                name="K/D Cumulé",
                x=minutes,
                y=cumulative,
                mode="lines+markers",
                line={"color": final_color, "width": 3},
                marker={"size": 6},
                yaxis="y2",
                hovertemplate="Min %{x}<br>Net K/D cumulé: %{y:+d}<extra></extra>",
            )
        )

    # Mise en forme avec axe Y secondaire
    fig.update_layout(
        barmode="relative",
        xaxis_title="Minute",
        yaxis_title="Kills / Morts",
        yaxis2={
            "title": "K/D cumulé",
            "overlaying": "y",
            "side": "right",
            "showgrid": False,
        },
        showlegend=True,
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "center",
            "x": 0.5,
        },
    )

    # Ligne horizontale à 0
    fig.add_hline(y=0, line_width=1, line_color=COLORS["neutral"], line_dash="dash")

    return apply_halo_plot_style(fig, title=title, height=height)


def plot_duel_history(
    duel_df: pl.DataFrame,
    me_gamertag: str,
    opponent_gamertag: str,
    *,
    title: str | None = None,
    height: int = 300,
) -> go.Figure:
    """Graphique de l'historique des duels entre deux joueurs.

    Args:
        duel_df: DataFrame Polars avec colonnes match_id, my_kills, opponent_kills, net
                 (depuis compute_duel_history_polars).
        me_gamertag: Gamertag du joueur principal.
        opponent_gamertag: Gamertag de l'adversaire.
        title: Titre du graphique (auto-généré si None).
        height: Hauteur en pixels.

    Returns:
        Figure Plotly avec l'historique des duels.
    """
    if not POLARS_AVAILABLE:
        raise ImportError("Polars requis pour cette fonction")

    if title is None:
        title = f"Historique des duels : {me_gamertag} vs {opponent_gamertag}"

    fig = go.Figure()

    if duel_df.is_empty():
        fig.add_annotation(
            text="Aucun duel trouvé",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"size": 16, "color": COLORS["neutral"]},
        )
        return apply_halo_plot_style(fig, title=title, height=height)

    matches = list(range(len(duel_df)))
    my_kills = duel_df["my_kills"].to_list()
    opponent_kills = duel_df["opponent_kills"].to_list()
    net_values = duel_df["net"].to_list()

    # Barres groupées
    fig.add_trace(
        go.Bar(
            name=me_gamertag,
            x=matches,
            y=my_kills,
            marker={"color": COLORS["kills"]},
            hovertemplate=f"<b>{me_gamertag}</b><br>Kills: %{{y}}<extra></extra>",
        )
    )

    fig.add_trace(
        go.Bar(
            name=opponent_gamertag,
            x=matches,
            y=opponent_kills,
            marker={"color": COLORS["deaths"]},
            hovertemplate=f"<b>{opponent_gamertag}</b><br>Kills: %{{y}}<extra></extra>",
        )
    )

    # Ligne de net
    fig.add_trace(
        go.Scatter(
            name="Net",
            x=matches,
            y=net_values,
            mode="lines+markers",
            line={"color": COLORS["highlight"], "width": 2},
            yaxis="y2",
            hovertemplate="Net: %{y:+d}<extra></extra>",
        )
    )

    # Calculer les totaux
    total_my_kills = sum(my_kills)
    total_opponent_kills = sum(opponent_kills)
    total_net = total_my_kills - total_opponent_kills

    # Ajouter annotation avec les totaux
    win_status = "Victoire" if total_net > 0 else ("Égalité" if total_net == 0 else "Défaite")
    annotation_text = f"Total: {total_my_kills}-{total_opponent_kills} ({win_status})"

    fig.add_annotation(
        text=annotation_text,
        xref="paper",
        yref="paper",
        x=1,
        y=1.15,
        showarrow=False,
        font={
            "size": 14,
            "color": COLORS["positive_kd"] if total_net >= 0 else COLORS["negative_kd"],
        },
        xanchor="right",
    )

    fig.update_layout(
        barmode="group",
        xaxis_title="Match #",
        yaxis_title="Kills",
        yaxis2={
            "title": "Net",
            "overlaying": "y",
            "side": "right",
            "showgrid": False,
        },
        showlegend=True,
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "center",
            "x": 0.5,
        },
    )

    # Ligne à 0 sur l'axe secondaire
    fig.add_hline(
        y=0,
        line_width=1,
        line_color=COLORS["neutral"],
        line_dash="dash",
        yref="y2",
    )

    return apply_halo_plot_style(fig, title=title, height=height)


def plot_nemesis_victim_summary(
    nemesis_data: dict[str, Any],
    victim_data: dict[str, Any],
    *,
    title: str = "Némésis et Souffre-douleur",
    height: int = 250,
) -> go.Figure:
    """Graphique résumé du némésis et souffre-douleur.

    Affiche les statistiques des deux principaux antagonistes.

    Args:
        nemesis_data: Dict avec gamertag, times_killed_by, matches.
        victim_data: Dict avec gamertag, times_killed, matches.
        title: Titre du graphique.
        height: Hauteur en pixels.

    Returns:
        Figure Plotly avec le résumé.
    """
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Némésis", "Souffre-douleur"),
        specs=[[{"type": "indicator"}, {"type": "indicator"}]],
    )

    # Némésis
    nemesis_gt = nemesis_data.get("gamertag", "N/A")
    nemesis_count = nemesis_data.get("times_killed_by", 0)

    fig.add_trace(
        go.Indicator(
            mode="number",
            value=nemesis_count,
            number={
                "suffix": " morts",
                "font": {"size": 36, "color": COLORS["nemesis"]},
            },
            title={
                "text": f"<b>{nemesis_gt}</b>",
                "font": {"size": 16},
            },
        ),
        row=1,
        col=1,
    )

    # Victime
    victim_gt = victim_data.get("gamertag", "N/A")
    victim_count = victim_data.get("times_killed", 0)

    fig.add_trace(
        go.Indicator(
            mode="number",
            value=victim_count,
            number={
                "suffix": " kills",
                "font": {"size": 36, "color": COLORS["victim"]},
            },
            title={
                "text": f"<b>{victim_gt}</b>",
                "font": {"size": 16},
            },
        ),
        row=1,
        col=2,
    )

    return apply_halo_plot_style(fig, title=title, height=height)


def plot_killer_victim_heatmap(
    matrix_df: pl.DataFrame,
    *,
    title: str = "Matrice Killer-Victim",
    height: int = 500,
) -> go.Figure:
    """Heatmap de la matrice killer-victim.

    Args:
        matrix_df: DataFrame Polars pivotée (killer en index, victim en colonnes)
                   depuis killer_victim_matrix_polars.
        title: Titre du graphique.
        height: Hauteur en pixels.

    Returns:
        Figure Plotly avec la heatmap.
    """
    if not POLARS_AVAILABLE:
        raise ImportError("Polars requis pour cette fonction")

    fig = go.Figure()

    if matrix_df.is_empty():
        fig.add_annotation(
            text="Aucune donnée disponible",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"size": 16, "color": COLORS["neutral"]},
        )
        return apply_halo_plot_style(fig, title=title, height=height)

    # Extraire les données
    killers = matrix_df["killer_gamertag"].to_list()
    victim_cols = [c for c in matrix_df.columns if c != "killer_gamertag"]

    # Créer la matrice de valeurs
    z_values = []
    for row in matrix_df.iter_rows(named=True):
        row_values = [row.get(col, 0) or 0 for col in victim_cols]
        z_values.append(row_values)

    fig.add_trace(
        go.Heatmap(
            z=z_values,
            x=victim_cols,
            y=killers,
            colorscale=[
                [0, "#1a1a2e"],
                [0.25, "#16213e"],
                [0.5, "#0f3460"],
                [0.75, "#e94560"],
                [1, "#ff6b6b"],
            ],
            hoverongaps=False,
            hovertemplate="<b>%{y}</b> → <b>%{x}</b><br>Kills: %{z}<extra></extra>",
        )
    )

    fig.update_layout(
        xaxis_title="Victime",
        yaxis_title="Tueur",
        xaxis={"side": "bottom"},
    )

    return apply_halo_plot_style(fig, title=title, height=height)


def plot_top_antagonists_bars(
    nemeses: list[dict],
    victims: list[dict],
    *,
    top_n: int = 5,
    title: str = "Top Antagonistes",
    height: int = 400,
) -> go.Figure:
    """Graphique barres horizontales des top antagonistes.

    Args:
        nemeses: Liste de dicts avec killer_gamertag, times_killed_by.
        victims: Liste de dicts avec victim_gamertag, times_killed.
        top_n: Nombre de joueurs à afficher par catégorie.
        title: Titre du graphique.
        height: Hauteur en pixels.

    Returns:
        Figure Plotly avec les top antagonistes.
    """
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=(f"Top {top_n} Némésis", f"Top {top_n} Victimes"),
        horizontal_spacing=0.15,
    )

    # Top Némésis
    top_nemeses = nemeses[:top_n] if nemeses else []
    if top_nemeses:
        nem_names = [n.get("killer_gamertag", "?") for n in reversed(top_nemeses)]
        nem_counts = [n.get("times_killed_by", 0) for n in reversed(top_nemeses)]

        fig.add_trace(
            go.Bar(
                y=nem_names,
                x=nem_counts,
                orientation="h",
                marker={"color": COLORS["nemesis"]},
                name="Morts",
                hovertemplate="<b>%{y}</b><br>M'a tué: %{x} fois<extra></extra>",
            ),
            row=1,
            col=1,
        )

    # Top Victimes
    top_victims = victims[:top_n] if victims else []
    if top_victims:
        vic_names = [v.get("victim_gamertag", "?") for v in reversed(top_victims)]
        vic_counts = [v.get("times_killed", 0) for v in reversed(top_victims)]

        fig.add_trace(
            go.Bar(
                y=vic_names,
                x=vic_counts,
                orientation="h",
                marker={"color": COLORS["victim"]},
                name="Kills",
                hovertemplate="<b>%{y}</b><br>Tué: %{x} fois<extra></extra>",
            ),
            row=1,
            col=2,
        )

    fig.update_layout(
        showlegend=False,
    )

    fig.update_xaxes(title_text="Fois tué par", row=1, col=1)
    fig.update_xaxes(title_text="Fois tué", row=1, col=2)

    return apply_halo_plot_style(fig, title=title, height=height)


# =============================================================================
# Fonctions utilitaires
# =============================================================================


def get_antagonist_chart_colors() -> dict[str, str]:
    """Retourne le dictionnaire des couleurs pour les graphiques antagonistes.

    Utile pour harmoniser les couleurs dans l'UI.

    Returns:
        Dict avec les codes couleur hex.
    """
    return COLORS.copy()


def create_kd_indicator(
    kills: int,
    deaths: int,
    *,
    title: str = "K/D",
    height: int = 150,
) -> go.Figure:
    """Crée un indicateur K/D simple.

    Args:
        kills: Nombre de kills.
        deaths: Nombre de morts.
        title: Titre de l'indicateur.
        height: Hauteur en pixels.

    Returns:
        Figure Plotly avec l'indicateur.
    """
    kd_ratio = kills / deaths if deaths > 0 else kills

    # Couleur basée sur le ratio
    if kd_ratio >= 1.5:
        color = COLORS["positive_kd"]
    elif kd_ratio >= 1.0:
        color = COLORS["highlight"]
    else:
        color = COLORS["negative_kd"]

    fig = go.Figure()

    fig.add_trace(
        go.Indicator(
            mode="number+delta",
            value=kd_ratio,
            number={
                "valueformat": ".2f",
                "font": {"size": 48, "color": color},
            },
            delta={
                "reference": 1.0,
                "valueformat": ".2f",
                "increasing": {"color": COLORS["positive_kd"]},
                "decreasing": {"color": COLORS["negative_kd"]},
            },
            title={
                "text": f"<b>{title}</b><br><span style='font-size:12px'>{kills}K / {deaths}D</span>",
                "font": {"size": 14},
            },
        )
    )

    return apply_halo_plot_style(fig, title="", height=height)
