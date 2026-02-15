# TODO: Tests Anti-Régression

> Plan détaillé pour éviter les régressions sur le chargement des données et settings

**Créé le:** 15 février 2026  
**Priorité:** 🔴 HAUTE  
**Objectif:** Détecter automatiquement les régressions qui casseraient l'accès aux joueurs, DB et settings

---

## � Audit des Tests Existants

**Effectué le:** 15 février 2026  
**Résultat global:** ✅ La majorité des tests sont bien écrits

### Tests qui testent la VRAIE logique (✅ Bons exemples)

| Fichier | Ce qu'il teste | Qualité |
|---------|----------------|---------|
| `tests/test_config_db_path.py` | ✅ Détection de DBs avec fixtures temporaires | **EXCELLENT** - Déjà implémenté ! |
| `tests/test_utils_coverage.py::TestLoadProfiles` | ✅ Lecture de `db_profiles.json` avec tmp_path | **BON** - Isolation complète |
| `tests/test_settings_backfill.py` | ✅ Cycle save/load settings avec fichiers temporaires | **BON** - Test de persistance |
| `tests/test_sync_ui.py` | ✅ Parsing de chemins avec exemples synthétiques | **BON** - Pas de dépendance prod |
| `tests/test_duckdb_repository.py` | ✅ Repository avec DBs temporaires + uuid | **BON** - Fixtures isolées |
| `tests/ui/test_settings_page.py` | ✅ UI avec mocks Streamlit | **BON** - Tests de comportement |

### Scripts à transformer en tests (⚠️ À améliorer)

| Fichier | Problème | Action recommandée |
|---------|----------|-------------------|
| `test_data_access.py` (racine) | ⚠️ Script manuel dépendant de l'environnement de prod | **MIGRER** vers `tests/integration/test_data_access_real_env.py` avec skip si pas de données |
| `scripts/_archive/test_highlight_events_sync.py` | ⚠️ Script nécessitant des chemins hardcodés | **ARCHIVER** - Remplacé par tests unitaires |

### Recommandations pour nouveaux tests

1. **✅ TOUJOURS** utiliser `tmp_path` (pytest fixture) pour fichiers temporaires
2. **✅ TOUJOURS** utiliser `monkeypatch` pour variables d'environnement
3. **✅ TOUJOURS** créer des DBs de test avec uuid/random pour isolation
4. **✅ TESTER** la logique (comportement, fallback, validation) pas les données hardcodées
5. **❌ JAMAIS** dépendre de `data/players/JGtm/` ou profils utilisateur spécifiques
6. **❌ JAMAIS** tester "count == 971" ou autres valeurs liées à la prod

### Exemple de transformation : AVANT vs APRÈS

**❌ MAUVAIS** (dépend de la prod) :
```python
def test_list_players():
    players = list_duckdb_v4_players()
    assert len(players) == 4  # Hardcodé !
    assert players[0].gamertag == "Madina97294"  # Hardcodé !
```

**✅ BON** (fixtures contrôlées) :
```python
def test_list_players_detects_existing(tmp_path):
    # Créer 3 DBs de test
    for i in range(3):
        db = tmp_path / f"data/players/Player{i}/stats.duckdb"
        db.parent.mkdir(parents=True)
        create_test_db(db, matches=10+i)
    
    with patch("src.config.get_repo_root", return_value=str(tmp_path)):
        players = list_duckdb_v4_players()
        
        # Teste la logique, pas les valeurs hardcodées
        assert len(players) == 3
        assert all(p.total_matches >= 10 for p in players)
```

---

## �📋 Tests Unitaires à Créer

### ✅ `tests/test_config_db_path.py`

**But:** Valider que `get_default_db_path()` **détecte et retourne les DBs existantes**

**Approche intelligente :** Créer des DBs de test et vérifier la logique de détection.

```python
# Tests à implémenter avec filesystem temporaire:

- [ ] test_get_default_db_path_detects_any_valid_db()
      → GIVEN: Créer data/players/TestPlayerA/stats.duckdb avec sync_meta valide
      → WHEN: Appeler get_default_db_path()
      → THEN: Retourne un chemin qui:
      →       - N'est pas vide ("")
      →       - Existe sur le filesystem (Path.exists())
      →       - Se termine par ".duckdb"
      →       - Pointe vers data/players/*/stats.duckdb

- [ ] test_get_default_db_path_returns_empty_when_no_players()
      → GIVEN: data/players/ vide (ou inexistant)
      → WHEN: Appeler get_default_db_path()
      → THEN: Retourne "" (comportement attendu)
      →       Pas de crash, pas d'exception

- [ ] test_get_default_db_path_env_override_has_priority()
      → GIVEN: data/players/ contient PlayerA/stats.duckdb
      →        OPENSPARTAN_DB=/custom/path/custom.duckdb (variable env)
      → WHEN: Appeler get_default_db_path()
      → THEN: Retourne "/custom/path/custom.duckdb" (env prioritaire)
      →       Ignore les DBs dans data/players/

- [ ] test_get_default_db_path_only_returns_duckdb_files()
      → GIVEN: Créer data/players/OldPlayer/stats.db (SQLite legacy)
      →        Créer data/players/NewPlayer/stats.duckdb (DuckDB v5)
      → WHEN: Appeler get_default_db_path()
      → THEN: Retourne le chemin vers stats.duckdb (ignore .db)
      →       Vérifie .endswith(".duckdb")

- [ ] test_get_default_db_path_survives_missing_data_dir()
      → GIVEN: data/ n'existe pas
      → WHEN: Appeler get_default_db_path()
      → THEN: Retourne "" sans lever d'exception
      →       Gère gracieusement le cas d'installation vide

- [ ] test_get_default_db_path_is_deterministic()
      → GIVEN: data/players/ contient 3 DBs
      → WHEN: Appeler get_default_db_path() 10 fois de suite
      → THEN: Les 10 résultats sont identiques
      →       (ordre stable, pas de randomisation)
```

