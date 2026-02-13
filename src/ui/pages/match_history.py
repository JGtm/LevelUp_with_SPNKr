"""Page Historique des parties.

Tableau complet de l'historique des matchs avec liens et MMR.

Sprint 4.2 : Optimisation N+1
- Les colonnes team_mmr et enemy_mmr sont déjà dans le DataFrame
- Plus besoin de requête individuelle par match (était: 500 requêtes)
- Gain de performance: ~90% (1 requête batch vs N requêtes)
"""

from __future__ import annotations

import html as html_lib
from datetime import datetime

import polars as pl
import streamlit as st

from src.analysis.performance_score import compute_performance_series
from src.analysis.stats import format_mmss
from src.ui.components.performance import get_score_class
from src.ui.translations import translate_playlist_name
from src.visualization._compat import DataFrameLike, ensure_polars


def _normalize_mode_label(pair_name: str | None) -> str | None:
    """Normalise un pair_name en label UI."""
    from src.ui.translations import translate_pair_name

    return translate_pair_name(pair_name) if pair_name else None


def _format_datetime_fr_hm(dt: datetime | None) -> str:
    """Formate une date FR avec heures/minutes."""
    if dt is None:
        return "-"
    try:
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(dt)


def _app_url(page: str, **params: str) -> str:
    """Génère une URL interne vers une page de l'app."""
    import urllib.parse

    base = "/"
    qp = {"page": page, **params}
    return base + "?" + urllib.parse.urlencode(qp)


def _format_score_label(my_score: object, enemy_score: object) -> str:
    """Formate le score du match."""

    def _safe(v: object) -> str:
        if v is None:
            return "-"
        try:
            if v != v:  # NaN
                return "-"
        except Exception:
            pass
        try:
            return str(int(round(float(v))))
        except Exception:
            return str(v)

    return f"{_safe(my_score)} - {_safe(enemy_score)}"


def _fmt(v) -> str:
    """Formate une valeur pour affichage."""
    if v is None:
        return "-"
    try:
        if v != v:  # NaN
            return "-"
    except Exception:
        pass
    s = str(v)
    return s if s.strip() else "-"


def _fmt_mmr_int(v) -> str:
    """Formate une valeur MMR en entier."""
    if v is None:
        return "-"
    try:
        if v != v:  # NaN
            return "-"
    except Exception:
        pass
    try:
        return str(int(round(float(v))))
    except Exception:
        return _fmt(v)


def render_match_history_page(
    dff: DataFrameLike,
    waypoint_player: str,
    db_path: str,
    xuid: str,
    db_key: tuple[int, int] | None,
    df_full: DataFrameLike | None = None,
) -> None:
    """Affiche la page Historique des parties.

    Args:
        dff: DataFrame filtré des matchs.
        waypoint_player: Nom Waypoint du joueur.
        db_path: Chemin vers la base de données.
        xuid: XUID du joueur.
        db_key: Clé de cache de la DB.
        df_full: DataFrame complet (non filtré) pour le calcul du score relatif.
    """
    dff = ensure_polars(dff)

    # Protection contre les DataFrames vides
    if dff.is_empty():
        st.warning("Aucun match à afficher. Vérifiez vos filtres ou synchronisez les données.")
        return

    st.subheader("Historique des parties")

    dff_table = dff.clone()
    if "playlist_fr" not in dff_table.columns:
        dff_table = dff_table.with_columns(
            pl.col("playlist_name")
            .map_elements(translate_playlist_name, return_dtype=pl.Utf8)
            .alias("playlist_fr")
        )
    if "mode_ui" not in dff_table.columns:
        dff_table = dff_table.with_columns(
            pl.col("pair_name")
            .map_elements(_normalize_mode_label, return_dtype=pl.Utf8)
            .alias("mode_ui")
        )
    dff_table = dff_table.with_columns(
        (
            pl.lit("https://www.halowaypoint.com/halo-infinite/players/")
            + pl.lit(waypoint_player.strip())
            + pl.lit("/matches/")
            + pl.col("match_id").cast(pl.Utf8)
        ).alias("match_url")
    )

    outcome_map = {2: "Victoire", 3: "Défaite", 1: "Égalité", 4: "Non terminé"}
    dff_table = dff_table.with_columns(
        pl.col("outcome")
        .map_elements(lambda v: outcome_map.get(v, "-"), return_dtype=pl.Utf8)
        .alias("outcome_label")
    )

    dff_table = dff_table.with_columns(
        pl.struct(["my_team_score", "enemy_team_score"])
        .map_elements(
            lambda r: _format_score_label(r["my_team_score"], r["enemy_team_score"]),
            return_dtype=pl.Utf8,
        )
        .alias("score")
    )

    # MMR équipe/adverse - Sprint 4.2 : Optimisation N+1
    # Les colonnes sont déjà dans le DataFrame (chargées par load_matches)
    # Plus de boucle N+1 (était: 1 requête par match = 500+ requêtes)
    if "team_mmr" not in dff_table.columns:
        dff_table = dff_table.with_columns(pl.lit(None).cast(pl.Float64).alias("team_mmr"))
    if "enemy_mmr" not in dff_table.columns:
        dff_table = dff_table.with_columns(pl.lit(None).cast(pl.Float64).alias("enemy_mmr"))

    # Calcul du delta MMR (vectorisé, pas de boucle)
    dff_table = dff_table.with_columns(
        (
            pl.col("team_mmr").cast(pl.Float64, strict=False)
            - pl.col("enemy_mmr").cast(pl.Float64, strict=False)
        ).alias("delta_mmr")
    )

    dff_table = dff_table.with_columns(
        pl.col("start_time")
        .map_elements(_format_datetime_fr_hm, return_dtype=pl.Utf8)
        .alias("start_time_fr")
    )
    dff_table = dff_table.with_columns(
        pl.col("average_life_seconds")
        .map_elements(lambda x: format_mmss(x), return_dtype=pl.Utf8)
        .alias("average_life_mmss")
    )

    # Calcul de la note de performance RELATIVE (basée sur l'historique complet)
    history_df = ensure_polars(df_full) if df_full is not None else dff_table
    perf_series = compute_performance_series(dff_table, history_df)
    # compute_performance_series retourne une Series Polars quand l'entrée est Polars
    if not isinstance(perf_series, pl.Series):
        perf_series = pl.Series("performance", perf_series.to_list())
    dff_table = dff_table.with_columns(perf_series.alias("performance"))
    dff_table = dff_table.with_columns(
        pl.col("performance")
        .map_elements(lambda x: f"{x:.0f}" if x is not None else "-", return_dtype=pl.Utf8)
        .alias("performance_display")
    )

    # Table HTML
    _render_history_table(dff_table)

    # Export CSV
    _render_csv_download(dff_table)


