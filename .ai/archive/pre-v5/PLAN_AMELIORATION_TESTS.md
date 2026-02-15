# Plan d'Amélioration Tests & Couverture UI
**LevelUp - Phase Qualité & Tests**

## 📊 État Initial
- ✅ 1408 tests passés (97.3%)
- ⏭️ 38 tests ignorés (2.6%)
- ❌ 1 test échoué (qualité code)
- 📈 Couverture globale : 41%
- 🎯 Couverture UI : 5-20% (cible : 40-50%)

---

## 🎯 Objectifs Globaux

1. **Corriger le test échoué** (cache_loaders.py trop gros)
2. **Éliminer tous les warnings** (Polars + dépréciation)
3. **Améliorer couverture UI** : 5-20% → 40-50%
4. **Ajouter tests scripts critiques**
5. **Tests anti-régression** pour les corrections

**Durée totale estimée** : 4 sprints (12-15 jours)

---

# Sprint 1 : Corrections Immédiates ⚡
**Durée** : 3 jours | **Priorité** : 🔴 Critique

## Objectifs
- ✅ Tous les tests passent (0 échec)
- ✅ 0 warning Polars
- ✅ 0 API déprécié

## Tâches

### Jour 1 : Refactoring cache_loaders.py

**Problème** : 838 lignes (cible < 800)

#### 1.1 Analyser la structure actuelle
```bash
# Identifier les blocs fonctionnels
grep -n "^def " src/ui/cache_loaders.py
wc -l src/ui/cache_loaders.py
```

#### 1.2 Créer l'architecture modulaire
```
src/ui/cache_loaders/
├── __init__.py           # Exports publics (50 lignes)
├── matches.py            # Chargement matchs (250 lignes)
├── players.py            # Chargement joueurs (200 lignes)
├── metadata.py           # Métadonnées (150 lignes)
└── aggregations.py       # Agrégations (180 lignes)
```

#### 1.3 Migration progressive
- [ ] Créer le dossier `src/ui/cache_loaders/`
- [ ] Créer `__init__.py` vide
- [ ] Extraire fonctions dans modules spécialisés
- [ ] Maintenir rétrocompatibilité import
- [ ] Mettre à jour imports dans le projet
- [ ] Vérifier tests passent toujours

#### 1.4 Tests de non-régression
```python
# tests/test_cache_loaders_refactoring.py
def test_all_functions_still_importable():
    """Vérifie que tous les exports publics fonctionnent."""
    from src.ui.cache_loaders import (
        load_match_data,
        load_player_stats,
        # ... tous les exports
    )
```

**Validation** : 
```bash
python -m pytest tests/test_legacy_free_global.py::TestSprintTargetsFileSize::test_cache_loaders_under_800_lines
```

---

### Jour 2 : Corriger warnings Polars

**Problème 1** : `map_elements` inefficace (2 occurrences)

#### 2.1 Correction filters_render.py ligne 686
```python
# AVANT (inefficace)
pl.col("pair_name").map_elements(lambda s: ..., return_dtype=pl.Utf8)

# APRÈS (natif Polars)
pl.col("pair_name").map_batches(
    lambda s: translate_pair_name_vectorized(s),
    return_dtype=pl.Utf8
)
# OU si simple cast:
pl.col("pair_name").cast(pl.Utf8)
```

**Fichier** : `src/app/filters_render.py`
- [ ] Ligne 686 : `pair_name` transformation
- [ ] Ligne 692 : `map_name` transformation

#### 2.2 Créer fonctions vectorisées
```python
# src/app/filters_render.py - Ajouter en haut du fichier
def translate_pair_name_vectorized(series: pl.Series) -> pl.Series:
    """Version vectorisée de translate_pair_name pour Polars."""
    # Utiliser when().then().otherwise() chains
    return series.str.replace_all(...)
```

#### 2.3 Tests de performance
```python
# tests/test_filters_render_polars_optimization.py
def test_no_map_elements_warning():
    """Vérifie qu'aucun warning Polars n'est émis."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        # Appeler les fonctions de filtrage
        assert len([x for x in w if "map_elements" in str(x.message)]) == 0

def test_vectorized_performance():
    """La version vectorisée doit être >5x plus rapide."""
    # Benchmark ancien vs nouveau
```

**Validation** :
```bash
python -m pytest tests/test_cross_page_filter_persistence.py -W error::polars.exceptions.PolarsInefficientMapWarning
```

---

### Jour 3 : Corriger API déprécié + Tests anti-régression

**Problème** : `min_periods` déprécié (Polars 1.21+)

#### 3.1 Correction timeseries_service.py ligne 217
```python
# AVANT (déprécié)
win_rate_rolling = _wins.rolling_mean(window_size=10, min_periods=10) * 100

# APRÈS (v1.21+)
win_rate_rolling = _wins.rolling_mean(window_size=10, min_samples=10) * 100
```

**Fichier** : `src/data/services/timeseries_service.py`

#### 3.2 Rechercher autres occurrences
```bash
# Chercher tous les usages potentiels
grep -rn "min_periods" src/ tests/
grep -rn "rolling_mean" src/ tests/ | grep -v "min_samples"
```

