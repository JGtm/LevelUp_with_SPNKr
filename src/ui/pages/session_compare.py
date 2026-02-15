"""Page de comparaison de sessions."""

from __future__ import annotations

import polars as pl
import streamlit as st

from src.analysis.mode_categories import infer_custom_category_from_pair_name
from src.ui.components.performance import (
    compute_session_performance_score_v2_ui,
    render_metric_comparison_row,
    render_performance_score_card,
)
from src.visualization._compat import (
    DataFrameLike,
    ensure_polars,
)
from src.visualization.performance import plot_cumulative_comparison

_CATEGORY_FR: dict[str, str] = {
    "Assassin": "Assassin",
    "Fiesta": "Fiesta",
    "BTB": "Grande bataille en équipe",
    "Ranked": "Classé",
    "Firefight": "Baptême du feu",
    "Other": "Autre",
}


def _infer_session_dominant_category(df_session: DataFrameLike) -> str:
    """Infère la catégorie dominante d'une session.

    On applique la catégorisation custom (alignée sidebar) à chaque match via
    `pair_name`, puis on prend la catégorie la plus fréquente.
    """
    df_session = ensure_polars(df_session)
    if df_session.is_empty() or "pair_name" not in df_session.columns:
        return "Other"

    cats = (
        df_session.get_column("pair_name")
        .map_elements(infer_custom_category_from_pair_name, return_dtype=pl.Utf8)
        .fill_null("Other")
        .alias("category")
    )
    if cats.is_empty():
        return "Other"

    vc = cats.value_counts().sort("count", descending=True)
    return str(vc[0, "category"]) if not vc.is_empty() else "Other"


def _get_friends_names(df_session: DataFrameLike) -> set[str]:
    """Récupère les noms/nicknames des amis présents dans une session.

    Utilise les aliases chargés en session_state si disponibles,
    sinon retourne les XUIDs tronqués.

    Args:
        df_session: DataFrame des matchs avec colonne friends_xuids.

    Returns:
        Set des noms d'amis (gamertags ou nicknames).
    """
    df_session = ensure_polars(df_session)
    if df_session.is_empty() or "friends_xuids" not in df_session.columns:
        return set()

    # Collecter tous les XUIDs des amis
    friends_xuids: set[str] = set()
    for friends_str in df_session.get_column("friends_xuids").drop_nulls().to_list():
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


def is_session_with_friends(df_session: DataFrameLike) -> bool:
    """Détermine si une session est considérée comme 'avec amis'.

    Une session est avec amis si la majorité des matchs ont is_with_friends=True.

    Args:
        df_session: DataFrame des matchs d'une session.

    Returns:
        True si la majorité des matchs sont avec amis.
    """
    df_session = ensure_polars(df_session)
    if df_session.is_empty():
        return False
    if "is_with_friends" not in df_session.columns:
        return False
    return df_session.get_column("is_with_friends").sum() > len(df_session) / 2


def get_session_friends_signature(df_session: DataFrameLike) -> set[str]:
    """Extrait l'ensemble des amis présents dans une session.

    Args:
        df_session: DataFrame des matchs d'une session.

    Returns:
        Set des XUIDs des amis présents (union de tous les matchs).
    """
    df_session = ensure_polars(df_session)
    if df_session.is_empty() or "friends_xuids" not in df_session.columns:
        return set()

    all_friends: set[str] = set()
    for friends_str in df_session.get_column("friends_xuids").drop_nulls().to_list():
        if friends_str:
            all_friends.update(friends_str.split(","))

    # Retirer les chaînes vides
    all_friends.discard("")
    return all_friends


