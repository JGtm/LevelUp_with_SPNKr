"""Page de comparaison de sessions.

Cette page permet de comparer les performances entre deux sessions de jeu,
avec des graphiques radar, des barres comparatives, et un tableau historique.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import plotly.graph_objects as go
import polars as pl

# Type alias pour compatibilité DataFrame
try:
    import pandas as pd

    DataFrameType = pd.DataFrame | pl.DataFrame
except ImportError:
    pd = None  # type: ignore[assignment]
    DataFrameType = pl.DataFrame  # type: ignore[misc]

import streamlit as st

from src.analysis.mode_categories import infer_custom_category_from_pair_name
from src.analysis.performance_score import compute_performance_series
from src.ui import translate_pair_name
from src.ui.components.performance import (
    compute_session_performance_score_v2_ui,
    get_score_class,
    render_metric_comparison_row,
    render_performance_score_card,
)
from src.visualization.performance import plot_cumulative_comparison

if TYPE_CHECKING:
    pass


_CATEGORY_FR: dict[str, str] = {
    "Assassin": "Assassin",
    "Fiesta": "Fiesta",
    "BTB": "Grande bataille en équipe",
    "Ranked": "Classé",
    "Firefight": "Baptême du feu",
    "Other": "Autre",
}


def _infer_session_dominant_category(df_session: pd.DataFrame) -> str:
    """Infère la catégorie dominante d'une session.

    On applique la catégorisation custom (alignée sidebar) à chaque match via
    `pair_name`, puis on prend la catégorie la plus fréquente.
    """
    if df_session.empty or "pair_name" not in df_session.columns:
        return "Other"

    cats = (
        df_session["pair_name"]
        .apply(infer_custom_category_from_pair_name)
        .fillna("Other")
        .astype(str)
    )
    if cats.empty:
        return "Other"

    vc = cats.value_counts()
    return str(vc.index[0]) if not vc.empty else "Other"


def _get_friends_names(df_session: pd.DataFrame) -> set[str]:
    """Récupère les noms/nicknames des amis présents dans une session.

    Utilise les aliases chargés en session_state si disponibles,
    sinon retourne les XUIDs tronqués.

    Args:
        df_session: DataFrame des matchs avec colonne friends_xuids.

    Returns:
        Set des noms d'amis (gamertags ou nicknames).
    """
    if df_session.empty or "friends_xuids" not in df_session.columns:
        return set()

    # Collecter tous les XUIDs des amis
    friends_xuids: set[str] = set()
    for friends_str in df_session["friends_xuids"].dropna():
        if friends_str:
            friends_xuids.update(friends_str.split(","))
    friends_xuids.discard("")

    if not friends_xuids:
        return set()

    # Charger les noms des amis depuis la DB si possible
    friends_mapping: dict[str, str] = {}

    # 1. Essayer depuis session_state (aliases chargés)
    aliases = st.session_state.get("xuid_aliases", {})

    # 2. Essayer de charger depuis la table Friends
    db_path = st.session_state.get("db_path")
    xuid = st.session_state.get("player_xuid")
    if db_path and xuid:
        try:
            # Détection du type de DB (DuckDB vs SQLite)
            if db_path.endswith(".duckdb"):
                # DuckDB : la table Friends peut ne pas exister
                import duckdb

                con = duckdb.connect(db_path, read_only=True)
                try:
                    # Vérifier si la table existe
                    tables = con.execute(
                        "SELECT table_name FROM information_schema.tables WHERE table_name = 'friends'"
                    ).fetchall()
                    if tables:
                        result = con.execute(
                            "SELECT friend_xuid, friend_gamertag, nickname FROM friends WHERE owner_xuid = ?",
                            (xuid,),
                        ).fetchall()
                        for row in result:
                            fxuid, gamertag, nickname = row
                            friends_mapping[fxuid] = nickname or gamertag or fxuid
                finally:
                    con.close()
            # SQLite legacy supprimé - DuckDB v4 uniquement
        except Exception:
            pass

    # Construire les noms
    names: set[str] = set()
    for xuid in friends_xuids:
        if xuid in friends_mapping:
            names.add(friends_mapping[xuid])
        elif xuid in aliases:
            names.add(aliases[xuid])
        else:
            # Garder le XUID tronqué comme fallback
            names.add(xuid[-6:] if len(xuid) > 6 else xuid)

    return names


def is_session_with_friends(df_session: pd.DataFrame) -> bool:
    """Détermine si une session est considérée comme 'avec amis'.

    Une session est avec amis si la majorité des matchs ont is_with_friends=True.

    Args:
        df_session: DataFrame des matchs d'une session.

    Returns:
        True si la majorité des matchs sont avec amis.
    """
    if df_session.empty:
        return False
    if "is_with_friends" not in df_session.columns:
        return False
    return df_session["is_with_friends"].sum() > len(df_session) / 2


def get_session_friends_signature(df_session: pd.DataFrame) -> set[str]:
    """Extrait l'ensemble des amis présents dans une session.

    Args:
        df_session: DataFrame des matchs d'une session.

    Returns:
        Set des XUIDs des amis présents (union de tous les matchs).
    """
    if df_session.empty or "friends_xuids" not in df_session.columns:
        return set()

    all_friends: set[str] = set()
    for friends_str in df_session["friends_xuids"].dropna():
        if friends_str:
            all_friends.update(friends_str.split(","))

    # Retirer les chaînes vides
    all_friends.discard("")
    return all_friends


def compute_similar_sessions_average(
    all_sessions_df: pd.DataFrame,
    is_with_friends: bool,
    exclude_session_ids: list[int] | None = None,
    same_friends_xuids: set[str] | None = None,
    mode_category: str | None = None,
) -> dict:
    """Calcule la moyenne des sessions similaires.

    Modes de comparaison :
    - Si same_friends_xuids est fourni : compare avec sessions ayant les MÊMES amis
    - Sinon : compare solo vs avec amis (n'importe lesquels)

    Args:
        all_sessions_df: DataFrame avec toutes les sessions.
        is_with_friends: True pour sessions avec amis, False pour solo.
        exclude_session_ids: Session IDs à exclure du calcul.
        same_friends_xuids: Si fourni, ne matcher que les sessions avec ces amis exacts.
        mode_category: Si fourni, ne garder que les sessions dont la catégorie dominante
            correspond (Assassin/Fiesta/BTB/Ranked/Firefight/Other).

    Returns:
        Dict avec kd_ratio, win_rate, accuracy, avg_life_seconds, session_count, etc.
    """
    if all_sessions_df.empty or "session_id" not in all_sessions_df.columns:
        return {}

    exclude_ids = set(exclude_session_ids or [])

    # Filtrer les sessions exclues
    df = all_sessions_df[~all_sessions_df["session_id"].isin(exclude_ids)].copy()
    if df.empty:
        return {}

    # Mode "mêmes amis" : matcher les sessions avec exactement les mêmes amis
    # NOTE: Si la colonne `is_with_friends` n'existe pas, on ne peut pas faire
    # de comparaison solo/amis. Dans ce cas, on considère "toutes sessions".
    if "is_with_friends" not in df.columns:
        matching_session_ids = df["session_id"].dropna().unique().tolist()
    elif same_friends_xuids and len(same_friends_xuids) > 0:
        matching_session_ids = []
        for session_id, group in df.groupby("session_id"):
            session_friends = get_session_friends_signature(group)
            # Match si au moins les mêmes amis sont présents (peut avoir plus)
            if same_friends_xuids <= session_friends:
                matching_session_ids.append(session_id)
    else:
        # Mode "solo vs avec amis" classique
        session_friend_ratio = df.groupby("session_id")["is_with_friends"].mean()
        matching_session_ids = session_friend_ratio[
            (session_friend_ratio > 0.5) == is_with_friends
        ].index.tolist()

    if len(matching_session_ids) == 0:
        return {}

    # Filtrer par catégorie dominante si demandée (nécessite pair_name dans le DataFrame)
    if mode_category and "pair_name" in df.columns:
        df_candidates = df[df["session_id"].isin(matching_session_ids)].copy()
        if df_candidates.empty:
            return {}

        dom_by_session = (
            df_candidates.assign(
                _cat=df_candidates["pair_name"].apply(infer_custom_category_from_pair_name)
            )
            .groupby("session_id")["_cat"]
            .apply(lambda s: s.value_counts().index[0] if len(s) else "Other")
        )

        matching_session_ids = [
            sid for sid in matching_session_ids if dom_by_session.get(sid) == mode_category
        ]
        if len(matching_session_ids) == 0:
            return {}

    # Filtrer les matchs des sessions correspondantes
    df_matching = df[df["session_id"].isin(matching_session_ids)]

    if df_matching.empty:
        return {}

    session_count = len(matching_session_ids)

    # Calculs agrégés directs sur le DataFrame (beaucoup plus rapide)
    total_kills = df_matching["kills"].sum()
    total_deaths = df_matching["deaths"].sum()
    total_assists = df_matching["assists"].sum()
    total_matches = len(df_matching)

    # K/D ratio moyen par session
    agg_spec: dict[str, object] = {
        "kills": "sum",
        "deaths": "sum",
        "assists": "sum",
        "outcome": lambda x: (x == 2).sum() / len(x) * 100 if len(x) > 0 else 0,
        "average_life_seconds": "mean",
    }
    acc_col: str | None = None
    if "accuracy" in df_matching.columns:
        acc_col = "accuracy"
    elif "shots_accuracy" in df_matching.columns:
        acc_col = "shots_accuracy"
    if acc_col:
        agg_spec[acc_col] = "mean"

    session_stats = (
        df_matching.groupby("session_id").agg(agg_spec).rename(columns={"outcome": "win_rate"})
    )

    # Calculer K/D par session puis moyenne
    session_stats["kd_ratio"] = session_stats.apply(
        lambda r: r["kills"] / r["deaths"] if r["deaths"] > 0 else r["kills"], axis=1
    )

    avg_kd = session_stats["kd_ratio"].mean()
    avg_win_rate = session_stats["win_rate"].mean()
    avg_life = session_stats["average_life_seconds"].mean()
    avg_accuracy = (
        session_stats[acc_col].mean() if acc_col and acc_col in session_stats.columns else None
    )

    return {
        "kd_ratio": avg_kd,
        "win_rate": avg_win_rate,
        "accuracy": avg_accuracy,
        "avg_life_seconds": avg_life,
        "kills_per_match": total_kills / total_matches if total_matches > 0 else 0,
        "deaths_per_match": total_deaths / total_matches if total_matches > 0 else 0,
        "assists_per_match": total_assists / total_matches if total_matches > 0 else 0,
        "session_count": session_count,
    }


def _format_seconds_to_mmss(seconds) -> str:
    """Formate des secondes en mm:ss ou retourne la valeur formatée."""
    if seconds is None:
        return "—"
    try:
        total = int(round(float(seconds)))
        if total < 0:
            return "—"
        m, s = divmod(total, 60)
        return f"{m}:{s:02d}"
    except Exception:
        return "—"


def _format_date_with_weekday(dt) -> str:
    """Formate une date avec jour de la semaine abrégé : lun. 12/01/26 14:30."""
    if dt is None or pd.isna(dt):
        return "-"
    try:
        # Jours en français
        weekdays_fr = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]
        wd = weekdays_fr[dt.weekday()]
        return f"{wd} {dt.strftime('%d/%m/%y %H:%M')}"
    except Exception:
        return "-"


def _outcome_class(label: str) -> str:
    """Retourne la classe CSS pour un résultat."""
    v = str(label or "").strip().casefold()
    if v.startswith("victoire"):
        return "text-win"
    if v.startswith("défaite") or v.startswith("defaite"):
        return "text-loss"
    if v.startswith("égalité") or v.startswith("egalite"):
        return "text-tie"
    if v.startswith("non"):
        return "text-nf"
    return ""


def render_session_history_table(
    df_sess: pd.DataFrame,
    session_name: str,
    df_full: pd.DataFrame | None = None,
) -> None:
    """Affiche le tableau historique d'une session.

    Args:
        df_sess: DataFrame de la session.
        session_name: Nom de la session pour les messages.
        df_full: DataFrame complet pour le calcul du score relatif.
    """
    if df_sess.empty:
        st.info(f"Aucune partie dans {session_name}.")
        return

    # Copie pour éviter les warnings pandas
    df_sess = df_sess.copy()

    # Traduire le mode si non traduit
    if "pair_fr" not in df_sess.columns and "pair_name" in df_sess.columns:
        df_sess["pair_fr"] = df_sess["pair_name"].apply(translate_pair_name)

    # Préparer les colonnes à afficher
    display_cols = []
    col_map = {}

    if "start_time" in df_sess.columns:
        df_sess["Heure"] = df_sess["start_time"].apply(_format_date_with_weekday)
        display_cols.append("Heure")

    if "pair_fr" in df_sess.columns:
        col_map["pair_fr"] = "Mode"
        display_cols.append("pair_fr")
    elif "pair_name" in df_sess.columns:
        # Traduire à la volée si pair_fr n'existe pas
        df_sess["mode_traduit"] = df_sess["pair_name"].apply(translate_pair_name)
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
        outcome_map = {2: "Victoire", 3: "Défaite", 1: "Égalité", 4: "Non terminé"}
        df_sess["Résultat"] = df_sess["outcome"].map(outcome_map).fillna("-")
        display_cols.append("Résultat")

    # Colonne Performance RELATIVE (après Résultat)
    history_df = df_full if df_full is not None else df_sess
    df_sess["Performance"] = compute_performance_series(df_sess, history_df)
    df_sess["Perf_display"] = df_sess["Performance"].apply(
        lambda x: f"{x:.0f}" if pd.notna(x) else "-"
    )
    display_cols.append("Perf_display")
    col_map["Perf_display"] = "Performance"

    if "team_mmr" in df_sess.columns:
        df_sess["MMR Équipe"] = df_sess["team_mmr"].apply(
            lambda x: f"{x:.0f}" if pd.notna(x) else "-"
        )
        display_cols.append("MMR Équipe")

    if "enemy_mmr" in df_sess.columns:
        df_sess["MMR Adverse"] = df_sess["enemy_mmr"].apply(
            lambda x: f"{x:.0f}" if pd.notna(x) else "-"
        )
        display_cols.append("MMR Adverse")

    # Renommer les colonnes
    df_display = df_sess[display_cols].copy()
    df_display = df_display.rename(columns=col_map)

    # Garder les scores de performance pour la coloration
    perf_scores = df_sess["Performance"].values if "Performance" in df_sess.columns else None

    # Trier par heure (conserver l'ordre chronologique via start_time)
    if "start_time" in df_sess.columns:
        sort_indices = df_sess["start_time"].argsort().values
        df_display = df_display.iloc[sort_indices]
        if perf_scores is not None:
            perf_scores = perf_scores[sort_indices]

    # Affichage HTML pour styliser les résultats
    import html as html_lib

    html_rows = []
    for idx, (_, row) in enumerate(df_display.iterrows()):
        cells = []
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


# Couleurs distinctes pour les sessions (contraste élevé, accessible daltoniens)
SESSION_COLORS = {
    "session_a": "#E74C3C",  # Rouge corail
    "session_a_fill": "rgba(231, 76, 60, 0.3)",
    "session_b": "#3498DB",  # Bleu vif
    "session_b_fill": "rgba(52, 152, 219, 0.3)",
    "historical": "#9B59B6",  # Violet
    "historical_fill": "rgba(155, 89, 182, 0.2)",
}


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

    st.plotly_chart(fig_radar, width="stretch")


def render_comparison_bar_chart(
    perf_a: dict,
    perf_b: dict,
    hist_avg: dict | None = None,
) -> None:
    """Affiche le graphique en barres comparatif.

    Args:
        perf_a: Métriques de la session A.
        perf_b: Métriques de la session B.
        hist_avg: Moyenne historique des sessions similaires (optionnel).
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

    fig_bar = go.Figure()

    # Axe gauche : frags/morts/ratio
    fig_bar.add_trace(
        go.Bar(
            name="Session A",
            x=left_metrics,
            y=a_left,
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
            y=b_left,
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
            y=[a_wr],
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
            y=[b_wr],
            marker_color=SESSION_COLORS["session_b"],
            hovertemplate="%{x} (B): %{y:.1f}%<extra></extra>",
            legendgroup="B",
            showlegend=False,
            yaxis="y2",
        )
    )

    # Ajouter la moyenne historique si disponible
    hist_n = int((hist_avg or {}).get("session_count", 0) or 0)
    if hist_avg and hist_n >= 1:
        h_left = [
            float(hist_avg.get("kills_per_match", 0) or 0.0),
            float(hist_avg.get("deaths_per_match", 0) or 0.0),
            float(hist_avg.get("kd_ratio", 0) or 0.0),
        ]
        h_wr = float(hist_avg.get("win_rate", 0) or 0.0)

        name = f"Moy. historique ({hist_n} sessions)" + (" ⚠️" if hist_n < 3 else "")
        hist_marker = {
            "color": SESSION_COLORS["historical"],
            "pattern": {"shape": ".", "fgcolor": "rgba(255,255,255,0.75)", "solidity": 0.10},
        }

        fig_bar.add_trace(
            go.Bar(
                name=name,
                x=left_metrics,
                y=h_left,
                marker=hist_marker,
                opacity=0.45,
                hovertemplate="%{x} (moy. hist): %{y:.2f}<extra></extra>",
                legendgroup="H",
                showlegend=True,
            )
        )
        fig_bar.add_trace(
            go.Bar(
                name=name,
                x=[right_metric],
                y=[h_wr],
                marker=hist_marker,
                opacity=0.45,
                hovertemplate="%{x} (moy. hist): %{y:.1f}%<extra></extra>",
                legendgroup="H",
                showlegend=False,
                yaxis="y2",
            )
        )

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

    st.plotly_chart(fig_bar, width="stretch")


def render_participation_trend_section(
    df_session_a: pd.DataFrame,
    df_session_b: pd.DataFrame,
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

    try:
        repo = DuckDBRepository(db_path, xuid)
        if not repo.has_personal_score_awards():
            return  # Pas de données PersonalScores

        # Récupérer les match_ids de chaque session
        match_ids_a = df_session_a["match_id"].tolist() if not df_session_a.empty else []
        match_ids_b = df_session_b["match_id"].tolist() if not df_session_b.empty else []

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

        def _match_row_from_df(dff: pd.DataFrame) -> dict | None:
            if dff.empty:
                return None
            return {
                "deaths": int(dff["deaths"].sum()) if "deaths" in dff.columns else 0,
                "time_played_seconds": float(dff["time_played_seconds"].sum())
                if "time_played_seconds" in dff.columns
                else 600.0 * len(dff),
                "pair_name": dff["pair_name"].iloc[0]
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
            fig = create_participation_profile_radar(profiles, title="", height=380)
            st.plotly_chart(fig, width="stretch")
        with col_legend:
            st.markdown("**Axes**")
            for line in RADAR_AXIS_LINES:
                st.markdown(line)

    except Exception:
        pass  # Ne pas bloquer la page en cas d'erreur


def render_session_comparison_page(
    all_sessions_df: pd.DataFrame,
    df_full: pd.DataFrame | None = None,
    *,
    db_path: str | None = None,
    xuid: str | None = None,
) -> None:
    """Rend la page de comparaison de sessions.

    Args:
        all_sessions_df: DataFrame avec toutes les sessions (colonnes session_id, session_label).
        df_full: DataFrame complet pour le calcul du score relatif.
        db_path: Chemin vers la base de données (optionnel, récupéré depuis session_state).
        xuid: XUID du joueur (optionnel, récupéré depuis session_state).
    """
    # Récupérer db_path et xuid depuis session_state si non fournis
    if db_path is None:
        db_path = st.session_state.get("db_path", "")
    if xuid is None:
        xuid = st.session_state.get("xuid", "")
    st.caption("Compare les performances entre deux sessions de jeu.")

    if all_sessions_df.empty:
        st.info("Aucune session disponible.")
        return

    # Liste des sessions triées (plus récente en premier)
    session_info = (
        all_sessions_df.groupby(["session_id", "session_label"])
        .size()
        .reset_index(name="count")
        .sort_values("session_id", ascending=False)
    )
    session_labels = session_info["session_label"].tolist()

    if len(session_labels) < 2:
        st.warning("Il faut au moins 2 sessions pour comparer.")
        return

    # Sélecteurs de sessions
    col_sel_a, col_sel_b = st.columns(2)
    with col_sel_a:
        # Session A = avant-dernière par défaut
        default_a = session_labels[1] if len(session_labels) > 1 else session_labels[0]
        session_a_label = st.selectbox(
            "Session A (référence)",
            options=session_labels,
            index=session_labels.index(default_a) if default_a in session_labels else 1,
            key="compare_session_a",
        )
    with col_sel_b:
        # Session B = dernière par défaut
        session_b_label = st.selectbox(
            "Session B (à comparer)",
            options=session_labels,
            index=0,
            key="compare_session_b",
        )

    # Filtrer les DataFrames
    df_session_a = all_sessions_df[all_sessions_df["session_label"] == session_a_label].copy()
    df_session_b = all_sessions_df[all_sessions_df["session_label"] == session_b_label].copy()

    # Calculer les scores de performance (v2)
    perf_a = compute_session_performance_score_v2_ui(df_session_a)
    perf_b = compute_session_performance_score_v2_ui(df_session_b)

    # ══════════════════════════════════════════════════════════════════════════
    # Calcul de la moyenne historique des sessions similaires
    # ══════════════════════════════════════════════════════════════════════════
    # Récupérer les session_ids à exclure
    session_a_id = (
        df_session_a["session_id"].iloc[0]
        if not df_session_a.empty and "session_id" in df_session_a.columns
        else None
    )
    session_b_id = (
        df_session_b["session_id"].iloc[0]
        if not df_session_b.empty and "session_id" in df_session_b.columns
        else None
    )
    exclude_ids = [sid for sid in [session_a_id, session_b_id] if sid is not None]

    # Déterminer le type de session (solo vs avec amis) - basé sur la session B (celle qu'on compare)
    has_with_friends_col = "is_with_friends" in all_sessions_df.columns
    session_b_with_friends = (
        is_session_with_friends(df_session_b) if has_with_friends_col else False
    )
    session_b_friends = (
        get_session_friends_signature(df_session_b) if has_with_friends_col else set()
    )
    session_b_category = _infer_session_dominant_category(df_session_b)

    # Option de comparaison : mêmes amis vs solo/avec amis
    compare_mode = "same_friends"  # Par défaut : mêmes amis si possible
    if not has_with_friends_col:
        # Fallback: pas d'info amis => comparer sur toutes les sessions
        hist_avg = compute_similar_sessions_average(
            all_sessions_df,
            is_with_friends=False,
            exclude_session_ids=exclude_ids,
            mode_category=session_b_category,
        )
        compare_mode = "all"
    elif session_b_with_friends and len(session_b_friends) > 0:
        # Essayer d'abord avec les mêmes amis
        hist_avg = compute_similar_sessions_average(
            all_sessions_df,
            is_with_friends=True,
            exclude_session_ids=exclude_ids,
            same_friends_xuids=session_b_friends,
            mode_category=session_b_category,
        )

        # Si pas assez de sessions avec les mêmes amis, fallback sur "avec amis"
        if hist_avg.get("session_count", 0) < 3:
            hist_avg = compute_similar_sessions_average(
                all_sessions_df,
                is_with_friends=True,
                exclude_session_ids=exclude_ids,
                same_friends_xuids=None,  # N'importe quels amis
                mode_category=session_b_category,
            )
            compare_mode = "any_friends"
    else:
        # Solo : comparer avec autres sessions solo
        hist_avg = compute_similar_sessions_average(
            all_sessions_df,
            is_with_friends=False,
            exclude_session_ids=exclude_ids,
            mode_category=session_b_category,
        )
        compare_mode = "solo"

    # Construire le label du type de session
    if not has_with_friends_col:
        session_type_label = "(amis indisponibles) 🎮"
        compare_label = (
            f"toutes sessions ({hist_avg.get('session_count', 0)} sessions)"
            f" — catégorie {_CATEGORY_FR.get(session_b_category, session_b_category)}"
        )
    elif session_b_with_friends and len(session_b_friends) > 0:
        # Récupérer les gamertags des amis (depuis la table Friends si possible)
        friends_names = _get_friends_names(df_session_b)
        if friends_names:
            friends_display = ", ".join(sorted(friends_names))
            session_type_label = f"avec {friends_display} 👥"
        else:
            session_type_label = f"avec {len(session_b_friends)} ami(s) 👥"

        if compare_mode == "same_friends":
            compare_label = (
                f"mêmes amis ({hist_avg.get('session_count', 0)} sessions)"
                f" — catégorie {_CATEGORY_FR.get(session_b_category, session_b_category)}"
            )
        else:
            compare_label = (
                f"sessions avec amis ({hist_avg.get('session_count', 0)} sessions)"
                f" — catégorie {_CATEGORY_FR.get(session_b_category, session_b_category)}"
            )
    else:
        session_type_label = "solo 🎮"
        compare_label = (
            f"sessions solo ({hist_avg.get('session_count', 0)} sessions)"
            f" — catégorie {_CATEGORY_FR.get(session_b_category, session_b_category)}"
        )

    # Déterminer qui est meilleur
    score_a = perf_a.get("score")
    score_b = perf_b.get("score")
    is_b_better = None
    if score_a is not None and score_b is not None:
        if score_b > score_a:
            is_b_better = True
        elif score_b < score_a:
            is_b_better = False

    # ══════════════════════════════════════════════════════════════════════════
    # Grandes cartes de score côte à côte
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("### 🏆 Score de performance")
    col_score_a, col_score_b = st.columns(2)
    with col_score_a:
        render_performance_score_card(
            "Session A",
            perf_a,
            is_better=not is_b_better if is_b_better is not None else None,
        )
    with col_score_b:
        render_performance_score_card("Session B", perf_b, is_better=is_b_better)

    st.markdown("---")

    # ══════════════════════════════════════════════════════════════════════════
    # Colonnes Session A / Session B avec métriques détaillées
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("### 📊 Métriques détaillées")

    # En-têtes
    col_h1, col_h2, col_h3 = st.columns([2, 1, 1])
    with col_h1:
        st.markdown("**Métrique**")
    with col_h2:
        st.markdown("**Session A**")
    with col_h3:
        st.markdown("**Session B**")

    st.markdown("---")

    render_metric_comparison_row("Nombre de parties", perf_a["matches"], perf_b["matches"], "{}")
    render_metric_comparison_row(
        "FDA (Frags-Décès-Assists)", perf_a["kda"], perf_b["kda"], "{:.2f}"
    )
    render_metric_comparison_row(
        "Taux de victoire", perf_a["win_rate"], perf_b["win_rate"], "{:.1f}%"
    )
    render_metric_comparison_row(
        "Durée de vie moyenne",
        perf_a["avg_life_seconds"],
        perf_b["avg_life_seconds"],
        _format_seconds_to_mmss,
    )

    st.markdown("---")

    render_metric_comparison_row("Total des frags", perf_a["kills"], perf_b["kills"], "{}")
    render_metric_comparison_row(
        "Total des morts", perf_a["deaths"], perf_b["deaths"], "{}", higher_is_better=False
    )
    render_metric_comparison_row(
        "Total des assistances", perf_a["assists"], perf_b["assists"], "{}"
    )

    # ══════════════════════════════════════════════════════════════════════════
    # Comparaison MMR
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("### 🎯 Comparaison MMR")

    col_mmr1, col_mmr2, col_mmr3 = st.columns([2, 1, 1])
    with col_mmr1:
        st.markdown("**Métrique MMR**")
    with col_mmr2:
        st.markdown("**Session A**")
    with col_mmr3:
        st.markdown("**Session B**")

    render_metric_comparison_row(
        "MMR équipe (moy)", perf_a["team_mmr_avg"], perf_b["team_mmr_avg"], "{:.1f}"
    )
    render_metric_comparison_row(
        "MMR adverse (moy)",
        perf_a["enemy_mmr_avg"],
        perf_b["enemy_mmr_avg"],
        "{:.1f}",
        higher_is_better=False,
    )
    render_metric_comparison_row(
        "Écart MMR (moy)", perf_a["delta_mmr_avg"], perf_b["delta_mmr_avg"], "{:+.1f}"
    )

    # ══════════════════════════════════════════════════════════════════════════
    # Graphiques comparatifs (côte à côte)
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("---")

    # Afficher l'indicateur du type de session et la moyenne historique
    if hist_avg and hist_avg.get("session_count", 0) >= 1:
        st.markdown(
            f"### 📈 Graphiques comparatifs\n"
            f"*Session {session_type_label} — Moyenne historique : {compare_label}*"
        )
    else:
        st.markdown(f"### 📈 Graphiques comparatifs\n*Session {session_type_label}*")

    col_radar, col_bars = st.columns(2)

    with col_radar:
        st.markdown("#### Vue radar")
        render_comparison_radar_chart(perf_a, perf_b, hist_avg=hist_avg)

    with col_bars:
        st.markdown("#### Comparaison par métrique")
        render_comparison_bar_chart(perf_a, perf_b, hist_avg=hist_avg)

    # ══════════════════════════════════════════════════════════════════════════
    # Net score cumulé par session (Sprint 6)
    # ══════════════════════════════════════════════════════════════════════════
    _req = ["start_time", "kills", "deaths"]
    if all(c in df_session_a.columns for c in _req) and all(
        c in df_session_b.columns for c in _req
    ):
        try:
            pl_a = pl.from_pandas(df_session_a.sort_values("start_time")[_req].copy())
            pl_b = pl.from_pandas(df_session_b.sort_values("start_time")[_req].copy())
            if not pl_a.is_empty() and not pl_b.is_empty():
                st.markdown("#### Net score cumulé par session")
                st.caption(
                    "Évolution du net score (Frags − Deaths) au fil des matchs de chaque session."
                )
                st.plotly_chart(
                    plot_cumulative_comparison(
                        pl_a,
                        pl_b,
                        label_a=session_a_label,
                        label_b=session_b_label,
                        title="",
                    ),
                    width="stretch",
                )
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════════
    # Tendance de participation (PersonalScores) - Sprint 8.2
    # ══════════════════════════════════════════════════════════════════════════
    render_participation_trend_section(
        df_session_a=df_session_a,
        df_session_b=df_session_b,
        db_path=db_path,
        xuid=xuid,
    )

    # ══════════════════════════════════════════════════════════════════════════
    # Tableau historique des parties
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("### 📋 Historique des parties")

    tab_hist_a, tab_hist_b = st.tabs(["Session A", "Session B"])

    with tab_hist_a:
        render_session_history_table(df_session_a, "Session A", df_full=df_full)

    with tab_hist_b:
        render_session_history_table(df_session_b, "Session B", df_full=df_full)
