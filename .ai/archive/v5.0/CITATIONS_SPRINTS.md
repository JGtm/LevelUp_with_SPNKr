# Citations - Plan de Sprints

**Date création** : 2026-02-14  
**Statut global** : ✅ COMPLETED  
**Architecture cible** : DuckDB v4 + Table `match_citations` par match  
**Date fin** : 2026-02-15

---

## 📋 Vue d'ensemble

**Objectif** : Migrer le système de citations vers architecture DuckDB-first avec stockage par match.

**Bénéfices** :
- 41 → 47 citations (+14.6%)
- Performance affichage : -90% (500ms → 50ms)
- Graphiques temporels d'évolution nativement possibles

**Sprint 0** : ✅ COMPLETED - Décisions validées, fichiers créés  
**Sprint 1** : ✅ COMPLETED - Tables DuckDB + Nettoyage  
**Sprint 2** : ✅ COMPLETED - CitationEngine core  
**Sprint 3** : ✅ COMPLETED - Intégration sync + backfill  
**Sprint 4** : ✅ COMPLETED - Refactoring UI  
**Sprint 5** : ✅ COMPLETED - Tests finaux + Documentation

---

## ✅ Sprint 0 : Analyse & Décisions (TERMINÉ)

**Durée** : 2h  
**Statut** : ✅ COMPLETED  
**Date fin** : 2026-02-14

### Livrables

- [x] Analyse 114 citations exclues
- [x] Identification 18 citations mappables
- [x] Validation utilisateur : 6 citations
- [x] Création `scripts/create_citation_mappings_table.py`
- [x] Création `src/analysis/citations/custom_rules.py`
- [x] Documentation [CITATIONS_DECISIONS_FINALES.md](CITATIONS_DECISIONS_FINALES.md)
- [x] Documentation [CITATIONS_ARCHITECTURE_ANALYSIS.md](CITATIONS_ARCHITECTURE_ANALYSIS.md)

### Review ✅

**Agent validateur** : Analyse terminée, documents créés, prêt pour implémentation.

---

## ✅ Sprint 1 : Tables DuckDB + Nettoyage

**Durée** : 2-3h  
**Statut** : ✅ COMPLETED  
**Date fin** : 2026-02-15  
**Dépendances** : Sprint 0 ✅  
**Owner** : Developer

### 📦 Tâches

#### 1.1 Table `citation_mappings` (référentiel)

**Fichier** : `scripts/create_citation_mappings_table.py` (existe déjà ✅)

- [ ] **Tâche 1.1.1** : Exécuter le script
  ```bash
  python scripts/create_citation_mappings_table.py
  ```
  - **Vérification** : `SELECT COUNT(*) FROM citation_mappings` doit retourner 14
  - **Test** : Vérifier colonnes (citation_name_norm, mapping_type, award_name, custom_function)

- [ ] **Tâche 1.1.2** : Valider les données insérées
  ```sql
  SELECT citation_name_display, mapping_type, award_name, custom_function 
  FROM citation_mappings 
  ORDER BY mapping_type, citation_name_display;
  ```
  - **Attendu** : 5 awards + 1 custom + 8 existantes

#### 1.2 Table `match_citations` (données par match)

**Fichier** : `scripts/create_match_citations_table.py` (à créer)

- [ ] **Tâche 1.2.1** : Créer le script
  - **Template** : S'inspirer de `create_citation_mappings_table.py`
  - **Schéma SQL** :
    ```sql
    CREATE TABLE IF NOT EXISTS match_citations (
        match_id TEXT NOT NULL,
        citation_name_norm TEXT NOT NULL,
        value INTEGER NOT NULL,
        PRIMARY KEY (match_id, citation_name_norm)
    );
    CREATE INDEX IF NOT EXISTS idx_match_citations_name 
        ON match_citations(citation_name_norm);
    ```
  - **Emplacement** : Doit créer la table dans **chaque** DB joueur `data/players/{gamertag}/stats.duckdb`

- [ ] **Tâche 1.2.2** : Exécuter le script
  ```bash
  python scripts/create_match_citations_table.py
  ```
  - **Vérification multi-joueurs** : Vérifier que la table existe dans au moins 2 DBs joueurs
  - **Test** : `SELECT name FROM sqlite_master WHERE type='table' AND name='match_citations'` (pour chaque DB)

- [ ] **Tâche 1.2.3** : Créer tests unitaires
  - **Fichier** : `tests/test_match_citations_table.py`
  - **Tests** :
    - `test_table_exists()` : Vérifier existence table
    - `test_schema_correct()` : Vérifier colonnes (match_id, citation_name_norm, value)
    - `test_primary_key()` : Vérifier PK (match_id, citation_name_norm)
    - `test_index_exists()` : Vérifier index sur citation_name_norm