#### 3.3 Tests de compatibilité
```python
# tests/test_timeseries_api_compatibility.py
def test_rolling_mean_uses_min_samples():
    """Vérifie l'utilisation de min_samples (non-déprécié)."""
    import inspect
    from src.data.services.timeseries_service import compute_rolling_win_rate
    
    source = inspect.getsource(compute_rolling_win_rate)
    assert "min_samples" in source
    assert "min_periods" not in source

def test_no_deprecation_warnings():
    """Aucun warning de dépréciation lors de l'exécution."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        # Appeler toutes les fonctions timeseries
        result = compute_rolling_win_rate(...)
        
        deprecation_warnings = [
            x for x in w 
            if issubclass(x.category, DeprecationWarning)
        ]
        assert len(deprecation_warnings) == 0
```

#### 3.4 Documentation des changements
- [ ] Mettre à jour CHANGELOG.md
- [ ] Documenter dans docs/POLARS_MIGRATION.md
- [ ] Ajouter commentaires dans le code

**Validation Sprint 1** :
```bash
# Tous les tests doivent passer sans warnings
python -m pytest -v --strict-warnings
python -m pytest tests/test_legacy_free_global.py -v

# Vérifier couverture maintenue
python -m pytest --cov=src --cov-report=term-missing | grep "TOTAL.*41%"
```

---

# Sprint 2 : Couverture UI - Pages Principales 🎨
**Durée** : 4 jours | **Priorité** : 🟡 Haute

## Objectifs
- 🎯 Couverture pages UI : 5-20% → 35-45%
- 📝 Tests de rendu Streamlit (mocks)
- 🧪 Tests d'interactions utilisateur

## Stratégie
Tester les pages par **flux utilisateur** plutôt que couverture exhaustive :
- Rendu sans erreur
- Gestion données vides
- Filtres fonctionnels
- Navigation

---

### Jour 1 : Framework de tests UI

#### 1.1 Helpers de tests Streamlit
```python
# tests/helpers/streamlit_mocks.py
"""Helpers pour mocker Streamlit dans les tests."""

from unittest.mock import MagicMock, patch
import pytest

@pytest.fixture
def mock_streamlit():
    """Mock complet de Streamlit pour tests UI."""
    with patch("streamlit.title"), \
         patch("streamlit.header"), \
         patch("streamlit.subheader"), \
         patch("streamlit.write"), \
         patch("streamlit.dataframe"), \
         patch("streamlit.plotly_chart") as mock_chart, \
         patch("streamlit.selectbox") as mock_select, \
         patch("streamlit.columns") as mock_cols:
        
        mock_cols.return_value = [MagicMock(), MagicMock()]
        
        yield {
            "chart": mock_chart,
            "selectbox": mock_select,
            "columns": mock_cols,
        }

@pytest.fixture
def mock_session_state():
    """Mock de st.session_state."""
    state = {}
    with patch("streamlit.session_state", state):
        yield state

@pytest.fixture
def sample_ui_data():
    """Données de test pour UI (Polars)."""
    import polars as pl
    return pl.DataFrame({
        "match_id": ["m1", "m2", "m3"],
        "start_time": ["2024-01-01", "2024-01-02", "2024-01-03"],
        "kills": [10, 15, 8],
        "deaths": [5, 8, 10],
        "outcome": [1, 1, 0],
    })
```

#### 1.2 Patterns de tests UI
```python
# tests/ui/test_ui_patterns.py
"""Patterns réutilisables pour tests UI."""

def test_page_renders_without_error(page_module, mock_streamlit, sample_ui_data):
    """Pattern : Une page se rend sans lever d'exception."""
    try:
        page_module.render(sample_ui_data)
    except Exception as e:
        pytest.fail(f"Page rendering failed: {e}")

def test_page_handles_empty_data(page_module, mock_streamlit):
    """Pattern : Gérer les DataFrames vides."""
    import polars as pl
    empty_df = pl.DataFrame()
    
    try:
        page_module.render(empty_df)
    except Exception as e:
        pytest.fail(f"Failed with empty data: {e}")

def test_page_handles_missing_columns(page_module, mock_streamlit):
    """Pattern : Gérer les colonnes manquantes."""
    import polars as pl
    minimal_df = pl.DataFrame({"match_id": ["m1"]})
    
    # Ne doit pas crasher, au pire afficher un message
    page_module.render(minimal_df)
```

---

### Jour 2 : Tests pages critiques (Career, Match History)

#### 2.1 Tests page Career
```python
# tests/ui/test_career_page_rendering.py
"""Tests de rendu pour la page Carrière."""

from src.ui.pages import career
import polars as pl

class TestCareerPageRendering:
    """Tests de rendu de la page Carrière."""
    
    def test_render_with_valid_data(self, mock_streamlit, sample_ui_data):
        """La page Career se rend avec des données valides."""
        # Ne doit pas lever d'exception
        career.render_career_page(sample_ui_data)
        
    def test_render_with_empty_matches(self, mock_streamlit):
        """Gérer l'absence de matchs."""
        empty_df = pl.DataFrame()
        career.render_career_page(empty_df)
        # Vérifier qu'un message approprié est affiché
        
    def test_career_stats_computation(self, sample_ui_data):
        """Les stats de carrière sont calculées correctement."""
        stats = career.compute_career_stats(sample_ui_data)
        
        assert "total_matches" in stats
        assert "win_rate" in stats
        assert "kd_ratio" in stats
        assert stats["total_matches"] == 3
        
    def test_career_filters_applied(self, mock_streamlit, sample_ui_data):
        """Les filtres de la page Career fonctionnent."""
        filtered = career.apply_career_filters(
            sample_ui_data,
            date_range=("2024-01-01", "2024-01-02")
        )
        assert len(filtered) == 2

class TestCareerRankDisplay:
    """Tests affichage rang de carrière."""
    
    def test_rank_display_with_rank(self, mock_streamlit):
        """Afficher le rang quand présent."""
        rank_data = {"tier": "Diamond", "level": 3, "progress": 75}
        career.render_rank_display(rank_data)
        
    def test_rank_display_without_rank(self, mock_streamlit):
        """Gérer l'absence de rang."""
        career.render_rank_display(None)
```