**Propriété testée :** La fonction DOIT détecter les DBs existantes sur le filesystem et retourner un chemin valide exploitable.

**Fichiers à tester:** `src/config.py::get_default_db_path()`

---

### ✅ `tests/test_profiles_loading.py`

**But:** Valider que `load_profiles()` **lit et parse correctement** le fichier de profils

**Approche intelligente :** Créer des fichiers JSON de test et vérifier la logique de lecture.

```python
# Tests à implémenter avec fichiers temporaires:

- [ ] test_load_profiles_reads_valid_json_file()
      → GIVEN: Créer db_profiles.json avec 2 profils de test:
      →        {"Player1": {"db_path": "...", "xuid": "123", ...},
      →         "Player2": {"db_path": "...", "xuid": "456", ...}}
      → WHEN: Appeler load_profiles()
      → THEN: Retourne un dict avec exactement 2 clés
      →       Chaque profil contient: db_path, xuid, waypoint_player
      →       Types corrects (str pour tous les champs)

- [ ] test_load_profiles_validates_required_fields()
      → GIVEN: JSON avec profil incomplet {"Player": {"db_path": "..."}} (xuid manquant)
      → WHEN: Appeler load_profiles()
      → THEN: Soit ignore le profil invalide, soit retourne avec valeur par défaut
      →       Pas de crash (validation résiliente)

- [ ] test_load_profiles_returns_empty_when_file_missing()
      → GIVEN: db_profiles.json n'existe pas
      → WHEN: Appeler load_profiles()
      → THEN: Retourne {} (dict vide)
      →       Pas d'exception levée

- [ ] test_load_profiles_handles_corrupted_json()
      → GIVEN: Créer fichier JSON syntaxiquement invalide (accolades manquantes)
      → WHEN: Appeler load_profiles()
      → THEN: Retourne {} (fallback gracieux)
      →       Pas de crash de l'application

- [ ] test_load_profiles_detects_file_changes()
      → GIVEN: Charger profiles → {"Player1": ...}
      →        Modifier le fichier → ajouter "Player2"
      →        Invalider le cache (si caching)
      → WHEN: Recharger load_profiles()
      → THEN: Retourne {"Player1": ..., "Player2": ...}
      →       Les modifications sont détectées

- [ ] test_load_profiles_respects_env_variable()
      → GIVEN: OPENSPARTAN_PROFILES_PATH=/tmp/custom_profiles.json
      →        Créer /tmp/custom_profiles.json avec profils de test
      → WHEN: Appeler load_profiles()
      → THEN: Charge depuis /tmp/custom_profiles.json
      →       Ignore db_profiles.json par défaut
```

**Propriété testée :** La fonction DOIT lire le fichier JSON et parser les profils, même avec fichier manquant/corrompu (fallback gracieux).

**Fichiers à tester:** `src/utils/profiles.py::load_profiles()`

---

### ✅ `tests/test_settings_loading.py`

**But:** Valider que `load_settings()` **lit et persiste correctement** la configuration utilisateur

**Approche intelligente :** Tester le cycle complet load → modify → save → reload.

```python
# Tests à implémenter avec fichiers temporaires:

- [ ] test_load_settings_reads_existing_file()
      → GIVEN: Créer app_settings.json avec configuration custom:
      →        {"media_captures_base_dir": "/custom/path",
      →         "spnkr_refresh_max_matches": 1000,
      →         "media_tolerance_minutes": 15}
      → WHEN: Appeler load_settings()
      → THEN: AppSettings retourné contient exactement ces valeurs
      →       Les valeurs utilisateur sont préservées

- [ ] test_load_settings_returns_defaults_when_file_missing()
      → GIVEN: app_settings.json n'existe pas
      → WHEN: Appeler load_settings()
      → THEN: Retourne AppSettings avec valeurs par défaut
      →       media_enabled=True (v5 invariant)
      →       spnkr_refresh_max_matches=500 (default)
      →       Pas de crash

- [ ] test_load_settings_validates_and_coerces_types()
      → GIVEN: app_settings.json avec types invalides:
      →        {"media_tolerance_minutes": "15"} (string au lieu de int)
      → WHEN: Appeler load_settings()
      → THEN: Pydantic coerce en int(15) automatiquement
      →       OU retourne valeur par défaut si coercion impossible

- [ ] test_save_settings_persists_to_file()
      → GIVEN: AppSettings avec valeurs custom
      → WHEN: save_settings(settings)
      → THEN: app_settings.json est créé/modifié
      →       Le fichier existe et est un JSON valide
      →       Contient toutes les clés attendues

- [ ] test_save_and_reload_preserves_all_values()
      → GIVEN: AppSettings avec 10+ champs modifiés
      → WHEN: save_settings(settings) puis load_settings()
      → THEN: settings_reloaded == settings_original
      →       Aucune perte de données dans le cycle

- [ ] test_load_settings_enforces_v5_invariants()
      → GIVEN: app_settings.json avec media_enabled=false
      → WHEN: load_settings()
      → THEN: AppSettings.media_enabled == True (forcé)
      →       Les invariants architecturaux sont appliqués
```

