"""UI: affichage des commendations (Halo 5 : Guardians).

Cette UI s'appuie sur le référentiel offline généré par:
- scripts/extract_h5g_commendations_fr.py

Fichiers attendus:
- data/wiki/halo5_commendations_fr.json
- static/commendations/h5g/*.png
"""

from __future__ import annotations

import json
import os
import html
import re
import unicodedata
from typing import Any
import streamlit as st

from src.config import get_repo_root

DEFAULT_H5G_JSON_PATH = os.path.join("data", "wiki", "halo5_commendations_fr.json")
DEFAULT_H5G_EXCLUDE_PATH = os.path.join("data", "wiki", "halo5_commendations_exclude.json")

# Référentiel “suivi” (curation manuelle) : définit comment calculer la progression.
DEFAULT_H5G_TRACKING_ASSUMED_PATH = os.path.join("out", "commendations_mapping_assumed_old.json")
DEFAULT_H5G_TRACKING_UNMATCHED_PATH = os.path.join("out", "commendations_mapping_unmatched_old.json")


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
    return "".join(ch for ch in unicodedata.normalize("NFKD", base) if not unicodedata.combining(ch))


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


def _display_citation_desc(desc: str) -> str:
    d = str(desc or "").strip()
    if not d:
        return d
    return _prefer_parenthetical_fr(d)


def _compute_mastery_display(
    current_count: int,
    tiers: list[dict[str, Any]],
) -> tuple[str, str, bool]:
    """Retourne (label_niveau, label_compteur, is_master)."""

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
        return "—", "", False

    master_target = targets[-1]
    if cur >= master_target:
        return "Maître", f"{cur}/{master_target}", True

    # Niveau = palier actuel + 1 (en considérant qu'en dessous du palier 1 => niveau 1)
    completed = 0
    for target in targets:
        if cur >= target:
            completed += 1
        else:
            break

    next_target = targets[min(completed, len(targets) - 1)]
    level = completed + 1
    return f"Niveau {level}", f"{cur}/{next_target}", False


def _image_basename_from_item(item: dict[str, Any]) -> str | None:
    for k in ("image_path", "image_url", "image_file"):
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            return os.path.basename(v.strip().replace("\\", "/"))
    return None


_NOTE_DROP_RE = re.compile(r"\b(a|ha)\s+supprimer\b", re.IGNORECASE)
_NOTE_MEDAL_IDS_RE = re.compile(r"\b(\d{9,})\b")


def _is_dropped_by_notes(notes: str) -> bool:
    s = str(notes or "").strip()
    if not s:
        return False
    return bool(_NOTE_DROP_RE.search(s))


def _medal_ids_from_notes(notes: str) -> list[int]:
    s = str(notes or "")
    if not s:
        return []
    # On ne considère ces ids que si la note parle explicitement de médaille(s).
    low = s.lower()
    if ("médaille" not in low) and ("medaille" not in low) and ("médailles" not in low) and ("medailles" not in low):
        return []
    out: list[int] = []
    seen: set[int] = set()
    for m in _NOTE_MEDAL_IDS_RE.finditer(s):
        try:
            nid = int(m.group(1))
        except Exception:
            continue
        if nid in seen:
            continue
        seen.add(nid)
        out.append(nid)
    return out


_SUM_COL_RE = re.compile(r"sum\(\s*(?P<col>[a-zA-Z_][a-zA-Z0-9_]*)\s*\)")


def _stat_col_from_expression(expr: str) -> str | None:
    s = str(expr or "").strip()
    if not s:
        return None
    m = _SUM_COL_RE.search(s)
    if not m:
        return None
    col = (m.group("col") or "").strip()
    return col or None