#### 1.3 Retirer citations de la blacklist

**Fichier** : `data/wiki/halo5_commendations_exclude.json`

- [ ] **Tâche 1.3.1** : Éditer le fichier
  - **Supprimer** :
    - "Défenseur du drapeau"
    - "Je te tiens !"
    - "Sus au porteur du drapeau"
    - "Partie prenante"
    - "À la charge"
    - "Annexion forcée"
  - **Vérification** : Fichier JSON valide après modification

- [ ] **Tâche 1.3.2** : Tester affichage
  - **Lancer app** : `streamlit run streamlit_app.py`
  - **Vérifier** : 47 citations affichées (41 + 6) dans la section Citations

#### 1.4 Archiver fichiers obsolètes

- [ ] **Tâche 1.4.1** : Créer dossier archive
  ```bash
  mkdir -p scripts/_archive/obsolete_citations
  ```

- [ ] **Tâche 1.4.2** : Déplacer fichiers JSON (si existent)
  ```bash
  # Vérifier existence puis déplacer
  if [ -f out/commendations_mapping_assumed.json ]; then
      mv out/commendations_mapping_assumed.json scripts/_archive/obsolete_citations/
  fi
  if [ -f out/commendations_mapping_unmatched.json ]; then
      mv out/commendations_mapping_unmatched.json scripts/_archive/obsolete_citations/
  fi
  ```

- [ ] **Tâche 1.4.3** : Mettre à jour `.gitignore`
  - **Ajouter** : `out/commendations_*.json`

- [ ] **Tâche 1.4.4** : Documenter dans CHANGELOG
  - **Section** : `[Unreleased] - 2026-02-14`
  - **Type** : `### Deprecated`
  - **Message** : "Fichiers JSON de tracking citations (out/*.json) remplacés par tables DuckDB"

### ✅ Critères de validation Sprint 1

- [ ] Table `citation_mappings` créée avec 14 lignes
- [ ] Table `match_citations` créée dans toutes les DBs joueurs
- [ ] 47 citations affichées dans l'app
- [ ] Fichiers JSON archivés (si existaient)
- [ ] Tests unitaires tables passent (✅ 4/4)
- [ ] `.gitignore` mis à jour
- [ ] CHANGELOG documenté

### 🔍 Review obligatoire avant validation

**Agent reviewer** :
1. Vérifier tables créées (`SELECT * FROM citation_mappings LIMIT 5`)
2. Vérifier schéma `match_citations` (colonnes, PK, index)
3. Tester affichage 47 citations
4. Vérifier tests unitaires passent
5. **Marquer Sprint 1 comme** :
   - ✅ COMPLETED si tout OK
   - ⚠️ WARNING si problèmes mineurs
   - ❌ FAILED si bloquant

---

## ✅ Sprint 2 : CitationEngine Core

**Durée** : 3-4h  
**Statut** : ✅ COMPLETED  
**Date fin** : 2026-02-15  
**Dépendances** : Sprint 1 ✅  
**Owner** : Developer

### 📦 Tâches

#### 2.1 Module `engine.py`

**Fichier** : `src/analysis/citations/engine.py` (à créer)

- [ ] **Tâche 2.1.1** : Créer classe `CitationEngine`
  - **Architecture** :
    ```python
    class CitationEngine:
        def __init__(self, db_path: str, xuid: str):
            """Initialise le moteur avec connexion DB joueur."""
            pass
        
        def load_mappings(self) -> dict[str, dict]:
            """Charge depuis citation_mappings (metadata.duckdb)."""
            pass
        
        def compute_citation_for_match(
            self, 
            mapping: dict, 
            match_data: dict
        ) -> int:
            """Calcule 1 citation pour 1 match."""
            pass
        
        def compute_all_for_match(
            self, 
            match_id: str, 
            match_data: dict
        ) -> dict[str, int]:
            """Calcule toutes citations pour 1 match.
            
            Returns:
                {"citation_name_norm": value}
            """
            pass
        
        def aggregate_citations(
            self, 
            citation_names: list[str], 
            match_ids: list[str] | None = None
        ) -> dict[str, int]:
            """Agrège depuis match_citations (SELECT SUM).
            
            Args:
                citation_names: Liste citations à agréger
                match_ids: Filtrer par matchs (None = tous)
            
            Returns:
                {"citation_name_norm": total_value}
            """
            pass
    ```

- [ ] **Tâche 2.1.2** : Implémenter `load_mappings()`
  - **Source** : `data/warehouse/metadata.duckdb`
  - **Requête** : `SELECT * FROM citation_mappings`
  - **Retour** : `{"citation_name_norm": {mapping dict}}`

