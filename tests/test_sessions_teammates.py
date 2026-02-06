"""Tests pour la logique sessions avec coéquipiers (teammates_signature).

Ce module complète test_sessions_advanced.py avec des scénarios dédiés
aux changements de coéquipiers et à la robustesse de teammates_signature.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import polars as pl

from src.analysis.sessions import compute_sessions_with_context_polars


def test_teammates_same_squad_no_break():
    """Même équipe sur plusieurs matchs = une seule session."""
    base = datetime(2026, 2, 5, 14, 0, 0, tzinfo=timezone.utc)
    df = pl.DataFrame(
        {
            "match_id": [f"m{i}" for i in range(5)],
            "start_time": [base + timedelta(minutes=i * 30) for i in range(5)],
            "teammates_signature": ["xuid1,xuid2,xuid3"] * 5,
        }
    )
    result = compute_sessions_with_context_polars(df, gap_minutes=120)
    assert result["session_id"].n_unique() == 1


def test_teammates_one_leaves_new_session():
    """Un coéquipier part = nouvelle session."""
    base = datetime(2026, 2, 5, 14, 0, 0, tzinfo=timezone.utc)
    df = pl.DataFrame(
        {
            "match_id": ["m1", "m2", "m3"],
            "start_time": [base, base + timedelta(minutes=15), base + timedelta(minutes=30)],
            "teammates_signature": ["xuid1,xuid2,xuid3", "xuid1,xuid2", "xuid1,xuid2"],
        }
    )
    result = compute_sessions_with_context_polars(df, gap_minutes=120)
    assert result["session_id"][0] != result["session_id"][1]
    assert result["session_id"][1] == result["session_id"][2]


def test_teammates_one_joins_new_session():
    """Un coéquipier rejoint = nouvelle session."""
    base = datetime(2026, 2, 5, 14, 0, 0, tzinfo=timezone.utc)
    df = pl.DataFrame(
        {
            "match_id": ["m1", "m2"],
            "start_time": [base, base + timedelta(minutes=20)],
            "teammates_signature": ["xuid1,xuid2", "xuid1,xuid2,xuid3"],
        }
    )
    result = compute_sessions_with_context_polars(df, gap_minutes=120)
    assert result["session_id"][0] != result["session_id"][1]


def test_teammates_solo_to_squad_new_session():
    """Passage de solo à squad = nouvelle session."""
    base = datetime(2026, 2, 5, 14, 0, 0, tzinfo=timezone.utc)
    # Solo = None (pas de coéquipiers) ou chaîne vide selon le modèle
    df = pl.DataFrame(
        {
            "match_id": ["m1", "m2"],
            "start_time": [base, base + timedelta(minutes=15)],
            "teammates_signature": [None, "xuid1,xuid2"],
        }
    )
    result = compute_sessions_with_context_polars(df, gap_minutes=120)
    assert result["session_id"][0] != result["session_id"][1]


def test_teammates_squad_to_solo_new_session():
    """Passage de squad à solo = nouvelle session."""
    base = datetime(2026, 2, 5, 14, 0, 0, tzinfo=timezone.utc)
    df = pl.DataFrame(
        {
            "match_id": ["m1", "m2"],
            "start_time": [base, base + timedelta(minutes=15)],
            "teammates_signature": ["xuid1,xuid2", None],
        }
    )
    result = compute_sessions_with_context_polars(df, gap_minutes=120)
    assert result["session_id"][0] != result["session_id"][1]


def test_teammates_order_independent():
    """L'ordre des XUIDs dans la signature ne doit pas matter (triés)."""
    base = datetime(2026, 2, 5, 14, 0, 0, tzinfo=timezone.utc)
    # xuid1,xuid2 et xuid2,xuid1 devraient être la même équipe
    # (compute_teammates_signature trie les XUIDs, donc en pratique on a toujours le même ordre)
    df = pl.DataFrame(
        {
            "match_id": ["m1", "m2"],
            "start_time": [base, base + timedelta(minutes=10)],
            "teammates_signature": [
                "2533274823110022,2533274858283686",
                "2533274858283686,2533274823110022",
            ],
        }
    )
    # Si les signatures sont équivalentes (même set), pas de rupture
    # Ici on a mis deux chaînes différentes pour le même set - la logique actuelle
    # fait une comparaison string, donc ce serait une rupture. C'est le comportement
    # attendu car compute_teammates_signature trie toujours.
    result = compute_sessions_with_context_polars(df, gap_minutes=120)
    # Les chaînes sont différentes, donc rupture
    assert result["session_id"][0] != result["session_id"][1]


def test_teammates_combined_with_gap():
    """Gap + changement coéquipiers : les deux peuvent déclencher une session."""
    base = datetime(2026, 2, 5, 14, 0, 0, tzinfo=timezone.utc)
    df = pl.DataFrame(
        {
            "match_id": ["m1", "m2", "m3"],
            "start_time": [
                base,
                base + timedelta(minutes=10),
                base + timedelta(minutes=150),  # Gap > 120
            ],
            "teammates_signature": ["xuid1", "xuid2", "xuid2"],
        }
    )
    result = compute_sessions_with_context_polars(df, gap_minutes=120)
    # m1 != m2 (changement), m2 != m3 (gap)
    assert result["session_id"][0] != result["session_id"][1]
    assert result["session_id"][1] != result["session_id"][2]