#### 2.2 Tests page Match History
```python
# tests/ui/test_match_history_page.py
"""Tests pour la page historique des matchs."""

from src.ui.pages import match_history

class TestMatchHistoryPage:
    """Tests de la page historique."""
    
    def test_render_match_list(self, mock_streamlit, sample_ui_data):
        """Afficher la liste des matchs."""
        match_history.render(sample_ui_data)
        
    def test_match_list_pagination(self, mock_streamlit):
        """Pagination fonctionne avec beaucoup de matchs."""
        large_dataset = pl.DataFrame({
            "match_id": [f"m{i}" for i in range(100)],
            "start_time": ["2024-01-01"] * 100,
        })
        match_history.render(large_dataset, page_size=20)
        
    def test_match_details_expansion(self, mock_streamlit, sample_ui_data):
        """Expansion des détails d'un match."""
        match_id = "m1"
        details = match_history.get_match_details(sample_ui_data, match_id)
        assert details is not None
        
    def test_filters_sidebar(self, mock_streamlit, sample_ui_data):
        """Filtres de la sidebar fonctionnent."""
        filtered = match_history.apply_filters(
            sample_ui_data,
            outcome="victory"
        )
        assert len(filtered) == 2  # m1 et m2 sont des victoires
```

---

### Jour 3 : Tests pages visualisation (Timeseries, Match View)

#### 3.1 Tests page Timeseries
```python
# tests/ui/test_timeseries_page_rendering.py
"""Tests pour la page Timeseries."""

from src.ui.pages import timeseries

class TestTimeseriesRendering:
    """Tests de rendu des graphiques temporels."""
    
    def test_render_kd_chart(self, mock_streamlit, sample_ui_data):
        """Graphique K/D se rend correctement."""
        timeseries.render_kd_timeseries(sample_ui_data)
        mock_streamlit["chart"].assert_called()
        
    def test_render_win_rate_chart(self, mock_streamlit, sample_ui_data):
        """Graphique win rate se rend."""
        timeseries.render_win_rate_chart(sample_ui_data)
        
    def test_chart_with_insufficient_data(self, mock_streamlit):
        """Gérer moins de 10 matchs (minimum rolling)."""
        small_df = pl.DataFrame({
            "match_id": ["m1", "m2"],
            "outcome": [1, 0],
        })
        # Ne doit pas crasher
        timeseries.render_win_rate_chart(small_df)
        
    def test_performance_score_chart(self, mock_streamlit, sample_ui_data):
        """Graphique performance score."""
        df_with_perf = sample_ui_data.with_columns(
            pl.lit(75.5).alias("performance_score")
        )
        timeseries.render_performance_chart(df_with_perf)

class TestTimeseriesFilters:
    """Tests des filtres de la page timeseries."""
    
    def test_date_range_filter(self, sample_ui_data):
        """Filtre par plage de dates."""
        filtered = timeseries.filter_by_date_range(
            sample_ui_data,
            start="2024-01-01",
            end="2024-01-02"
        )
        assert len(filtered) <= len(sample_ui_data)
        
    def test_playlist_filter(self, sample_ui_data):
        """Filtre par playlist."""
        df_with_playlist = sample_ui_data.with_columns(
            pl.lit("Ranked Arena").alias("playlist_name")
        )
        filtered = timeseries.filter_by_playlist(
            df_with_playlist,
            playlist="Ranked Arena"
        )
        assert len(filtered) > 0
```

#### 3.2 Tests Match View
```python
# tests/ui/test_match_view_page.py
"""Tests pour la vue détaillée d'un match."""

from src.ui.pages import match_view

class TestMatchViewPage:
    """Tests de la page vue match."""
    
    def test_render_match_overview(self, mock_streamlit, sample_match_data):
        """Vue d'ensemble du match."""
        match_view.render_overview(sample_match_data)
        
    def test_render_scoreboard(self, mock_streamlit, sample_match_data):
        """Tableau des scores."""
        match_view.render_scoreboard(sample_match_data)
        
    def test_render_timeline(self, mock_streamlit, sample_match_data):
        """Timeline des événements."""
        match_view.render_timeline(sample_match_data)
        
    def test_render_medals_section(self, mock_streamlit):
        """Section médailles."""
        medals = [
            {"name": "Killing Spree", "count": 3},
            {"name": "Double Kill", "count": 5},
        ]
        match_view.render_medals(medals)

class TestMatchViewCharts:
    """Tests des graphiques de match."""
    
    def test_damage_chart_renders(self, mock_streamlit, sample_match_data):
        """Graphique de dégâts."""
        match_view.render_damage_chart(sample_match_data)
        
    def test_accuracy_chart(self, mock_streamlit, sample_match_data):
        """Graphique de précision."""
        match_view.render_accuracy_chart(sample_match_data)
```

---

### Jour 4 : Tests pages coéquipiers & médias