- [ ] **Tâche 2.1.3** : Implémenter `compute_citation_for_match()`
  - **Support types** :
    - `medal` : Lookup dans `match_data["medals"]` (dict medal_id → count)
    - `stat` : Lookup dans `match_data["stats"]` (dict stat_name → value)
    - `award` : Somme dans `match_data["awards"]` (dict award_name → count)
    - `custom` : Appel fonction depuis `CUSTOM_FUNCTIONS` registry

- [ ] **Tâche 2.1.4** : Implémenter `compute_all_for_match()`
  - **Logique** :
    1. Charger tous les mappings
    2. Pour chaque mapping, calculer la valeur
    3. Retourner dict sparse (seulement value > 0)

- [ ] **Tâche 2.1.5** : Implémenter `aggregate_citations()`
  - **Requête SQL** :
    ```sql
    SELECT citation_name_norm, SUM(value) as total
    FROM match_citations
    WHERE citation_name_norm IN (?)
      AND (match_id IN (?) OR ? IS NULL)
    GROUP BY citation_name_norm
    ```

#### 2.2 Support types de données

- [ ] **Tâche 2.2.1** : Helper `_load_match_medals(match_id)`
  - **Source** : `SELECT medal_name_id, count FROM medals_earned WHERE match_id = ?`
  - **Retour** : `{medal_id: count}`

- [ ] **Tâche 2.2.2** : Helper `_load_match_stats(match_id)`
  - **Source** : `SELECT * FROM match_stats WHERE match_id = ?`
  - **Retour** : `{"kills": 10, "deaths": 5, ...}`

- [ ] **Tâche 2.2.3** : Helper `_load_match_awards(match_id)`
  - **Source** : `SELECT award_name, SUM(award_count) FROM personal_score_awards WHERE match_id = ? GROUP BY award_name`
  - **Retour** : `{"Flag Defense": 3, "Zone Capture": 5}`

- [ ] **Tâche 2.2.4** : Intégration `CUSTOM_FUNCTIONS`
  - **Import** : `from src.analysis.citations.custom_rules import CUSTOM_FUNCTIONS`
  - **Appel** : `func = CUSTOM_FUNCTIONS.get(mapping["custom_function"])` puis `func(data)`

#### 2.3 Tests unitaires `CitationEngine`

**Fichier** : `tests/test_citation_engine.py`

- [ ] **Tâche 2.3.1** : Tests `load_mappings()`
  - `test_load_mappings_returns_dict()`
  - `test_load_mappings_has_14_entries()`
  - `test_load_mappings_structure()`

- [ ] **Tâche 2.3.2** : Tests `compute_citation_for_match()`
  - `test_compute_medal_type()` : Citation type medal
  - `test_compute_stat_type()` : Citation type stat
  - `test_compute_award_type()` : Citation type award
  - `test_compute_custom_type()` : Citation type custom
  - `test_compute_returns_zero_if_missing()` : Données manquantes

- [ ] **Tâche 2.3.3** : Tests `compute_all_for_match()`
  - `test_compute_all_returns_sparse()` : Seulement value > 0
  - `test_compute_all_includes_all_types()` : Tous types supportés
  - `test_compute_all_empty_match()` : Match sans données

- [ ] **Tâche 2.3.4** : Tests `aggregate_citations()`
  - `test_aggregate_all_matches()` : Tous matchs
  - `test_aggregate_filtered_matches()` : Sous-ensemble matchs
  - `test_aggregate_returns_totals()` : Sommes correctes

### ✅ Critères de validation Sprint 2

- [ ] `CitationEngine` implémentée avec 4 méthodes publiques
- [ ] Support 4 types (medal, stat, award, custom)
- [ ] Tests unitaires passent (✅ 12/12 minimum)
- [ ] Coverage > 80% sur `engine.py`
- [ ] Documentation docstrings complète

### 🔍 Review obligatoire avant validation

**Agent reviewer** :
1. Exécuter `python -m pytest tests/test_citation_engine.py -v`
2. Vérifier couverture `python -m pytest --cov=src/analysis/citations/engine`
3. Tester manuellement avec 1 match réel
4. Vérifier que `aggregate_citations()` retourne bonnes valeurs
5. **Marquer Sprint 2 comme** :
   - ✅ COMPLETED si tests OK + coverage > 80%
   - ⚠️ WARNING si coverage 60-80%
   - ❌ FAILED si tests fail

---

## ✅ Sprint 3 : Intégration Sync + Backfill

**Durée** : 3-4h  
**Statut** : ✅ COMPLETED  
**Date fin** : 2026-02-15  
**Dépendances** : Sprint 2 ✅  
**Owner** : Developer

