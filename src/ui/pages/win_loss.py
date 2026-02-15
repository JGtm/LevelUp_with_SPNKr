"""Page Victoires/Défaites.

Analyse des victoires et défaites par période et par carte.
"""

from __future__ import annotations

import pandas as pd  # requis pour l'API .style de Streamlit
import polars as pl
import streamlit as st

from src.config import HALO_COLORS
from src.data.services.win_loss_service import WinLossService
from src.visualization import (
    plot_map_comparison,
    plot_map_ratio_with_winloss,
    plot_matches_at_top_by_week,
    plot_metric_bars_by_match,
    plot_outcomes_over_time,
    plot_stacked_outcomes_by_category,
    plot_streak_chart,
    plot_win_ratio_heatmap,
)
from src.visualization._compat import DataFrameLike, ensure_polars


def _clear_min_matches_maps_auto() -> None:
    """Callback pour désactiver le mode auto du slider."""
    st.session_state["_min_matches_maps_auto"] = False


def _styler_map(styler, func, subset):
    """Applique un style en mode compatible pandas 1.x et 2.x."""
    try:
        return styler.map(func, subset=subset)
    except AttributeError:
        return styler.applymap(func, subset=subset)


def _to_float(v: object) -> float | None:
    """Convertit une valeur en float, ou None si impossible."""
    try:
        if v is None:
            return None
        x = float(v)
        return x if x == x else None
    except Exception:
        return None


def _style_map_table_row(row: pd.Series) -> pd.Series:
    """Style les lignes du tableau par carte."""
    green = str(getattr(HALO_COLORS, "green", "#2ECC71"))
    red = str(getattr(HALO_COLORS, "red", "#E74C3C"))
    violet = "#8E6CFF"

    win_pct = _to_float(row.get("Taux victoire (%)"))
    loss_pct = _to_float(row.get("Taux défaite (%)"))
    ratio_val = _to_float(row.get("Ratio global"))

    styles: dict[str, str] = {str(c): "" for c in row.index}

    if win_pct is not None and loss_pct is not None:
        if win_pct > loss_pct:
            styles["Taux victoire (%)"] = f"color: {green}; font-weight: 800;"
            styles["Taux défaite (%)"] = f"color: {red}; font-weight: 800;"
        elif win_pct < loss_pct:
            styles["Taux victoire (%)"] = f"color: {red}; font-weight: 800;"
            styles["Taux défaite (%)"] = f"color: {green}; font-weight: 800;"
        else:
            styles["Taux victoire (%)"] = f"color: {violet}; font-weight: 800;"
            styles["Taux défaite (%)"] = f"color: {violet}; font-weight: 800;"

    if ratio_val is not None:
        if ratio_val > 1.0:
            styles["Ratio global"] = f"color: {green}; font-weight: 800;"
        elif ratio_val < 1.0:
            styles["Ratio global"] = f"color: {red}; font-weight: 800;"
        else:
            styles["Ratio global"] = f"color: {violet}; font-weight: 800;"

    return pd.Series(styles)


def render_win_loss_page(
    dff: DataFrameLike,
    base: DataFrameLike,
    picked_session_labels: list[str] | None,
    db_path: str,
    xuid: str,
    db_key: tuple[int, int] | None,
) -> None:
    """Affiche la page Victoires/Défaites.

    Args:
        dff: DataFrame filtré des matchs.
        base: DataFrame de base (toutes les parties après filtres Firefight).
        picked_session_labels: Labels des sessions sélectionnées.
        db_path: Chemin vers la base de données.
        xuid: XUID du joueur.
        db_key: Clé de cache de la DB.
    """
    dff = ensure_polars(dff)
    base = ensure_polars(base)
    if dff.is_empty():
        st.warning("Aucun match à afficher. Vérifiez vos filtres ou synchronisez les données.")
        return

    with st.spinner("Calcul des victoires/défaites…"):
        current_mode = st.session_state.get("filter_mode")
        is_session_scope = bool(current_mode == "Sessions" and picked_session_labels)

        bucket_label = _render_outcomes_over_time(dff, is_session_scope)
        _render_map_mode_breakdown(dff)
        _render_heatmap_section(dff)
        _render_top_by_week(dff)
        _render_streak_section(dff)
        _render_personal_score_section(dff)
        _render_period_section(dff, bucket_label, is_session_scope)
        _render_ratio_by_map_section(dff, base, db_path, xuid, db_key)