#### 4.1 Tests page Teammates
```python
# tests/ui/test_teammates_page.py
"""Tests pour la page coéquipiers."""

from src.ui.pages import teammates

class TestTeammatesPage:
    """Tests page coéquipiers."""
    
    def test_render_teammates_list(self, mock_streamlit, sample_teammates_data):
        """Liste des coéquipiers."""
        teammates.render(sample_teammates_data)
        
    def test_teammate_selection(self, mock_streamlit, sample_teammates_data):
        """Sélection d'un coéquipier pour comparaison."""
        teammate = teammates.select_teammate(sample_teammates_data)
        assert teammate is not None
        
    def test_comparison_charts(self, mock_streamlit, player_data, teammate_data):
        """Graphiques de comparaison."""
        teammates.render_comparison(player_data, teammate_data)
        
    def test_synergy_metrics(self, player_data, teammate_data):
        """Métriques de synergie."""
        metrics = teammates.compute_synergy(player_data, teammate_data)
        assert "win_rate_together" in metrics
        assert "avg_assists" in metrics

class TestTeammatesFilters:
    """Tests filtres coéquipiers."""
    
    def test_min_matches_filter(self, sample_teammates_data):
        """Filtre par nombre minimum de matchs."""
        filtered = teammates.filter_by_min_matches(
            sample_teammates_data,
            min_matches=5
        )
        assert all(filtered["match_count"] >= 5)
```

#### 4.2 Tests Media Library
```python
# tests/ui/test_media_library_page.py
"""Tests pour la bibliothèque média."""

from src.ui.pages import media_library

class TestMediaLibraryPage:
    """Tests bibliothèque média."""
    
    def test_render_empty_library(self, mock_streamlit):
        """Gérer bibliothèque vide."""
        media_library.render([])
        
    def test_render_with_media(self, mock_streamlit, sample_media_items):
        """Afficher médias existants."""
        media_library.render(sample_media_items)
        
    def test_thumbnail_grid(self, mock_streamlit, sample_media_items):
        """Grille de miniatures."""
        media_library.render_thumbnail_grid(sample_media_items)
        
    def test_media_filters(self, sample_media_items):
        """Filtres de médias (type, date)."""
        filtered = media_library.filter_media(
            sample_media_items,
            media_type="screenshot"
        )
        assert all(item["type"] == "screenshot" for item in filtered)
        
    def test_lightbox_display(self, mock_streamlit, sample_media_items):
        """Affichage lightbox."""
        media_library.show_lightbox(sample_media_items[0])
```

**Validation Sprint 2** :
```bash
# Vérifier amélioration couverture UI
python -m pytest tests/ui/ -v --cov=src/ui/pages --cov-report=term-missing

# Objectif : src/ui/pages/ passe de ~10% à ~40%
```

---

# Sprint 3 : Tests Scripts Critiques 🔧
**Durée** : 3 jours | **Priorité** : 🟡 Haute

## Objectifs
- ✅ Tests pour 6 scripts critiques
- 🧪 Tests de validation des données
- 🔄 Tests de récupération d'erreurs

---

### Jour 1 : Tests scripts métadonnées

#### 1.1 Tests populate_metadata_from_discovery.py
```python
# tests/scripts/test_populate_metadata_discovery.py
"""Tests pour populate_metadata_from_discovery.py."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from populate_metadata_from_discovery import (
    discover_metadata_from_matches,
    update_metadata_tables,
)

class TestMetadataDiscovery:
    """Tests découverte métadonnées."""
    
    def test_discover_playlists(self, temp_db_with_matches):
        """Découvrir playlists depuis matchs."""
        metadata = discover_metadata_from_matches(temp_db_with_matches)
        
        assert "playlists" in metadata
        assert len(metadata["playlists"]) > 0
        
    def test_discover_maps(self, temp_db_with_matches):
        """Découvrir cartes."""
        metadata = discover_metadata_from_matches(temp_db_with_matches)
        
        assert "maps" in metadata
        assert all("map_id" in m for m in metadata["maps"])
        
    def test_update_metadata_tables(self, temp_metadata_db):
        """Mise à jour tables métadonnées."""
        new_data = {
            "playlists": [
                {"id": "p1", "name": "New Playlist"},
            ]
        }
        update_metadata_tables(temp_metadata_db, new_data)
        
        # Vérifier insertion
        conn = duckdb.connect(str(temp_metadata_db))
        result = conn.execute(
            "SELECT * FROM playlists WHERE playlist_id = 'p1'"
        ).fetchone()
        assert result is not None
        
    def test_skip_duplicates(self, temp_metadata_db):
        """Ne pas dupliquer entrées existantes."""
        data = {"playlists": [{"id": "p1", "name": "Playlist"}]}
        
        # Insérer 2 fois
        update_metadata_tables(temp_metadata_db, data)
        update_metadata_tables(temp_metadata_db, data)
        
        # Vérifier une seule entrée
        conn = duckdb.connect(str(temp_metadata_db))
        count = conn.execute(
            "SELECT COUNT(*) FROM playlists WHERE playlist_id = 'p1'"
        ).fetchone()[0]
        assert count == 1
```

#### 1.2 Tests populate_metadata_players.py
```python
# tests/scripts/test_populate_metadata_players.py
"""Tests pour populate_metadata_players.py."""

from populate_metadata_players import (
    extract_players_from_matches,
    update_player_aliases,
)

class TestPlayerMetadata:
    """Tests métadonnées joueurs."""
    
    def test_extract_players(self, sample_match_json):
        """Extraire joueurs depuis JSON match."""
        players = extract_players_from_matches([sample_match_json])
        
        assert len(players) > 0
        assert all("xuid" in p for p in players)
        assert all("gamertag" in p for p in players)
        
    def test_update_aliases(self, temp_metadata_db):
        """Mise à jour aliases joueurs."""
        players = [
            {"xuid": "12345", "gamertag": "Player1"},
            {"xuid": "12345", "gamertag": "Player1_New"},
        ]
        update_player_aliases(temp_metadata_db, players)
        
        # Vérifier historique des noms
        conn = duckdb.connect(str(temp_metadata_db))
        aliases = conn.execute(
            "SELECT * FROM player_aliases WHERE xuid = '12345'"
        ).fetchall()
        assert len(aliases) >= 2
```