**Propriété testée :** Les settings utilisateur DOIVENT être lues, validées, persistées et rechargées sans perte de données.

**Fichiers à tester:** `src/ui/settings.py::load_settings()`, `save_settings()`

---

## 🔄 Tests d'Intégration

### ✅ `tests/integration/test_launcher_players.py`

**But:** Valider que le launcher **détecte et liste les joueurs existants**

**Approche intelligente :** Créer un environnement contrôlé et tester la détection.

```python
# Tests à implémenter avec subprocess et filesystem temporaire:

- [ ] test_launcher_info_detects_existing_players()
      → GIVEN: Créer 3 DBs de test: data/players/{A,B,C}/stats.duckdb
      →        Chaque DB contient sync_meta avec gamertag + xuid
      → WHEN: Exécuter subprocess: python launcher.py info
      → THEN: stdout contient 3 lignes de joueurs
      →       Chaque ligne contient gamertag + count de matchs
      →       Format: "PlayerA (N matchs)"

- [ ] test_launcher_info_shows_zero_when_no_players()
      → GIVEN: data/players/ vide (ou seulement dossiers sans .duckdb)
      → WHEN: Exécuter python launcher.py info
      → THEN: stdout contient "Aucun joueur trouvé" ou "0 joueurs"
      →       Exit code == 0 (pas une erreur, juste info)

- [ ] test_launcher_run_uses_detected_default_db()
      → GIVEN: data/players/TestPlayer/stats.duckdb existe
      → WHEN: subprocess avec mock (intercepter la commande Streamlit)
      →       python launcher.py run
      → THEN: Commande Streamlit contient chemin vers TestPlayer/stats.duckdb
      →       Vérifie que db_path est passé correctement

- [ ] test_launcher_run_with_gamertag_selector()
      → GIVEN: data/players/ contient PlayerA et PlayerB
      → WHEN: python launcher.py run --gamertag PlayerB
      → THEN: Streamlit lancé avec db_path pointant vers PlayerB
      →       Pas PlayerA (sélection explicite)
```

**Propriété testée :** Le launcher DOIT scanner data/players/ et détecter toutes les DBs valides pour les lister/sélectionner.

**Fichiers à tester:** `launcher.py::_list_players()`, `_get_db_for_player()`

---

### ✅ `tests/integration/test_streamlit_startup.py`

**But:** Valider que streamlit_app.py **charge les données au démarrage**

**Approche intelligente :** Tester l'initialisation complète avec données de test.

```python
# Tests à implémenter avec mocks Streamlit:

- [ ] test_streamlit_refuses_direct_execution_without_launcher()
      → GIVEN: Lancer directement: python streamlit_app.py
      → WHEN: Le script détecte qu'il n'est pas lancé via Streamlit
      → THEN: Exit code == 1
      →       stdout/stderr contient message d'erreur clair
      →       Indique d'utiliser launcher.py ou streamlit run

- [ ] test_streamlit_initializes_db_path_from_existing_players()
      → GIVEN: data/players/TestPlayer/stats.duckdb existe
      →        Mock st.session_state vide
      → WHEN: Appeler main() ou init_source_state()
      → THEN: session_state["db_path"] est défini
      →       != "" (détection réussie)
      →       Path(session_state["db_path"]).exists() == True

- [ ] test_streamlit_loads_profiles_at_startup()
      → GIVEN: db_profiles.json contient 2 profils
      →        Mock st.session_state
      → WHEN: render_source_section() est appelé
      → THEN: load_profiles() a été exécuté (vérifier via mock/spy)
      →       Pas d'exception levée
      →       Les profils sont disponibles pour le sélecteur

- [ ] test_streamlit_loads_settings_at_startup()
      → GIVEN: app_settings.json avec config custom
      →        Mock st.session_state
      → WHEN: main() initialise l'app
      → THEN: session_state["app_settings"] existe
      →       Type == AppSettings
      →       Contient les valeurs du fichier JSON

- [ ] test_streamlit_survives_missing_data_gracefully()
      → GIVEN: data/players/ vide, app_settings.json manquant
      → WHEN: main() démarre
      → THEN: Pas de crash (exceptions gérées)
      →       session_state initialisé avec valeurs par défaut
      →       UI affiche message informatif (pas d'erreur hostile)
```

**Propriété testée :** L'app DOIT charger DB, profils et settings au démarrage, et survivre aux données manquantes.

**Fichiers à tester:** `streamlit_app.py::main()`, `init_source_state()`

---

## 🛡️ Tests de Régression Spécifiques

### ✅ `tests/regression/test_issue_20260215_missing_data.py`

**But:** Reproduire la régression du 15 février 2026 - "Application vide alors que les données existent"

**Cause racine :** `get_default_db_path()` retournait `""` au lieu de détecter les DBs dans `data/players/`

**Approche intelligente :** Tester la **détection et lecture des ressources existantes**.

