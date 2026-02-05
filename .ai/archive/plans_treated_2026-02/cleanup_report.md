# Rapport de Nettoyage - 2026-01-31 21:01:41

> Mode: **DRY-RUN**

## Résumé

| Métrique | Valeur |
|----------|--------|
| Fichiers temp supprimés | 0 |
| Dossiers temp supprimés | 0 |
| Espace libéré | 0.0 B |
| Imports inutilisés corrigés | 0 |
| Fichiers orphelins détectés | 90 |
| Fichiers avec code mort | 0 |

## Fichiers Orphelins (non importés)

Ces fichiers Python ne semblent jamais être importés. Vérifiez s'ils sont encore nécessaires :

- `src\app\main_helpers.py`
- `src\ui\sections\source.py`
- `src\data\integration\streamlit_bridge.py`
- `src\ui\components\kpi.py`
- `src\ui\profile_api_cache.py`
- `src\ui\career_ranks.py`
- `src\ui\cache.py`
- `src\data\infrastructure\database\duckdb_engine.py`
- `src\ui\pages\match_view_charts.py`
- `src\db\queries.py`
- `src\analysis\maps.py`
- `src\ui\pages\teammates_helpers.py`
- `src\ui\profile_api.py`
- `src\ui\styles.py`
- `src\ui\profile_api_urls.py`
- `src\db\profiles.py`
- `src\ui\pages\match_view_helpers.py`
- `src\data\query\examples.py`
- `src\ui\pages\media_library.py`
- `src\db\loaders.py`
- `src\ui\pages\citations.py`
- `src\data\domain\models\medal.py`
- `src\data\query\analytics.py`
- `src\ui\player_assets.py`
- `src\ui\sections\openspartan.py`
- `src\visualization\theme.py`
- `src\ui\pages\match_view_players.py`
- `src\app\helpers.py`
- `src\analysis\sessions.py`
- `src\ui\medals.py`
- `src\data\repositories\factory.py`
- `src\visualization\maps.py`
- `src\analysis\stats.py`
- `src\app\state.py`
- `src\ui\pages\teammates_charts.py`
- `src\app\sidebar.py`
- `src\analysis\killer_victim.py`
- `src\ui\sync.py`
- `src\visualization\timeseries.py`
- `src\ui\pages\settings.py`
- `src\ui\components\checkbox_filter.py`
- `src\data\domain\models\player.py`
- `src\ui\pages\match_history.py`
- `src\ui\pages\last_match.py`
- `src\data\infrastructure\database\sqlite_metadata.py`
- `src\data\repositories\protocol.py`
- `src\ui\aliases.py`
- `src\app\kpis.py`
- `src\ui\perf.py`
- `src\data\repositories\hybrid.py`
- `src\ui\formatting.py`
- `src\visualization\trio.py`
- `src\app\kpis_render.py`
- `src\app\navigation.py`
- `src\ui\commendations.py`
- `src\ui\pages\match_view.py`
- `src\ui\pages\win_loss.py`
- `src\ui\multiplayer.py`
- `src\app\filters.py`
- `src\app\data_loader.py`
- `src\analysis\filters.py`
- `src\data\infrastructure\parquet\reader.py`
- `src\data\repositories\shadow.py`
- `src\app\page_router.py`
- `src\ui\path_picker.py`
- `src\ui\components\duckdb_analytics.py`
- `src\data\repositories\legacy.py`
- `src\db\schema.py`
- `src\analysis\performance_score.py`
- `src\visualization\distributions.py`
- `src\ui\pages\teammates.py`
- `src\ui\components\performance.py`
- `src\app\routing.py`
- `src\ui\translations.py`
- `src\ui\profile_api_tokens.py`
- `src\analysis\mode_categories.py`
- `src\db\parsers.py`
- `src\data\query\engine.py`
- `src\ui\pages\session_compare.py`
- `src\data\domain\models\match.py`
- `src\ui\settings.py`
- `src\analysis\performance_config.py`
- `src\db\loaders_cached.py`
- `src\visualization\match_bars.py`
- `src\data\query\trends.py`
- `src\ui\pages\timeseries.py`
- `src\db\connection.py`
- `src\data\infrastructure\parquet\writer.py`
- `src\app\profile.py`
- `src\app\filters_render.py`

## Code Mort Potentiel

_Aucun code mort détecté (ou vulture non installé)._

## Actions Recommandées

1. **Revoir les fichiers orphelins** : Supprimer ou archiver si non utilisés
2. **Analyser le code mort** : Supprimer les fonctions non appelées
3. **Lancer les tests** : `pytest tests/ -v` après nettoyage

---

*Rapport généré automatiquement par `scripts/cleanup_codebase.py`*