---

### Jour 2 : Tests scripts utilitaires

#### 2.1 Tests resolve_missing_gamertags.py
```python
# tests/scripts/test_resolve_missing_gamertags.py
"""Tests pour resolve_missing_gamertags.py."""

from resolve_missing_gamertags import (
    find_missing_gamertags,
    resolve_via_api,
)

class TestGamertagResolution:
    """Tests résolution gamertags."""
    
    def test_find_missing(self, temp_db_with_xuids):
        """Trouver XUIDs sans gamertag."""
        missing = find_missing_gamertags(temp_db_with_xuids)
        
        assert isinstance(missing, list)
        assert all(isinstance(xuid, str) for xuid in missing)
        
    @pytest.mark.skipif(
        not os.getenv("SPARTAN_TOKEN"),
        reason="API token required"
    )
    def test_resolve_via_api(self, mock_spnkr_client):
        """Résoudre via API Halo."""
        xuids = ["12345", "67890"]
        resolved = resolve_via_api(xuids, mock_spnkr_client)
        
        assert len(resolved) == 2
        assert all("gamertag" in r for r in resolved)
        
    def test_handle_api_errors(self, mock_spnkr_client_with_errors):
        """Gérer erreurs API."""
        xuids = ["invalid_xuid"]
        resolved = resolve_via_api(xuids, mock_spnkr_client_with_errors)
        
        # Ne doit pas crasher
        assert isinstance(resolved, list)
```

#### 2.2 Tests refetch_film_roster.py
```python
# tests/scripts/test_refetch_film_roster.py
"""Tests pour refetch_film_roster.py."""

from refetch_film_roster import (
    find_matches_missing_roster,
    refetch_roster_data,
)

class TestFilmRosterRefetch:
    """Tests re-fetch roster films."""
    
    def test_find_missing_roster(self, temp_db):
        """Trouver matchs sans roster."""
        missing = find_matches_missing_roster(temp_db)
        
        assert isinstance(missing, list)
        
    def test_refetch_updates_db(self, temp_db, mock_api_client):
        """Re-fetch met à jour la DB."""
        match_ids = ["match1", "match2"]
        refetch_roster_data(temp_db, match_ids, mock_api_client)
        
        # Vérifier mise à jour
        conn = duckdb.connect(str(temp_db))
        result = conn.execute(
            "SELECT COUNT(*) FROM participants WHERE match_id IN ('match1', 'match2')"
        ).fetchone()[0]
        assert result > 0
```

---

### Jour 3 : Tests scripts maintenance

#### 3.1 Tests diagnose_player_db.py
```python
# tests/scripts/test_diagnose_player_db.py
"""Tests pour diagnose_player_db.py."""

from diagnose_player_db import (
    check_db_integrity,
    detect_anomalies,
    generate_report,
)

class TestDatabaseDiagnostics:
    """Tests diagnostics DB."""
    
    def test_check_integrity_healthy_db(self, temp_healthy_db):
        """DB saine ne lève pas d'erreurs."""
        issues = check_db_integrity(temp_healthy_db)
        assert len(issues) == 0
        
    def test_detect_duplicate_matches(self, temp_db_with_duplicates):
        """Détecter doublons de matchs."""
        anomalies = detect_anomalies(temp_db_with_duplicates)
        
        assert "duplicate_matches" in anomalies
        assert len(anomalies["duplicate_matches"]) > 0
        
    def test_detect_orphan_records(self, temp_db_with_orphans):
        """Détecter enregistrements orphelins."""
        anomalies = detect_anomalies(temp_db_with_orphans)
        
        assert "orphan_medals" in anomalies or "orphan_participants" in anomalies
        
    def test_generate_report(self, temp_db):
        """Générer rapport de diagnostic."""
        report = generate_report(temp_db)
        
        assert "total_matches" in report
        assert "last_sync" in report
        assert "db_size_mb" in report
```

#### 3.2 Tests prefetch_profile_assets.py
```python
# tests/scripts/test_prefetch_profile_assets.py
"""Tests pour prefetch_profile_assets.py."""

from prefetch_profile_assets import (
    list_xuids_needing_assets,
    download_profile_assets,
    validate_assets,
)

class TestProfileAssetsPrefetch:
    """Tests préchargement assets."""
    
    def test_list_xuids_needing_update(self, temp_cache_dir):
        """Lister XUIDs nécessitant mise à jour."""
        xuids = list_xuids_needing_assets(temp_cache_dir, max_age_days=7)
        
        assert isinstance(xuids, list)
        
    def test_download_emblem(self, mock_api_client, temp_cache_dir):
        """Télécharger emblème."""
        xuid = "12345"
        success = download_profile_assets(
            xuid,
            mock_api_client,
            temp_cache_dir,
            asset_types=["emblem"]
        )
        
        assert success
        assert (temp_cache_dir / "emblems" / f"{xuid}.png").exists()
        
    def test_validate_downloaded_assets(self, temp_cache_dir):
        """Valider assets téléchargés."""
        # Créer faux asset
        emblem_path = temp_cache_dir / "emblems" / "12345.png"
        emblem_path.parent.mkdir(parents=True, exist_ok=True)
        emblem_path.write_bytes(b"fake_png_data")
        
        is_valid = validate_assets("12345", temp_cache_dir)
        # Devrait échouer car pas un vrai PNG
        assert not is_valid
```

