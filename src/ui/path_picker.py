"""Widgets Streamlit pour choisir un chemin local.

Streamlit ne fournit pas (encore) de sélecteur natif de dossier multi-plateforme.
On implémente donc un petit navigateur de dossiers, utile quand l'app tourne en local.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

import streamlit as st


def _list_windows_drives() -> list[str]:
    drives: list[str] = []
    for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        root = f"{c}:\\"
        if os.path.exists(root):
            drives.append(root)
    return drives


def _safe_listdir_dirs(path: str) -> list[str]:
    try:
        entries = os.listdir(path)
    except Exception:
        return []

    out: list[str] = []
    for name in entries:
        try:
            p = os.path.join(path, name)
            if os.path.isdir(p):
                out.append(name)
        except Exception:
            continue
    out.sort(key=lambda s: s.casefold())
    return out


def _safe_listdir_files(path: str, *, exts: Iterable[str] | None = None) -> list[str]:
    try:
        entries = os.listdir(path)
    except Exception:
        return []

    norm_exts: set[str] | None = None
    if exts is not None:
        norm_exts = set()
        for e in exts:
            s = str(e or "").strip().lower()
            if not s:
                continue
            if not s.startswith("."):
                s = "." + s
            norm_exts.add(s)
        if not norm_exts:
            norm_exts = None

    out: list[str] = []
    for name in entries:
        try:
            p = os.path.join(path, name)
            if not os.path.isfile(p):
                continue
            if norm_exts is not None and Path(name).suffix.lower() not in norm_exts:
                continue
            out.append(name)
        except Exception:
            continue
    out.sort(key=lambda s: s.casefold())
    return out


def directory_input(
    label: str,
    *,
    value: str = "",
    key: str,
    help: str | None = None,
    placeholder: str = "",
    start_path: str | None = None,
) -> str:
    """Champ de saisie simple pour un dossier.

    Args:
        label: Libellé.
        value: Valeur initiale.
        key: Base key (stable) pour session_state.
        help: Texte d'aide.
        placeholder: Placeholder du champ.
        start_path: Non utilisé (compatibilité).

    Returns:
        Chemin choisi (string).
    """

    text_key = f"{key}__text"

    if text_key not in st.session_state:
        st.session_state[text_key] = str(value or "")

    path_value = st.text_input(
        label,
        value=st.session_state[text_key],
        key=text_key,
        help=help or "Collez le chemin absolu du dossier (ex: C:\\Users\\...\\Videos)",
        placeholder=placeholder or "C:\\Users\\...\\Videos",
    )

    return str(path_value or "").strip()


def file_input(
    label: str,
    *,
    value: str = "",
    key: str,
    help: str | None = None,
    placeholder: str = "",
    start_path: str | None = None,
    exts: Iterable[str] | None = None,
) -> str:
    """Champ de saisie simple pour un fichier.

    Args:
        label: Libellé.
        value: Valeur initiale.
        key: Key pour session_state.
        help: Texte d'aide.
        placeholder: Placeholder du champ.
        start_path: Non utilisé (compatibilité).
        exts: Non utilisé (compatibilité).

    Returns:
        Chemin choisi (string).
    """

    if key not in st.session_state:
        st.session_state[key] = str(value or "")

    file_value = st.text_input(
        label,
        value=st.session_state[key],
        key=key,
        help=help or "Collez le chemin absolu du fichier",
        placeholder=placeholder or "C:\\Users\\...\\file.ext",
    )

    return str(file_value or "").strip()
