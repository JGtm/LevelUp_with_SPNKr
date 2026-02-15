"""UI: affichage des commendations (Halo 5 : Guardians).

Cette UI s'appuie sur le référentiel offline généré par:
- scripts/extract_h5g_commendations_fr.py

Fichiers attendus:
- data/wiki/halo5_commendations_fr.json
- static/commendations/h5g/*.png
"""

from __future__ import annotations

import base64
import html
import json
import os
import re
import unicodedata
from typing import Any

import streamlit as st

from src.config import get_repo_root

DEFAULT_H5G_JSON_PATH = os.path.join("data", "wiki", "halo5_commendations_fr.json")
DEFAULT_H5G_EXCLUDE_PATH = os.path.join("data", "wiki", "halo5_commendations_exclude.json")


_H5G_TITLE_OVERRIDES_FR: dict[str, str] = {
    "4 Little Spartans went out to play": "Quatre petits Spartans sont allés jouer",
    "Bosses, Bases, and mayhem. Oh my!": "Boss, bases et chaos. Oh là là !",
    "Expect the unexpected": "Attendez-vous à l'inattendu",
    "Forgot to pay the toll": "Vous avez oublié de payer le péage",
    "From Downtown": "Depuis le centre-ville",
    "From the top rope": "Depuis la troisième corde",
    "Kill or be killed": "Tuer ou être tué",
    "No time to lose": "Pas de temps à perdre",
    "So cuddly": "Tellement câlin",
    "Somebody call for an extermination?": "Quelqu'un a demandé une extermination ?",
    "Something on your face": "Vous avez quelque chose sur le visage",
    "The Pain Train": "Le train de la douleur",
    "The Reaper": "Le faucheur",
    "Till someone loses an eye": "Jusqu'à ce que quelqu'un perde un œil",
    "Too close to the fire": "Trop près du feu",
    "Too fast for you": "Trop rapide pour toi",
    # Traductions "idiom" supplémentaires
    "Helping Hand": "Coup de main",
    "Player vs Everything": "Seul contre tous",
    "I'm just perfect": "Zéro défaut",
    "Power play": "Coup de force",
    "Is that my ball?": "C’est ma balle ?",
    "Road Trip": "Virée sur la route",
    "Kicking it Old School": "Retour aux sources",
    "Lawnmower": "Tondeuse",
    "Sting like a bee": "Pique comme une abeille",
    "Flag 'em down": "Sors les drapeaux",
    "Look ma no pin": "Regarde maman, sans goupille",
    "No Hard Feelings": "Sans rancune",
    "Tick Tick Boom": "Tic-tac, boum",
    "Grand Theft": "Vol à la tire",
    "Not so fast": "Pas si vite",
}


# Descriptions personnalisées pour certaines citations (override du JSON)
_H5G_DESC_OVERRIDES_FR: dict[str, str] = {
    # Seul contre tous / Player vs Everything
    "Player vs Everything": "Gagner des parties en Baptême du feu",
    "Seul contre tous": "Gagner des parties en Baptême du feu",
}


def _repo_root() -> str:
    # Robuste si le projet est lancé depuis un autre CWD.
    return get_repo_root(__file__)


def _abs_from_repo(path: str) -> str:
    if not path:
        return path
    if os.path.isabs(path):
        return path
    return os.path.join(_repo_root(), path)


def _normalize_name(s: str) -> str:
    base = " ".join(str(s or "").strip().lower().split())
    # Ignore les accents pour rendre les exclusions robustes (é/è/ê, etc.).
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", base) if not unicodedata.combining(ch)
    )


def _looks_english(text: str) -> bool:
    s = str(text or "").strip()
    if not s:
        return False
    low = " " + s.lower() + " "
    common = (
        " the ",
        " and ",
        " with ",
        " from ",
        " to ",
        " your ",
        " for ",
        " earn ",
        " kill ",
        " kills ",
        " win ",
        " match ",
        " matches ",
        " enemies ",
        " enemy ",
        " assist ",
        " assists ",
        " headshot ",
        " headshots ",
        " capture ",
    )
    return any(w in low for w in common)


_LAST_PAREN_RE = re.compile(r"\((?P<inside>[^()]*)\)\s*$")


