"""Shim de rétro-compatibilité — redirige vers src.data.sync.migrations.

DÉPRÉCIÉ : utiliser `from src.data.sync.migrations import ...` directement.
Ce fichier sera supprimé lors d'un futur sprint.
"""

from src.data.sync.migrations import (  # noqa: F401
    BACKFILL_FLAGS,
    _add_column_if_missing,
    column_exists,
    compute_backfill_mask,
    ensure_backfill_completed_column,
    ensure_end_time_column,
    ensure_match_participants_columns,
    ensure_match_stats_columns,
    ensure_medals_earned_bigint,
    ensure_performance_score_column,
    get_table_columns,
    table_exists,
)