### 📦 Tâches

#### 3.1 Intégration au sync

**Fichier** : `scripts/sync.py`

- [ ] **Tâche 3.1.1** : Ajouter calcul citations après insertion matchs
  - **Emplacement** : Après `repo.insert_match_data()`
  - **Logique** :
    ```python
    from src.analysis.citations.engine import CitationEngine
    
    # Après insertion match
    engine = CitationEngine(db_path, xuid)
    match_data = {
        "medals": medals_dict,
        "stats": stats_dict,
        "awards": awards_dict
    }
    citations = engine.compute_all_for_match(match_id, match_data)
    
    # INSERT sparse (seulement value > 0)
    for citation_norm, value in citations.items():
        if value > 0:
            repo.insert_citation(match_id, citation_norm, value)
    ```

- [ ] **Tâche 3.1.2** : Créer méthode `DuckDBRepository.insert_citation()`
  - **Fichier** : `src/data/repositories/duckdb_repo.py`
  - **Signature** :
    ```python
    def insert_citation(
        self, 
        match_id: str, 
        citation_name_norm: str, 
        value: int
    ) -> None:
        """Insère ou met à jour une citation pour un match."""
        pass
    ```
  - **SQL** : `INSERT OR REPLACE INTO match_citations VALUES (?, ?, ?)`

- [ ] **Tâche 3.1.3** : Logger nb citations insérées
  - **Message** : `f"✅ Citations insérées: {len(citations)} pour match {match_id}"`

- [ ] **Tâche 3.1.4** : Tester avec 1 match réel
  - **Commande** : `python scripts/sync.py --delta --player TestPlayer --max-matches 1`
  - **Vérification** : `SELECT * FROM match_citations WHERE match_id = ?`

#### 3.2 Option backfill `--citations`

**Fichier** : `scripts/backfill/cli.py`

- [ ] **Tâche 3.2.1** : Ajouter argument `--citations`
  - **Ligne ~150** :
    ```python
    parser.add_argument(
        "--citations",
        action="store_true",
        help="Calculer et insérer les citations pour les matchs existants"
    )
    parser.add_argument(
        "--force-citations",
        action="store_true",
        help="Force le recalcul des citations pour TOUS les matchs"
    )
    ```

- [ ] **Tâche 3.2.2** : Passer argument à `backfill_player_data()`
  - **Fichier** : `scripts/backfill_data.py`
  - **Ajouter paramètres** : `citations=args.citations, force_citations=args.force_citations`

**Fichier** : `scripts/backfill/orchestrator.py`

- [ ] **Tâche 3.2.3** : Ajouter paramètre `citations` à `backfill_player_data()`
  - **Signature** :
    ```python
    async def backfill_player_data(
        player: str,
        ...,
        citations: bool = False,
        force_citations: bool = False,
        ...
    ) -> dict:
    ```

- [ ] **Tâche 3.2.4** : Implémenter logique backfill citations
  - **Fichier** : Créer `scripts/backfill/strategies.py` (section citations)
  - **Fonction** :
    ```python
    def backfill_citations_for_match(
        match_id: str,
        db_path: str,
        xuid: str,
        force: bool = False
    ) -> int:
        """Calcule et insère citations pour 1 match.
        
        Args:
            force: Si True, recalcule même si déjà présent
        
        Returns:
            Nombre de citations insérées
        """
        # 1. Vérifier si déjà calculé (sauf si force=True)
        if not force:
            existing = check_citations_exist(match_id, db_path)
            if existing:
                return 0
        
        # 2. Charger données match
        engine = CitationEngine(db_path, xuid)
        match_data = load_match_data(match_id, db_path)
        
        # 3. Calculer citations
        citations = engine.compute_all_for_match(match_id, match_data)
        
        # 4. Insérer (sparse)
        repo = DuckDBRepository(db_path, xuid)
        count = 0
        for citation_norm, value in citations.items():
            if value > 0:
                repo.insert_citation(match_id, citation_norm, value)
                count += 1
        
        return count
    ```

- [ ] **Tâche 3.2.5** : Intégrer dans orchestrator
  - **Logique** :
    ```python
    if citations or all_data:
        logger.info("Traitement citations...")
        for match_id in match_ids:
            count = backfill_citations_for_match(
                match_id, db_path, xuid, force_citations
            )
            results["citations_inserted"] += count
    ```

- [ ] **Tâche 3.2.6** : Ajouter progress bar
  - **Utiliser** : `tqdm` comme pour les autres backfills
  - **Message** : `"Calcul citations"`

#### 3.3 Tests backfill

**Fichier** : `tests/test_backfill_citations.py`