def _prefer_parenthetical_fr(text: str) -> str:
    s = str(text or "").strip()
    if not s:
        return s

    m = _LAST_PAREN_RE.search(s)
    if not m:
        return s

    inside = (m.group("inside") or "").strip()
    before = s[: m.start()].strip()
    if inside and _looks_english(before):
        inside = inside.replace("Obtener ", "Obtenir ").replace("Obtener", "Obtenir")
        return inside
    return s


def _display_citation_name(name: str) -> str:
    n = str(name or "").strip()
    if not n:
        return n
    return _H5G_TITLE_OVERRIDES_FR.get(n, n)


def _display_citation_desc(desc: str, name: str | None = None) -> str:
    """Retourne la description à afficher pour une citation.

    Args:
        desc: Description originale de la citation.
        name: Nom de la citation (pour les overrides).

    Returns:
        Description traduite/personnalisée.
    """
    # Priorité aux overrides de description
    if name:
        n = str(name).strip()
        if n in _H5G_DESC_OVERRIDES_FR:
            return _H5G_DESC_OVERRIDES_FR[n]
        # Essayer aussi avec le nom traduit
        translated_name = _H5G_TITLE_OVERRIDES_FR.get(n, n)
        if translated_name in _H5G_DESC_OVERRIDES_FR:
            return _H5G_DESC_OVERRIDES_FR[translated_name]

    d = str(desc or "").strip()
    if not d:
        return d
    return _prefer_parenthetical_fr(d)


def _compute_mastery_display(
    current_count: int,
    tiers: list[dict[str, Any]],
) -> tuple[str, str, bool, float]:
    """Retourne (label_niveau, label_compteur, is_master, progress_ratio).

    progress_ratio représente l'avancement *dans le niveau actuel* (0..1).
    """

    targets: list[int] = []
    for t in tiers or []:
        v = t.get("target_count")
        if v is None:
            continue
        try:
            targets.append(int(v))
        except Exception:
            continue
    targets = sorted({x for x in targets if x > 0})

    try:
        cur = int(current_count)
    except Exception:
        cur = 0
    if cur < 0:
        cur = 0

    if not targets:
        return "—", "", False, 0.0

    master_target = targets[-1]
    if cur >= master_target:
        # En Maître, on affiche uniquement le total.
        return "Maître", f"{cur}", True, 1.0

    # Niveau = palier actuel + 1 (en considérant qu'en dessous du palier 1 => niveau 1)
    completed = 0
    for target in targets:
        if cur >= target:
            completed += 1
        else:
            break

    next_target = targets[min(completed, len(targets) - 1)]
    prev_target = 0 if completed <= 0 else targets[completed - 1]
    denom = max(1, int(next_target - prev_target))
    ratio = float(max(0, cur - prev_target)) / float(denom)
    if ratio < 0.0:
        ratio = 0.0
    if ratio > 1.0:
        ratio = 1.0
    level = completed + 1
    return f"Niveau {level}", f"{cur}/{next_target}", False, ratio


def _image_basename_from_item(item: dict[str, Any]) -> str | None:
    for k in ("image_path", "image_url", "image_file"):
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            return os.path.basename(v.strip().replace("\\", "/"))
    return None