```python
# Tests à implémenter avec vraies DBs de test:

- [ ] test_get_default_db_path_detects_existing_players()
      → GIVEN: Créer data/players/TestPlayer/stats.duckdb avec sync_meta
      → WHEN: Appeler get_default_db_path()
      → THEN: Retourne un chemin non vide qui existe sur le filesystem
      →       ET Path(result).exists() == True
      →       ET result.endswith(".duckdb")

- [ ] test_get_default_db_path_returns_empty_when_no_players()
      → GIVEN: data/players/ vide (ou inexistant)
      → WHEN: Appeler get_default_db_path()
      → THEN: Retourne "" (comportement attendu, pas d'erreur)

- [ ] test_list_duckdb_v4_players_reads_actual_dbs()
      → GIVEN: Créer 3 DBs de test avec gamertags différents
      →        Chaque DB contient N matchs dans player_match_enrichment
      → WHEN: Appeler list_duckdb_v4_players()
      → THEN: Retourne une liste de 3 PlayerInfo
      →       Chaque total_matches correspond au COUNT(*) réel de la DB
      →       Vérifie que gamertag/xuid sont correctement lus depuis sync_meta

- [ ] test_launcher_info_lists_all_existing_players()
      → GIVEN: Créer N DBs de test dans data/players/
      → WHEN: Exécuter launcher.py info (subprocess)
      → THEN: L'output liste exactement N joueurs
      →       Chaque joueur affiché a un count >= 0
      →       Pas de "0 joueurs trouvés" si data/players/ contient des DBs

- [ ] test_streamlit_init_loads_existing_db_path()
      → GIVEN: data/players/ contient au moins 1 DB valide
      →        Mock Streamlit session_state
      → WHEN: init_source_state() (ou équivalent dans app)
      → THEN: session_state["db_path"] est défini
      →       ET != ""
      →       ET le fichier existe
```

**Propriété testée :** Si des DBs existent sur le filesystem, **elles doivent être détectées et chargées**. Pas de valeurs vides quand les données sont présentes.

---

### ✅ `tests/regression/test_issue_20260215_dropdown_zero_matches.py`

**But:** Reproduire la régression "0 matchs" dans la dropdown sidebar

**Contexte:** 15 février 2026 - Tous les joueurs affichaient "0 matchs" dans le sélecteur de la sidebar car `list_duckdb_v4_players()` cherchait dans `match_stats` (table v4) au lieu de `player_match_enrichment` (table v5).

**Approche intelligente :** Tester le **comportement** et la **logique de fallback**, pas des valeurs hardcodées.

```python
# Tests à implémenter avec fixtures DuckDB contrôlées:

- [ ] test_list_players_uses_v5_table_priority()
      → GIVEN: DB de test avec player_match_enrichment contenant 10 matchs
      →        DB de test avec match_stats (v4) contenant 5 matchs (legacy)
      → WHEN: Appeler list_duckdb_v4_players()
      → THEN: total_matches == 10 (utilise player_match_enrichment, PAS match_stats)
      
- [ ] test_list_players_fallback_chain_works()
      → GIVEN: Créer 3 DBs de test:
      →   1. DB avec player_match_enrichment (v5) → 15 matchs attendus
      →   2. DB avec match_stats uniquement (v4) → 8 matchs attendus 
      →   3. DB avec player_match_stats uniquement (v3) → 3 matchs attendus
      → WHEN: Appeler list_duckdb_v4_players() sur chaque DB
      → THEN: Vérifie que chaque fallback fonctionne dans l'ordre
      →       (player_match_enrichment > match_stats > player_match_stats)

- [ ] test_list_players_empty_db_returns_zero()
      → GIVEN: DB vide (aucune table de matchs)
      → WHEN: Appeler list_duckdb_v4_players()
      → THEN: total_matches == 0 (pas de crash, retourne PlayerInfo valide)

- [ ] test_player_info_format_reflects_actual_count()
      → GIVEN: DuckDBPlayerInfo créé avec total_matches=N (paramétré)
      → WHEN: Appeler display_with_stats()
      → THEN: Le string contient exactement "({N} matchs)" ou "(0 matchs)"
      →       Vérifie le format via regex: r"\((\d+) matchs?\)"

- [ ] test_render_selector_all_players_have_counts()
      → GIVEN: Mock list_duckdb_v4_players() → retourne [joueur1(42), joueur2(0), joueur3(156)]
      → WHEN: render_duckdb_v4_player_selector()
      → THEN: Tous les labels du selectbox contiennent un count entre parenthèses
      →       Regex: r".+ \(\d+ matchs?\)$"
      →       Aucun label ne doit contenir "(None matchs)" ou manquer le count
```

**Propriété testée :** La fonction **doit toujours** essayer `player_match_enrichment` en premier, puis fallback, et toujours retourner un count valide (>=0). **Pas de valeurs hardcodées dépendant des données de prod.**

---

### ✅ `tests/regression/test_issue_20260215_settings_spnkr_obsolete.py`

**But:** Reproduire la régression de la section "SPNKr API" obsolète

**Contexte:** 15 février 2026 - La page settings affichait une section "SPNKr API" avec des toggles pour activer/désactiver highlights events, medals, etc. Mais dans l'architecture v5, TOUT est TOUJOURS récupéré automatiquement lors du sync.

**Approche intelligente :** Tester les **invariants architecturaux v5** et la **cohérence UI/code**.

