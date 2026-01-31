# CLAUDE.md - Instructions pour agents IA

> Ce fichier est lu par Claude Code et autres agents IA au début de chaque session.

## Contexte Projet

OpenSpartan Graph - Dashboard de statistiques Halo Infinite avec architecture hybride SQLite + Parquet.

## Workflow Agentique

**AVANT TOUTE ACTION** : Consulter les fichiers `.ai/` :
- `.ai/project_map.md` : Cartographie du projet
- `.ai/thought_log.md` : Journal des décisions
- `.ai/data_lineage.md` : Flux de données

**APRÈS CHAQUE MODIFICATION SIGNIFICATIVE** : Mettre à jour ces fichiers.

## Architecture des Données

| Type | Stockage | Chemin |
|------|----------|--------|
| Référentiels | SQLite | `data/warehouse/metadata.db` |
| Matchs (volume) | Parquet | `data/warehouse/match_facts/` |
| Config | JSON | `db_profiles.json`, `app_settings.json` |

## Commandes Utiles

```bash
# Ingestion des référentiels
python scripts/ingest_halo_data.py --action all

# Lancer l'app Streamlit
streamlit run streamlit_app.py

# Tests
pytest tests/ -v
```

## Règles

1. Répondre en français
2. Utiliser Pydantic v2 pour valider les données
3. Préférer Polars à Pandas pour les gros volumes
4. Documenter les décisions dans `.ai/thought_log.md`