- [ ] **Tâche 3.3.1** : Test backfill 1 match
  - `test_backfill_citations_single_match()` : Vérifie INSERT citations

- [ ] **Tâche 3.3.2** : Test backfill avec force
  - `test_backfill_citations_force_recalculates()` : Force recalcul

- [ ] **Tâche 3.3.3** : Test backfill skip si existe
  - `test_backfill_citations_skips_existing()` : Ne recalcule pas par défaut

- [ ] **Tâche 3.3.4** : Test intégration complète
  - `test_backfill_player_with_citations()` : Backfill joueur complet

#### 3.4 Documentation CLI

- [ ] **Tâche 3.4.1** : Mettre à jour help `--citations`
  - **Ajouter exemples** dans `_get_usage_examples()` :
    ```python
    Examples:
        # Calculer citations pour matchs existants
        python scripts/backfill_data.py --player JGtm --citations
        
        # Force recalcul toutes citations
        python scripts/backfill_data.py --player JGtm --citations --force-citations
        
        # Backfill tout (inclut citations)
        python scripts/backfill_data.py --player JGtm --all-data
    ```

- [ ] **Tâche 3.4.2** : Mettre à jour `_print_totals()`
  - **Ajouter** :
    ```python
    if getattr(args, "citations", False):
        logger.info(f"Citations insérées: {totals.get('citations_inserted', 0)}")
    ```

### ✅ Critères de validation Sprint 3

- [ ] Sync insère citations automatiquement après chaque match
- [ ] Option `--citations` fonctionnelle dans backfill
- [ ] Option `--force-citations` recalcule tout
- [ ] Progress bar affichée pendant backfill
- [ ] Tests backfill passent (✅ 4/4)
- [ ] Help CLI documenté

### 🔍 Review obligatoire avant validation

**Agent reviewer** :
1. Tester sync 1 match : `python scripts/sync.py --delta --player TestPlayer --max-matches 1`
2. Vérifier INSERT citations : `SELECT COUNT(*) FROM match_citations`
3. Tester backfill : `python scripts/backfill_data.py --player TestPlayer --citations --max-matches 10`
4. Vérifier force : `python scripts/backfill_data.py --player TestPlayer --citations --force-citations --max-matches 5`
5. Exécuter tests : `python -m pytest tests/test_backfill_citations.py -v`
6. **Marquer Sprint 3 comme** :
   - ✅ COMPLETED si sync + backfill OK + tests passent
   - ⚠️ WARNING si problèmes mineurs (ex: progress bar manquante)
   - ❌ FAILED si INSERT fail ou tests fail

---

## ✅ Sprint 4 : Refactoring UI

**Durée** : 2-3h  
**Statut** : ✅ COMPLETED  
**Date fin** : 2026-02-15  
**Dépendances** : Sprint 3 ✅  
**Owner** : Developer

### 📦 Tâches

#### 4.1 Simplifier `src/ui/commendations.py`

**Fichier** : `src/ui/commendations.py`

- [ ] **Tâche 4.1.1** : Supprimer code obsolète
  - **Lignes ~59-103** : Supprimer `CUSTOM_CITATION_RULES` dict
  - **Lignes ~105-200** : Supprimer `_compute_custom_citation_value()` fonction
  - **Rechercher et supprimer** : `load_h5g_commendations_tracking_rules()` (si existe)

- [ ] **Tâche 4.1.2** : Remplacer par `CitationEngine`
  - **Import** :
    ```python
    from src.analysis.citations.engine import CitationEngine
    ```
  
  - **Remplacer boucle de calcul** (lignes ~850) par :
    ```python
    # Charger engine
    engine = CitationEngine(db_path, xuid)
    
    # Agréger citations (tous matchs)
    citation_names_all = [_normalize_name(it["name"]) for it in items]
    citations_totals_full = engine.aggregate_citations(
        citation_names=citation_names_all,
        match_ids=None  # Tous matchs
    )
    
    # Agréger citations (matchs filtrés)
    if is_filtered:
        citations_totals_filtered = engine.aggregate_citations(
            citation_names=citation_names_all,
            match_ids=filtered_match_ids
        )
    else:
        citations_totals_filtered = citations_totals_full
    ```

- [ ] **Tâche 4.1.3** : Remplacer calcul par citation
  - **Avant** (lignes ~850-890) :
    ```python
    # SUPPRIMER ceci
    if norm_name in CUSTOM_CITATION_RULES:
        current = _compute_custom_citation_value(...)
    elif isinstance(rule.get("medal_ids"), list):
        ...
    ```
  
  - **Après** :
    ```python
    # Simple lookup
    current_full = citations_totals_full.get(norm_name, 0)
    current_filtered = citations_totals_filtered.get(norm_name, 0)
    
    # Delta
    delta = current_filtered if is_filtered else 0
    ```