```python
# Tests à implémenter avec isolation Streamlit et mocks:

- [ ] test_settings_sync_section_exists_not_spnkr()
      → GIVEN: Mock Streamlit environment
      → WHEN: render_settings_page() est appelé
      → THEN: Au moins un st.expander() contient le texte "Synchronisation"
      →       Aucun expander ne doit contenir "SPNKr API" (terme obsolète)
      →       Vérifier via inspection des appels st.expander()

- [ ] test_settings_sync_enforces_v5_defaults()
      → GIVEN: AppSettings avec spnkr_refresh_with_highlight_events=False
      →                      et spnkr_refresh_match_type="all"
      → WHEN: Sauvegarder via bouton "Enregistrer"
      → THEN: Valeurs rechargées doivent être:
      →       spnkr_refresh_with_highlight_events=True (forcé)
      →       spnkr_refresh_match_type="matchmaking" (forcé)
      →       Tester via AppSettings.model_validate(saved_dict)

- [ ] test_settings_sync_shows_v5_info_box()
      → GIVEN: Render settings page
      → WHEN: Parser les appels st.info()
      → THEN: Au moins un st.info() mentionne:
      →       - "Architecture v5" ou "v5"
      →       - "highlights" ou "Highlight events"
      →       - "médailles" ou "Médailles"
      →       - "automatiquement" ou "toujours"

- [ ] test_sync_script_ignores_disabled_highlights_param()
      → GIVEN: Mock API SPNKr
      →        Appeler sync_player_duckdb(..., with_highlight_events=False)
      → WHEN: Observer les appels API
      → THEN: Vérifie qu'un endpoint /highlight ou /film a été appelé
      →       (prouve que le paramètre est ignoré)
      →       Utiliser mock.assert_called_with() pour vérifier

- [ ] test_settings_sync_no_misleading_toggles()
      → GIVEN: Render settings page
      → WHEN: Parser tous les st.toggle() et st.checkbox()
      → THEN: Aucun toggle/checkbox ne doit avoir un label suggérant
      →       qu'on peut désactiver: highlights, medals, skill, aliases
      →       Chercher patterns: "Inclure highlight", "Activer médailles", etc.
      →       Ces options doivent être dans la section "backfill" uniquement
```

**Propriété testée :** Les settings **ne doivent jamais** permettre de désactiver les données core v5 (highlights, medals, skill). L'UI doit refléter l'architecture, pas induire en erreur.

---

### ✅ `tests/regression/test_issue_20260215_settings_media_obsolete.py`

**But:** Reproduire la régression de la section "Médias" - Configuration perdue

**Contexte:** 15 février 2026 - L'utilisateur avait défini `media_captures_base_dir` mais l'UI affichait un toggle obsolète "Activer la section Médias" qui laissait penser qu'on pouvait la désactiver, alors que c'est toujours actif en v5.

**Approche intelligente :** Vérifier la **persistance et lecture des configurations utilisateur**.

```python
# Tests à implémenter avec fichier app_settings.json de test:

- [ ] test_settings_loads_existing_media_config()
      → GIVEN: Créer app_settings.json avec:
      →        {"media_enabled": true, "media_captures_base_dir": "D:/TestCaptures"}
      → WHEN: load_settings()
      → THEN: AppSettings.media_enabled == True
      →       AppSettings.media_captures_base_dir == "D:/TestCaptures"
      →       Les valeurs configurées sont PRÉSERVÉES

- [ ] test_settings_preserves_media_path_on_save()
      → GIVEN: AppSettings avec media_captures_base_dir="/custom/path"
      → WHEN: Sauvegarder via save_settings()
      → THEN: Recharger → media_captures_base_dir == "/custom/path"
      →       Le chemin utilisateur n'est pas écrasé par ""

- [ ] test_settings_ignores_legacy_fields_on_save()
      → GIVEN: Ancien app_settings.json avec media_screens_dir et media_videos_dir
      → WHEN: Charger puis sauvegarder (cycle complet)
      → THEN: Nouveau settings.json ne contient PAS ces champs legacy
      →       OU ils sont forcés à "" (pas propagés)

- [ ] test_settings_media_always_enabled_on_save()
      → GIVEN: Essayer de créer AppSettings(media_enabled=False, ...)
      → WHEN: Sauvegarder puis recharger
      → THEN: media_enabled est forcé à True (invariant v5)
      →       Protection contre configuration invalide

- [ ] test_settings_ui_shows_user_configured_path()
      → GIVEN: app_settings.json avec media_captures_base_dir="X:/MyPath"
      → WHEN: render_settings_page(settings)
      → THEN: Le directory_input affiche "X:/MyPath" comme valeur
      →       L'utilisateur voit sa config actuelle (pas de valeur vide)
```

**Propriété testée :** Si l'utilisateur a configuré un chemin média, **il doit être chargé, affiché et préservé**. Pas de perte de configuration silencieuse.

---

### ✅ `tests/regression/test_issue_20260215_settings_source_unclear.py`

**But:** Vérifier la détection et rafraîchissement des joueurs disponibles

**Contexte:** 15 février 2026 - La section "Source" existait mais son utilité n'était pas claire. Elle doit détecter les DBs existantes et permettre de rafraîchir la liste.

**Approche intelligente :** Tester la **fonctionnalité réelle** : détection dynamique des joueurs.