def _filter_candidate_sessions(
    all_sessions_df: DataFrameLike,
    is_with_friends: bool,
    exclude_session_ids: list[int] | None = None,
    same_friends_xuids: set[str] | None = None,
    mode_category: str | None = None,
) -> list:
    """Filtre les sessions candidates pour la comparaison historique."""
    all_sessions_df = ensure_polars(all_sessions_df)
    if all_sessions_df.is_empty() or "session_id" not in all_sessions_df.columns:
        return []

    exclude_ids = list(set(exclude_session_ids or []))

    # Filtrer les sessions exclues
    df = all_sessions_df.filter(~pl.col("session_id").is_in(exclude_ids))
    if df.is_empty():
        return []

    # Mode "mêmes amis" : matcher les sessions avec exactement les mêmes amis
    # NOTE: Si la colonne `is_with_friends` n'existe pas, on ne peut pas faire
    # de comparaison solo/amis. Dans ce cas, on considère "toutes sessions".
    if "is_with_friends" not in df.columns:
        matching_session_ids = df.get_column("session_id").drop_nulls().unique().to_list()
    elif same_friends_xuids and len(same_friends_xuids) > 0:
        matching_session_ids = []
        for group_df in df.partition_by("session_id", maintain_order=True):
            session_id = group_df[0, "session_id"]
            session_friends = get_session_friends_signature(group_df)
            # Match si au moins les mêmes amis sont présents (peut avoir plus)
            if same_friends_xuids <= session_friends:
                matching_session_ids.append(session_id)
    else:
        # Mode "solo vs avec amis" classique
        session_agg = df.group_by("session_id").agg(
            pl.col("is_with_friends").mean().alias("friend_ratio")
        )
        if is_with_friends:
            matching_session_ids = (
                session_agg.filter(pl.col("friend_ratio") > 0.5).get_column("session_id").to_list()
            )
        else:
            matching_session_ids = (
                session_agg.filter(pl.col("friend_ratio") <= 0.5).get_column("session_id").to_list()
            )

    if len(matching_session_ids) == 0:
        return []

    # Filtrer par catégorie dominante si demandée (nécessite pair_name dans le DataFrame)
    if mode_category and "pair_name" in df.columns:
        df_candidates = df.filter(pl.col("session_id").is_in(matching_session_ids))
        if df_candidates.is_empty():
            return []

        df_candidates = df_candidates.with_columns(
            pl.col("pair_name")
            .map_elements(infer_custom_category_from_pair_name, return_dtype=pl.Utf8)
            .alias("_cat")
        )
        dom_by_session: dict = {}
        for group_df in df_candidates.partition_by("session_id", maintain_order=True):
            sid = group_df[0, "session_id"]
            vc = group_df.get_column("_cat").value_counts().sort("count", descending=True)
            dom_by_session[sid] = str(vc[0, "_cat"]) if not vc.is_empty() else "Other"

        matching_session_ids = [
            sid for sid in matching_session_ids if dom_by_session.get(sid) == mode_category
        ]

    return matching_session_ids


