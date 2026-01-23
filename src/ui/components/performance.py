"""Composants UI pour les scores de performance.

Ce module contient les fonctions de calcul et d'affichage
des scores de performance pour les sessions de jeu.
"""

from __future__ import annotations

from typing import Callable

import pandas as pd
import streamlit as st

from src.analysis.performance_score import (
    compute_session_performance_score_v1,
    compute_session_performance_score_v2,
)


def compute_session_performance_score(df_session: pd.DataFrame) -> dict:
    """Calcule un score de performance (0-100) pour une session.
    
    Le score est une moyenne pondérée de :
    - K/D ratio normalisé (30%)
    - Win rate (25%)
    - Précision moyenne (25%)
    - Score moyen par partie normalisé (20%)
    
    Args:
        df_session: DataFrame contenant les matchs de la session.
        
    Returns:
        Dict avec score global et composantes détaillées.
    """
    return compute_session_performance_score_v1(df_session)


def compute_session_performance_score_v2_ui(
    df_session: pd.DataFrame,
    *,
    include_mmr_adjustment: bool = True,
) -> dict:
    """Calcule un score de performance v2 (0–100) pour une session.

    Version pensée pour être réutilisée ailleurs que dans la page de comparaison.
    """
    return compute_session_performance_score_v2(
        df_session,
        include_mmr_adjustment=include_mmr_adjustment,
    )


def get_score_color(score: float | None) -> str:
    """Retourne la couleur CSS selon le score de performance."""
    if score is None:
        return "#9E9E9E"  # Gris
    if score >= 75:
        return "#1B5E20"  # Vert foncé (excellent)
    if score >= 60:
        return "#4CAF50"  # Vert (bon)
    if score >= 45:
        return "#FF9800"  # Orange (moyen)
    if score >= 30:
        return "#F44336"  # Rouge (faible)
    return "#B71C1C"  # Rouge foncé (mauvais)


def get_score_label(score: float | None) -> str:
    """Retourne le label textuel selon le score."""
    if score is None:
        return "N/A"
    if score >= 75:
        return "Excellent"
    if score >= 60:
        return "Bon"
    if score >= 45:
        return "Moyen"
    if score >= 30:
        return "Faible"
    return "Difficile"


def render_performance_score_card(
    label: str,
    perf: dict,
    is_better: bool | None = None,
) -> None:
    """Affiche une grande carte avec le score de performance.
    
    Args:
        label: Titre de la carte (ex: "Session A").
        perf: Dict retourné par compute_session_performance_score.
        is_better: True si cette session est meilleure, False si pire, None si pas de comparaison.
    """
    score = perf.get("score")
    color = get_score_color(score)
    score_label = get_score_label(score)
    score_display = f"{score:.0f}" if score is not None else "—"
    
    # Indicateur de comparaison
    badge = ""
    if is_better is True:
        badge = "<span style='color: #1B5E20; font-size: 1.2rem; margin-left: 8px;'>▲</span>"
    elif is_better is False:
        badge = "<span style='color: #B71C1C; font-size: 1.2rem; margin-left: 8px;'>▼</span>"
    
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            border: 2px solid {color};
            border-radius: 16px;
            padding: 24px;
            text-align: center;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        ">
            <div style="color: #9E9E9E; font-size: 0.9rem; margin-bottom: 8px;">{label}</div>
            <div style="
                color: {color};
                font-size: 4rem;
                font-weight: 800;
                line-height: 1;
            ">{score_display}{badge}</div>
            <div style="color: {color}; font-size: 1.1rem; margin-top: 8px; font-weight: 600;">{score_label}</div>
            <div style="color: #757575; font-size: 0.85rem; margin-top: 12px;">
                {perf.get('matches', 0)} parties
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_comparison_row(
    label: str,
    val_a,
    val_b,
    fmt: str | Callable = "{}",
    higher_is_better: bool = True,
) -> None:
    """Affiche une ligne de métrique avec comparaison colorée.
    
    Args:
        label: Nom de la métrique.
        val_a: Valeur pour la session A.
        val_b: Valeur pour la session B.
        fmt: Format string pour l'affichage OU une fonction callable.
        higher_is_better: Si True, la valeur la plus haute est verte.
    """
    col1, col2, col3 = st.columns([2, 1, 1])
    
    # Déterminer les couleurs
    color_a, color_b = "#E0E0E0", "#E0E0E0"
    if val_a is not None and val_b is not None:
        if higher_is_better:
            if val_a > val_b:
                color_a = "#4CAF50"
            elif val_b > val_a:
                color_b = "#4CAF50"
        else:
            if val_a < val_b:
                color_a = "#4CAF50"
            elif val_b < val_a:
                color_b = "#4CAF50"
    
    # Fonction de formatage
    def _format_value(val):
        if val is None:
            return "—"
        if callable(fmt):
            return fmt(val)
        return fmt.format(val)
    
    with col1:
        st.markdown(f"**{label}**")
    with col2:
        display_a = _format_value(val_a)
        st.markdown(
            f"<span style='color: {color_a}; font-weight: 600;'>{display_a}</span>",
            unsafe_allow_html=True,
        )
    with col3:
        display_b = _format_value(val_b)
        st.markdown(
            f"<span style='color: {color_b}; font-weight: 600;'>{display_b}</span>",
            unsafe_allow_html=True,
        )