@st.cache_data(show_spinner=False)
def load_h5g_commendations_exclude(
    path: str = DEFAULT_H5G_EXCLUDE_PATH,
    mtime: float | None = None,
) -> tuple[set[str], set[str]]:
    abs_path = _abs_from_repo(path)
    if not os.path.exists(abs_path):
        return set(), set()

    try:
        with open(abs_path, "r", encoding="utf-8") as f:
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
def load_h5g_commendations_json(path: str = DEFAULT_H5G_JSON_PATH, mtime: float | None = None) -> dict[str, Any]:
    abs_path = _abs_from_repo(path)
    if not os.path.exists(abs_path):
        return {"items": []}
    with open(abs_path, "r", encoding="utf-8") as f:
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
def load_h5g_commendations_tracking_rules(
    assumed_path: str = DEFAULT_H5G_TRACKING_ASSUMED_PATH,
    assumed_mtime: float | None = None,
    unmatched_path: str = DEFAULT_H5G_TRACKING_UNMATCHED_PATH,
    unmatched_mtime: float | None = None,
) -> dict[str, dict[str, Any]]:
    """Index {normalized citation name -> règle de suivi}.

    La règle peut contenir:
    - medal_ids: list[int]  (somme de plusieurs médailles)
    - medal_id: int         (médaille unique)
    - stat: str             (ex: kills)
    - expression: str       (ex: kills = sum(kills))
    """

    def _load_one(path: str) -> list[dict[str, Any]]:
        abs_path = _abs_from_repo(path)
        if not os.path.exists(abs_path):
            return []
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
        except Exception:
            return []
        items = data.get("items")
        return items if isinstance(items, list) else []

    merged = _load_one(assumed_path) + _load_one(unmatched_path)

    out: dict[str, dict[str, Any]] = {}
    for it in merged:
        if not isinstance(it, dict):
            continue
        name = str(it.get("name") or "").strip()
        if not name:
            continue
        notes = str(it.get("notes") or "").strip()
        if _is_dropped_by_notes(notes):
            continue

        rule: dict[str, Any] = {}

        # 1) Notes explicites : "compter médailles ..." => somme d'ids.
        medal_ids = _medal_ids_from_notes(notes)
        if medal_ids:
            rule["medal_ids"] = medal_ids

        # 2) chosen / candidates
        chosen = it.get("chosen")
        candidates = it.get("candidates")
        picks: list[dict[str, Any]] = []
        if isinstance(chosen, dict):
            picks.append(chosen)
        if isinstance(candidates, list):
            picks.extend([x for x in candidates if isinstance(x, dict)])

        # Si on a déjà une règle via notes, on ne l'écrase pas.
        if "medal_ids" not in rule:
            for p in picks:
                t = p.get("type")
                if t == "medal":
                    nid = p.get("name_id")
                    if nid is None:
                        continue
                    try:
                        rule["medal_id"] = int(nid)
                        break
                    except Exception:
                        continue
                if t == "stat":
                    stat = str(p.get("stat") or "").strip()
                    expr = str(p.get("expression") or "").strip()
                    if expr:
                        rule["expression"] = expr
                        col = _stat_col_from_expression(expr)
                        if col:
                            rule["stat"] = col
                    if stat and "stat" not in rule:
                        rule["stat"] = stat
                    if rule:
                        break

        # Pas de méthode => non suivie.
        if not rule:
            continue

        out[_normalize_name(name)] = rule

    return out


