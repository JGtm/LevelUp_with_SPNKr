"""Fonctions de filtrage et helpers pour les options UI."""

import re
from collections.abc import Callable

import pandas as pd
import polars as pl


def mark_firefight(df: pl.DataFrame) -> pl.DataFrame:
    """Ajoute une colonne is_firefight pour identifier les matchs PvE.

    Heuristique basée sur les libellés Playlist / Pair contenant "Firefight".

    Args:
        df: DataFrame de matchs (Polars).

    Returns:
        DataFrame avec colonne is_firefight ajoutée.
    """
    pat = r"(?i)\bfirefight\b"
    pl_col = (
        pl.col("playlist_name").fill_null("").cast(pl.Utf8)
        if "playlist_name" in df.columns
        else pl.lit("")
    )
    pair_col = (
        pl.col("pair_name").fill_null("").cast(pl.Utf8) if "pair_name" in df.columns else pl.lit("")
    )
    gv_col = (
        pl.col("game_variant_name").fill_null("").cast(pl.Utf8)
        if "game_variant_name" in df.columns
        else pl.lit("")
    )

    is_ff = pl_col.str.contains(pat) | pair_col.str.contains(pat) | gv_col.str.contains(pat)
    return df.with_columns(is_ff.alias("is_firefight"))


def is_allowed_playlist_name(name: str) -> bool:
    """Vérifie si une playlist est dans la liste autorisée.

    Playlists autorisées par défaut:
    - Quick Play
    - Ranked Slayer
    - Ranked Arena
    - Big Team Battle

    Args:
        name: Nom de la playlist.

    Returns:
        True si la playlist est autorisée.
    """
    s = (name or "").strip().casefold()
    if not s:
        return False
    # FR (UI)
    if re.search(r"\bpartie\s*rapide\b", s):
        return True
    if re.search(r"\bar(?:e|è)ne\b.*\bclass(?:e|é)e\b", s):
        return True
    # "classé" (masc) / "classée" (fém)
    if re.search(r"\bassassin\b.*\bclass(?:e|é)(?:e)?\b", s):
        return True
    # Big Team Battle (FR: Grande équipe / Grand combat)
    if re.search(r"\bbig\s*team\b", s):
        return True
    if re.search(r"\bgrande?\s*(?:équipe|equipe|combat)\b", s):
        return True
    # EN (API)
    if re.search(r"\bquick\s*play\b", s):
        return True
    if re.search(r"\branked\b.*\bslayer\b", s):
        return True
    if re.search(r"\branked\b.*\barena\b", s):
        return True
    return False


def build_option_map(
    series_name: pl.Series | pd.Series, series_id: pl.Series | pd.Series
) -> dict[str, str]:
    """Construit un dictionnaire label -> id pour les selectbox.

    Nettoie les libellés (supprime les suffixes UUID) et gère les collisions.

    Args:
        series_name: Série des noms (Polars ou Pandas).
        series_id: Série des IDs correspondants (Polars ou Pandas).

    Returns:
        Dictionnaire {label_propre: id} trié alphabétiquement.
    """

    def clean_label(s: str) -> str:
        s = (s or "").strip()
        # Supprime les suffixes type " - <hash/uuid>"
        m = re.match(r"^(.*?)(?:\s*[\-–—]\s*[0-9A-Za-z]{8,})$", s)
        if m:
            s = (m.group(1) or "").strip()
        return s

    out: dict[str, str] = {}
    collisions: dict[str, int] = {}

    # Convertir en listes selon le type
    if isinstance(series_name, pl.Series):
        names = series_name.fill_null("").to_list()
        ids = series_id.fill_null("").to_list()
    else:  # Pandas Series
        names = series_name.fillna("").tolist()
        ids = series_id.fillna("").tolist()
    for name, _id in zip(names, ids, strict=False):
        if not _id:
            continue
        if not (isinstance(name, str) and name.strip()):
            continue

        label = clean_label(name)
        if not label:
            continue

        # Gère les collisions de noms
        key = label
        if key in out and out[key] != _id:
            collisions[label] = collisions.get(label, 1) + 1
            key = f"{label} (v{collisions[label]})"

        out[key] = _id

    return dict(sorted(out.items(), key=lambda kv: kv[0].lower()))


def build_xuid_option_map(
    xuids: list[str],
    display_name_fn: Callable[[str], str] | None = None,
) -> dict[str, str]:
    """Construit un dictionnaire label -> xuid pour les selectbox.

    Args:
        xuids: Liste de XUID.
        display_name_fn: Fonction pour obtenir le display name d'un XUID.
                        Si None, utilise le XUID tel quel.

    Returns:
        Dictionnaire {label: xuid} trié alphabétiquement.
    """
    out: dict[str, str] = {}
    for x in xuids:
        label = display_name_fn(x) if display_name_fn else x
        out[f"{label} — {x}"] = x
    return dict(sorted(out.items(), key=lambda kv: kv[0].lower()))