def _render_outcomes_over_time(dff: pl.DataFrame, is_session_scope: bool) -> str:
    """Affiche le graphe outcomes over time. Retourne le bucket_label."""
    try:
        fig_out, bucket_label = plot_outcomes_over_time(dff, session_style=is_session_scope)
        st.markdown(
            f"Par **{bucket_label}** : on regroupe les parties par {bucket_label} et on compte le nombre de "
            "victoires/défaites (et autres statuts) pour suivre l'évolution."
        )
        if fig_out is not None:
            st.plotly_chart(fig_out, width="stretch")
        else:
            st.info("Données insuffisantes pour afficher l'évolution des résultats.")
        return bucket_label
    except Exception as e:
        st.warning(f"Impossible d'afficher l'évolution des résultats : {e}")
        return "période"


def _render_map_mode_breakdown(dff: pl.DataFrame) -> None:
    """Affiche les résultats par carte et mode (Sprint 5.4)."""
    st.divider()
    st.subheader("Résultats par carte et mode")
    col_by_map, col_by_mode = st.columns(2)

    with col_by_map:
        st.markdown("##### Par carte")
        if "map_name" in dff.columns and "outcome" in dff.columns:
            try:
                fig_map = plot_stacked_outcomes_by_category(
                    dff,
                    "map_name",
                    title=None,
                    min_matches=2,
                    sort_by="total",
                    max_categories=12,
                )
                if fig_map is not None:
                    st.plotly_chart(fig_map, width="stretch")
                else:
                    st.info("Données insuffisantes pour les résultats par carte.")
            except Exception as e:
                st.warning(f"Impossible d'afficher les résultats par carte : {e}")
        else:
            st.info("Données insuffisantes.")

    with col_by_mode:
        st.markdown("##### Par mode")
        mode_col = (
            "mode_ui"
            if "mode_ui" in dff.columns
            else ("mode_category" if "mode_category" in dff.columns else "pair_name")
        )
        if mode_col in dff.columns and "outcome" in dff.columns:
            try:
                fig_mode = plot_stacked_outcomes_by_category(
                    dff,
                    mode_col,
                    title=None,
                    min_matches=2,
                    sort_by="total",
                    max_categories=10,
                )
                if fig_mode is not None:
                    st.plotly_chart(fig_mode, width="stretch")
                else:
                    st.info("Données insuffisantes pour les résultats par mode.")
            except Exception as e:
                st.warning(f"Impossible d'afficher les résultats par mode : {e}")
        else:
            st.info("Données insuffisantes.")


def _render_heatmap_section(dff: pl.DataFrame) -> None:
    """Affiche la heatmap Win Rate par jour et heure."""
    st.divider()
    st.subheader("Win Rate par jour et heure")
    st.caption(
        "Identifie les créneaux horaires où tu performes le mieux. "
        "Les cellules affichent le nombre de matchs."
    )
    if "start_time" in dff.columns and "outcome" in dff.columns:
        try:
            fig_heat = plot_win_ratio_heatmap(dff, title=None, min_matches=2)
            if fig_heat is not None:
                st.plotly_chart(fig_heat, width="stretch")
            else:
                st.info("Données insuffisantes pour la heatmap win rate.")
        except Exception as e:
            st.warning(f"Impossible d'afficher la heatmap win rate : {e}")
    else:
        st.info("Données temporelles manquantes.")


def _render_top_by_week(dff: pl.DataFrame) -> None:
    """Affiche Matchs Top vs Total par semaine (Sprint 5.4.7)."""
    st.divider()
    st.subheader("Matchs Top vs Total par semaine")
    st.caption(
        "Compare le nombre de matchs où tu as terminé en tête (rang 1) par rapport au total. "
        'La ligne indique le taux de "Top 1".'
    )
    if "start_time" not in dff.columns:
        st.info("Données temporelles manquantes.")
        return
    try:
        rank_col = "rank" if "rank" in dff.columns else "outcome"
        fig_top = plot_matches_at_top_by_week(
            dff,
            title=None,
            rank_col=rank_col,
            top_n_ranks=1,
        )
        if fig_top is not None:
            st.plotly_chart(fig_top, width="stretch")
        else:
            st.info("Données insuffisantes pour les matchs Top.")
    except Exception as e:
        st.warning(f"Impossible d'afficher les matchs Top : {e}")


def _render_streak_section(dff: pl.DataFrame) -> None:
    """Affiche les séries de victoires/défaites (Sprint 7.2)."""
    st.divider()
    st.subheader("Séries de victoires / défaites")
    st.caption(
        "Visualise les séries consécutives de victoires (barres positives) "
        "et de défaites (barres négatives). Les séries longues indiquent "
        "les phases de momentum positif ou négatif."
    )
    if "outcome" in dff.columns and "start_time" in dff.columns:
        try:
            fig_streak = plot_streak_chart(dff, title=None)
            if fig_streak is not None:
                st.plotly_chart(fig_streak, width="stretch")
            else:
                st.info("Données insuffisantes pour les séries.")
        except Exception as e:
            st.warning(f"Impossible d'afficher les séries de victoires/défaites : {e}")
    else:
        st.info("Données de résultat manquantes.")


