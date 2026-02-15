"""Graphiques et tableaux de comparaison de sessions.

Ce module contient les fonctions de visualisation extraites de
session_compare.py pour respecter la limite de 800 lignes par fichier :
- Tableau historique des parties
- Radar chart comparatif
- Graphique en barres comparatif
- Tendance de participation
"""

from __future__ import annotations

import html as html_lib
from typing import TYPE_CHECKING

import plotly.graph_objects as go
import polars as pl
import streamlit as st

from src.analysis.performance_score import compute_performance_series
from src.ui import translate_pair_name
from src.ui.components.performance import get_score_class
from src.ui.pages.session_compare import (
    _format_date_with_weekday,
    _outcome_class,
)
from src.visualization._compat import (
    DataFrameLike,
    ensure_polars,
)

if TYPE_CHECKING:
    pass


# Couleurs distinctes pour les sessions (contraste élevé, accessible daltoniens)
SESSION_COLORS = {
    "session_a": "#E74C3C",  # Rouge corail
    "session_a_fill": "rgba(231, 76, 60, 0.3)",
    "session_b": "#3498DB",  # Bleu vif
    "session_b_fill": "rgba(52, 152, 219, 0.3)",
    "historical": "#9B59B6",  # Violet
    "historical_fill": "rgba(155, 89, 182, 0.2)",
}


# ════════════════════════════════════════════════════════════════════════════
# Tableau historique des parties
# ════════════════════════════════════════════════════════════════════════════


def _build_history_dataframe(
    df_sess: DataFrameLike,
    df_full: DataFrameLike | None = None,
) -> tuple[pl.DataFrame, pl.Series | None]:
    """Construit le DataFrame d'affichage et les scores de performance.

    Prépare les colonnes à afficher (heure, mode, carte, frags, résultat, etc.)
    et calcule les scores de performance relatifs.

    Args:
        df_sess: DataFrame de la session (copie modifiable).
        df_full: DataFrame complet pour le calcul du score relatif.

    Returns:
        Tuple (df_display Polars préparé, Series Polars des scores de performance).
    """
    df_sess = ensure_polars(df_sess)
    if df_full is not None:
        df_full = ensure_polars(df_full)

    # Trier par start_time si disponible (pour l'ordre chronologique)
    if "start_time" in df_sess.columns:
        df_sess = df_sess.sort("start_time")

    # Traduire le mode si non traduit
    if "pair_fr" not in df_sess.columns and "pair_name" in df_sess.columns:
        df_sess = df_sess.with_columns(
            pl.col("pair_name")
            .map_elements(translate_pair_name, return_dtype=pl.Utf8)
            .alias("pair_fr")
        )

    # Préparer les colonnes à afficher
    display_cols: list[str] = []
    col_map: dict[str, str] = {}

    if "start_time" in df_sess.columns:
        df_sess = df_sess.with_columns(
            pl.col("start_time")
            .map_elements(_format_date_with_weekday, return_dtype=pl.Utf8)
            .alias("Heure")
        )
        display_cols.append("Heure")

    if "pair_fr" in df_sess.columns:
        col_map["pair_fr"] = "Mode"
        display_cols.append("pair_fr")
    elif "pair_name" in df_sess.columns:
        df_sess = df_sess.with_columns(
            pl.col("pair_name")
            .map_elements(translate_pair_name, return_dtype=pl.Utf8)
            .alias("mode_traduit")
        )
        col_map["mode_traduit"] = "Mode"
        display_cols.append("mode_traduit")

    if "map_ui" in df_sess.columns:
        col_map["map_ui"] = "Carte"
        display_cols.append("map_ui")
    elif "map_name" in df_sess.columns:
        col_map["map_name"] = "Carte"
        display_cols.append("map_name")

    for c in ["kills", "deaths", "assists"]:
        if c in df_sess.columns:
            col_map[c] = {"kills": "Frags", "deaths": "Morts", "assists": "Assists"}[c]
            display_cols.append(c)

    if "outcome" in df_sess.columns:
        df_sess = df_sess.with_columns(
            pl.col("outcome")
            .replace_strict(
                {2: "Victoire", 3: "Défaite", 1: "Égalité", 4: "Non terminé"},
                default="-",
                return_dtype=pl.Utf8,
            )
            .fill_null("-")
            .alias("Résultat")
        )
        display_cols.append("Résultat")

    # Colonne Performance RELATIVE (après Résultat)
    history_df = df_full if df_full is not None else df_sess
    perf_series = compute_performance_series(df_sess, history_df)
    df_sess = df_sess.with_columns(perf_series.alias("Performance"))
    df_sess = df_sess.with_columns(
        pl.when(pl.col("Performance").is_not_null())
        .then(pl.col("Performance").round(0).cast(pl.Int64).cast(pl.Utf8))
        .otherwise(pl.lit("-"))
        .alias("Perf_display")
    )
    display_cols.append("Perf_display")
    col_map["Perf_display"] = "Performance"

    if "team_mmr" in df_sess.columns:
        df_sess = df_sess.with_columns(
            pl.when(pl.col("team_mmr").is_not_null())
            .then(pl.col("team_mmr").round(0).cast(pl.Int64).cast(pl.Utf8))
            .otherwise(pl.lit("-"))
            .alias("MMR Équipe")
        )
        display_cols.append("MMR Équipe")

    if "enemy_mmr" in df_sess.columns:
        df_sess = df_sess.with_columns(
            pl.when(pl.col("enemy_mmr").is_not_null())
            .then(pl.col("enemy_mmr").round(0).cast(pl.Int64).cast(pl.Utf8))
            .otherwise(pl.lit("-"))
            .alias("MMR Adverse")
        )
        display_cols.append("MMR Adverse")

    # Sélectionner et renommer les colonnes
    df_display = df_sess.select(display_cols).rename(col_map)

    # Garder les scores de performance pour la coloration
    perf_scores = df_sess.get_column("Performance") if "Performance" in df_sess.columns else None

    return df_display, perf_scores