def render_h5g_commendations_section(
    *,
    counts_by_medal: dict[int, int] | None = None,
    stats_totals: dict[str, int] | None = None,
) -> None:
    abs_json = _abs_from_repo(DEFAULT_H5G_JSON_PATH)
    json_mtime = None
    try:
        json_mtime = os.path.getmtime(abs_json)
    except OSError:
        json_mtime = None

    abs_excl = _abs_from_repo(DEFAULT_H5G_EXCLUDE_PATH)
    excl_mtime = None
    try:
        excl_mtime = os.path.getmtime(abs_excl)
    except OSError:
        excl_mtime = None

    abs_assumed = _abs_from_repo(DEFAULT_H5G_TRACKING_ASSUMED_PATH)
    assumed_mtime = None
    try:
        assumed_mtime = os.path.getmtime(abs_assumed)
    except OSError:
        assumed_mtime = None

    abs_unmatched = _abs_from_repo(DEFAULT_H5G_TRACKING_UNMATCHED_PATH)
    unmatched_mtime = None
    try:
        unmatched_mtime = os.path.getmtime(abs_unmatched)
    except OSError:
        unmatched_mtime = None

    tracking = load_h5g_commendations_tracking_rules(
        DEFAULT_H5G_TRACKING_ASSUMED_PATH,
        assumed_mtime,
        DEFAULT_H5G_TRACKING_UNMATCHED_PATH,
        unmatched_mtime,
    )

    counts_by_medal = counts_by_medal or {}
    stats_totals = stats_totals or {}

    data = load_h5g_commendations_json(DEFAULT_H5G_JSON_PATH, json_mtime)
    items: list[dict[str, Any]] = list(data.get("items") or [])

    excluded_images, excluded_names = load_h5g_commendations_exclude(DEFAULT_H5G_EXCLUDE_PATH, excl_mtime)
    if items and (excluded_images or excluded_names):
        kept: list[dict[str, Any]] = []
        for it in items:
            key = _image_basename_from_item(it)
            if key and key in excluded_images:
                continue
            if _normalize_name(str(it.get("name") or "")) in excluded_names:
                continue
            kept.append(it)
        excluded_count = len(items) - len(kept)
        items = kept
    else:
        excluded_count = 0

    st.subheader("Citations")
    if not items:
        c1, c2 = st.columns([2, 1])
        with c1:
            st.info(
                "Référentiel indisponible. "
                "Si le fichier JSON vient d'être créé/modifié, clique sur *Recharger* (cache Streamlit)."
            )
            st.caption(f"Chemin attendu: {abs_json}")
            if excluded_count:
                st.caption(
                    f"Note: {excluded_count} citation(s) sont exclues via {abs_excl} (blacklist)."
                )
        with c2:
            if st.button("Recharger", width="stretch"):
                load_h5g_commendations_json.clear()
                load_h5g_commendations_exclude.clear()
                st.rerun()
        return

    # Infos offline
    local_icons_dir = _abs_from_repo(os.path.join("static", "commendations", "h5g"))
    has_local_icons = os.path.isdir(local_icons_dir)
    extra = f" — {excluded_count} exclue(s)" if excluded_count else ""

    # N'affiche que les citations suivies (celles ayant une méthode de calcul).
    items = [it for it in items if _normalize_name(str(it.get("name") or "").strip()) in tracking]

    # Filtres
    cats = sorted({str(x.get("category") or "").strip() for x in items if str(x.get("category") or "").strip()})
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        picked_cat = st.selectbox("Catégorie", options=["(toutes)"] + cats, index=0)
    with c2:
        q = st.text_input("Recherche", value="", placeholder="ex: assassin, pilote, multifrag…")
    with c3:
        limit = int(st.slider("Nombre affiché", 20, 200, 60, 10))

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

    filtered = filtered[:limit]

    # 8 colonnes au lieu de 6 ≈ -25% de largeur par vignette.
    cols_per_row = 8
    cols = st.columns(cols_per_row)
    for i, item in enumerate(filtered):
        col = cols[i % cols_per_row]
        name_raw = str(item.get("name") or "").strip()
        desc_raw = str(item.get("description") or "").strip()
        name = _display_citation_name(name_raw)
        desc = _display_citation_desc(desc_raw)
        img = _img_src(item)
        key = _image_basename_from_item(item)
        tiers = item.get("tiers") or []

        rule = tracking.get(_normalize_name(name_raw)) or {}
        current = 0
        if isinstance(rule.get("medal_ids"), list):
            total = 0
            for mid in rule.get("medal_ids") or []:
                try:
                    total += int(counts_by_medal.get(int(mid), 0))
                except Exception:
                    continue
            current = int(total)
        elif rule.get("medal_id") is not None:
            try:
                current = int(counts_by_medal.get(int(rule.get("medal_id")), 0))
            except Exception:
                current = 0
        elif isinstance(rule.get("stat"), str) and rule.get("stat"):
            key = str(rule.get("stat") or "").strip()
            try:
                current = int(stats_totals.get(key, 0))
            except Exception:
                current = 0

        level_label, counter_label, is_master = _compute_mastery_display(current, tiers)

        with col:
            st.markdown("<div class='os-citation-top-gap'></div>", unsafe_allow_html=True)
            if img:
                st.image(img, width="stretch")
            else:
                st.markdown("<div class='os-medal-missing'>?</div>", unsafe_allow_html=True)

            tip = html.escape(desc) if desc else ""
            st.markdown(
                "<div class='os-citation-name' title='" + tip + "'>" + html.escape(name) + "</div>",
                unsafe_allow_html=True,
            )
            level_class = "os-citation-level os-citation-level--master" if is_master else "os-citation-level"
            st.markdown(
                f"<div class='{level_class}'>{html.escape(level_label)}</div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                "<div class='os-citation-counter'>" + html.escape(counter_label) + "</div>",
                unsafe_allow_html=True,
            )