def _aggregate_session_stats(
    df_matching: DataFrameLike,
    matching_session_ids: list,
) -> dict:
    """Agrège les statistiques des sessions filtrées."""
    df_matching = ensure_polars(df_matching)
    if df_matching.is_empty():
        return {}

    session_count = len(matching_session_ids)

    # Calculs agrégés directs sur le DataFrame (beaucoup plus rapide)
    total_kills = df_matching.get_column("kills").sum()
    total_deaths = df_matching.get_column("deaths").sum()
    total_assists = df_matching.get_column("assists").sum()
    total_matches = len(df_matching)

    # K/D ratio moyen par session
    agg_exprs: list = [
        pl.col("kills").sum(),
        pl.col("deaths").sum(),
        pl.col("assists").sum(),
        ((pl.col("outcome") == 2).sum().cast(pl.Float64) / pl.len().cast(pl.Float64) * 100).alias(
            "win_rate"
        ),
        pl.col("average_life_seconds").mean(),
    ]
    acc_col: str | None = None
    if "accuracy" in df_matching.columns:
        acc_col = "accuracy"
    elif "shots_accuracy" in df_matching.columns:
        acc_col = "shots_accuracy"
    if acc_col:
        agg_exprs.append(pl.col(acc_col).mean())

    session_stats = df_matching.group_by("session_id").agg(agg_exprs)

    # Calculer K/D par session puis moyenne
    session_stats = session_stats.with_columns(
        pl.when(pl.col("deaths") > 0)
        .then(pl.col("kills").cast(pl.Float64) / pl.col("deaths").cast(pl.Float64))
        .otherwise(pl.col("kills").cast(pl.Float64))
        .alias("kd_ratio")
    )

    avg_kd = session_stats.get_column("kd_ratio").mean()
    avg_win_rate = session_stats.get_column("win_rate").mean()
    avg_life = session_stats.get_column("average_life_seconds").mean()
    avg_accuracy = (
        session_stats.get_column(acc_col).mean()
        if acc_col and acc_col in session_stats.columns
        else None
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


def compute_similar_sessions_average(
    all_sessions_df: DataFrameLike,
    is_with_friends: bool,
    exclude_session_ids: list[int] | None = None,
    same_friends_xuids: set[str] | None = None,
    mode_category: str | None = None,
) -> dict:
    """Calcule la moyenne des sessions similaires (orchestre filtrage + agrégation)."""
    all_sessions_df = ensure_polars(all_sessions_df)
    matching_session_ids = _filter_candidate_sessions(
        all_sessions_df,
        is_with_friends,
        exclude_session_ids,
        same_friends_xuids,
        mode_category,
    )
    if not matching_session_ids:
        return {}

    exclude_ids = list(set(exclude_session_ids or []))
    df = all_sessions_df.filter(~pl.col("session_id").is_in(exclude_ids))
    df_matching = df.filter(pl.col("session_id").is_in(matching_session_ids))

    return _aggregate_session_stats(df_matching, matching_session_ids)


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
    if dt is None:
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


def _select_sessions(session_labels: list[str]) -> tuple[str, str]:
    """Affiche les sélecteurs de sessions A et B et retourne les labels choisis."""
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
    return session_a_label, session_b_label


def _compute_historical_context(
    all_sessions_df: DataFrameLike,
    df_session_b: DataFrameLike,
    exclude_ids: list,
    session_b_category: str,
) -> tuple[dict, str]:
    """Calcule la moyenne historique des sessions similaires.

    Returns:
        Tuple (hist_avg dict, compare_mode string).
    """
    has_with_friends_col = "is_with_friends" in all_sessions_df.columns
    session_b_with_friends = (
        is_session_with_friends(df_session_b) if has_with_friends_col else False
    )
    session_b_friends = (
        get_session_friends_signature(df_session_b) if has_with_friends_col else set()
    )

    if not has_with_friends_col:
        # Fallback: pas d'info amis => comparer sur toutes les sessions
        hist_avg = compute_similar_sessions_average(
            all_sessions_df,
            is_with_friends=False,
            exclude_session_ids=exclude_ids,
            mode_category=session_b_category,
        )
        return hist_avg, "all"

    if session_b_with_friends and len(session_b_friends) > 0:
        # Essayer d'abord avec les mêmes amis
        hist_avg = compute_similar_sessions_average(
            all_sessions_df,
            is_with_friends=True,
            exclude_session_ids=exclude_ids,
            same_friends_xuids=session_b_friends,
            mode_category=session_b_category,
        )
        compare_mode = "same_friends"

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
        return hist_avg, compare_mode

    # Solo : comparer avec autres sessions solo
    hist_avg = compute_similar_sessions_average(
        all_sessions_df,
        is_with_friends=False,
        exclude_session_ids=exclude_ids,
        mode_category=session_b_category,
    )
    return hist_avg, "solo"


def _build_session_labels(
    all_sessions_df: DataFrameLike,
    df_session_b: DataFrameLike,
    hist_avg: dict,
    compare_mode: str,
    session_b_category: str,
) -> tuple[str, str]:
    """Construit les labels de type de session et de comparaison."""
    has_with_friends_col = "is_with_friends" in all_sessions_df.columns
    session_b_with_friends = (
        is_session_with_friends(df_session_b) if has_with_friends_col else False
    )
    session_b_friends = (
        get_session_friends_signature(df_session_b) if has_with_friends_col else set()
    )
    cat_label = _CATEGORY_FR.get(session_b_category, session_b_category)

    if not has_with_friends_col:
        session_type_label = "(amis indisponibles) 🎮"
        compare_label = (
            f"toutes sessions ({hist_avg.get('session_count', 0)} sessions)"
            f" — catégorie {cat_label}"
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
                f" — catégorie {cat_label}"
            )
        else:
            compare_label = (
                f"sessions avec amis ({hist_avg.get('session_count', 0)} sessions)"
                f" — catégorie {cat_label}"
            )
    else:
        session_type_label = "solo 🎮"
        compare_label = (
            f"sessions solo ({hist_avg.get('session_count', 0)} sessions)"
            f" — catégorie {cat_label}"
        )

    return session_type_label, compare_label


def _render_score_cards(perf_a: dict, perf_b: dict) -> None:
    """Affiche les grandes cartes de score côte à côte."""
    score_a = perf_a.get("score")
    score_b = perf_b.get("score")
    is_b_better = None
    if score_a is not None and score_b is not None:
        if score_b > score_a:
            is_b_better = True
        elif score_b < score_a:
            is_b_better = False

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


def _render_detailed_metrics(perf_a: dict, perf_b: dict) -> None:
    """Affiche la section des métriques détaillées."""
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


def _render_mmr_comparison(perf_a: dict, perf_b: dict) -> None:
    """Affiche la section de comparaison MMR."""
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


def _render_cumulative_section(
    df_session_a: DataFrameLike,
    df_session_b: DataFrameLike,
    session_a_label: str,
    session_b_label: str,
) -> None:
    """Affiche la section du net score cumulé par session."""
    df_session_a = ensure_polars(df_session_a)
    df_session_b = ensure_polars(df_session_b)
    _req = ["start_time", "kills", "deaths"]
    if not all(c in df_session_a.columns for c in _req) or not all(
        c in df_session_b.columns for c in _req
    ):
        return

    try:
        pl_a = df_session_a.sort("start_time").select(_req)
        pl_b = df_session_b.sort("start_time").select(_req)
        if not pl_a.is_empty() and not pl_b.is_empty():
            st.markdown("#### Net score cumulé par session")
            st.caption(
                "Évolution du net score (Frags − Deaths) au fil des matchs de chaque session."
            )
            try:
                fig_cumul = plot_cumulative_comparison(
                    pl_a,
                    pl_b,
                    label_a=session_a_label,
                    label_b=session_b_label,
                    title="",
                )
                if fig_cumul is not None:
                    st.plotly_chart(fig_cumul, width="stretch")
                else:
                    st.info("Données insuffisantes pour le net score cumulé.")
            except Exception as e:
                st.warning(f"Impossible d'afficher le net score cumulé : {e}")
    except Exception:
        pass


def render_session_comparison_page(
    all_sessions_df: DataFrameLike,
    df_full: DataFrameLike | None = None,
    *,
    db_path: str | None = None,
    xuid: str | None = None,
) -> None:
    """Rend la page de comparaison de sessions (orchestrateur)."""
    all_sessions_df = ensure_polars(all_sessions_df)
    if df_full is not None:
        df_full = ensure_polars(df_full)
    # Récupérer db_path et xuid depuis session_state si non fournis
    if db_path is None:
        db_path = st.session_state.get("db_path", "")
    if xuid is None:
        xuid = st.session_state.get("xuid", "")
    st.caption("Compare les performances entre deux sessions de jeu.")

    if all_sessions_df.is_empty():
        st.info("Aucune session disponible.")
        return

    # Liste des sessions triées (plus récente en premier)
    session_info = (
        all_sessions_df.group_by(["session_id", "session_label"])
        .len()
        .rename({"len": "count"})
        .sort("session_id", descending=True)
    )
    session_labels = session_info.get_column("session_label").to_list()

    if len(session_labels) < 2:
        st.warning("Il faut au moins 2 sessions pour comparer.")
        return

    # Sélecteurs de sessions
    session_a_label, session_b_label = _select_sessions(session_labels)

    # Filtrer les DataFrames
    df_session_a = all_sessions_df.filter(pl.col("session_label") == session_a_label)
    df_session_b = all_sessions_df.filter(pl.col("session_label") == session_b_label)

    # Calculer les scores de performance (v2)
    perf_a = compute_session_performance_score_v2_ui(df_session_a)
    perf_b = compute_session_performance_score_v2_ui(df_session_b)

    # Contexte historique
    session_a_id = (
        df_session_a[0, "session_id"]
        if not df_session_a.is_empty() and "session_id" in df_session_a.columns
        else None
    )
    session_b_id = (
        df_session_b[0, "session_id"]
        if not df_session_b.is_empty() and "session_id" in df_session_b.columns
        else None
    )
    exclude_ids = [sid for sid in [session_a_id, session_b_id] if sid is not None]
    session_b_category = _infer_session_dominant_category(df_session_b)

    hist_avg, compare_mode = _compute_historical_context(
        all_sessions_df,
        df_session_b,
        exclude_ids,
        session_b_category,
    )
    session_type_label, compare_label = _build_session_labels(
        all_sessions_df,
        df_session_b,
        hist_avg,
        compare_mode,
        session_b_category,
    )

    # ══════════════════════════════════════════════════════════════════════════
    # Sections de la page
    # ══════════════════════════════════════════════════════════════════════════
    _render_score_cards(perf_a, perf_b)
    _render_detailed_metrics(perf_a, perf_b)
    _render_mmr_comparison(perf_a, perf_b)

    # Graphiques comparatifs
    st.markdown("---")
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

    # Net score cumulé
    _render_cumulative_section(df_session_a, df_session_b, session_a_label, session_b_label)

    # Tendance de participation (PersonalScores) - Sprint 8.2
    render_participation_trend_section(
        df_session_a=df_session_a,
        df_session_b=df_session_b,
        db_path=db_path,
        xuid=xuid,
    )

    # Tableau historique des parties
    st.markdown("---")
    st.markdown("### 📋 Historique des parties")
    tab_hist_a, tab_hist_b = st.tabs(["Session A", "Session B"])
    with tab_hist_a:
        render_session_history_table(df_session_a, "Session A", df_full=df_full)
    with tab_hist_b:
        render_session_history_table(df_session_b, "Session B", df_full=df_full)


# Re-exports pour compatibilité ascendante
from src.ui.pages.session_compare_charts import (  # noqa: E402, F401
    SESSION_COLORS,
    render_comparison_bar_chart,
    render_comparison_radar_chart,
    render_participation_trend_section,
    render_session_history_table,
)