def _render_history_html(
    df_display: pl.DataFrame,
    perf_scores: pl.Series | None = None,
) -> None:
    """Génère et affiche le tableau HTML stylisé des parties.

    Args:
        df_display: DataFrame Polars préparé pour l'affichage.
        perf_scores: Series Polars des scores de performance pour la coloration.
    """
    html_rows: list[str] = []
    for idx, row in enumerate(df_display.iter_rows(named=True)):
        cells: list[str] = []
        for col in df_display.columns:
            val = row[col]
            if col == "Résultat":
                css_class = _outcome_class(str(val))
                cells.append(f"<td class='{css_class}'>{html_lib.escape(str(val))}</td>")
            elif col == "Performance":
                # Coloration selon le score
                perf_val = perf_scores[idx] if perf_scores is not None else None
                css_class = get_score_class(perf_val)
                cells.append(
                    f"<td class='{css_class}'>{html_lib.escape(str(val) if val is not None else '-')}</td>"
                )
            else:
                cells.append(f"<td>{html_lib.escape(str(val) if val is not None else '-')}</td>")
        html_rows.append("<tr>" + "".join(cells) + "</tr>")

    header_cells = "".join(f"<th>{html_lib.escape(c)}</th>" for c in df_display.columns)
    html_table = f"""
    <table class="session-history-table">
    <thead><tr>{header_cells}</tr></thead>
    <tbody>{''.join(html_rows)}</tbody>
    </table>
    """
    st.markdown(html_table, unsafe_allow_html=True)


def render_session_history_table(
    df_sess: DataFrameLike,
    session_name: str,
    df_full: DataFrameLike | None = None,
) -> None:
    """Affiche le tableau historique d'une session.

    Orchestre la construction du DataFrame d'affichage et le rendu HTML.

    Args:
        df_sess: DataFrame de la session.
        session_name: Nom de la session pour les messages.
        df_full: DataFrame complet pour le calcul du score relatif.
    """
    df_sess = ensure_polars(df_sess)
    if df_sess.is_empty():
        st.info(f"Aucune partie dans {session_name}.")
        return

    if df_full is not None:
        df_full = ensure_polars(df_full)
    df_display, perf_scores = _build_history_dataframe(df_sess.clone(), df_full)
    _render_history_html(df_display, perf_scores)


# ════════════════════════════════════════════════════════════════════════════
# Radar chart comparatif
# ════════════════════════════════════════════════════════════════════════════