**Validation Sprint 3** :
```bash
# Exécuter tous les tests scripts
python -m pytest tests/scripts/ -v

# Vérifier couverture scripts
python -m pytest tests/scripts/ --cov=scripts --cov-report=term-missing
```

---

# Sprint 4 : Tests de Charge & Documentation 📚
**Durée** : 2-3 jours | **Priorité** : 🟢 Moyenne

## Objectifs
- 🚀 Tests de performance
- 📊 Tests de charge
- 📖 Documentation tests

---

### Jour 1 : Tests de performance

#### 1.1 Framework benchmarks
```python
# tests/performance/conftest.py
"""Fixtures pour tests de performance."""

import pytest
import time
from contextlib import contextmanager

@contextmanager
def measure_time():
    """Context manager pour mesurer le temps d'exécution."""
    start = time.perf_counter()
    yield lambda: time.perf_counter() - start
    
@pytest.fixture
def large_dataset():
    """Dataset de 10000 matchs pour tests de charge."""
    import polars as pl
    return pl.DataFrame({
        "match_id": [f"m{i}" for i in range(10000)],
        "start_time": ["2024-01-01"] * 10000,
        "kills": [10] * 10000,
        "deaths": [5] * 10000,
    })

@pytest.fixture
def benchmark_threshold():
    """Seuils de performance acceptables."""
    return {
        "load_matches": 2.0,      # secondes
        "compute_stats": 1.0,
        "render_chart": 0.5,
        "filter_data": 0.3,
    }
```

#### 1.2 Tests de charge données
```python
# tests/performance/test_data_loading_performance.py
"""Tests de performance chargement données."""

class TestDataLoadingPerformance:
    """Tests performance chargement."""
    
    def test_load_10k_matches_under_threshold(
        self, 
        temp_db_with_10k_matches,
        benchmark_threshold
    ):
        """Charger 10k matchs en moins de 2s."""
        from src.data.repositories import DuckDBRepository
        
        repo = DuckDBRepository(temp_db_with_10k_matches, "test_xuid")
        
        with measure_time() as elapsed:
            matches = repo.load_matches(limit=10000)
        
        assert elapsed() < benchmark_threshold["load_matches"]
        assert len(matches) == 10000
        
    def test_filter_large_dataset_fast(self, large_dataset, benchmark_threshold):
        """Filtrer gros dataset rapidement."""
        from src.app.filters import apply_filters
        
        with measure_time() as elapsed:
            filtered = apply_filters(
                large_dataset,
                date_range=("2024-01-01", "2024-01-31")
            )
        
        assert elapsed() < benchmark_threshold["filter_data"]
```

#### 1.3 Tests de charge visualisations
```python
# tests/performance/test_visualization_performance.py
"""Tests performance visualisations."""

class TestVisualizationPerformance:
    """Tests performance graphiques."""
    
    def test_render_timeseries_10k_points(
        self,
        large_dataset,
        benchmark_threshold
    ):
        """Rendre timeseries avec 10k points."""
        from src.visualization.timeseries import plot_kd_timeseries
        
        with measure_time() as elapsed:
            fig = plot_kd_timeseries(large_dataset)
        
        assert elapsed() < benchmark_threshold["render_chart"]
        assert fig is not None
        
    def test_aggregation_performance(self, large_dataset, benchmark_threshold):
        """Agrégations sur gros dataset."""
        from src.analysis.stats import compute_aggregated_stats
        
        with measure_time() as elapsed:
            stats = compute_aggregated_stats(large_dataset)
        
        assert elapsed() < benchmark_threshold["compute_stats"]
```

---

### Jour 2 : Tests edge cases & stress

#### 2.1 Tests cas limites
```python
# tests/edge_cases/test_extreme_data_scenarios.py
"""Tests scénarios extrêmes."""

class TestExtremeScenarios:
    """Tests cas limites."""
    
    def test_player_with_zero_matches(self):
        """Joueur sans aucun match."""
        import polars as pl
        empty_df = pl.DataFrame()
        
        # Toutes les fonctions doivent gérer ça
        from src.analysis.stats import compute_aggregated_stats
        stats = compute_aggregated_stats(empty_df)
        
        assert stats["total_matches"] == 0
        
    def test_player_with_single_match(self, single_match_df):
        """Joueur avec un seul match."""
        from src.analysis.stats import compute_winrate
        winrate = compute_winrate(single_match_df)
        
        # Doit retourner 0% ou 100%, pas NaN
        assert winrate in [0.0, 100.0]
        
    def test_all_matches_same_timestamp(self):
        """Tous les matchs au même instant (bug potentiel)."""
        import polars as pl
        df = pl.DataFrame({
            "match_id": ["m1", "m2", "m3"],
            "start_time": ["2024-01-01 10:00:00"] * 3,
            "outcome": [1, 0, 1],
        })
        
        from src.analysis.win_streaks import compute_win_streaks
        streaks = compute_win_streaks(df)
        
        # Ne doit pas crasher
        assert streaks is not None
        
    def test_extreme_kd_values(self):
        """K/D extrêmes (0 deaths, 100+ kills)."""
        import polars as pl
        df = pl.DataFrame({
            "kills": [0, 150, 1],
            "deaths": [50, 0, 1],
        })
        
        from src.analysis.stats import compute_kd_ratio
        kd = compute_kd_ratio(df)
        
        # Pas de NaN ou Inf
        assert all(not (pd.isna(v) or pd.isinf(v)) for v in kd)
        
    def test_missing_required_columns(self):
        """Colonnes requises manquantes."""
        import polars as pl
        df = pl.DataFrame({"match_id": ["m1"]})  # Pas de kills/deaths
        
        from src.analysis.stats import compute_kd_ratio
        
        # Doit lever une erreur explicite ou retourner valeur par défaut
        try:
            kd = compute_kd_ratio(df)
        except KeyError as e:
            assert "kills" in str(e) or "deaths" in str(e)
```