def _render_personal_score_section(dff: pl.DataFrame) -> None:
    """Affiche le score personnel par match (Sprint 7.1)."""
    if "personal_score" not in dff.columns:
        return
    st.divider()
    st.subheader("Score personnel par match")
    st.caption(
        "Barres colorées du score personnel pour chaque match, " "avec courbe de moyenne lissée."
    )
    colors = HALO_COLORS.as_dict()
    fig_ps = plot_metric_bars_by_match(
        dff,
        metric_col="personal_score",
        title=None,
        y_axis_title="Score personnel",
        hover_label="Score",
        bar_color=colors["amber"],
        smooth_color=colors["violet"],
        smooth_window=10,
    )
    if fig_ps is not None:
        st.plotly_chart(fig_ps, width="stretch")
    else:
        st.info("Données de score personnel insuffisantes.")


def _render_period_section(
    dff: pl.DataFrame,
    bucket_label: str,
    is_session_scope: bool,
) -> None:
    """Affiche le tableau par période."""
    st.divider()
    st.subheader("Par période")
    period = WinLossService.compute_period_table(dff.to_pandas(), bucket_label, is_session_scope)
    if period.is_empty:
        st.info("Aucune donnée pour construire le tableau.")
        return

    out_tbl = period.table

    def _style_pct(v) -> str:
        try:
            x = float(v)  # noqa: F841
        except Exception:
            return ""
        return "color: #E0E0E0; font-weight: 700;"

    win_rate_col = next(
        (c for c in ("Taux de victoires", "Win rate", "Taux de victoire") if c in out_tbl.columns),
        None,
    )
    if win_rate_col:
        out_styled = _styler_map(out_tbl.style, _style_pct, subset=[win_rate_col])
        col_cfg = {win_rate_col: st.column_config.NumberColumn(win_rate_col, format="%.1f%%")}
    else:
        out_styled = out_tbl.style
        col_cfg = {}

    st.dataframe(out_styled, width="stretch", hide_index=True, column_config=col_cfg)


def _render_ratio_by_map_section(
    dff: pl.DataFrame,
    base: pl.DataFrame,
    db_path: str,
    xuid: str,
    db_key: tuple[int, int] | None,
) -> None:
    """Affiche le ratio par cartes avec sélection du scope."""
    st.divider()
    st.subheader("Ratio par cartes")
    st.caption("Compare tes performances par map.")

    scope = st.radio(
        "Scope",
        options=[
            "Moi (filtres actuels)",
            "Moi (toutes les parties)",
            "Avec Madina972",
            "Avec Chocoboflor",
        ],
        horizontal=True,
    )
    min_matches = st.slider(
        "Minimum de matchs par carte",
        1,
        30,
        1,
        step=1,
        key="min_matches_maps",
        on_change=_clear_min_matches_maps_auto,
    )

    base_scope_pl = WinLossService.get_friend_scope_df(
        scope,
        dff,
        base,
        db_path,
        xuid,
        db_key,
    )

    with st.spinner("Calcul des stats par carte\u2026"):
        map_result = WinLossService.compute_map_breakdown(base_scope_pl, min_matches)
        breakdown = map_result.breakdown if not map_result.is_empty else pl.DataFrame()

    if map_result.is_empty:
        st.warning("Pas assez de matchs par map avec ces filtres.")
        return

    metric = st.selectbox(
        "Métrique",
        options=[
            ("ratio_global", "Ratio Victoire/défaite"),
            ("win_rate", "Taux de victoires"),
            ("accuracy_avg", "Précision moyenne"),
        ],
        format_func=lambda x: x[1],
    )
    key, label = metric

    view = breakdown.head(20).reverse()
    try:
        if key == "ratio_global":
            fig = plot_map_ratio_with_winloss(view, title=label)
        else:
            fig = plot_map_comparison(view, key, title=label)

        if fig is not None:
            if key in ("win_rate",):
                fig.update_xaxes(tickformat=".0%")
            if key in ("accuracy_avg",):
                fig.update_xaxes(ticksuffix="%")
            st.plotly_chart(fig, width="stretch")
        else:
            st.info(f"Données insuffisantes pour {label}.")
    except Exception as e:
        st.warning(f"Impossible d'afficher le graphique {label} : {e}")

    base_scope = base_scope_pl
    _render_map_table(breakdown, base_scope)