def render_comparison_radar_chart(
    perf_a: dict,
    perf_b: dict,
    hist_avg: dict | None = None,
) -> None:
    """Affiche le radar chart comparatif avec moyenne historique optionnelle.

    Args:
        perf_a: Métriques de la session A.
        perf_b: Métriques de la session B.
        hist_avg: Moyenne historique des sessions similaires (optionnel).
    """
    categories = ["K/D", "Victoire %", "Précision"]

    def _normalize_for_radar(kd, wr, acc):
        kd_norm = min(100, (kd or 0) * 50)  # K/D 2.0 = 100
        wr_norm = wr or 0  # Déjà en %
        acc_norm = acc if acc is not None else 50  # Déjà en %
        return [kd_norm, wr_norm, acc_norm]

    values_a = _normalize_for_radar(perf_a["kd_ratio"], perf_a["win_rate"], perf_a["accuracy"])
    values_b = _normalize_for_radar(perf_b["kd_ratio"], perf_b["win_rate"], perf_b["accuracy"])

    fig_radar = go.Figure()

    # Moyenne historique en fond (si disponible)
    hist_n = int((hist_avg or {}).get("session_count", 0) or 0)
    if hist_avg and hist_n >= 1:
        values_hist = _normalize_for_radar(
            hist_avg.get("kd_ratio"), hist_avg.get("win_rate"), hist_avg.get("accuracy")
        )
        suffix = " ⚠️" if hist_n < 3 else ""
        fig_radar.add_trace(
            go.Scatterpolar(
                r=values_hist + [values_hist[0]],
                theta=categories + [categories[0]],
                fill="toself",
                name=f"Moy. historique ({hist_n} sessions){suffix}",
                line_color=SESSION_COLORS["historical"],
                fillcolor=SESSION_COLORS["historical_fill"],
                line={"dash": "dot"},
            )
        )

    fig_radar.add_trace(
        go.Scatterpolar(
            r=values_a + [values_a[0]],  # Fermer le polygone
            theta=categories + [categories[0]],
            fill="toself",
            name="Session A",
            line_color=SESSION_COLORS["session_a"],
            fillcolor=SESSION_COLORS["session_a_fill"],
        )
    )

    fig_radar.add_trace(
        go.Scatterpolar(
            r=values_b + [values_b[0]],
            theta=categories + [categories[0]],
            fill="toself",
            name="Session B",
            line_color=SESSION_COLORS["session_b"],
            fillcolor=SESSION_COLORS["session_b_fill"],
        )
    )

    fig_radar.update_layout(
        polar={
            "radialaxis": {"visible": True, "range": [0, 100]},
            "bgcolor": "rgba(0,0,0,0)",
        },
        showlegend=True,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#E0E0E0"},
        height=400,
    )

    try:
        if fig_radar is not None:
            st.plotly_chart(fig_radar, width="stretch")
        else:
            st.info("Impossible de générer le radar de comparaison.")
    except Exception as e:
        st.warning(f"Impossible d'afficher le radar de comparaison : {e}")


# ════════════════════════════════════════════════════════════════════════════
# Graphique en barres comparatif
# ════════════════════════════════════════════════════════════════════════════


def _prepare_bar_metrics(
    perf_a: dict,
    perf_b: dict,
    hist_avg: dict | None = None,
) -> dict:
    """Prépare les données métriques pour le graphique en barres.

    Args:
        perf_a: Métriques de la session A.
        perf_b: Métriques de la session B.
        hist_avg: Moyenne historique (optionnel).

    Returns:
        Dict contenant les valeurs préparées pour A, B et l'historique.
    """

    def _per_match(total: float | int | None, matches: int | None) -> float:
        m = int(matches or 0)
        if m <= 0:
            return 0.0
        try:
            return float(total or 0.0) / float(m)
        except Exception:
            return 0.0

    left_metrics = ["Frags / partie", "Morts / partie", "Ratio F/D"]
    right_metric = "Victoire (%)"

    a_left = [
        _per_match(perf_a.get("kills"), perf_a.get("matches")),
        _per_match(perf_a.get("deaths"), perf_a.get("matches")),
        float(perf_a.get("kd_ratio") or 0.0),
    ]
    b_left = [
        _per_match(perf_b.get("kills"), perf_b.get("matches")),
        _per_match(perf_b.get("deaths"), perf_b.get("matches")),
        float(perf_b.get("kd_ratio") or 0.0),
    ]
    a_wr = float(perf_a.get("win_rate") or 0.0)
    b_wr = float(perf_b.get("win_rate") or 0.0)

    result: dict = {
        "left_metrics": left_metrics,
        "right_metric": right_metric,
        "a_left": a_left,
        "b_left": b_left,
        "a_wr": a_wr,
        "b_wr": b_wr,
    }

    hist_n = int((hist_avg or {}).get("session_count", 0) or 0)
    if hist_avg and hist_n >= 1:
        result["hist"] = {
            "h_left": [
                float(hist_avg.get("kills_per_match", 0) or 0.0),
                float(hist_avg.get("deaths_per_match", 0) or 0.0),
                float(hist_avg.get("kd_ratio", 0) or 0.0),
            ],
            "h_wr": float(hist_avg.get("win_rate", 0) or 0.0),
            "name": f"Moy. historique ({hist_n} sessions)" + (" ⚠️" if hist_n < 3 else ""),
        }

    return result