```python
# Tests à implémenter avec filesystem contrôlé:

- [ ] test_get_local_dbs_detects_existing_players()
      → GIVEN: Créer 3 fichiers data/players/{A,B,C}/stats.duckdb
      → WHEN: Appeler get_local_dbs() (via la fonction passée à render_source_section)
      → THEN: Retourne une liste de 3 chemins
      →       Chaque chemin existe et se termine par .duckdb
      →       Les gamertags A, B, C sont identifiables dans les paths

- [ ] test_get_local_dbs_returns_empty_when_no_players()
      → GIVEN: data/players/ vide ou inexistant
      → WHEN: Appeler get_local_dbs()
      → THEN: Retourne [] (liste vide, pas d'erreur)

- [ ] test_refresh_button_detects_new_player()
      → GIVEN: Initialement 2 DBs dans data/players/
      →        Lister avec get_local_dbs() → [DB1, DB2]
      → WHEN: Ajouter une 3ème DB (data/players/NewPlayer/stats.duckdb)
      →       Cliquer sur bouton "Rafraîchir" (invalider cache)
      → THEN: get_local_dbs() retourne maintenant [DB1, DB2, DB3]
      →       Le nouveau joueur est détecté

- [ ] test_clear_caches_button_calls_callback()
      → GIVEN: Mock on_clear_caches callback
      → WHEN: render_source_section(..., on_clear_caches=mock_fn)
      →       Simuler clic sur "Vider caches"
      → THEN: mock_fn.assert_called_once()
      →       Le callback est bien appelé

- [ ] test_source_section_resolves_xuid_from_db()
      → GIVEN: DB de test avec sync_meta contenant xuid="12345", gamertag="TestGT"
      → WHEN: render_source_section(default_db=path_to_test_db, ...)
      → THEN: Retourne (db_path, xuid, waypoint_player)
      →       xuid == "12345" (lu depuis sync_meta)
      →       waypoint_player == "TestGT" ou proche
```

**Propriété testée :** La section Source doit **détecter les DBs existantes** et permettre de **rafraîchir dynamiquement** quand de nouveaux joueurs sont ajoutés.

---

### ✅ `tests/regression/test_issue_20260215_v5_xuid_required.py`

**But:** Reproduire la régression "Aucun match trouvé" pour DBs v5 (shared matches)

**Contexte:** 15 février 2026 après-midi - Tous les joueurs affichaient "Aucun match trouvé" même avec des DBs contenant des données. Le code chargeait les matchs avec `DuckDBRepository(db_path, xuid="")`, mais en architecture v5 (shared matches), la requête SQL filtre sur `match_participants.xuid = ?` → avec `xuid=""`, **0 résultats**.

**Cause racine :** `_load_matches_duckdb_v4_polars` passait `xuid=""` au repository, alors qu'en mode v5 le XUID est **obligatoire** pour filtrer les tables shared.

**Approche intelligente :** Tester avec DBs v4 (table locale) ET v5 (tables shared) pour valider les deux architectures.

```python
# Tests à implémenter avec DBs temporaires v4 et v5:

- [ ] test_load_matches_v4_with_empty_xuid()
      → GIVEN: DB v4 pure (table match_stats locale, pas de shared)
      →        DB contient 10 matchs pour le joueur
      → WHEN: load_df_optimized(db_path, xuid="")
      → THEN: Retourne DataFrame avec 10 matchs
      →       Car v4 ne filtre PAS sur xuid (1 joueur = 1 DB)

- [ ] test_load_matches_v5_requires_xuid()
      → GIVEN: DB v5 (tables shared.match_registry + match_participants)
      →        sync_meta contient xuid="2535405290604855"
      →        match_participants contient 15 matchs pour ce xuid
      → WHEN: _load_matches_duckdb_v4_polars(db_path) sans xuid
      → THEN: Code lit xuid depuis sync_meta automatiquement
      →       Retourne DataFrame avec 15 matchs
      →       PAS 0 matchs (régression)

- [ ] test_load_matches_v5_empty_xuid_returns_zero()
      → GIVEN: DB v5 avec shared.match_participants contenant 20 matchs
      →        MAIS sync_meta.xuid est vide ou absent
      → WHEN: _load_matches_duckdb_v4_polars(db_path)
      → THEN: Retourne DataFrame vide (0 matchs)
      →       Car impossible de filtrer sans xuid en mode v5

- [ ] test_load_matches_fallback_chain()
      → GIVEN: DB en transition (shared + match_stats locale)
      →        sync_meta.xuid = "123456"
      →        shared.match_participants contient 10 matchs (xuid=123456)
      →        match_stats locale contient 10 matchs (même matchs)
      → WHEN: _load_matches_duckdb_v4_polars(db_path)
      → THEN: Utilise les tables shared en priorité
      →       Retourne 10 matchs avec toutes les colonnes

- [ ] test_sync_meta_xuid_extraction()
      → GIVEN: DB avec sync_meta.xuid = "2535405290604855"
      → WHEN: Créer DuckDBRepository pour cette db
      → THEN: Repository.xuid == "2535405290604855"
      →       Pas "" (string vide)
```

**Propriété testée :** En architecture v5 (shared matches), le code DOIT **toujours** récupérer le XUID depuis `sync_meta` avant de charger les matchs. Le filtrage sur xuid vide → 0 résultats.

---

## 🔬 Tests de Cohérence

### ✅ `tests/test_data_consistency.py`

**But:** Valider la cohérence entre différentes sources de données

```python
# Tests à implémenter:
- [ ] test_profiles_match_filesystem()
      → Lister data/players/*/stats.duckdb
      → Charger load_profiles()
      → Vérifie que chaque profil pointe vers un fichier existant

- [ ] test_default_db_exists_on_filesystem()
      → default_db = get_default_db_path()
      → Si default_db != "":
      →   Vérifie que Path(default_db).exists()

- [ ] test_profiles_xuids_match_db_content()
      → Pour chaque profil dans load_profiles()
      → Ouvrir la DB
      → Lire sync_meta.xuid
      → Vérifie égalité avec profil["xuid"]

- [ ] test_no_orphan_dbs()
      → Lister data/players/*/stats.duckdb
      → Charger load_profiles()
      → Vérifie que chaque DB a un profil correspondant
      → (warn si orphelins, pas fail)
```

