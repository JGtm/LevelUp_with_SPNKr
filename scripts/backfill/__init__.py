"""Package backfill — Refactoring structurel du script backfill_data.py.

Structure :
- core.py         : Fonctions d'insertion de base (medals, events, skill, etc.)
- detection.py    : Détection des matchs avec données manquantes (AND/OR configurable)
- strategies.py   : Stratégies de backfill spécifiques (killer/victim, end_time, perf_score)
- orchestrator.py : Orchestration du backfill pour un ou plusieurs joueurs
- cli.py          : Parsing des arguments CLI
"""