def _render_map_table(breakdown: pl.DataFrame, base_scope: pl.DataFrame) -> None:
    """Affiche le tableau détaillé par carte."""
    from src.ui.translations import translate_playlist_name

    # Transformations internes en Polars
    cols_expr = [
        (pl.col("win_rate") * 100).round(1).alias("win_rate"),
        (pl.col("loss_rate") * 100).round(1).alias("loss_rate"),
        pl.col("accuracy_avg").cast(pl.Float64, strict=False).round(2).alias("accuracy_avg"),
        pl.col("ratio_global").cast(pl.Float64, strict=False).round(2).alias("ratio_global"),
    ]
    if "performance_avg" in breakdown.columns:
        cols_expr.append(
            pl.col("performance_avg")
            .cast(pl.Float64, strict=False)
            .round(1)
            .alias("performance_avg")
        )
    tbl = breakdown.with_columns(cols_expr)

    def _single_or_multi_label(values: list) -> str:
        """Détermine un label unique ou 'Plusieurs' à partir d'une liste."""
        try:
            vals = sorted({str(x).strip() for x in values if x is not None and str(x).strip()})
        except Exception:
            return "-"
        if len(vals) == 0:
            return "-"
        if len(vals) == 1:
            return vals[0]
        return "Plusieurs"

    def _clean_asset_label(s: str | None) -> str:
        """Nettoie un label d'asset."""
        if not s:
            return ""
        return str(s).split("/")[-1].replace("-", " ").strip().title()

    def _normalize_mode_label(p: str | None) -> str | None:
        """Normalise un label de mode de jeu."""
        from src.ui.translations import translate_pair_name

        return translate_pair_name(p) if p else None

    if "playlist_ui" in base_scope.columns:
        playlist_ctx = _single_or_multi_label(base_scope["playlist_ui"].drop_nulls().to_list())
    else:
        playlist_vals = (
            base_scope["playlist_name"]
            .map_elements(_clean_asset_label, return_dtype=pl.Utf8)
            .map_elements(translate_playlist_name, return_dtype=pl.Utf8)
            .drop_nulls()
            .to_list()
        )
        playlist_ctx = _single_or_multi_label(playlist_vals)

    if "mode_ui" in base_scope.columns:
        mode_ctx = _single_or_multi_label(base_scope["mode_ui"].drop_nulls().to_list())
    else:
        mode_vals = (
            base_scope["pair_name"]
            .map_elements(_normalize_mode_label, return_dtype=pl.Utf8)
            .drop_nulls()
            .to_list()
        )
        mode_ctx = _single_or_multi_label(mode_vals)

    tbl = tbl.with_columns(
        [
            pl.lit(playlist_ctx).alias("playlist_ctx"),
            pl.lit(mode_ctx).alias("mode_ctx"),
        ]
    )
    rename_map = {
        "map_name": "Carte",
        "matches": "Parties",
        "accuracy_avg": "Précision moy. (%)",
        "performance_avg": "Performance moy.",
        "win_rate": "Taux victoire (%)",
        "loss_rate": "Taux défaite (%)",
        "ratio_global": "Ratio global",
        "playlist_ctx": "Playlist",
        "mode_ctx": "Mode",
    }
    tbl = tbl.rename({k: v for k, v in rename_map.items() if k in tbl.columns})

    ordered_cols = [
        "Carte",
        "Playlist",
        "Mode",
        "Parties",
        "Précision moy. (%)",
        "Performance moy.",
        "Taux victoire (%)",
        "Taux défaite (%)",
        "Ratio global",
    ]
    tbl = tbl.select([c for c in ordered_cols if c in tbl.columns])

    # Conversion pandas à la frontière .style
    tbl_pd = tbl.to_pandas()
    tbl_styled = tbl_pd.style.apply(_style_map_table_row, axis=1)
    st.dataframe(
        tbl_styled,
        width="stretch",
        hide_index=True,
        column_config={
            "Parties": st.column_config.NumberColumn("Parties", format="%d"),
            "Précision moy. (%)": st.column_config.NumberColumn(
                "Précision moy. (%)", format="%.2f"
            ),
            "Performance moy.": st.column_config.NumberColumn("Performance moy.", format="%.1f"),
            "Taux victoire (%)": st.column_config.NumberColumn("Taux victoire (%)", format="%.1f"),
            "Taux défaite (%)": st.column_config.NumberColumn("Taux défaite (%)", format="%.1f"),
            "Ratio global": st.column_config.NumberColumn("Ratio global", format="%.2f"),
        },
    )