---

## ♻️ Migration de Scripts Manuels vers Tests Automatisés

### ❌ `test_data_access.py` (racine) → ✅ `tests/integration/test_data_access_real_env.py`

**Problème actuel :**
- Script manuel à la racine du projet
- Dépend de l'environnement de production (`data/players/`, `db_profiles.json`, `app_settings.json`)
- N'est pas exécuté automatiquement par pytest
- Pas de validation (juste des print)

**Solution :**

```python
# tests/integration/test_data_access_real_env.py
"""Tests d'accès aux données sur environnement réel.

Ces tests sont SKIP par défaut et ne s'exécutent que si:
- pytest --run-integration
- OU variable env LEVELUP_RUN_INTEGRATION_TESTS=1

Ils vérifient que les données de l'environnement de développement
sont accessibles (utile pour diagnostiquer l'environnement local).
"""

import pytest
from pathlib import Path

pytestmark = pytest.mark.integration  # Marqueur pour --run-integration

@pytest.fixture(autouse=True)
def require_integration_flag():
    """Skip ces tests sauf si explicitement demandé."""
    import os
    if not os.environ.get("LEVELUP_RUN_INTEGRATION_TESTS"):
        pytest.skip("Tests d'intégration désactivés par défaut")

class TestRealEnvDataAccess:
    """Tests sur l'environnement réel de développement."""
    
    def test_default_db_accessible(self):
        """Vérifie que get_default_db_path() retourne une DB accessible."""
        from src.config import get_default_db_path
        
        db_path = get_default_db_path()
        
        # Si vide, c'est OK (pas de joueurs), mais doit être str
        assert isinstance(db_path, str), "get_default_db_path() must return str"
        
        # Si non vide, la DB doit exister
        if db_path:
            assert Path(db_path).exists(), f"DB not found: {db_path}"
            assert db_path.endswith(".duckdb"), f"Not a DuckDB file: {db_path}"
    
    def test_profiles_loadable(self):
        """Vérifie que load_profiles() fonctionne."""
        from src.utils.profiles import load_profiles
        
        profiles = load_profiles()
        
        # Peut être vide, mais doit être dict
        assert isinstance(profiles, dict), "load_profiles() must return dict"
        
        # Si des profils existent, valider structure
        for name, info in profiles.items():
            assert "db_path" in info, f"Profile {name} missing db_path"
            assert isinstance(info["db_path"], str)
    
    def test_settings_loadable(self):
        """Vérifie que load_settings() fonctionne."""
        from src.ui import load_settings
        
        settings = load_settings()
        
        # Doit retourner AppSettings valide
        assert settings is not None
        assert hasattr(settings, "media_enabled")
        assert hasattr(settings, "spnkr_refresh_max_matches")
    
    def test_at_least_one_player_or_warning(self, capsys):
        """Vérifie qu'au moins 1 joueur existe OU affiche warning."""
        from src.config import get_repo_root
        
        repo_root = Path(get_repo_root())
        players_dir = repo_root / "data" / "players"
        
        if not players_dir.exists():
            pytest.skip("data/players/ does not exist")
        
        dbs = list(players_dir.glob("*/stats.duckdb"))
        
        if not dbs:
            print("⚠️ WARNING: No players found in data/players/")
            print("   Run 'python scripts/sync.py' to add players")
            pytest.skip("No players in environment (expected for fresh install)")
        
        # Au moins 1 joueur trouvé
        assert len(dbs) > 0
```

**À faire :**
- [ ] Créer `tests/integration/test_data_access_real_env.py`
- [ ] Ajouter `pytest.ini` avec marqueur integration
- [ ] Supprimer ou déplacer `test_data_access.py` vers `scripts/dev/`
- [ ] Documenter dans `docs/TESTING_V5.md` comment lancer ces tests

**Commandes :**
```bash
# Tests unitaires (fixtures isolées) - RAPIDE
pytest tests/ -v

# Tests d'intégration sur env réel - LENT
LEVELUP_RUN_INTEGRATION_TESTS=1 pytest tests/integration/ -v
```

---

## 📊 Tests de Performance

### ✅ `tests/performance/test_startup_time.py`

**But:** Détecter les ralentissements au démarrage

```python
# Tests à implémenter:
- [ ] test_get_default_db_path_fast()
      → Mesurer temps d'exécution
      → Vérifie < 100ms (même avec 100 joueurs)

- [ ] test_load_profiles_fast()
      → Mesurer temps d'exécution
      → Vérifie < 50ms

- [ ] test_load_settings_fast()
      → Mesurer temps d'exécution
      → Vérifie < 50ms
```

---

## 🚀 CI/CD à Mettre en Place

### ✅ `.github/workflows/anti-regression.yml`