#### 2.2 Tests de stress
```python
# tests/stress/test_concurrent_operations.py
"""Tests opérations concurrentes."""

import concurrent.futures

class TestConcurrentOperations:
    """Tests stress multi-threading."""
    
    def test_concurrent_db_reads(self, temp_db):
        """Lectures concurrentes de la DB."""
        from src.data.repositories import DuckDBRepository
        
        def read_matches(xuid):
            repo = DuckDBRepository(temp_db, xuid)
            return repo.load_matches(limit=100)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(read_matches, f"xuid_{i}")
                for i in range(10)
            ]
            results = [f.result() for f in futures]
        
        # Toutes les lectures doivent réussir
        assert len(results) == 10
        
    def test_concurrent_sync_operations(self, temp_db, mock_api):
        """Syncs concurrents."""
        from src.data.sync.engine import DuckDBSyncEngine
        
        def sync_player(gamertag):
            engine = DuckDBSyncEngine(temp_db, gamertag, mock_api)
            return engine.sync_delta()
        
        # Simuler 3 joueurs qui sync en même temps
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(sync_player, f"player{i}")
                for i in range(3)
            ]
            results = [f.result() for f in futures]
        
        # Toutes les syncs doivent terminer sans erreur
        assert all(r.success for r in results)
```

---

### Jour 3 : Documentation & Finalisation

#### 3.1 Documentation tests
```markdown
# docs/TESTING.md
"""Guide des tests LevelUp."""

## Structure des Tests

### Tests Unitaires (`tests/`)
- `test_*.py` - Tests des modules src/
- Couverture cible : >80%
- Exécution rapide (<1s par test)

### Tests d'Intégration (`tests/integration/`)
- Tests end-to-end
- Nécessitent DuckDB réelle
- Durée : 5-10s par test

### Tests UI (`tests/ui/`)
- Tests pages Streamlit
- Utilisent mocks
- Vérifient rendu sans erreur

### Tests Performance (`tests/performance/`)
- Benchmarks
- Tests de charge
- Seuils de performance

### Tests Scripts (`tests/scripts/`)
- Tests des scripts maintenance
- Validation entrées/sorties

## Exécuter les Tests

```bash
# Tous les tests
python -m pytest

# Tests rapides uniquement
python -m pytest -m "not slow"

# Avec couverture
python -m pytest --cov=src --cov-report=html

# Tests d'une catégorie
python -m pytest tests/ui/
python -m pytest tests/performance/

# Tests d'un fichier
python -m pytest tests/test_duckdb_repository.py -v
```

## Écrire un Test

### Pattern de base
```python
def test_feature_name():
    """Description claire de ce qui est testé."""
    # Arrange - Préparer les données
    data = create_test_data()
    
    # Act - Exécuter la fonction
    result = function_to_test(data)
    
    # Assert - Vérifier le résultat
    assert result.is_valid
    assert result.count == expected_count
```

### Test avec fixtures
```python
def test_with_database(temp_db):
    """Utiliser une fixture pour DB temporaire."""
    repo = Repository(temp_db)
    result = repo.query()
    assert result is not None
```

## Markers

```python
@pytest.mark.slow
def test_expensive_operation():
    """Test long (>5s)."""
    pass

@pytest.mark.skipif(condition, reason="...")
def test_conditional():
    """Test conditionnel."""
    pass

@pytest.mark.parametrize("input,expected", [...])
def test_multiple_cases(input, expected):
    """Test paramétré."""
    assert function(input) == expected
```

## Couverture

Objectifs par module :
- `src/data/` : >80%
- `src/analysis/` : >80%
- `src/visualization/` : >85%
- `src/ui/pages/` : >40%
- `src/app/` : >50%

## CI/CD

Les tests s'exécutent automatiquement sur :
- Pull requests
- Push sur main
- Release tags

Échec si :
- Tests échouent
- Couverture < 40%
- Warnings non résolus
```

#### 3.2 Mise à jour README tests
```markdown
# README.md - Section Tests

## Tests

### Exécuter les tests

```bash
# Installation des dépendances de test
pip install -e ".[dev]"

# Tous les tests
python -m pytest

# Tests avec couverture
python -m pytest --cov=src --cov-report=term-missing

# Tests spécifiques
python -m pytest tests/ui/              # Tests UI
python -m pytest tests/integration/     # Tests intégration
python -m pytest -k "test_sync"         # Tests contenant "sync"
```

### Statistiques Tests

- 🎯 **1408+ tests**
- ✅ **97.3%+ de succès**
- 📊 **41%+ couverture globale**
- 🎨 **40%+ couverture UI**

### Catégories

| Catégorie | Tests | Couverture |
|-----------|-------|------------|
| Data Layer | 420 | 65% |
| Visualizations | 150 | 90% |
| UI Pages | 280 | 40% |
| Sync Engine | 180 | 55% |
| Analysis | 110 | 70% |

Voir [docs/TESTING.md](docs/TESTING.md) pour plus de détails.
```