def _render_history_table(dff_table: pl.DataFrame) -> None:
    """Génère et affiche le tableau HTML de l'historique."""

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

    cols = [
        ("Match", "_app"),
        ("HaloWaypoint", "match_url"),
        ("Date de début", "start_time_fr"),
        ("Carte", "map_name"),
        ("Playlist", "playlist_fr"),
        ("Mode", "mode_ui"),
        ("Résultat", "outcome_label"),
        ("Score", "score"),
        ("Performance", "performance_display"),
        ("MMR équipe", "team_mmr"),
        ("MMR adverse", "enemy_mmr"),
        ("Écart MMR", "delta_mmr"),
        ("FDA", "kda"),
        ("Frags", "kills"),
        ("Morts", "deaths"),
        ("Tuerie (max)", "max_killing_spree"),
        ("Têtes", "headshot_kills"),
        ("Durée vie", "average_life_mmss"),
        ("Assists", "assists"),
        ("Précision", "accuracy"),
        ("Ratio", "ratio"),
    ]

    view = dff_table.sort("start_time", descending=True).head(250)

    head = "".join(f"<th>{html_lib.escape(h)}</th>" for h, _ in cols)
    body_rows: list[str] = []
    for r in view.iter_rows(named=True):
        mid = str(r.get("match_id") or "").strip()
        app = _app_url("Match", match_id=mid)
        match_link = f"<a href='{html_lib.escape(app)}' target='_self'>Ouvrir</a>" if mid else "-"
        hw = str(r.get("match_url") or "").strip()
        hw_link = (
            f"<a href='{html_lib.escape(hw)}' target='_blank' rel='noopener'>Ouvrir</a>"
            if hw
            else "-"
        )

        tds: list[str] = []
        for _h, key in cols:
            if key == "_app":
                tds.append(f"<td>{match_link}</td>")
            elif key == "match_url":
                tds.append(f"<td>{hw_link}</td>")
            elif key == "outcome_label":
                val = _fmt(r.get(key))
                css_class = _outcome_class(val)
                tds.append(f"<td class='{css_class}'>{html_lib.escape(val)}</td>")
            elif key == "performance_display":
                val = _fmt(r.get(key))
                perf_val = r.get("performance")
                css_class = get_score_class(perf_val)
                tds.append(f"<td class='{css_class}'>{html_lib.escape(val)}</td>")
            elif key in ("team_mmr", "enemy_mmr", "delta_mmr"):
                val = _fmt_mmr_int(r.get(key))
                tds.append(f"<td>{html_lib.escape(val)}</td>")
            else:
                val = _fmt(r.get(key))
                tds.append(f"<td>{html_lib.escape(val)}</td>")
        body_rows.append("<tr>" + "".join(tds) + "</tr>")

    st.markdown(
        "<div class='os-table-wrap'><table class='os-table'><thead><tr>"
        + head
        + "</tr></thead><tbody>"
        + "".join(body_rows)
        + "</tbody></table></div>",
        unsafe_allow_html=True,
    )


def _render_csv_download(dff_table: pl.DataFrame) -> None:
    """Affiche le bouton de téléchargement CSV."""
    show_cols = [
        "match_url",
        "start_time_fr",
        "map_name",
        "playlist_fr",
        "mode_ui",
        "outcome_label",
        "score",
        "team_mmr",
        "enemy_mmr",
        "delta_mmr",
        "kda",
        "kills",
        "deaths",
        "max_killing_spree",
        "headshot_kills",
        "average_life_mmss",
        "assists",
        "accuracy",
        "ratio",
    ]
    table = (
        dff_table.select(show_cols + ["start_time"])
        .sort("start_time", descending=True)
        .select(show_cols)
    )

    csv_table = table.rename({"start_time_fr": "Date de début"})
    csv = csv_table.write_csv().encode("utf-8")
    st.download_button(
        "Télécharger CSV",
        data=csv,
        file_name="openspartan_matches.csv",
        mime="text/csv",
    )