@st.cache_data(show_spinner=False)
def load_h5g_commendations_exclude(
    path: str = DEFAULT_H5G_EXCLUDE_PATH,
    mtime: float | None = None,
) -> tuple[set[str], set[str]]:
    abs_path = _abs_from_repo(path)
    if not os.path.exists(abs_path):
        return set(), set()

    try:
        with open(abs_path, encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return set(), set()

    excluded_images: set[str] = set()
    excluded_names: set[str] = set()

    def _consume(values: Any, *, as_image: bool) -> None:
        if not isinstance(values, list):
            return
        for v in values:
            if not isinstance(v, str):
                continue
            s = v.strip()
            if not s:
                continue
            if as_image:
                excluded_images.add(os.path.basename(s.replace("\\", "/")))
            else:
                excluded_names.add(_normalize_name(s))

    if isinstance(raw, list):
        for v in raw:
            if not isinstance(v, str):
                continue
            s = v.strip()
            if not s:
                continue
            # Heuristique: si ça ressemble à un nom de fichier, c'est une image.
            if "." in os.path.basename(s.replace("\\", "/")):
                excluded_images.add(os.path.basename(s.replace("\\", "/")))
            else:
                excluded_names.add(_normalize_name(s))
        return excluded_images, excluded_names

    if isinstance(raw, dict):
        _consume(raw.get("image_basenames"), as_image=True)
        _consume(raw.get("names"), as_image=False)
        # Compat: certains préfèrent {items:[...]}.
        _consume(raw.get("items"), as_image=False)
        return excluded_images, excluded_names

    return set(), set()


@st.cache_data(show_spinner=False)
def load_h5g_commendations_json(
    path: str = DEFAULT_H5G_JSON_PATH, mtime: float | None = None
) -> dict[str, Any]:
    abs_path = _abs_from_repo(path)
    if not os.path.exists(abs_path):
        return {"items": []}
    with open(abs_path, encoding="utf-8") as f:
        data = json.load(f) or {}
    if not isinstance(data, dict):
        return {"items": []}
    if not isinstance(data.get("items"), list):
        data["items"] = []
    return data


def _img_src(item: dict[str, Any]) -> str | None:
    # Priorité: chemin local.
    p = item.get("image_path")
    if isinstance(p, str) and p.strip():
        abs_p = _abs_from_repo(p.strip())
        if os.path.exists(abs_p):
            return abs_p
    return None


@st.cache_data(show_spinner=False)
def _img_data_uri(abs_path: str, mtime: float | None = None) -> str | None:
    _ = mtime
    if not abs_path or not os.path.exists(abs_path):
        return None
    ext = os.path.splitext(abs_path)[1].lower()
    mime = (
        "image/png"
        if ext == ".png"
        else "image/jpeg"
        if ext in {".jpg", ".jpeg"}
        else "application/octet-stream"
    )
    try:
        with open(abs_path, "rb") as f:
            raw = f.read()
    except Exception:
        return None
    if not raw:
        return None
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{b64}"


def render_h5g_commendations_section(
    *,
    db_path: str | None = None,
    xuid: str | None = None,
    filtered_match_ids: list[str] | None = None,
    all_match_ids: list[str] | None = None,
) -> None:
    """Affiche la section des commendations Halo 5.

    Utilise ``CitationEngine`` pour agréger les valeurs depuis ``match_citations``.

    Args:
        db_path: Chemin vers la base DuckDB du joueur.
        xuid: XUID du joueur.
        filtered_match_ids: IDs des matchs filtrés (pour delta). ``None`` = pas de filtre.
        all_match_ids: IDs de tous les matchs. ``None`` = agrège tout sans filtre.
    """
    from src.analysis.citations.engine import CitationEngine

    abs_json = _abs_from_repo(DEFAULT_H5G_JSON_PATH)
    json_mtime = None
    try:
        json_mtime = os.path.getmtime(abs_json)
    except OSError:
        json_mtime = None

    data = load_h5g_commendations_json(DEFAULT_H5G_JSON_PATH, json_mtime)
    items: list[dict[str, Any]] = list(data.get("items") or [])

    # Le filtrage des citations se fait désormais via citation_mappings.enabled
    # dans metadata.duckdb (pas besoin du JSON d'exclusion).

    if not items:
        c1, c2 = st.columns([2, 1])
        with c1:
            st.info(
                "Référentiel indisponible. "
                "Si le fichier JSON vient d'être créé/modifié, clique sur *Recharger* (cache Streamlit)."
            )
            st.caption(f"Chemin attendu: {abs_json}")
        with c2:
            if st.button("Recharger", width="stretch"):
                load_h5g_commendations_json.clear()
                st.rerun()
        return

    # Charger les mappings et agréger les valeurs via CitationEngine
    engine: CitationEngine | None = None
    citations_full: dict[str, int] = {}
    citations_filtered: dict[str, int] = {}

    if db_path and xuid:
        engine = CitationEngine(db_path, xuid)
        # Agrégation complète (tous les matchs)
        citations_full = engine.aggregate_for_display(match_ids=None)
        # Agrégation filtrée si nécessaire
        if filtered_match_ids is not None:
            citations_filtered = engine.aggregate_for_display(match_ids=filtered_match_ids)

    # Détermine si on est en mode filtré
    is_filtered = filtered_match_ids is not None and all_match_ids is not None

    # SUPPRIMÉ : Ne plus filtrer les citations par mapping
    # On affiche toutes les citations du JSON, même si elles n'ont pas de valeur
    # mapped_norms = set(citation_mappings.keys())
    # items = [it for it in items if _has_mapping(it)]

    # Filtres UI
    cats = sorted(
        {
            str(x.get("category") or "").strip()
            for x in items
            if str(x.get("category") or "").strip()
        }
    )
    c1, c2 = st.columns([1, 2])
    with c1:
        picked_cat = st.selectbox("Catégorie", options=["(toutes)"] + cats, index=0)
    with c2:
        q = st.text_input("Recherche", value="", placeholder="ex: assassin, pilote, multifrag…")

    filtered = items
    if picked_cat != "(toutes)":
        filtered = [x for x in filtered if str(x.get("category") or "").strip() == picked_cat]
    if q.strip():
        qn = q.strip().lower()
        filtered = [
            x
            for x in filtered
            if (qn in str(x.get("name") or "").lower())
            or (qn in str(x.get("description") or "").lower())
            or (qn in str(x.get("category") or "").lower())
        ]

    # Grille 8 colonnes
    cols_per_row = 8
    cols = st.columns(cols_per_row)
    for i, item in enumerate(filtered):
        col = cols[i % cols_per_row]
        name_raw = str(item.get("name") or "").strip()
        desc_raw = str(item.get("description") or "").strip()
        name = _display_citation_name(name_raw)
        desc = _display_citation_desc(desc_raw, name_raw)
        img = _img_src(item)
        tiers = item.get("tiers") or []

        norm_name = _normalize_name(name_raw)

        # Valeurs depuis match_citations (agrégées par CitationEngine)
        current_full = citations_full.get(norm_name, 0)
        current_filtered = citations_filtered.get(norm_name, 0) if is_filtered else current_full

        # Calcul du delta pour cette citation
        delta_citation = current_filtered if (is_filtered and current_filtered > 0) else 0

        level_label, counter_label, is_master, progress_ratio = _compute_mastery_display(
            current_full, tiers
        )

        with col:
            st.markdown("<div class='os-citation-top-gap'></div>", unsafe_allow_html=True)
            data_uri = None
            if img:
                try:
                    mtime = os.path.getmtime(img)
                except OSError:
                    mtime = None
                data_uri = _img_data_uri(img, mtime)

            # Tooltip avec la description de la citation.
            tip = html.escape(desc) if desc else html.escape(name)

            if data_uri:
                ring_class = (
                    "os-citation-ring os-citation-ring--master" if is_master else "os-citation-ring"
                )
                ring_color = "#d6b35a" if is_master else "#41d6ff"
                st.markdown(
                    "<div class='"
                    + ring_class
                    + "' title='"
                    + tip
                    + "' "
                    + 'style="--p:'
                    + str(float(progress_ratio))
                    + ";--ring-color:"
                    + ring_color
                    + ";--img:url('"
                    + data_uri
                    + "')\"></div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    "<div class='os-medal-missing' title='" + tip + "'>?</div>",
                    unsafe_allow_html=True,
                )

            st.markdown(
                "<div class='os-citation-name' title='" + tip + "'>" + html.escape(name) + "</div>",
                unsafe_allow_html=True,
            )
            level_class = (
                "os-citation-level os-citation-level--master" if is_master else "os-citation-level"
            )
            st.markdown(
                f"<div class='{level_class}'>{html.escape(level_label)}</div>",
                unsafe_allow_html=True,
            )
            # Afficher le compteur avec le delta si filtré
            delta_html = ""
            if is_filtered and delta_citation > 0:
                delta_html = (
                    f" <span style='color: #4CAF50; font-weight: bold;'>+{delta_citation}</span>"
                )
            st.markdown(
                "<div class='os-citation-counter'>"
                + html.escape(counter_label)
                + delta_html
                + "</div>",
                unsafe_allow_html=True,
            )
