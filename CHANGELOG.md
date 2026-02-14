# Changelog

Toutes les modifications notables de ce projet sont documentées ici.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).

## [Unreleased]

### Added

- **Citations DuckDB-first** — Nouveau système de citations stockées par match dans `match_citations`
  - `CitationEngine` (`src/analysis/citations/engine.py`) : moteur de calcul et agrégation SQL
  - Table `citation_mappings` dans `metadata.duckdb` : 14 règles (8 existantes + 6 réintégrées)
  - Table `match_citations` dans chaque `stats.duckdb` joueur
  - Backfill CLI : `--citations` / `--force-citations` dans `scripts/backfill_data.py`
  - 6 citations objectives réintégrées : Défenseur du drapeau, Je te tiens !, Sus au porteur du drapeau, Partie prenante, À la charge, Annexion forcée
  - Documentation : `docs/CITATIONS.md`
  - Script diagnostic : `scripts/diagnose_citations.py`
- **Colonne `enabled`** dans `citation_mappings` : permet de désactiver une citation sans supprimer le mapping
- **Support V5 (shared_matches)** dans `CitationEngine` :
  - Auto-détection de `shared_matches.duckdb`
  - `load_match_medals()` lit `shared.medals_earned` filtré par xuid
  - `load_match_stats()` / `load_match_df()` lisent depuis `shared.match_participants` + `shared.match_registry`
  - Fallback transparent V4 si shared n'existe pas

### Changed

- `render_h5g_commendations_section()` utilise désormais `CitationEngine` au lieu du calcul à la volée
  - Nouvelle signature : `db_path`, `xuid`, `filtered_match_ids`, `all_match_ids`
  - Performance améliorée : agrégation SQL vs itérations row-by-row (~90% plus rapide)
- `render_citations_page()` simplifié : ne pré-agrège plus les médailles/stats pour les citations
- Filtrage des citations désormais piloté par `citation_mappings.enabled` (plus besoin du JSON d'exclusion)

### Removed

- `CUSTOM_CITATION_RULES` dict (était dans `commendations.py`)
- `_compute_custom_citation_value()` fonction (itérations lentes)
- `load_h5g_commendations_tracking_rules()` — remplacé par `citation_mappings` DuckDB
- Constantes `DEFAULT_H5G_TRACKING_ASSUMED_PATH` / `DEFAULT_H5G_TRACKING_UNMATCHED_PATH`
- Dépendance aux fichiers JSON de tracking (`out/commendations_mapping_*.json`)
- Logique d'exclusion JSON dans `render_h5g_commendations_section()` (remplacée par `enabled` en DB)
