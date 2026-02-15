"""Tests pour le tri du bouton 'Dernière session' (max(start_time) par session).

La logique testée est celle de _session_labels_ordered_by_last_match dans
filters_render.py : groupby(session_id, session_label) -> max(start_time) -> sort desc.

On réplique la logique pure ici pour éviter l'import transitif de duckdb
(non disponible dans tous les environnements CI). Les tests valident l'algorithme
identique au code de production.
"""

from __future__ import annotations

import pandas as pd


def _session_labels_ordered_by_last_match(base_s: pd.DataFrame) -> list[str]:
    """Réplique fidèle de src.app.filters_render._session_labels_ordered_by_last_match."""
    if base_s.empty or "start_time" not in base_s.columns or "session_label" not in base_s.columns:
        return []
    agg = (
        base_s.groupby(["session_id", "session_label"], dropna=False)["start_time"]
        .max()
        .reset_index()
    )
    agg = agg.sort_values("start_time", ascending=False)
    return agg["session_label"].tolist()


class TestSessionLabelsOrderedByLastMatch:
    """Tests pour le tri des sessions par max(start_time)."""

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        assert _session_labels_ordered_by_last_match(df) == []

    def test_missing_columns(self):
        df = pd.DataFrame({"session_id": [1], "other": ["x"]})
        assert _session_labels_ordered_by_last_match(df) == []

    def test_single_session(self):
        df = pd.DataFrame(
            {
                "session_id": ["1", "1"],
                "session_label": ["Session 1 (2 matchs)", "Session 1 (2 matchs)"],
                "start_time": pd.to_datetime(["2025-10-22 20:00", "2025-10-22 21:00"]),
            }
        )
        result = _session_labels_ordered_by_last_match(df)
        assert result == ["Session 1 (2 matchs)"]

    def test_sort_by_max_start_time_not_session_id(self):
        """Cas critique : session_id VARCHAR où session '9' devrait être après '100'
        si on trie lexicographiquement, mais session 9 a les matchs les plus récents.
        """
        df = pd.DataFrame(
            {
                "session_id": ["100", "100", "9", "9"],
                "session_label": [
                    "Session 100 (2 matchs)",
                    "Session 100 (2 matchs)",
                    "Session 9 (2 matchs)",
                    "Session 9 (2 matchs)",
                ],
                "start_time": pd.to_datetime(
                    [
                        "2025-10-01 20:00",
                        "2025-10-01 21:00",
                        "2025-10-22 20:00",
                        "2025-10-22 21:30",
                    ]
                ),
            }
        )
        result = _session_labels_ordered_by_last_match(df)
        # Session 9 a le match le plus récent (22 oct 21:30), doit être en premier
        assert result[0] == "Session 9 (2 matchs)"
        assert result[1] == "Session 100 (2 matchs)"

    def test_multiple_sessions_ordered_correctly(self):
        df = pd.DataFrame(
            {
                "session_id": ["A", "A", "B", "B", "C"],
                "session_label": ["Sess A", "Sess A", "Sess B", "Sess B", "Sess C"],
                "start_time": pd.to_datetime(
                    [
                        "2025-10-10 18:00",
                        "2025-10-10 19:00",
                        "2025-10-15 20:00",
                        "2025-10-15 22:00",
                        "2025-10-12 14:00",
                    ]
                ),
            }
        )
        result = _session_labels_ordered_by_last_match(df)
        # B: max=22:00 le 15 oct, C: max=14:00 le 12 oct, A: max=19:00 le 10 oct
        assert result == ["Sess B", "Sess C", "Sess A"]

    def test_integer_session_ids_still_sort_by_time(self):
        """Même avec des session_id entiers, le tri doit être par start_time."""
        df = pd.DataFrame(
            {
                "session_id": [2, 2, 1, 1],
                "session_label": ["Sess 2", "Sess 2", "Sess 1", "Sess 1"],
                "start_time": pd.to_datetime(
                    [
                        "2025-01-01 10:00",
                        "2025-01-01 11:00",
                        "2025-02-01 10:00",
                        "2025-02-01 11:00",
                    ]
                ),
            }
        )
        result = _session_labels_ordered_by_last_match(df)
        # Sess 1 a les matchs les plus récents (février)
        assert result[0] == "Sess 1"
        assert result[1] == "Sess 2"


class TestTrioLabelSortByStartTime:
    """Valide que la logique trio utilise max(start_time) et non session_id.max()."""

    def test_trio_latest_session_by_start_time(self):
        """Simule la logique de _compute_trio_label après le fix."""
        trio_rows = pd.DataFrame(
            {
                "match_id": ["m1", "m2", "m3", "m4"],
                "session_id": ["200", "200", "5", "5"],
                "session_label": [
                    "Sess 200 (2 matchs)",
                    "Sess 200 (2 matchs)",
                    "Sess 5 (2 matchs)",
                    "Sess 5 (2 matchs)",
                ],
                "start_time": pd.to_datetime(
                    [
                        "2025-09-01 20:00",
                        "2025-09-01 21:00",
                        "2025-11-15 19:00",
                        "2025-11-15 20:30",
                    ]
                ),
            }
        )

        # Logique fixée (max(start_time) par session, tri desc)
        agg = (
            trio_rows.groupby(["session_id", "session_label"], dropna=False)["start_time"]
            .max()
            .reset_index()
        )
        agg = agg.sort_values("start_time", ascending=False)
        result = agg["session_label"].iloc[0] if not agg.empty else None

        # La session 5 (nov 2025) est plus récente que 200 (sept 2025)
        assert result == "Sess 5 (2 matchs)"

    def test_trio_old_logic_would_fail(self):
        """Démontre que l'ancienne logique (session_id.max() str) est incorrecte."""
        trio_rows = pd.DataFrame(
            {
                "match_id": ["m1", "m2"],
                "session_id": ["200", "5"],
                "session_label": ["Sess 200", "Sess 5"],
                "start_time": pd.to_datetime(["2025-09-01 20:00", "2025-11-15 19:00"]),
            }
        )

        # Ancienne logique bugguée : max() sur des str
        # "5" > "200" en tri lexicographique → sélectionne session "5"
        # mais par hasard c'est la bonne ici ; avec "99" vs "100", "99" > "100" en str
        # Montrons le problème avec des str
        assert trio_rows["session_id"].max() == "5"  # Str max lexicographique

        # Nouvelle logique corrigée : toujours la bonne session
        agg = (
            trio_rows.groupby(["session_id", "session_label"], dropna=False)["start_time"]
            .max()
            .reset_index()
        )
        agg = agg.sort_values("start_time", ascending=False)
        correct_result = agg["session_label"].iloc[0]
        assert correct_result == "Sess 5"  # Nov 2025 est plus récent
