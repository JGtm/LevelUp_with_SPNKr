"""Page Victoires/Défaites.

Analyse des victoires et défaites par période et par carte.
"""

from __future__ import annotations

import polars as pl

# Type alias pour compatibilité DataFrame
try:
    import pandas as pd

    DataFrameType = pd.DataFrame | pl.DataFrame
except ImportError:
    pd = None  # type: ignore[assignment]
    DataFrameType = pl.DataFrame  # type: ignore[misc]

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
    dff: pd.DataFrame,
    base: pd.DataFrame,
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
    # Protection contre les DataFrames vides
    if dff.empty:
        st.warning("Aucun match à afficher. Vérifiez vos filtres ou synchronisez les données.")
        return

    with st.spinner("Calcul des victoires/défaites…"):
        current_mode = st.session_state.get("filter_mode")
        is_session_scope = bool(current_mode == "Sessions" and picked_session_labels)
        fig_out, bucket_label = plot_outcomes_over_time(dff, session_style=is_session_scope)
        st.markdown(
            f"Par **{bucket_label}** : on regroupe les parties par {bucket_label} et on compte le nombre de "
            "victoires/défaites (et autres statuts) pour suivre l'évolution."
        )
        st.plotly_chart(fig_out, width="stretch")

        # === Nouvelles visualisations Sprint 5.4 ===
        st.divider()
        st.subheader("Résultats par carte et mode")

        col_by_map, col_by_mode = st.columns(2)

        with col_by_map:
            st.markdown("##### Par carte")
            if "map_name" in dff.columns and "outcome" in dff.columns:
                fig_map = plot_stacked_outcomes_by_category(
                    dff,
                    "map_name",
                    title=None,
                    min_matches=2,
                    sort_by="total",
                    max_categories=12,
                )
                st.plotly_chart(fig_map, width="stretch")
            else:
                st.info("Données insuffisantes.")

        with col_by_mode:
            st.markdown("##### Par mode")
            # Utiliser mode_category si disponible, sinon pair_name
            mode_col = (
                "mode_ui"
                if "mode_ui" in dff.columns
                else ("mode_category" if "mode_category" in dff.columns else "pair_name")
            )
            if mode_col in dff.columns and "outcome" in dff.columns:
                fig_mode = plot_stacked_outcomes_by_category(
                    dff,
                    mode_col,
                    title=None,
                    min_matches=2,
                    sort_by="total",
                    max_categories=10,
                )
                st.plotly_chart(fig_mode, width="stretch")
            else:
                st.info("Données insuffisantes.")

        # Heatmap jour/heure
        st.divider()
        st.subheader("Win Rate par jour et heure")
        st.caption(
            "Identifie les créneaux horaires où tu performes le mieux. "
            "Les cellules affichent le nombre de matchs."
        )

        if "start_time" in dff.columns and "outcome" in dff.columns:
            fig_heat = plot_win_ratio_heatmap(
                dff,
                title=None,
                min_matches=2,
            )
            st.plotly_chart(fig_heat, width="stretch")
        else:
            st.info("Données temporelles manquantes.")

        # Matches at Top vs Total par semaine (Sprint 5.4.7)
        st.divider()
        st.subheader("Matchs Top vs Total par semaine")
        st.caption(
            "Compare le nombre de matchs où tu as terminé en tête (rang 1) par rapport au total. "
            'La ligne indique le taux de "Top 1".'
        )

        if "start_time" in dff.columns:
            # Utiliser rank si disponible, sinon outcome (victoire = top)
            rank_col = "rank" if "rank" in dff.columns else None
            if rank_col:
                fig_top = plot_matches_at_top_by_week(
                    dff,
                    title=None,
                    rank_col=rank_col,
                    top_n_ranks=1,
                )
            else:
                fig_top = plot_matches_at_top_by_week(
                    dff,
                    title=None,
                    rank_col="outcome",  # Fallback
                    top_n_ranks=1,
                )
            st.plotly_chart(fig_top, width="stretch")
        else:
            st.info("Données temporelles manquantes.")

        # === Séries de victoires / défaites (Sprint 7.2) ===
        st.divider()
        st.subheader("Séries de victoires / défaites")
        st.caption(
            "Visualise les séries consécutives de victoires (barres positives) "
            "et de défaites (barres négatives). Les séries longues indiquent "
            "les phases de momentum positif ou négatif."
        )
        if "outcome" in dff.columns and "start_time" in dff.columns:
            fig_streak = plot_streak_chart(dff, title=None)
            st.plotly_chart(fig_streak, width="stretch")
        else:
            st.info("Données de résultat manquantes.")

        # === Score personnel par match (Sprint 7.1) ===
        if "personal_score" in dff.columns:
            st.divider()
            st.subheader("Score personnel par match")
            st.caption(
                "Barres colorées du score personnel pour chaque match, "
                "avec courbe de moyenne lissée."
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

        st.divider()
        st.subheader("Par période")
        # Calcul via service Sprint 14
        period = WinLossService.compute_period_table(dff, bucket_label, is_session_scope)
        if period.is_empty:
            st.info("Aucune donnée pour construire le tableau.")
        else:
            out_tbl = period.table

            def _style_pct(v) -> str:
                try:
                    x = float(v)  # noqa: F841
                except Exception:
                    return ""
                return "color: #E0E0E0; font-weight: 700;"

            win_rate_col = next(
                (
                    c
                    for c in ("Taux de victoires", "Win rate", "Taux de victoire")
                    if c in out_tbl.columns
                ),
                None,
            )
            if win_rate_col:
                out_styled = _styler_map(out_tbl.style, _style_pct, subset=[win_rate_col])
                col_cfg = {
                    win_rate_col: st.column_config.NumberColumn(win_rate_col, format="%.1f%%")
                }
            else:
                out_styled = out_tbl.style
                col_cfg = {}

            st.dataframe(out_styled, width="stretch", hide_index=True, column_config=col_cfg)

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

        # Scope et breakdown via service Sprint 14
        base_scope = WinLossService.get_friend_scope_df(scope, dff, base, db_path, xuid, db_key)

        with st.spinner("Calcul des stats par carte…"):
            map_result = WinLossService.compute_map_breakdown(base_scope, min_matches)
            breakdown = map_result.breakdown

        if map_result.is_empty:
            st.warning("Pas assez de matchs par map avec ces filtres.")
        else:
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

            view = breakdown.head(20).iloc[::-1]
            if key == "ratio_global":
                fig = plot_map_ratio_with_winloss(view, title=label)
            else:
                fig = plot_map_comparison(view, key, title=label)

            if key in ("win_rate",):
                fig.update_xaxes(tickformat=".0%")
            if key in ("accuracy_avg",):
                fig.update_xaxes(ticksuffix="%")

            st.plotly_chart(fig, width="stretch")

            # Tableau détaillé
            _render_map_table(breakdown, base_scope)


def _render_map_table(breakdown: pd.DataFrame, base_scope: pd.DataFrame) -> None:
    """Affiche le tableau détaillé par carte."""
    from src.ui.translations import translate_playlist_name

    tbl = breakdown.copy()
    tbl["win_rate"] = (tbl["win_rate"] * 100).round(1)
    tbl["loss_rate"] = (tbl["loss_rate"] * 100).round(1)
    # Convertir en numérique pour éviter TypeError si la colonne est de type object
    tbl["accuracy_avg"] = pd.to_numeric(tbl["accuracy_avg"], errors="coerce").round(2)
    tbl["ratio_global"] = pd.to_numeric(tbl["ratio_global"], errors="coerce").round(2)
    if "performance_avg" in tbl.columns:
        tbl["performance_avg"] = pd.to_numeric(tbl["performance_avg"], errors="coerce").round(1)

    def _single_or_multi_label(series: pd.Series) -> str:
        try:
            vals = sorted({str(x).strip() for x in series.dropna().tolist() if str(x).strip()})
        except Exception:
            return "-"
        if len(vals) == 0:
            return "-"
        if len(vals) == 1:
            return vals[0]
        return "Plusieurs"

    def _clean_asset_label(s: str | None) -> str:
        if not s:
            return ""
        return str(s).split("/")[-1].replace("-", " ").strip().title()

    def _normalize_mode_label(p: str | None) -> str | None:
        from src.ui.translations import translate_pair_name

        return translate_pair_name(p) if p else None

    if "playlist_ui" in base_scope.columns:
        playlist_ctx = _single_or_multi_label(base_scope["playlist_ui"])
    else:
        playlist_ctx = _single_or_multi_label(
            base_scope["playlist_name"].apply(_clean_asset_label).apply(translate_playlist_name)
        )

    if "mode_ui" in base_scope.columns:
        mode_ctx = _single_or_multi_label(base_scope["mode_ui"])
    else:
        mode_ctx = _single_or_multi_label(base_scope["pair_name"].apply(_normalize_mode_label))

    tbl_disp = tbl.copy()
    tbl_disp["playlist_ctx"] = playlist_ctx
    tbl_disp["mode_ctx"] = mode_ctx
    tbl_disp = tbl_disp.rename(
        columns={
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
    )
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
    tbl_disp = tbl_disp[[c for c in ordered_cols if c in tbl_disp.columns]]

    tbl_styled = tbl_disp.style.apply(_style_map_table_row, axis=1)
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