- [ ] **Tâche 4.1.4** : Tester affichage
  - **Lancer app** : `streamlit run streamlit_app.py`
  - **Vérifier** :
    - 47 citations affichées
    - Valeurs correctes (comparer avec ancien code)
    - Delta fonctionne avec filtres

#### 4.2 Support filtres & delta

- [ ] **Tâche 4.2.1** : Calculer `filtered_match_ids`
  - **Source** : `df_filtered["match_id"].to_list()` (déjà existant normalement)

- [ ] **Tâche 4.2.2** : Gérer cas "pas de filtres"
  - **Logique** :
    ```python
    is_filtered = (df_filtered.height != df_full.height)
    if is_filtered:
        filtered_match_ids = df_filtered["match_id"].to_list()
        citations_filtered = engine.aggregate_citations(..., filtered_match_ids)
    else:
        citations_filtered = citations_full  # Évite requête inutile
    ```

- [ ] **Tâche 4.2.3** : Afficher delta en badge
  - **Déjà existant** : Badge delta pour médailles/stats
  - **Réutiliser** : Même logique pour citations

#### 4.3 Optimisation performance

- [ ] **Tâche 4.3.1** : Cache Streamlit optionnel
  - **Ajouter** (si besoin) :
    ```python
    @st.cache_data(ttl=300)  # 5 min cache
    def _load_citations_totals(db_path: str, xuid: str) -> dict:
        engine = CitationEngine(db_path, xuid)
        return engine.aggregate_citations(citation_names=all_names)
    ```

- [ ] **Tâche 4.3.2** : Benchmark temps affichage
  - **Avant refactoring** : ~500ms (mesurer avec `time.time()`)
  - **Après refactoring** : Doit être < 100ms

#### 4.4 Tests UI

**Fichier** : `tests/test_commendations_ui.py`

- [ ] **Tâche 4.4.1** : Test affichage 47 citations
  - `test_display_47_citations()` : Vérifier nombre

- [ ] **Tâche 4.4.2** : Test valeurs correctes
  - `test_citation_values_match_db()` : Comparer avec DB

- [ ] **Tâche 4.4.3** : Test filtres
  - `test_citations_filtered_by_date()` : Filtrer par période
  - `test_citations_delta_displayed()` : Delta affiché

- [ ] **Tâche 4.4.4** : Test performance
  - `test_citations_load_time_under_100ms()` : Benchmark

### ✅ Critères de validation Sprint 4

- [ ] Code obsolète supprimé (CUSTOM_CITATION_RULES, _compute_custom_citation_value)
- [ ] CitationEngine intégré dans UI
- [ ] 47 citations affichées correctement
- [ ] Filtres + delta fonctionnels
- [ ] Temps affichage < 100ms
- [ ] Tests UI passent (✅ 4/4)

### 🔍 Review obligatoire avant validation

**Agent reviewer** :
1. Vérifier code supprimé (grep "CUSTOM_CITATION_RULES" doit être vide)
2. Tester app : `streamlit run streamlit_app.py`
3. Compter citations affichées (doit être 47)
4. Tester filtres (date, mode) et vérifier delta
5. Benchmark temps : Mesurer avec DevTools Network
6. Exécuter tests : `python -m pytest tests/test_commendations_ui.py -v`
7. **Marquer Sprint 4 comme** :
   - ✅ COMPLETED si affichage OK + perfs < 100ms + tests passent
   - ⚠️ WARNING si perfs 100-200ms mais fonctionnel
   - ❌ FAILED si affichage cassé ou tests fail

---

## ✅ Sprint 5 : Tests Finaux + Documentation

**Durée** : 2h  
**Statut** : ✅ COMPLETED  
**Date fin** : 2026-02-15  
**Dépendances** : Sprint 4 ✅  
**Owner** : Developer

### 📦 Tâches

#### 5.1 Tests d'intégration

**Fichier** : `tests/integration/test_citations_integration.py`

- [ ] **Tâche 5.1.1** : Test workflow complet
  - `test_sync_backfill_display_citations()` :
    1. Sync 10 matchs
    2. Vérifier citations insérées
    3. Backfill 5 matchs anciens
    4. Charger UI et vérifier totaux

- [ ] **Tâche 5.1.2** : Test migration données existantes
  - `test_migrate_from_old_system()` :
    1. Si ancien système existe, comparer valeurs
    2. Vérifier cohérence

- [ ] **Tâche 5.1.3** : Test performance end-to-end
  - `test_performance_1000_matches()` :
    1. Backfill 1000 matchs
    2. Mesurer temps agrégation
    3. Vérifier < 50ms