```yaml
# Workflow à créer:
name: Anti-Regression Tests

on:
  push:
    branches: [main, develop]
    paths:
      - 'src/config.py'
      - 'src/utils/profiles.py'
      - 'src/ui/settings.py'
      - 'streamlit_app.py'
      - 'launcher.py'
  pull_request:
    paths:
      - 'src/config.py'
      - 'src/utils/profiles.py'
      - 'src/ui/settings.py'
      - 'streamlit_app.py'
      - 'launcher.py'

jobs:
  test-data-loading:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e .
          pip install pytest pytest-cov
      
      - name: Create test data structure
        run: |
          mkdir -p data/players/TestPlayer
          # Créer une DB minimale pour tests
      
      - name: Run anti-regression tests
        run: |
          pytest tests/test_config_db_path.py -v
          pytest tests/test_profiles_loading.py -v
          pytest tests/test_settings_loading.py -v
          pytest tests/regression/ -v
      
      - name: Test launcher
        run: |
          python launcher.py info
      
      - name: Verify no empty defaults
        run: |
          python -c "from src.config import get_default_db_path; assert get_default_db_path() != '', 'REGRESSION: get_default_db_path returned empty string'"
```

---

## 📝 Documentation à Ajouter

### ✅ `docs/TESTING_DATA_LOADING.md`

```markdown
# Tests de Chargement des Données

## Contrat de get_default_db_path()

**INVARIANTS:**
- Si data/players/ contient au moins 1 joueur avec stats.duckdb
  → DOIT retourner un chemin non vide
- Le chemin retourné DOIT exister sur le filesystem
- Le chemin retourné DOIT être déterministe (toujours le même)
- Si data/players/ vide → retourner ""

**TESTS REQUIS:**
- Voir tests/test_config_db_path.py

## Contrat de load_profiles()

**INVARIANTS:**
- DOIT retourner un dict (peut être vide)
- JAMAIS de crash même si db_profiles.json corrompu
- Cache invalidé si mtime change

**TESTS REQUIS:**
- Voir tests/test_profiles_loading.py

## Contrat de load_settings()

**INVARIANTS:**
- DOIT retourner un objet AppSettings
- Validation Pydantic active
- Valeurs par défaut si fichier manquant

**TESTS REQUIS:**
- Voir tests/test_settings_loading.py
```

---

## 🎯 Plan d'Action Priorisé

### Phase 1 : Tests Critiques (Cette semaine)
- [x] Créer ce fichier TODO
- [ ] Créer `tests/test_config_db_path.py` → 6 tests
- [ ] Créer `tests/test_profiles_loading.py` → 6 tests
- [ ] Créer `tests/regression/test_issue_20260215_missing_data.py` → 3 tests
- [ ] Ajouter au CI/CD

**Critère de succès:** Si on revient à `return ""`, les tests échouent

### Phase 2 : Tests d'Intégration (Semaine prochaine)
- [ ] Créer `tests/integration/test_launcher_players.py` → 3 tests
- [ ] Créer `tests/integration/test_streamlit_startup.py` → 4 tests
- [ ] Créer `tests/test_data_consistency.py` → 4 tests

### Phase 3 : Tests Complémentaires (Sprint suivant)
- [ ] Créer `tests/test_settings_loading.py` → 5 tests
- [ ] Créer `tests/performance/test_startup_time.py` → 3 tests
- [ ] Documentation `docs/TESTING_DATA_LOADING.md`

---

## 🔍 Cas Limites à Tester

**Scénarios edge-case:**

1. **Dossier data/players/ existe mais vide**
   - get_default_db_path() → ""
   - load_profiles() → {}
   - launcher.py info → message clair

2. **1 seul joueur avec 0 matchs**
   - get_default_db_path() → chemin du joueur
   - launcher.py info → affiche "0 matchs"

3. **Fichiers .db et .duckdb mélangés**
   - get_default_db_path() → ignore les .db
   - Retourne seulement .duckdb

4. **Permission denied sur db_profiles.json**
   - load_profiles() → {} (pas de crash)
   - Warning loggé

5. **DB corrompue dans data/players/**
   - get_default_db_path() → retourne le chemin quand même
   - C'est au code appelant de gérer l'erreur d'ouverture

6. **Caractères spéciaux dans gamertag**
   - Ex: "Player™2024"
   - Doit fonctionner sans crash

---

## 📊 Métriques de Succès

**Objectif:** Aucune régression sur le chargement des données

**KPI:**
- ✅ 100% des tests de régression passent
- ✅ Coverage > 90% sur src/config.py, src/utils/profiles.py, src/ui/settings.py
- ✅ Temps d'exécution tests < 5s
- ✅ CI/CD détecte les régressions avant merge

**Validation:**
```bash
# Commande de validation complète
pytest tests/test_config_db_path.py \
       tests/test_profiles_loading.py \
       tests/regression/ \
       --cov=src/config \
       --cov=src/utils/profiles \
       --cov=src/ui/settings \
       --cov-report=term-missing \
       --cov-fail-under=90
```

---

## 🚨 Alertes Anti-Régression

**Triggers à configurer:**

1. **Pre-commit hook**
   ```bash
   # .git/hooks/pre-commit
   pytest tests/regression/ -x
   ```

2. **Pull Request checks**
   - Tests de régression obligatoires
   - Blocage si échec

3. **Monitoring post-déploiement**
   - Health check: `python test_data_access.py`
   - Alert si crash

---

## 📚 Références

- Issue: Régression du 15 février 2026 - App vide
- Cause: `get_default_db_path()` retournait `""`
- Fix: Commit [à remplir après commit]
- Tests: Ce fichier TODO

---

**Dernière mise à jour:** 15 février 2026  
**Assigné à:** Équipe Dev  
**Statut:** 🔴 TODO - Tests non créés