def _add_historical_traces(
    fig: go.Figure,
    metrics: dict,
    left_metrics: list[str],
    right_metric: str,
) -> None:
    """Ajoute les traces de la moyenne historique au graphique en barres."""
    h = metrics["hist"]
    hist_marker = {
        "color": SESSION_COLORS["historical"],
        "pattern": {"shape": ".", "fgcolor": "rgba(255,255,255,0.75)", "solidity": 0.10},
    }
    fig.add_trace(
        go.Bar(
            name=h["name"],
            x=left_metrics,
            y=h["h_left"],
            marker=hist_marker,
            opacity=0.45,
            hovertemplate="%{x} (moy. hist): %{y:.2f}<extra></extra>",
            legendgroup="H",
            showlegend=True,
        )
    )
    fig.add_trace(
        go.Bar(
            name=h["name"],
            x=[right_metric],
            y=[h["h_wr"]],
            marker=hist_marker,
            opacity=0.45,
            hovertemplate="%{x} (moy. hist): %{y:.1f}%<extra></extra>",
            legendgroup="H",
            showlegend=False,
            yaxis="y2",
        )
    )


def _build_bar_chart_figure(metrics: dict) -> go.Figure:
    """Construit la figure Plotly du graphique en barres comparatif.

    Args:
        metrics: Données préparées par _prepare_bar_metrics.

    Returns:
        Figure Plotly configurée.
    """
    left_metrics = metrics["left_metrics"]
    right_metric = metrics["right_metric"]

    fig_bar = go.Figure()

    # Axe gauche : frags/morts/ratio
    fig_bar.add_trace(
        go.Bar(
            name="Session A",
            x=left_metrics,
            y=metrics["a_left"],
            marker_color=SESSION_COLORS["session_a"],
            hovertemplate="%{x} (A): %{y:.2f}<extra></extra>",
            legendgroup="A",
            showlegend=True,
        )
    )
    fig_bar.add_trace(
        go.Bar(
            name="Session B",
            x=left_metrics,
            y=metrics["b_left"],
            marker_color=SESSION_COLORS["session_b"],
            hovertemplate="%{x} (B): %{y:.2f}<extra></extra>",
            legendgroup="B",
            showlegend=True,
        )
    )

    # Axe droit : victoire (%)
    fig_bar.add_trace(
        go.Bar(
            name="Session A",
            x=[right_metric],
            y=[metrics["a_wr"]],
            marker_color=SESSION_COLORS["session_a"],
            hovertemplate="%{x} (A): %{y:.1f}%<extra></extra>",
            legendgroup="A",
            showlegend=False,
            yaxis="y2",
        )
    )
    fig_bar.add_trace(
        go.Bar(
            name="Session B",
            x=[right_metric],
            y=[metrics["b_wr"]],
            marker_color=SESSION_COLORS["session_b"],
            hovertemplate="%{x} (B): %{y:.1f}%<extra></extra>",
            legendgroup="B",
            showlegend=False,
            yaxis="y2",
        )
    )

    # Ajouter la moyenne historique si disponible
    if "hist" in metrics:
        _add_historical_traces(fig_bar, metrics, left_metrics, right_metric)

    fig_bar.update_layout(
        barmode="group",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#E0E0E0"},
        xaxis={"showgrid": False},
        yaxis={
            "showgrid": True,
            "gridcolor": "rgba(255,255,255,0.1)",
            "title": "Par partie / Ratio",
        },
        yaxis2={
            "title": "Victoire (%)",
            "overlaying": "y",
            "side": "right",
            "showgrid": False,
            "rangemode": "tozero",
        },
        height=350,
    )

    return fig_bar


def render_comparison_bar_chart(
    perf_a: dict,
    perf_b: dict,
    hist_avg: dict | None = None,
) -> None:
    """Affiche le graphique en barres comparatif.

    Orchestre la préparation des métriques et la construction de la figure.

    Args:
        perf_a: Métriques de la session A.
        perf_b: Métriques de la session B.
        hist_avg: Moyenne historique des sessions similaires (optionnel).
    """
    metrics = _prepare_bar_metrics(perf_a, perf_b, hist_avg)
    try:
        fig = _build_bar_chart_figure(metrics)
        if fig is not None:
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("Données insuffisantes pour le graphique comparatif.")
    except Exception as e:
        st.warning(f"Impossible d'afficher le graphique comparatif : {e}")