#### 5.2 Documentation

**Fichier** : `docs/CITATIONS.md` (à créer)

- [ ] **Tâche 5.2.1** : Documenter architecture
  - **Sections** :
    - Tables DuckDB (citation_mappings, match_citations)
    - Schémas SQL
    - Workflow (sync → calcul → INSERT)

- [ ] **Tâche 5.2.2** : Guide ajouter citation
  - **Étapes** :
    1. Définir règle dans `citation_mappings`
    2. Si custom, créer fonction dans `custom_rules.py`
    3. Backfill matchs existants
    4. Retirer de blacklist (si besoin)

- [ ] **Tâche 5.2.3** : Guide backfill
  - **Exemples CLI** :
    ```bash
    # Backfill citations joueur
    python scripts/backfill_data.py --player JGtm --citations
    
    # Force recalcul tout
    python scripts/backfill_data.py --all --citations --force-citations
    ```

- [ ] **Tâche 5.2.4** : FAQ
  - **Questions** :
    - Comment changer une règle de calcul ?
    - Quel impact espace disque ?
    - Comment voir évolution temporelle ? (requête SQL exemple)

**Fichier** : `.ai/thought_log.md`

- [ ] **Tâche 5.2.5** : Documenter décisions
  - **Section** : "2026-02-14 - Refactoring Citations"
  - **Contenu** :
    - Décisions architecture (match_citations)
    - Raisons (performance, graphiques temporels)
    - Trade-offs (espace disque vs performance)

**Fichier** : `CHANGELOG.md`