#### 3.3 Checklist finale
```markdown
# .ai/CHECKLIST_TESTS_SPRINT_4.md

## Checklist Finale - Sprint 4

### Corrections Immédiates ✅
- [x] cache_loaders.py < 800 lignes
- [x] 0 warning Polars map_elements
- [x] 0 API déprécié (min_periods)
- [x] Test anti-régression créés
- [x] Tous tests passent

### Couverture UI ✅
- [x] Tests pages Career (>40%)
- [x] Tests pages Match History (>35%)
- [x] Tests pages Timeseries (>40%)
- [x] Tests pages Match View (>30%)
- [x] Tests pages Teammates (>35%)
- [x] Tests pages Media Library (>30%)
- [x] Helpers de test Streamlit
- [x] Fixtures réutilisables

### Tests Scripts ✅
- [x] populate_metadata_from_discovery
- [x] populate_metadata_players
- [x] resolve_missing_gamertags
- [x] refetch_film_roster
- [x] diagnose_player_db
- [x] prefetch_profile_assets

### Performance ✅
- [x] Tests charge 10k matchs
- [x] Tests performance visualisations
- [x] Tests cas limites
- [x] Tests stress concurrent

### Documentation ✅
- [x] docs/TESTING.md créé
- [x] README.md mis à jour
- [x] Commentaires dans tests
- [x] Guide fixtures

## Métriques Finales Attendues

```bash
python -m pytest -v --cov=src --cov-report=term-missing

# Objectifs :
# - 1450+ tests
# - 0 échec
# - 0 warning
# - Couverture globale : 48%+
# - Couverture UI : 40%+
```

## Validation Finale

```bash
# 1. Tests passent tous
python -m pytest

# 2. Pas de warnings
python -m pytest --strict-warnings

# 3. Couverture atteinte
python -m pytest --cov=src --cov-report=term | grep "TOTAL.*4[8-9]%"

# 4. Qualité code OK
python -m pytest tests/test_legacy_free_global.py

# 5. Performance OK
python -m pytest tests/performance/ -v
```
```

**Validation Sprint 4** :
```bash
# Validation finale complète
python -m pytest -v --cov=src --cov-report=html --cov-report=term-missing

# Ouvrir rapport HTML
open htmlcov/index.html

# Vérifier métriques
python scripts/check_test_metrics.py
```

---

## 📈 Métriques de Succès Globales

### Avant les Sprints
- ❌ 1 test échoué
- ⚠️ 7 warnings
- 📊 Couverture : 41%
- 🎨 Couverture UI : 5-20%

### Après les Sprints (cible)
- ✅ 0 test échoué
- ✅ 0 warning
- 📊 Couverture : 48%+ (+7 points)
- 🎨 Couverture UI : 40-50% (+25-35 points)
- 🆕 +50 nouveaux tests
- 📚 Documentation complète

---

## 🔄 Workflow de Développement Post-Sprints

### Avant chaque commit
```bash
# 1. Exécuter tests affectés
python -m pytest tests/test_modified_module.py

# 2. Vérifier warnings
python -m pytest --strict-warnings

# 3. Couverture maintenue
python -m pytest --cov=src/modified_module
```

### Avant chaque PR
```bash
# Suite complète
python -m pytest -v

# Qualité code
python -m ruff check src/
python -m black --check src/

# Couverture globale
python -m pytest --cov=src --cov-report=term-missing
```

### CI/CD (GitHub Actions à créer)
```yaml
# .github/workflows/tests.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
      - run: pip install -e ".[dev]"
      - run: python -m pytest --cov=src --cov-fail-under=45
```

---

## 📝 Notes Importantes

### Philosophie des Tests
1. **Tests rapides** : <1s pour unitaires, <10s pour intégration
2. **Tests isolés** : Chaque test est indépendant
3. **Tests clairs** : Nom explicite + docstring
4. **Tests maintenables** : Fixtures réutilisables

### Priorités si Temps Limité
1. ✅ **Sprint 1** (critique) : Corrections immédiates
2. ⚠️ **Sprint 2** (haute) : UI pages principales (Career, Match History)
3. 🟡 **Sprint 3** (optionnel) : Scripts critiques seulement (3 sur 6)
4. 🟢 **Sprint 4** (bonus) : Documentation minimum

### Maintenance Continue
- **Chaque nouvelle feature** : Ajouter tests en même temps
- **Chaque bug corrigé** : Ajouter test de non-régression
- **Revue mensuelle** : Couverture et qualité tests
- **Refactoring prudent** : Toujours avec tests verts

---

## 🎉 Livrable Final

À la fin des 4 sprints, le projet aura :

1. ✅ **Zéro dette technique test** (0 échec, 0 warning)
2. 📊 **Couverture améliorée** (+7 points global, +30 points UI)
3. 🧪 **~1450 tests** (+50 nouveaux)
4. 📚 **Documentation tests complète**
5. 🚀 **Tests de performance** établis
6. 🔧 **Scripts critiques testés**
7. 🎯 **Qualité mesurable** et maintenue

**Cette base solide permettra de développer sereinement les futures fonctionnalités ! 🚀**