# ════════════════════════════════════════════════════════════════════════════
# Tendance de participation (PersonalScores)
# ════════════════════════════════════════════════════════════════════════════


def render_participation_trend_section(
    df_session_a: DataFrameLike,
    df_session_b: DataFrameLike,
    db_path: str,
    xuid: str,
) -> None:
    """Affiche la tendance de participation entre deux sessions (Sprint 8.2).

    Utilise les PersonalScores pour montrer l'évolution du profil de jeu.

    Args:
        df_session_a: DataFrame de la session A.
        df_session_b: DataFrame de la session B.
        db_path: Chemin vers la base de données.
        xuid: XUID du joueur.
    """
    from src.data.repositories import DuckDBRepository

    df_session_a = ensure_polars(df_session_a)
    df_session_b = ensure_polars(df_session_b)

    try:
        repo = DuckDBRepository(db_path, xuid)
        if not repo.has_personal_score_awards():
            return  # Pas de données PersonalScores

        # Récupérer les match_ids de chaque session
        match_ids_a = (
            df_session_a.get_column("match_id").to_list() if not df_session_a.is_empty() else []
        )
        match_ids_b = (
            df_session_b.get_column("match_id").to_list() if not df_session_b.is_empty() else []
        )

        if not match_ids_a and not match_ids_b:
            return

        # Charger les données de participation
        df_a = (
            repo.load_personal_score_awards_as_polars(match_ids=match_ids_a)
            if match_ids_a
            else None
        )
        df_b = (
            repo.load_personal_score_awards_as_polars(match_ids=match_ids_b)
            if match_ids_b
            else None
        )

        if (df_a is None or df_a.is_empty()) and (df_b is None or df_b.is_empty()):
            return

        from src.ui.components.radar_chart import create_participation_profile_radar
        from src.visualization.participation_radar import (
            RADAR_AXIS_LINES,
            compute_participation_profile,
            get_radar_thresholds,
        )

        thresholds = get_radar_thresholds(db_path) if db_path else None

        def _match_row_from_df(dff: pl.DataFrame) -> dict | None:
            if dff.is_empty():
                return None
            return {
                "deaths": int(dff.get_column("deaths").sum()) if "deaths" in dff.columns else 0,
                "time_played_seconds": float(dff.get_column("time_played_seconds").sum())
                if "time_played_seconds" in dff.columns
                else 600.0 * len(dff),
                "pair_name": dff[0, "pair_name"]
                if "pair_name" in dff.columns and len(dff) > 0
                else None,
            }

        profiles = []

        if df_a is not None and not df_a.is_empty():
            match_row_a = _match_row_from_df(df_session_a)
            profile_a = compute_participation_profile(
                df_a,
                match_row=match_row_a,
                name="Session A",
                color=SESSION_COLORS["session_a"],
                pair_name=match_row_a.get("pair_name") if match_row_a else None,
                thresholds=thresholds,
            )
            profiles.append(profile_a)

        if df_b is not None and not df_b.is_empty():
            match_row_b = _match_row_from_df(df_session_b)
            profile_b = compute_participation_profile(
                df_b,
                match_row=match_row_b,
                name="Session B",
                color=SESSION_COLORS["session_b"],
                pair_name=match_row_b.get("pair_name") if match_row_b else None,
                thresholds=thresholds,
            )
            profiles.append(profile_b)

        if not profiles:
            return

        st.markdown("---")
        st.markdown("#### 🎯 Évolution du profil de participation")
        st.caption("Comparaison de la contribution au score entre les deux sessions")

        col_radar, col_legend = st.columns([2, 1])
        with col_radar:
            try:
                fig = create_participation_profile_radar(profiles, title="", height=380)
                if fig is not None:
                    st.plotly_chart(fig, width="stretch")
                else:
                    st.info("Impossible de générer le radar de participation.")
            except Exception as e:
                st.warning(f"Impossible d'afficher le radar de participation : {e}")
        with col_legend:
            st.markdown("**Axes**")
            for line in RADAR_AXIS_LINES:
                st.markdown(line)

    except Exception:
        pass  # Ne pas bloquer la page en cas d'erreur