- [ ] **Tâche 5.2.6** : Release notes
  - **Section** : `[Unreleased] - 2026-02-14`
  - **Added** :
    - 6 nouvelles citations objectives
    - Table `match_citations` pour stockage par match
    - Graphiques temporels d'évolution (future)
  - **Changed** :
    - Performance affichage citations : -90%
    - Architecture DuckDB-first (vs fichiers JSON)
  - **Deprecated** :
    - Fichiers JSON tracking (out/*.json)
  - **Removed** :
    - Code hardcodé `CUSTOM_CITATION_RULES`

#### 5.3 Monitoring & Métriques

- [ ] **Tâche 5.3.1** : Ajouter logs sync
  - **Message** : `f"✅ {count} citations insérées pour {match_id}"`

- [ ] **Tâche 5.3.2** : Ajouter stats backfill
  - **Afficher** : Temps moyen par match, nb lignes insérées

- [ ] **Tâche 5.3.3** : Script de diagnostic
  - **Fichier** : `scripts/diagnose_citations.py`
  - **Fonctions** :
    - Compter lignes `match_citations` par joueur
    - Lister citations les plus progressées
    - Vérifier cohérence (matchs sans citations)

#### 5.4 Nettoyage final

- [ ] **Tâche 5.4.1** : Supprimer code mort
  - **Rechercher** : `grep -r "CUSTOM_CITATION_RULES" src/`
  - **Rechercher** : `grep -r "load_h5g_commendations_tracking_rules" src/`

- [ ] **Tâche 5.4.2** : Formater code
  - **Exécuter** : `black src/ scripts/`
  - **Exécuter** : `isort src/ scripts/`
  - **Exécuter** : `ruff check src/ scripts/`

- [ ] **Tâche 5.4.3** : Vérifier tests couvrent tout
  - **Coverage globale** : `python -m pytest --cov=src/analysis/citations --cov=src/data/repositories`
  - **Objectif** : > 85%

### ✅ Critères de validation Sprint 5

- [ ] Tests d'intégration passent (✅ 3/3)
- [ ] Documentation `docs/CITATIONS.md` complète
- [ ] CHANGELOG mis à jour
- [ ] `.ai/thought_log.md` documenté
- [ ] Coverage > 85%
- [ ] Code formaté (black, isort, ruff)
- [ ] Aucun code mort restant

### 🔍 Review obligatoire avant validation

**Agent reviewer** :
1. Exécuter suite tests complète : `python -m pytest`
2. Vérifier coverage : `python -m pytest --cov=src --cov-report=html`
3. Lire `docs/CITATIONS.md` et valider clarté
4. Vérifier CHANGELOG complet
5. Tester script diagnostic : `python scripts/diagnose_citations.py`
6. **Marquer Sprint 5 comme** :
   - ✅ COMPLETED si tests OK + doc complète + coverage > 85%
   - ⚠️ WARNING si doc incomplète mais fonctionnel
   - ❌ FAILED si tests fail ou coverage < 70%

---

## 📊 Suivi Global des Sprints

| Sprint | Statut | Durée estimée | Durée réelle | Tests | Coverage | Bloqueurs |
|--------|--------|---------------|--------------|-------|----------|-----------|
| 0 - Analyse | ✅ COMPLETED | 2h | 2h | N/A | N/A | Aucun |
| 1 - Tables DB | 🔵 TODO | 2-3h | - | 4/4 | N/A | - |
| 2 - Engine | 🔵 TODO | 3-4h | - | 12/12 | >80% | Sprint 1 |
| 3 - Sync+Backfill | 🔵 TODO | 3-4h | - | 4/4 | >70% | Sprint 2 |
| 4 - UI | 🔵 TODO | 2-3h | - | 4/4 | >75% | Sprint 3 |
| 5 - Tests+Doc | 🔵 TODO | 2h | - | 3/3 | >85% | Sprint 4 |
| **TOTAL** | **🟡 IN_PROGRESS** | **12-16h** | **-** | **27/27** | **>85%** | **-** |

### Légende statuts

- 🔵 **TODO** : Pas commencé
- 🟡 **IN_PROGRESS** : En cours
- ✅ **COMPLETED** : Terminé et validé
- ⚠️ **WARNING** : Terminé avec réserves
- ❌ **FAILED** : Échec, nécessite reprise

---

## 🎯 Règles de Livraison (OBLIGATOIRES)

### Avant de marquer un sprint COMPLETED

1. **✅ Toutes les tâches terminées** : Checklist complète
2. **✅ Tests unitaires passent** : `pytest` vert pour le scope du sprint
3. **✅ Review agent effectuée** : Agent validateur a vérifié
4. **✅ Documentation à jour** : Docstrings, CHANGELOG, docs/
5. **✅ Pas de régression** : Tests existants toujours verts
6. **✅ Code formaté** : black + isort + ruff OK

### Processus de review agent

**Pour chaque sprint, AVANT de marquer COMPLETED** :

1. **Agent lit les critères de validation**
2. **Agent exécute les commandes de vérification**
3. **Agent teste manuellement (si applicable)**
4. **Agent décide** :
   - ✅ COMPLETED : Tout OK, sprint validé
   - ⚠️ WARNING : Fonctionnel mais problèmes mineurs (documenter)
   - ❌ FAILED : Bloquant, nécessite correction

5. **Agent documente** :
   - Résultat validation dans section Review du sprint
   - Bloqueurs identifiés (si WARNING/FAILED)
   - Recommandations pour sprint suivant

### Workflow type

```bash
# Developer termine les tâches
git commit -m "feat(citations): Sprint 1 - Tables DuckDB"

# Developer demande review
# Agent lance validation automatique
python -m pytest tests/test_match_citations_table.py -v
python scripts/validate_sprint.py --sprint 1

# Agent marque sprint
# Si OK : ✅ COMPLETED dans CITATIONS_SPRINTS.md
# Si KO : ⚠️ WARNING ou ❌ FAILED avec détails
```

---

## 📝 Notes Techniques

### Architecture fichiers

```
scripts/
├── backfill/
│   ├── cli.py              # Arguments CLI (ajout --citations)
│   ├── orchestrator.py     # Orchestration (ajout citations)
│   └── strategies.py       # Backfill citations spécifique
├── backfill_data.py        # Point d'entrée
├── create_citation_mappings_table.py  # ✅ Existe
└── create_match_citations_table.py    # 🔵 À créer

src/analysis/citations/
├── __init__.py             # ✅ Existe
├── custom_rules.py         # ✅ Existe (6 fonctions)
└── engine.py               # 🔵 À créer (CitationEngine)

tests/
├── test_citation_engine.py           # 🔵 À créer (12 tests)
├── test_backfill_citations.py        # 🔵 À créer (4 tests)
├── test_commendations_ui.py          # 🔵 À créer (4 tests)
├── test_match_citations_table.py     # 🔵 À créer (4 tests)
└── integration/
    └── test_citations_integration.py # 🔵 À créer (3 tests)
```

### Commandes utiles

```bash
# Créer tables
python scripts/create_citation_mappings_table.py
python scripts/create_match_citations_table.py

# Sync avec citations
python scripts/sync.py --delta --player JGtm

# Backfill citations
python scripts/backfill_data.py --player JGtm --citations
python scripts/backfill_data.py --all --citations --force-citations

# Tests
python -m pytest tests/test_citation_engine.py -v
python -m pytest --cov=src/analysis/citations
python -m pytest  # Suite complète

# Diagnostic
python scripts/diagnose_citations.py --player JGtm
```

---

**Document créé** : 2026-02-14  
**Prochaine action** : Commencer Sprint 1 - Créer tables DuckDB
