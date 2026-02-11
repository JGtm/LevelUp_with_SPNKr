# Thought Log - Journal de Raisonnement

> Ce fichier capture le raisonnement de l'agent entre les sessions.
> Archivé : 2026-02-01 (logs précédents dans `.ai/archive/thought_log_pre_phase6.md`)

---

## Journal

### [2026-02-11] - Sprints 3 + 4 (partiel) — Damage participants, Carrière, UI améliorations

**Statut** : Sprint 3 livré, Sprint 4 partiellement livré

**Sprint 3A — Damage participants** : Toutes les tâches 3A.1 à 3A.6 réalisées.

**Changements code (3A)** :
- `src/data/sync/models.py` : Ajout `damage_dealt: float | None` et `damage_taken: float | None` à `MatchParticipantRow`
- `src/data/sync/transformers.py` : Extraction `DamageDealt`/`DamageTaken` via `_safe_float()` dans `extract_participants()`
- `src/data/sync/engine.py` : DDL mis à jour (14 colonnes), migration `_ensure_match_participants_rank_score()` étendue, `_insert_participant_rows()` avec 14 colonnes
- `scripts/backfill_data.py` : 16+ points d'édition pour `--participants-damage` et `--force-participants-damage` (détection, UPDATE, compteurs, argparse)
- `tests/test_participants_damage.py` (nouveau) : 10 tests couvrant extraction damage, valeurs None, zéro valide, multi-joueur

**Sprint 3B — Page Carrière** : Toutes les tâches 3B.1 à 3B.5 réalisées.

**Changements code (3B)** :
- `src/ui/components/career_progress_circle.py` (nouveau) : Gauge Plotly `go.Indicator(mode="gauge+number")` avec couleurs par palier (rouge→ambre→cyan→vert)
- `src/ui/pages/career.py` (nouveau) : Page complète avec `_load_career_data()`, `_load_career_history()`, `_create_xp_history_chart()`, layout 3 colonnes (icône, métriques, gauge) + historique XP
- `src/app/page_router.py` : "Carrière" ajouté à PAGES + dispatch
- `src/ui/pages/__init__.py` : Export `render_career_page`
- `streamlit_app.py` : Import + wiring `render_career_page_fn`
- `tests/test_career_page.py` (nouveau) : Tests gauge (go.Figure, max_rank, zero XP, custom height) + labels FR

**Sprint 4.0 — Nettoyage duplications** : Livré.

- `src/visualization/distributions.py` : 4 copies dupliquées de `plot_top_weapons()` supprimées (lignes 647, 891, 1070, 1221). Fichier passé de 1284 à 1071 lignes. Une seule définition conservée (ligne 495).

**Sprint 4.1 — Médianes sur histogrammes** : Livré.

- `plot_kda_distribution()` : Ligne médiane `add_vline` (dash ambre #ffaa00) avec annotation
- `plot_histogram()` : Ligne médiane après la section KDE
- `plot_first_event_distribution()` : Médianes frag et mort (dot ambre) en plus des moyennes existantes

**Sprint 4.2 — Renommage Kills→Frags** : Livré.

- Fichiers modifiés : `timeseries.py`, `session_compare.py`, `match_history.py`, `match_view_charts.py`, `objective_analysis.py`, `teammates.py`, `teammates_charts.py`
- "Kills" conservé uniquement dans `plot_top_weapons` (contexte armes spécifique)

**Ce qui RESTE à faire pour le Sprint 4** :

| Tâche | Statut | Détail |
|-------|--------|--------|
| 4.3 Normalisation noms de mode | Pas commencé | Appliquer `translate_pair_name()` dans le graphe "Par mode" de `win_loss.py` |
| 4.M1 Migration Polars `distributions.py` | Pas commencé | Remplacer `_normalize_df()` par `_to_polars()`, migrer les fonctions simples |
| 4.M2 Migration Polars `timeseries.py` | Pas commencé | Convertir `dff` en Polars au début, travailler en Polars |
| 4.M3+M4 Migration Polars `teammates.py` + `teammates_charts.py` | Pas commencé | Arrêter de convertir en Pandas, modifier signatures |
| 4.M6 Migration Polars `win_loss.py` | Pas commencé | Convertir en Polars pour la logique, garder `.to_pandas()` pour styler |
| 4.5 Features teammates | Pas commencé | Stats/min en barres, frags parfaits, radar trio |
| Tests Sprint 4 | Pas commencé | Étendre test_visualizations.py, créer tests normalisation/teammates |

**Analyse technique pour la reprise (4.M6 win_loss.py)** :
- Le fichier utilise `pivot_table`, `pd.to_datetime`, `.dt.to_period()`, et surtout `tbl.style.apply()` (Pandas styler)
- Stratégie recommandée : accepter `pl.DataFrame | pd.DataFrame`, convertir à Polars au début, passer Polars aux fonctions de distributions.py (qui gèrent les deux types via `_normalize_df()`), convertir à Pandas uniquement pour le pivot_table (section "Par période") et le styler (section map table)
- `plot_win_ratio_heatmap` et `plot_matches_at_top_by_week` n'ont PAS de `_normalize_df()` → requièrent Pandas → convertir avant appel
- `compute_map_breakdown` accepte déjà les deux types, retourne Pandas

**Tests** : Non exécutables en MSYS2 (duckdb absent — limitation connue, pas une régression).

---

### [2026-02-10] - Sprint 2 livré — Migration Pandas→Polars core

**Statut** : Livré (commit 245c91b)

---

### [2026-02-10] - Sprint 1 livré — Nettoyage scripts + Archivage documentation

**Statut** : Livré

**Sprint 1 — PLAN_UNIFIE.md** : Toutes les tâches 1.1 à 1.9 réalisées.

**Résultat scripts/** :
- 113 scripts → **16 actifs** + 10 en `migration/` + 71 archivés dans `_archive/` + 13 supprimés + 3 dans `_obsolete/` supprimé
- 7 backfill redondants supprimés (couverts par `backfill_data.py`)
- 6 fix one-shot supprimés (corrections déjà appliquées)
- `scripts/_obsolete/` supprimé
- 9 scripts `test_*`/`validate_*`/`verify_*` archivés (équivalents dans `tests/`)

**Résultat .ai/** :
- 5 documents racine archivés : `SUPER_PLAN.md`, `CODE_REVIEW_CLEANUP_PLAN.md`, `AGENT_ARCHITECTURE.md`, `ORCHESTRATION_PROMPTS.md`, `workflows.md` (consolidés dans `PLAN_UNIFIE.md`)
- Recherches killfeed (KILL_FEED_*.md, JSON, etc.) archivées dans `.ai/archive/research/`

**Corrections** :
- `tests/test_spnkr_refactoring.py` : mis à jour `sys.path` vers `scripts/_archive/` (spnkr_import_db.py archivé)
- Docstring `backfill_data.py` : documenté le workaround OR (exécution par étapes recommandée)

**Tests** : 93 passés, aucune régression. Échecs préexistants (pyarrow/duckdb absents en MSYS2).

---

### [2026-02-10] - Sprint 0 livré + Documentation environnement MSYS2

**Statut** : Livré

**Sprint 0 — PLAN_UNIFIE.md** : Toutes les tâches 0.1 à 0.7 réalisées.

**Changements code** :
- `src/app/filters_render.py` : `_compute_trio_label()` utilise maintenant `max(start_time)` par session au lieu de `session_id.max()` pour trouver la dernière session trio. Évite le tri lexicographique incorrect des session_id VARCHAR.
- `src/app/filters.py` : même correction dans la version dupliquée de `_compute_trio_label()`.
- `src/ui/filter_state.py` : ajout de `FILTER_DATA_KEYS`, `FILTER_WIDGET_KEY_PREFIXES` et `get_all_filter_keys_to_clear()` pour centraliser les clés de filtres à nettoyer lors du changement de joueur.
- `streamlit_app.py` : remplacement du nettoyage partiel (8 clés hardcodées) par `get_all_filter_keys_to_clear()` qui couvre 15 clés de données + toutes les clés de widgets checkbox (`filter_playlists_*`, `filter_modes_*`, `filter_maps_*`).

**Tests** :
- `tests/test_session_last_button.py` (nouveau, 8 tests) : tri par `max(start_time)`, cas VARCHAR, cas trio.
- `tests/test_filter_state.py` (étendu, +7 tests) : `get_all_filter_keys_to_clear()`, simulation switch joueur A→B→A.

**Nettoyage** :
- `.venv_windows/` supprimé (était déjà vide/cassé)
- `levelup_halo.egg-info/` supprimé
- `out/` vidé

**Environnement MSYS2** :
- Découverte que `.venv` était vide (aucun package) et que l'environnement est MSYS2/MinGW, pas Windows natif.
- Les packages C (numpy, pandas, polars) doivent être installés via `pacman`, pas `pip`.
- DuckDB n'a pas de package MSYS2, donc les tests qui importent `duckdb` transitoirement échouent en `ModuleNotFoundError` — c'est une limitation connue, pas une régression.
- Venv recréé avec `--system-site-packages` pour hériter des packages pacman.
- `.venv/bin/` (pas `.venv/Scripts/`) car MSYS2 suit les conventions Unix.
- Documenté dans `CLAUDE.md` section "Environnement Python" pour éviter que les futurs agents perdent du temps.

---

### [2026-02-09] - Analyse persistance des filtres multi-joueurs (sans modification de code)

**Statut** : 📋 Analyse et plan détaillé rédigés

**Contexte** : L'utilisateur signale des conflits et une mauvaise persistance des filtres par DB joueur : au switch utilisateur les filtres ne sont pas correctement restaurés, au retour sur le joueur initial encore plus de filtres sont désélectionnés ; demande d’analyse approfondie + plan de correction ultra détaillé, sans toucher au code.

**Cause racine identifiée** :
- Les **clés des widgets** Streamlit (checkboxes playlists/modes/cartes : `filter_playlists_cb_*`, `filter_playlists_cat_*`, `*_version`, etc.) sont **globales** et **non supprimées** au changement de joueur.
- Après `apply_filter_preferences(new_player)`, les données en `session_state` sont correctes mais Streamlit réaffiche l’état des **widgets** (ancien joueur) → affichage incohérent → l’utilisateur « corrige » en cliquant → la sélection est modifiée → la sauvegarde automatique en fin de rendu **écrase** le JSON du joueur avec une sélection dégradée.
- Liste de nettoyage au changement de joueur **incomplète** : manquent `gap_minutes`, `_latest_session_label`, `min_matches_maps`, etc., et surtout **toutes les clés dont le nom commence par** `filter_playlists_`, `filter_modes_`, `filter_maps_`.

**Livrable** : `.ai/ANALYSE_PERSISTANCE_FILTRES_MULTI_JOUEURS.md` — analyse détaillée, scénario type « encore plus de filtres désélectionnés », plan de correction en 7 phases (nettoyage exhaustif, centralisation des clés, tests, option scopage widgets par joueur, doc).

**Prochaines étapes** : Implémenter le plan (Phase 1–2 en priorité : nettoyage exhaustif + centralisation des clés).

---

### [2026-02-09] - Revue complète du script backfill_data.py + Diagnostic persistance

**Statut** : 🔧 Correctif partiel appliqué (commit final), diagnostic complet documenté

**Contexte** : L'utilisateur signale que le script backfill_data.py "ne semble pas bien fonctionner". Symptôme concret : 605 matchs détectés, après traitement de 200 et relance → toujours 605.

**Symptôme utilisateur (Madina97294)** :
1. Lance `--all --all-data` → Trouve **605 matchs** à traiter
2. Traite **200 matchs** puis interrompt (Ctrl+C)
3. Relance → Trouve toujours **605 matchs** (au lieu de ~405)
4. **Conclusion** : Les données ne sont PAS persistées

**Diagnostic double problème** :

**Problème A - Commit non persisté lors d'interruption (✅ CORRIGÉ)** :
- **Cause** : `finally: conn.close()` sans commit final (ligne 1957-1958)
- **Impact** : DuckDB perd les données en cache lors d'interruption Ctrl+C
- **Correction appliquée** : Ajout de `conn.commit()` dans le `finally` avant `conn.close()`
- **Fichier modifié** : `scripts/backfill_data.py` ligne 1957-1964

**Problème B - Détection OR inefficace (⚠️ NON CORRIGÉ)** :
- **Cause** : `where_clause = " OR ".join(conditions)` (ligne 982)
- **Impact** : Un match est sélectionné s'il manque **AU MOINS UNE** donnée parmi ~15 types
- **Conséquence** : Matchs partiellement traités sont RE-SÉLECTIONNÉS et RE-TÉLÉCHARGÉS depuis l'API
- **Exemple** : Match avec medals/events/skill présents mais sans `sessions` → RE-téléchargé complètement
- **Workaround** : Traiter par étapes au lieu de `--all-data` (voir document)

**Analyse effectuée** :
- Lecture du fichier complet (2461 lignes)
- Identification de 10 problèmes classés par sévérité
- Diagnostic du problème de persistance (commit + détection)
- Rédaction document détaillé + section "Problème Urgent" : `.ai/BACKFILL_SCRIPT_REVIEW.md`

**Problèmes critiques identifiés** :
1. **🔴 Commit non persisté** : Interruption perd les données (✅ corrigé ligne 1957-1964)
2. **🔴 Détection OR inefficace** : Re-téléchargements inutiles avec `--all-data` (⚠️ workaround documenté)
3. **🔴 Violation règle Pandas** : Usage de `pd.Series` (lignes 119, 698, 709)
4. **🔴 Gestion erreurs silencieuse** : 9 blocs `except Exception: pass` sans logs
5. **🔴 Taille excessive** : 2461 lignes, difficile à maintenir

**Solutions proposées (Problème B)** :
- **Court terme** : Mode `--strict-detection` (AND au lieu de OR)
- **Long terme** : Table `backfill_status` pour tracker par type de donnée

**Tests de validation** :
1. Test persistance : Traiter 30 matchs, interrompre, relancer → Devrait trouver ~575 matchs
2. Test re-téléchargement : Traiter medals uniquement, relancer `--all-data` → Observer si re-sélection

**Recommandations prioritaires** :
- **Phase 0** (immédiat) : ✅ Commit final ajouté, à tester
- **Phase 1** (1-2j) : Supprimer Pandas, ajouter logs exceptions, implémenter `--strict-detection`
- **Phase 2** (3-5j) : Optimiser SQL (CTEs), centraliser migrations
- **Phase 3** (1-2 sem) : Découper en modules, table `backfill_status`

**Impact estimé** :
- Commit final : **Données persistées** lors d'interruption (✅ critique)
- Mode strict : **Pas de re-téléchargements** inutiles (gain énorme)
- SQL optimisé : **10-20x plus rapide**

**Fichiers modifiés** :
- `scripts/backfill_data.py` (ligne 1957-1964)
- `.ai/BACKFILL_SCRIPT_REVIEW.md` (section "Problème Urgent" ajoutée)
- `.ai/thought_log.md` (cette entrée)

**Prochaines étapes** : Utilisateur teste la persistance, puis implémenter mode strict si validé.

---

### [2026-02-08] - Comparaison de sessions : KeyError kills / pair_name (root cause)

**Statut** : Corrigé

**Problème** : Sur l’onglet « Comparaison de sessions », KeyError sur `pair_name` puis sur `kills`.

**Root cause** : La page reçoit `all_sessions_df` issu de `cached_compute_sessions_db()`. En chemin **DuckDB v4**, cette fonction ne sélectionne que `match_id`, `start_time`, `session_id`, `session_label` (pour limiter la lecture disque). Elle ne charge pas `pair_name`, `kills`, `deaths`, etc. La page suppose au contraire un DataFrame « sessions » **enrichi** (une ligne par match avec session_id, session_label + toutes les colonnes de match_stats). D’où les KeyError dès qu’on accède à `pair_name` ou `kills`.

**Correction** :
- **page_router** : Pour « Comparaison de sessions », fusionner `df` (stats complètes) avec `all_sessions_df` sur `match_id` avant d’appeler la page. La page reçoit ainsi un DataFrame enrichi (session_id, session_label + kills, pair_name, etc.). Si merge impossible (all_sessions_df vide ou pas de match_id), on garde l’ancien comportement (all_sessions_df tel quel).
- **session_compare.py** : Garde déjà ajoutée pour le filtre par catégorie : `if mode_category and "pair_name" in df.columns` pour éviter KeyError si `pair_name` absent.

**Fichiers modifiés** : src/app/page_router.py, src/ui/pages/session_compare.py (garde pair_name), .ai/thought_log.md.

---

### [2026-02-07] - Shots fired / shots hit en BDD et backfill (SHOTS_FIRED_HIT_BDD_PLAN)

**Statut** : Implémenté (Sprints 1–3)

**Objectif** : Persister `shots_fired` et `shots_hit` pour le joueur propriétaire et pour tous les participants, avec options de backfill.

**Sprint 1** :
- `engine._insert_match_row` : colonnes `shots_fired`, `shots_hit` incluses dans l’INSERT (déjà extraites par `transform_match_stats`).
- Backfill `--shots` et `--force-shots` dans `backfill_data.py` (sélection matchs NULL, mise à jour, compteur `shots_updated`).
- Docstring et tests (test_sync_engine : extraction shots dans transform_match_stats ; test_sync_performance_score : schémas avec shots_fired/shots_hit).

**Sprint 2** :
- `match_participants` : colonnes `shots_fired`, `shots_hit` (SYNC_SCHEMA_DDL + migration `_ensure_match_participants_rank_score`).
- `MatchParticipantRow` et `extract_participants` : extraction ShotsFired/ShotsHit depuis CoreStats par joueur.
- Sync engine : `_insert_participant_rows` inclut shots_fired, shots_hit.
- Backfill `--participants-shots` et `--force-participants-shots` (sélection, UPDATE par participant, `participants_shots_updated`).
- Test `test_participants_shots_extracted` (extract_participants).

**Sprint 3** :
- CLAUDE.md : exemples de commandes backfill shots.
- data_lineage.md : origine `shots_fired` / `shots_hit` (API → match_stats, match_participants).
- thought_log : cette entrée.

**Fichiers modifiés** : src/data/sync/engine.py, src/data/sync/models.py, src/data/sync/transformers.py, scripts/backfill_data.py, tests/test_sync_engine.py, tests/test_sync_performance_score.py, CLAUDE.md, .ai/data_lineage.md, .ai/thought_log.md.

---

### [2026-02-07] - Fix association médias : capture_end_utc + tolérance 20 min

**Statut** : Terminé

**Problème** : Des captures du joueur (ex. JGtm, 41 captures dans son dossier) restaient en « Sans correspondance » alors qu'elles proviennent toutes de ses matchs.

**Cause** : L'association utilisait `COALESCE(mtime_paris_epoch, mtime)` — le mtime du fichier peut être modifié par copie/sync Xbox→PC, OneDrive, etc. Ce n'est pas le moment réel de la capture.

**Correction** :
- Utiliser `COALESCE(epoch(capture_end_utc), mtime_paris_epoch, mtime)` : `capture_end_utc` = EXIF DateTimeOriginal (images) ou mtime-duration (vidéos) = moment réel de la capture.
- Tolérance par défaut passée de 5 à 20 min (délais sync Xbox, upload, etc.).

**Fichiers modifiés** : src/data/media_indexer.py.

---

### [2026-02-07] - Correctif dossier captures par joueur (MEDIA_CAPTURES_PER_PLAYER_PLAN)

**Statut** : Implémenté

**Objectif** : Dossier par joueur (`base_dir/{gamertag}/`), association mono-DB, affichage cross-DB pour partage par match_id.

**Réalisations** :
- **Paramètres** : `media_captures_base_dir` dans AppSettings, migration depuis media_screens_dir/media_videos_dir (parent commun). UI Paramètres : un seul champ « Dossier de base des captures », bouton « Réinitialiser l'index médias ».
- **Scan** : `scan_and_index(player_captures_dir=...)` accepte un dossier joueur unique (images + vidéos). Fallback legacy : videos_dir + screens_dir.
- **Association** : mono-DB uniquement. Une seule ligne (media_path, match_id, xuid) avec xuid = propriétaire de la DB. Suppression de `_backfill_media_associations_missing_xuids`.
- **load_media_for_ui** : cross-DB. « Mes captures » = DB courante ; « Captures de XXX » = médias des autres DB dont match_id dans match_stats de la DB courante. Une seule ligne par média (priorité mine > teammate > unassigned).
- **Indexation** : au démarrage, indexe tous les joueurs ayant base_dir/gamertag. Fallback legacy si base_dir vide.
- **Scripts** : `index_media.py` (--gamertag, --all), `reset_media_db.py` (--gamertag, --all).

**Fichiers modifiés** : src/ui/settings.py, src/ui/pages/settings.py, src/data/media_indexer.py, streamlit_app.py, scripts/index_media.py, scripts/reset_media_db.py (nouveau).

---

### [2026-02-07] - Correction association médias (onglet Médias)

**Statut** : Terminé

**Problème** : Sur le profil d’un joueur (ex. JGtm), les médias apparaissaient parfois tous sous « Captures de MAdina », parfois sous « Captures de Chocoboflor », sans stabilité. Les captures proviennent pourtant de matchs où le joueur du profil a joué (au minimum).

**Causes identifiées** :
1. **Association** : On parcourait les BDD joueurs dans un ordre non déterministe (`iterdir()`). Pour chaque média on associait le « meilleur » match **par BDD** puis on insérait une seule ligne (celle du premier joueur trouvé). Résultat : un seul xuid par média, dépendant de l’ordre des dossiers.
2. **Affichage** : Une même capture pouvait avoir plusieurs lignes (une par xuid associé) ; l’UI affichait la même capture dans plusieurs sections selon l’ordre des lignes.

**Corrections** :
- **`associate_with_matches`** : Pour chaque média sans association, on collecte tous les candidats (match_id, distance) parmi **toutes** les BDD joueurs, on retient **un seul** match (distance minimale), puis on insère une ligne `(media_path, match_id, xuid)` pour **chaque** joueur dont la BDD contient ce match. Ainsi le propriétaire du profil est toujours associé s’il a ce match. Ordre des BDD rendu déterministe : `sorted(iterdir())` et `_get_all_player_dbs_current_first()` pour prioriser la BDD courante.
- **Backfill** : `_backfill_media_associations_missing_xuids()` complète les associations existantes en ajoutant les xuid manquants pour chaque `(media_path, match_id)` (autres joueurs ayant ce match).
- **`load_media_for_ui`** : Une seule ligne par média : priorité section « mine » > « teammate » > « unassigned », puis tri stable par gamertag. Chaque capture n’apparaît plus que dans une seule section.

**Fichiers modifiés** : src/data/media_indexer.py, .ai/thought_log.md.

---

### [2026-02-07] - ✅ Sprints Médias restants (S1–S3 déjà livrés, S6 intégration)

**Statut** : Terminé

**Constat** : Sprints 1, 2, 3 du plan MEDIA_TAB_IMPLEMENTATION_PLAN étaient déjà implémentés et testés (voir entrées précédentes thought_log). Sprint 6 (Intégration et réglages) complété.

**Sprint 6 réalisations** :
- Scan delta au démarrage déjà en place (_background_media_indexing, thread daemon).
- Gestion cas limites : os.walk protégé par try/except OSError (dossiers inaccessibles / réseau) ; erreurs métadonnées par fichier ne bloquent pas le scan.
- Documentation : data_lineage.md (flux 5 « Dossiers médias → DuckDB »), project_map.md (media_indexer, tables media_*), MEDIA_TAB_IMPLEMENTATION_PLAN (tous sprints marqués livrés).
- media_library.py : note en en-tête indiquant que l’onglet principal est « Médias » (media_tab.py), ce module conservé pour compatibilité.

**Fichiers modifiés** : src/data/media_indexer.py, .ai/data_lineage.md, .ai/project_map.md, .ai/features/MEDIA_TAB_IMPLEMENTATION_PLAN.md, src/ui/pages/media_library.py, .ai/thought_log.md.

---

### [2026-02-07] - ✅ Stockage sessions (session_id / session_label)

**Statut** : Terminé

**Réalisations** :
- Sprint 1 : Schéma `session_id`, `session_label` dans `match_stats`, constante `session_stability_hours = 4.0`, migration dans `engine.py`
- Sprint 2 : `src/data/sessions_backfill.py` (get_friends_xuids_for_backfill), script `scripts/backfill_sessions.py` (--all, --force, --dry-run)
- Sprint 3 : Lecture hybride dans `cached_compute_sessions_db` (données stockées si tous matchs ≥ 4h et session_id présent, sinon recalcul)
- Sprint 4 : Suppression slider gap_minutes, valeur fixe 120, passage de `friends_tuple` au cache
- Sprint 5 : Doc CLAUDE.md, DATA_SESSIONS.md, SESSIONS_STOCKAGE_PLAN.md

**Fichiers modifiés** : src/config.py, src/data/sync/engine.py, src/data/sessions_backfill.py, src/ui/cache.py, src/app/filters_render.py, src/app/filters.py, page_router.py, teammates.py, streamlit_app.py. Backfill sessions intégré dans scripts/backfill_data.py (--sessions, --force-sessions) ; script backfill_sessions.py supprimé.

---

### [2026-02-07] - ✅ Sprint 3 Médias : Thumbnails (vidéos + images)

**Statut** : Terminé

**Réalisations** :
- Vidéos : GIF animé via ffmpeg (scripts/generate_thumbnails), stockage dans videos_dir/thumbs/
- Images : miniatures dédiées via PIL (redimensionnement max 320px), stockage dans screens_dir/thumbs/
- generate_thumbnails_for_new(videos_dir, screens_dir) — étendu pour vidéos ET images
- Gestion erreurs : ffmpeg absent → skip vidéos sans bloquer ; PIL absent → skip images
- Intégration streamlit : passe videos_dir et screens_dir
- 4 nouveaux tests : generate_image_thumbnails, no_ffmpeg_skips, empty_dirs, get_image_thumbnail_path
- Exécution pytest : 18 passed

**Fichiers modifiés** : src/data/media_indexer.py, streamlit_app.py, tests/test_media_indexer.py

---

### [2026-02-07] - ✅ Sprint 2 Médias : Association capture ↔ match (multi-joueurs)

**Statut** : Terminé

**Réalisations** :
- Algorithme déjà implémenté en Sprint 1 : fenêtre temporelle, match le plus proche, map_id/map_name
- Parcours de toutes les BDD joueurs (_get_all_player_dbs), stockage dans BDD du joueur actuel
- 4 nouveaux tests Sprint 2 : closest_match, multi_players, map_id_map_name, search_all_player_dbs
- Exécution pytest : 14 passed (10 Sprint 1 + 4 Sprint 2)

**Fichiers modifiés** : tests/test_media_indexer.py

---

### [2026-02-07] - ✅ Sprint 1 Médias : Fondations BDD et scan delta

**Statut** : Terminé

**Réalisations** :
- Schéma `media_files` : capture_start_utc, capture_end_utc, duration_seconds, title, status (active/deleted)
- Schéma `media_match_associations` : map_id, map_name
- Module `media_indexer.py` réécrit : scan delta, métadonnées (ffprobe vidéos, EXIF images), status='deleted' pour fichiers absents
- Migration pour tables existantes (ajout colonnes, mtime_paris_epoch, status)
- Tests : 10 tests créés et exécutés (pytest tests/test_media_indexer.py -v) — 10 passed

**Fichiers modifiés** : src/data/media_indexer.py, tests/test_media_indexer.py

---

### [2026-02-07] - 📋 Planification onglet « Médias » (remplace Bibliothèque médias)

**Statut** : Planification terminée (v2 – décisions validées + sprints)

**Contexte** :
Refonte complète à partir de zéro de l'onglet "Bibliothèque de médias" → nouvel onglet "Médias". Aucune réutilisation du code existant (UI/UX chaotique et inacceptable).

**Document** : `.ai/features/MEDIA_TAB_IMPLEMENTATION_PLAN.md`

**Décisions validées** :
- Orphelines : si pas de match chez l'utilisateur → chercher dans BDD des autres joueurs ; "Sans correspondance" = aucune correspondance trouvée nulle part.
- Multi-matchs : associer au match le plus proche.
- Fichiers supprimés : marquer `deleted` en BDD, ne pas afficher.
- Lightbox HTML pour consultation des médias.
- Composant HTML/JS pour animation au survol.
- Images : générer miniature dédiée (plus rapide).
- Sous-dossiers : scan récursif ; NAS prévu, latences mineures.

**Sprints prévus** : 1 Fondations BDD / 2 Association match multi-joueurs / 3 Thumbnails / 4 Composants UI (thumbnail + lightbox) / 5 Page Médias / 6 Intégration. Total estimé : 10–15 jours.

---

### [2026-02-06] - ✅ Radar participation unifié : implémentation + raffinements

**Statut** : ✅ **Terminé**

**Contexte** :
Refonte de la section "Participation au match" : un seul radar à 6 axes, réutilisable.

**Réalisations** :
- `src/visualization/participation_radar.py` : `RADAR_THRESHOLDS`, `RADAR_AXIS_LINES`, `compute_participation_profile()`, `compute_global_radar_thresholds()`, `get_radar_thresholds()`
- `src/ui/components/radar_chart.py` : `create_participation_profile_radar()` (thème Halo)
- `src/ui/pages/match_view_participation.py` : radar + légende sur même rangée (2/3 + 1/3)
- `src/ui/pages/teammates.py` : Complémentarité avec radar unifié
- `src/ui/pages/session_compare.py` : Comparaison sessions migrée
- `tests/test_participation_radar.py` : tests unitaires

**Raffinements** : Seuils globaux (meilleur match hors Firefight/BTB, facteur 0.85) ; Survie = mélange morts/min + durée vie moy (50/50) ; Légende des axes à droite du radar ; Thème sombre cohérent.

**Document** : `.ai/features/RADAR_PARTICIPATION_UNIFIE_PLAN.md`

---

### [2026-02-06] - ✅ Sprint 3 TERMINÉ : Migration SQLite → DuckDB Complète

**Statut** : ✅ **TERMINÉ** - Toutes les tâches du sprint complétées

**Contexte** :
Éliminer toutes les références SQLite du code applicatif (hors scripts de migration).

**RÉALISATIONS** :

#### Modifications principales
- ✅ `src/db/connection.py` : Réécrit - DuckDB uniquement, `SQLiteForbiddenError` si `.db` fourni
- ✅ `scripts/sync.py` : Supprimé sqlite3, _refuse_sqlite_path(), branches SQLite (rebuild_cache, etc.)
- ✅ `src/db/loaders.py` : has_table() utilise uniquement DuckDB (information_schema), refuse .db
- ✅ `src/ui/multiplayer.py` : Supprimé _get_sqlite_connection(), branches SQLite
- ✅ `src/ui/sync.py` : Métadonnées vides pour .db (au lieu d'appeler get_sync_metadata)

#### Scripts utilitaires
- ✅ `validate_refdata_integrity.py` : sqlite_master → information_schema
- ✅ `migrate_game_variant_category.py` : sqlite_master → information_schema
- ✅ `migrate_add_columns.py` : sqlite_master → information_schema, PRAGMA → information_schema.columns

#### Tests
- ✅ `test_cache_integrity.py` : Skip (tests legacy SQLite MatchCache)
- ✅ `test_connection_duckdb.py` : Nouveau - SQLiteForbiddenError, get_connection DuckDB

#### Documentation
- ✅ `recover_from_sqlite.py`, `migrate_player_to_duckdb.py` : En-tête "migration only"

**Validation** : `pytest tests/ -v` (nécessite `pip install -e ".[dev]"`)

---

### [2026-02-06] - ✅ Sprint 2 TERMINÉ : Logique Sessions (teammates_signature)

**Statut** : ✅ **TERMINÉ** - Toutes les tâches complétées

**Contexte** :
Sprint 2 pour améliorer la détection des sessions avec prise en compte des changements de coéquipiers (teammates_signature).

**RÉALISATIONS** :

#### Modifications
- ✅ `src/analysis/sessions.py` :
  - NULL traité comme valeur distincte (évite fusionner A, NULL, B en une session)
  - Premier match forcé à session_id=0 (correctif bug Polars)
  - Version Pandas : même logique NULL avec fillna sentinelle
- ✅ `scripts/backfill_teammates_signature.py` : Existant, utilise DuckDB uniquement
- ✅ `src/data/sync/transformers.py` : compute_teammates_signature vérifié (déjà correct)

#### Tests créés/étendus
- ✅ `tests/test_sessions_advanced.py` : +3 tests (NULL, premier match, cohérence)
- ✅ `tests/test_sessions_teammates.py` : Nouveau (7 scénarios coéquipiers)
- ✅ `tests/test_transformers_teammates.py` : Nouveau (9 tests compute_teammates_signature)

#### Documentation
- ✅ `.ai/DATA_SESSIONS.md` : Guide logique sessions + teammates_signature

**Validation** : Exécuter `pytest tests/ -v` dans un environnement avec `pip install -e ".[dev]"`.

---

### [2026-02-06] - ✅ Sprint 1 TERMINÉ : Données Manquantes (Discovery UGC + metadata.duckdb)

**Statut** : ✅ **TERMINÉ** - Toutes les tâches complétées

**Contexte** :
Sprint 1 pour restaurer l'enregistrement des noms de cartes, modes, playlists et autres métadonnées manquantes. Les colonnes `playlist_name`, `map_name`, `pair_name`, `game_variant_name` étaient NULL car Discovery UGC n'était jamais appelé et metadata.duckdb était absent.

**RÉALISATIONS** :

#### Composants créés
- ✅ `src/data/sync/metadata_resolver.py` : Classe MetadataResolver pour résoudre les noms depuis metadata.duckdb
- ✅ `scripts/populate_metadata_from_discovery.py` : Script pour créer/peupler metadata.duckdb depuis Discovery UGC
- ✅ `scripts/backfill_metadata.py` : Script pour backfill les métadonnées dans match_stats existants
- ✅ `scripts/validate_sprint1_metadata.py` : Script de validation manuelle

#### Tests créés
- ✅ `tests/test_metadata_resolver.py` : 15 tests unitaires pour MetadataResolver
- ✅ `tests/test_transformers_metadata.py` : 7 tests pour transformers avec métadonnées
- ✅ `tests/integration/test_metadata_resolution.py` : 6 tests d'intégration end-to-end

#### Documentation
- ✅ `docs/METADATA_RESOLUTION.md` : Guide complet de résolution métadonnées + troubleshooting

#### Modifications
- ✅ `src/data/sync/transformers.py` : Mis à jour pour utiliser le nouveau MetadataResolver
- ✅ `.ai/CONSOLIDATED_AUDITS_AND_ROADMAP.md` : Sprint 1 marqué comme terminé

**Architecture de résolution** :
1. **Priorité 1** : PublicName depuis Discovery UGC API (enrichissement en temps réel via `enrich_match_info_with_assets()`)
2. **Priorité 2** : PublicName depuis metadata.duckdb (cache local via `MetadataResolver`)
3. **Priorité 3** : Fallback sur asset_id (UUID si aucun nom trouvé)

**Utilisation** :
```bash
# Créer/populer metadata.duckdb
python scripts/populate_metadata_from_discovery.py --all-players

# Backfill les métadonnées existantes
python scripts/backfill_metadata.py --player JGtm
```

**Note** : Les tests nécessitent DuckDB installé. Validation manuelle disponible via `scripts/validate_sprint1_metadata.py`.

---

### [2026-02-05] - ✅ Sprint Gamertag/Roster : IMPLÉMENTATION COMPLÈTE

**Statut** : ✅ Toutes les phases implémentées

**Contexte** :
Sprint "Correction Gamertags, Roster et Coéquipiers" implémenté pour corriger les gamertags corrompus, les rosters cassés, et la détection des coéquipiers.

**PHASES COMPLÉTÉES** :

#### Phase 1 : Création table `match_participants`
- ✅ DDL dans `src/data/sync/engine.py`
- ✅ `MatchParticipantRow` dataclass dans `src/data/sync/models.py`
- ✅ `extract_participants()` dans `src/data/sync/transformers.py`
- ✅ Intégration dans `_process_single_match()` du sync engine

#### Phase 2 : Correction requêtes coéquipiers
- ✅ `load_same_team_match_ids()` réécrit pour utiliser `match_participants`
- ✅ Fallback sur l'ancienne méthode si table manquante

#### Phase 3 : CLI `--participants` dans backfill
- ✅ Arguments `--participants` et `--force-participants`
- ✅ Fonction `_insert_participant_rows()` dans `backfill_data.py`
- ✅ Intégration complète dans le flux de backfill

#### Phase 4 : Résolution gamertag centralisée
- ✅ `resolve_gamertag()` dans `duckdb_repo.py` (cascade : match_participants → xuid_aliases → teammates_aggregate → highlight_events)
- ✅ `resolve_gamertags_batch()` pour les traitements par lot
- ✅ `load_match_rosters()` utilise `resolve_gamertags_batch`
- ✅ `cached_load_match_player_gamertags()` dans `cache.py` utilise `resolve_gamertags_batch`

#### Phase 6 : Backfill killer_victim_pairs
- ✅ Arguments `--killer-victim`
- ✅ Fonction `_backfill_killer_victim_pairs()` dans `backfill_data.py`
- ✅ Utilise l'algorithme de pairing de `src/analysis/killer_victim.py`

**Commandes disponibles** :
```bash
# Backfill participants (nouveau)
python scripts/backfill_data.py --player JGtm --participants

# Backfill paires killer/victim
python scripts/backfill_data.py --player JGtm --killer-victim

# Backfill complet (inclut participants + killer_victim)
python scripts/backfill_data.py --player JGtm --all-data
```

---

### [2026-02-05] - 📊 Sprint Gamertag/Roster : Documentation killer_victim_pairs

**Statut** : ✅ Documentation complète créée

**Contexte** :
L'utilisateur demande où sont stockées les données "qui a tué qui" avec timestamps.

**RÉSULTAT DE L'ANALYSE** :

1. **Table `killer_victim_pairs`** : Existe mais est **VIDE** (0 lignes)
   - Schéma : `killer_xuid`, `victim_xuid`, `time_ms`, etc.
   - Destinée à stocker les paires killer→victim

2. **Source de données** : `highlight_events`
   - Events `kill` : contiennent le killer (xuid, gamertag, time_ms)
   - Events `death` : contiennent la victime (xuid, gamertag, time_ms)
   - Pairing possible par timestamp (±5ms) :
     ```
     kill @ 40528ms (quisqueyano159) → death @ 40529ms (Ale8037)
     ```

3. **Modules existants** (bien documentés, mais données manquantes) :
   - `src/analysis/killer_victim.py` : Algorithme de pairing + fonctions Polars
   - `src/visualization/antagonist_charts.py` : Graphiques Plotly (non intégrés UI)
   - `scripts/populate_antagonists.py` : Cherche DB SQLite legacy (obsolète)

**Actions prises** :
- ✅ Sprint mis à jour avec Phase 6 (backfill killer_victim_pairs)
- ✅ Sprint mis à jour avec Phase 7 (intégration graphiques UI)
- ✅ Documentation IA créée : `.ai/DATA_KILLER_VICTIM.md`
- ✅ `project_map.md` mis à jour avec les tables manquantes

**Commandes de backfill** (à implémenter) :
```bash
python scripts/backfill_data.py --player JGtm --killer-victim
python scripts/populate_antagonists.py --gamertag JGtm --force
```

---

### [2026-02-05] - 🔴 CRITIQUE : Données Manquantes en BDD — DIAGNOSTIC TERMINÉ

**Statut** : ✅ **CAUSE RACINE IDENTIFIÉE** - Prêt pour la phase correction

**Contexte** :
L'utilisateur signale que plusieurs données ne sont plus enregistrées en BDD :
1. Noms des cartes, modes et playlists (`playlist_name`, `map_name`, `pair_name`, `game_variant_name` sont NULL)
2. Noms des joueurs par match non récupérés correctement
3. Joueurs non affectés à l'équipe adverse
4. Nom de l'équipe adverse non récupéré
5. Valeurs "attendues" pour frags et morts (`kills_expected`, `deaths_expected`, `assists_expected` sont NULL)

**CAUSES CONFIRMÉES** :
1. **Discovery UGC jamais appelé** : `client.get_asset()` n'est pas utilisé dans `_process_single_match()`. L'option `with_assets=True` existe mais n'est jamais vérifiée.
2. **metadata.duckdb absent** : Le dossier `data/warehouse/` n'existe pas → `create_metadata_resolver()` retourne `None` → aucune résolution depuis référentiels.
3. **Fallback sur IDs** : Sans PublicName (API) ni metadata_resolver, les noms deviennent les UUID.
4. **StatPerformances** : À vérifier avec logs si l'API skill renvoie la structure attendue.

**Actions prises** :
- ✅ Diagnostic complet documenté dans `.ai/explore/CRITICAL_DATA_MISSING_EXPLORATION.md`
- ✅ Script de vérification SQL créé : `scripts/diagnostic_critical_data.py`
- ✅ Proposition d'implémentation Discovery UGC (référence spnkr_import_db.py)

**Prochaines étapes (phase correction)** :
1. Implémenter les appels Discovery UGC dans `_process_single_match()` quand `options.with_assets=True`
2. Enrichir `MatchInfo` avec les PublicName avant de passer à `transform_match_stats()`

---

### [2026-02-05] - 🔴 CORRECTION CRITIQUE : Chargement des stats coéquipiers (Multi-DB)

**Statut** : ✅ **CORRIGÉ** - Ne plus refaire cette erreur !

**Contexte** :
L'onglet "Mes coéquipiers" affichait les mêmes valeurs pour tous les joueurs (ex: JGtm, Madina97294, Chocoboflor avaient tous 1.02, 1.38, 0.48 en stats/min).

**CAUSE RACINE** :
```python
# ❌ CODE INCORRECT (le xuid est IGNORÉ pour DuckDB v4)
f1_df = load_df_optimized(db_path, f1_xuid, db_key=db_key)
f2_df = load_df_optimized(db_path, f2_xuid, db_key=db_key)
# → Charge TOUJOURS depuis la DB du joueur principal, pas celle du coéquipier !
```

**SOLUTION** :
```python
# ✅ CODE CORRECT - Charger depuis la DB de chaque coéquipier
f1_df = _load_teammate_stats_from_own_db(f1_gamertag, match_ids, db_path)
f2_df = _load_teammate_stats_from_own_db(f2_gamertag, match_ids, db_path)
# → Construit le chemin data/players/{gamertag}/stats.duckdb
```

**RÈGLE À RETENIR** :

| ❌ NE JAMAIS FAIRE | ✅ TOUJOURS FAIRE |
|-------------------|-------------------|
| `load_df_optimized(db_path, autre_xuid)` | `_load_teammate_stats_from_own_db(gamertag, match_ids, db_path)` |
| Passer le xuid d'un autre joueur | Construire le chemin vers sa DB |

**Pourquoi le xuid est ignoré ?**
- Dans l'architecture DuckDB v4, chaque joueur a sa propre DB : `data/players/{gamertag}/stats.duckdb`
- `load_df_optimized()` charge depuis `db_path` et ignore le paramètre `xuid`
- Pour charger les stats d'un coéquipier, il faut charger depuis **SA** DB

**Fichiers modifiés** :
- `src/ui/pages/teammates.py` : Ajout de `_load_teammate_stats_from_own_db()`, correction de 3 appels
- `CLAUDE.md` : Ajout de la documentation sur l'architecture multi-joueurs

**Mémo rapide** :
```
Pour afficher les stats d'un coéquipier sur des matchs communs :
1. Identifier les match_id communs (via teammates_aggregate ou filtres)
2. Obtenir le gamertag du coéquipier (display_name_from_xuid)
3. Charger depuis data/players/{gamertag}/stats.duckdb
4. Filtrer sur les match_id communs
```

**Rappel SQLite** : **PROSCRIT** - Aucun fallback SQLite dans le projet.

---

### [2026-02-03 PM] - 🔴 ANALYSE CRITIQUE : 12 Régressions majeures identifiées

**Statut** : ⚠️ **ANALYSE COMPLÈTE** - Plan de correction en 5 sprints créé

**Contexte** : L'utilisateur a signalé de nombreuses régressions après les dernières modifications.

**Régressions identifiées** :

| # | Symptôme | Cause racine |
|---|----------|--------------|
| 1 | Dernier match : 17 jan 2026 | Données non synchronisées ou cache obsolète |
| 2 | Précision : nan% | Colonne `accuracy` NULL dans match_stats |
| 3 | Premier kill/mort ne fonctionne pas | Table highlight_events vide ou mal requêtée |
| 4-5 | Distributions vides (précision, FDA) | Dérivé de #2 (pas de données accuracy) |
| 6 | **Score de performance non disponible** | **OUBLI D'IMPLÉMENTATION** dans `timeseries.py` |
| 7 | Roster indisponible | `cached_load_match_rosters()` retourne `None` pour DuckDB v4 |
| 8, 11 | Médailles indisponibles | Table medals_earned vide |
| 9-10 | Médias non associés + doublons | start_time NULL + double message |
| 12 | Page coéquipiers vide | Fonctions cache.py retournent vide pour DuckDB v4 |

**Découverte importante sur le score de performance** :
- `timeseries.py` vérifie si `performance_score` existe mais **ne la calcule jamais**
- `match_history.py` et `session_compare.py` appellent `compute_performance_series()` ✅
- Correction simple : ajouter l'appel à `compute_performance_series()` dans `timeseries.py`

**Cause racine principale** :
```python
# src/ui/cache.py - PROBLÈME CRITIQUE
if _is_duckdb_v4_path(db_path):
    return []  # ❌ Retourne toujours vide au lieu de charger les données
```

**Fonctions impactées** :
- `cached_same_team_match_ids_with_friend()` → `()`
- `cached_query_matches_with_friend()` → `[]`
- `cached_load_match_rosters()` → `None`
- `cached_load_friends()` → `[]`

**Documents créés** :
- `.ai/diagnostics/REGRESSIONS_ANALYSIS_2026-02-03.md` - Analyse complète
- `.ai/sprints/SPRINT_REGRESSIONS_FIX.md` - Plan de correction en 5 sprints

**Ordre de priorité** :
1. Sprint 2 : Diagnostic des données DuckDB
2. Sprint 1 : Correction cache.py
3. Sprint 4 : Page coéquipiers
4. Sprint 3 : Médias
5. Sprint 5 : Tests

**Prochaine action** : Exécuter le diagnostic pour vérifier l'état des données avant correction.

---

### [2026-02-03] - SPRINTS 8 & 9 TERMINÉS : Backfill + Migration + Tests

**Statut** : ✅ **SUCCÈS** - Infrastructure complète pour killer_victim_pairs

**Sprint 8 : Backfill et Migration**

| Tâche | Fichier | Description |
|-------|---------|-------------|
| 8.0 | `src/data/sync/engine.py` | Schémas DuckDB pour `killer_victim_pairs` et `personal_score_awards` |
| 8.1 | `scripts/backfill_killer_victim_pairs.py` | Calcule les paires depuis highlight_events |
| 8.3 | `scripts/migrate_game_variant_category.py` | Ajoute colonne manquante à match_stats |
| 8.4 | `scripts/validate_refdata_integrity.py` | Vérifie cohérence des données |
| 8.5 | `docs/MIGRATION_REFDATA.md` | Guide de migration complet |

**Sprint 9 : Optimisation et Tests**

| Tâche | Fichier | Description |
|-------|---------|-------------|
| 9.1 | `src/data/repositories/duckdb_repo.py` | 4 méthodes Polars ajoutées |
| 9.2 | `tests/integration/test_refdata_antagonists.py` | 15+ tests d'intégration |
| 9.3 | `scripts/benchmark_polars.py` | Benchmark Polars vs Pandas |

**Nouvelles tables DuckDB** :

```sql
-- killer_victim_pairs : Paires killer→victim par match
CREATE TABLE killer_victim_pairs (
    id INTEGER PRIMARY KEY,
    match_id VARCHAR NOT NULL,
    killer_xuid VARCHAR NOT NULL,
    killer_gamertag VARCHAR,
    victim_xuid VARCHAR NOT NULL,
    victim_gamertag VARCHAR,
    kill_count INTEGER DEFAULT 1,
    time_ms INTEGER,
    is_validated BOOLEAN DEFAULT FALSE
);

-- personal_score_awards : Décomposition score (REPORTÉ - API non dispo)
```

**Nouvelles méthodes Repository** :

```python
repo.load_killer_victim_pairs_as_polars(match_id="...")
repo.load_match_stats_as_polars(limit=100)
repo.get_antagonists_summary_polars(top_n=20)
repo.has_killer_victim_pairs()
```

**Note** : Sprint 8.2 (backfill personal_score_awards) reporté car l'API ne fournit pas ces données.

**Commandes de migration** :

```bash
# 1. Migrer le schéma
python scripts/migrate_game_variant_category.py --all

# 2. Backfill les paires
python scripts/backfill_killer_victim_pairs.py --all

# 3. Valider
python scripts/validate_refdata_integrity.py --all
```

---

### [2026-02-03] - SPRINTS 6 & 7 TERMINÉS : Performance Cumulée + Page Objectifs

**Statut** : ✅ **SUCCÈS** - 50+ tests passent (24 Sprint 6 + 26 Sprint 4)

**Sprint 6 : Performance Cumulée avec Polars**

Module créé : `src/analysis/cumulative.py`

| Fonction | Description |
|----------|-------------|
| `compute_cumulative_net_score_series_polars()` | Série cumulative net score (kills - deaths) |
| `compute_cumulative_kd_series_polars()` | Série cumulative K/D ratio |
| `compute_cumulative_kda_series_polars()` | Série cumulative KDA |
| `compute_cumulative_objective_score_series_polars()` | Série cumulative score objectifs |
| `compute_cumulative_metrics_polars()` | Métriques agrégées finales |
| `compute_rolling_kd_polars()` | K/D glissant sur N matchs |
| `compute_session_trend_polars()` | Tendance de session (amélioration/déclin) |

Module créé : `src/visualization/performance.py`

| Graphique | Description |
|-----------|-------------|
| `plot_cumulative_net_score()` | Courbe net score avec barres par match |
| `plot_cumulative_kd()` | Courbe K/D cumulé avec ligne cible |
| `plot_rolling_kd()` | K/D glissant avec K/D par match |
| `plot_session_trend()` | Indicateurs de tendance (début/fin/delta) |
| `plot_cumulative_comparison()` | Comparaison deux sessions superposées |
| `create_cumulative_metrics_indicator()` | Indicateurs compacts métriques |

**Sprint 7 : Page Analyse Objectifs**

Page créée : `src/ui/pages/objective_analysis.py`

Sections de la page :
1. Vue d'ensemble avec métriques (objectifs, kills, assists, ratio)
2. Profil du joueur (Slayer/Support/Polyvalent)
3. Graphiques : scatter objectifs vs kills, répartition, tendances
4. Analyse des assistances avec camembert
5. Top awards par catégorie
6. Conseils personnalisés

Module créé : `src/visualization/objective_charts.py`

| Graphique | Description |
|-----------|-------------|
| `plot_objective_vs_kills_scatter()` | Scatter correlation + tendance |
| `plot_objective_breakdown_bars()` | Barres répartition par catégorie |
| `plot_top_players_objective_bars()` | Top N joueurs horizontal |
| `plot_objective_ratio_gauge()` | Gauge ratio objectifs/total |
| `plot_assist_breakdown_pie()` | Camembert types d'assistances |
| `plot_objective_trend_over_time()` | Évolution dans le temps |

Nouvelles fonctions dans `src/analysis/objective_participation.py` :

| Fonction | Description |
|----------|-------------|
| `compute_objective_kill_ratio_polars()` | Ratio objectifs/kills par match |
| `compute_player_profile_polars()` | Déterminer profil joueur |
| `compute_objective_efficiency_polars()` | Efficacité objective |

**Corrections** :
- `HALO_COLORS.get()` → `HALO_COLORS.green` (attribut vs dict)
- `THEME_COLORS.get("text")` → `THEME_COLORS.text_primary`
- `pl.count()` → `pl.len()` (dépréciation Polars)

**Tests** : 50 passent (24 Sprint 6 + 26 Sprint 4)

**Prochains sprints** : 8 (Backfill), 9 (Optimisation)

---

### [2026-02-03] - SPRINTS 4 & 5 TERMINÉS : Analyses et Visualisations

**Statut** : ✅ **SUCCÈS** - 46 tests passent

**Sprint 4 : Analyses Score Personnel avec Polars**

Module créé : `src/analysis/objective_participation.py`

| Fonction | Description |
|----------|-------------|
| `compute_objective_participation_score_polars()` | Score de participation (objectifs, assists, kills) |
| `rank_players_by_objective_contribution_polars()` | Classement des joueurs par contribution |
| `compute_assist_breakdown_polars()` | Décomposition des assistances |
| `compute_objective_summary_by_match_polars()` | Résumé par match |
| `compute_award_frequency_polars()` | Fréquence des awards |

Dataclasses :
- `ObjectiveParticipationResult` : Scores et ratios
- `AssistBreakdownResult` : Décomposition des assists
- `PlayerObjectiveRanking` : Classement joueur

**Sprint 5 : Visualisations Antagonistes**

Module créé : `src/visualization/antagonist_charts.py`

| Graphique | Description |
|-----------|-------------|
| `plot_killer_victim_stacked_bars()` | Barres empilées kills/deaths par joueur |
| `plot_kd_timeseries()` | K/D par minute avec cumul |
| `plot_duel_history()` | Historique des duels entre 2 joueurs |
| `plot_nemesis_victim_summary()` | Indicateurs némésis/souffre-douleur |
| `plot_killer_victim_heatmap()` | Heatmap matrice killer→victim |
| `plot_top_antagonists_bars()` | Top némésis et victimes |
| `create_kd_indicator()` | Indicateur K/D simple |

**Corrections** :
- Ajout des fonctions Polars manquantes dans `killer_victim.py`
- Correction d'un test avec assertions incorrectes (`victim_times_killed`)

**Tests** : 46 passent (26 Sprint 4 + 20 Sprint 3)

**Prochains sprints** : 6 (Performance Cumulée), 7 (Analyses Avancées)

---

### [2026-02-02] - RÉSULTATS: Investigation Bit-Shifted Binary Chunks (v2)

**Statut** : ✅ **SUCCÈS PARTIEL** - Events extraits, Weapon ID non trouvé

**Contexte** :
Investigation approfondie des film chunks avec extraction bit-shifted selon la méthode Den Delimarsky.

**Résultats validés** :

| Test | Résultat | Détails |
|------|----------|---------|
| Structure Den Delimarsky | ✅ VALIDÉE | 72+ bytes par event |
| Event types (10/20/50) | ✅ VALIDÉS | mode/death/kill confirmés |
| Timestamp format | ✅ **BIG ENDIAN** | Pas Little Endian comme supposé |
| Corrélation théâtre | ✅ **100%** | 14/14 kills matchés (< 2.5s delta) |

**Résultat négatif** :

| Test | Résultat | Détails |
|------|----------|---------|
| Weapon ID dans extra bytes | ❌ ÉCHEC | Pattern `0x2ee0` constant pour TOUTES les armes |

**Découverte clé** : Le timestamp est en **Big Endian**, pas Little Endian !

```python
# FAUX
timestamp = struct.unpack('<I', ts_bytes)[0]

# CORRECT
timestamp = struct.unpack('>I', ts_bytes)[0]
```

**Livrables** :
- `scripts/analyze_chunks_bitshifted.py` : Script d'analyse complet
- `.ai/research/BINARY_CHUNK_ANALYSIS_V2_PLAN.md` : Documentation mise à jour
- `data/investigation/chunks/189d1c23_full/` : Chunks du match Fiesta

**Conclusion** :
Les events (kills, deaths) peuvent être extraits avec timestamps précis (~1-2s).
Le weapon ID **n'est PAS encodé** dans la structure documentée par Den Delimarsky.
Le pattern `0x2ee0` trouvé précédemment n'est PAS un weapon ID mais un marker constant.

**Investigation complémentaire (Headers et Medals)** :

1. **Header (bytes 0-11)** = Identifiant JOUEUR (pas arme)
   - Chaque joueur a un header unique et constant
   - Exemple: JGtm = `4cde91e8aba1301621967cf9`

2. **Medal ID (byte 71)** = Inférence partielle possible (~7%)
   - Kill Sniper 1:04 → Medal 108 ("Snipe") ✓
   - Mais 14/15 kills n'ont pas de medal liée à l'arme

**Conclusion définitive** : Le weapon ID n'est pas disponible dans les film chunks.

**Dernière théorie (Event DEATH victime)** :
- Event DEATH de la victime analysé → Extra bytes identiques pour différentes armes
- Pas de structure killer+victim combinée
- API Match Stats vérifié → Seulement compteurs agrégés (PowerWeaponKills, MeleeKills, etc.)

**VERDICT FINAL** : Les weapon stats individuelles par kill ne sont PAS disponibles (limitation 343i).

---

### [2026-02-02] - IMPORTANT : Limites de l'API Halo Infinite (Weapon Stats)

**Statut** : ❌ **CONFIRMÉ - Les weapon breakdowns N'EXISTENT PAS dans l'API**

**Contexte** :
L'utilisateur a demandé d'obtenir les armes utilisées pour chaque kill. Après investigation approfondie, nous confirmons que cette donnée n'est pas disponible.

**Vérifications effectuées** :
1. Match Stats API (`/hi/matches/{id}/stats`) - 15 matchs testés
2. Service Record API (`/hi/players/{xuid}/matchmade/servicerecord`)
3. Blog de Den Delimarsky (référence communautaire)

**Résultat** : `CoreStats.Breakdowns.Weapons[]` **n'existe pas** dans les réponses API réelles.

**Ce qui est disponible** :
```
GrenadeKills, HeadshotKills, MeleeKills, PowerWeaponKills (compteurs agrégés uniquement)
```

**Ce qui N'EST PAS disponible** :
- Kills par type d'arme (BR75, Sidekick, etc.)
- Précision par arme
- Dégâts par arme
- Association kill → arme utilisée

**Documentation** : Voir `.ai/archive/BINARY_CHUNK_ANALYSIS_FINAL.md` section "Limites de l'API"

**Impact** : Le projet ne peut pas implémenter de statistiques par arme. Cette limitation est côté 343 Industries, pas côté LevelUp.

---

### [2026-02-02] - RÉSULTATS : Analyse binaire des Film Chunks (weapon_id)

**Statut** : ✅ **SUCCÈS - WEAPON ID TROUVÉ !**

**Découverte clé** :
- Les weapon IDs sont dans les **chunks type 3** (summary), pas type 2 (gameplay)
- Position : **bytes 74-75** (offset 72+2/72+3 dans extra_bytes)
- Format : uint16 little-endian

**Mapping confirmé** :
| Bytes | uint16 | Arme |
|-------|--------|------|
| `0x2e 0xe0` | 57390 | Sidekick |
| `0x17 0x70` | 28695 | MA40 AR |

**Validation** : Match `7f1bbf06-d54d-4434-ad80-923fcabe8b1b`
- 48 kills total (tous joueurs)
- 41 kills Sidekick (pattern `0x2e 0xe0`)
- 7 kills AR/Melee (pattern `0x17 0x70`)
- Correspond aux données fournies par l'utilisateur

---

### [2026-02-02] - ANCIENNE ANALYSE (avant découverte chunk type 3)

**Statut** : ⚠️ Échec partiel (chunks type 2 uniquement)

**Ce qui a été fait** :
1. Téléchargement des chunks binaires (27 fichiers, ~20 MB) via `refetch_film_roster.py`
2. Création de `scripts/extract_binary_events.py` - extraction via structure 72 bytes
3. Création de `scripts/analyze_binary_patterns.py` - analyse via marker 0x2D 0xC0
4. Analyse de 907 contextes marker et 378 events candidats

**Résultats** :
- **Structure roster** identifiée via marker `0x2D 0xC0` (XUID/Gamertag/métadonnées)
- **Faux positifs** massifs (~90%) dans la détection d'events
- **Timestamps aberrants** (>8h) indiquant des structures différentes dans les chunks type 2
- **Weapon_id NON TROUVÉ** dans les bytes analysés

**Conclusion** :
La structure 72 bytes documentée est pour les **chunks type 3 (summary)**, pas type 2 (gameplay).
Les chunks type 3 ne sont pas toujours présents dans les manifests.

**Pistes restantes** :
1. Trouver des matchs avec chunks type 3
2. Corréler avec weapon_stats de l'API match_stats
3. Analyser les données de replay frame-by-frame

**Livrables** :
- `.ai/research/BINARY_ANALYSIS_RESULTS.md` : Rapport complet
- `data/investigation/*.json` : Données d'analyse

---

### [2026-02-02] - RECHERCHE : Identification des armes dans les Highlight Events

**Contexte** :
Les highlight events contiennent des événements kill/death mais **l'arme utilisée n'est pas documentée**. L'utilisateur souhaite explorer les données brutes pour identifier des patterns potentiels.

**État de l'art** (source: Den Delimarsky, SPNKr) :

La structure connue d'un event fait 72 bytes :
| Offset | Taille | Contenu |
|--------|--------|---------|
| 0 | 12 | Header (inconnu) |
| 12 | 32 | Gamertag (UTF-16) |
| 44 | 15 | Padding |
| 59 | 1 | Type (10=mode, 20=death, 50=kill) |
| 60 | 4 | Timestamp (ms) |
| 64 | 3 | Padding |
| 67 | 1 | Medal marker |
| 68 | 3 | Padding |
| 71 | 1 | Medal ID |
| 72+ | ? | **BYTES NON DOCUMENTÉS** |

**Hypothèses de recherche** :
1. L'arme pourrait être dans les bytes au-delà de l'offset 72
2. L'arme pourrait être encodée dans le header (0-12 bytes)
3. L'arme pourrait être dans un event séparé corrélé par timestamp
4. Les chunks de type 2 (in-game events) pourraient contenir l'arme active

**Livrables créés** :
- `.ai/research/HIGHLIGHT_WEAPON_RESEARCH.md` : Rapport de recherche détaillé
- `scripts/analyze_highlight_binary.py` : Script d'analyse expérimentale

**Prochaines étapes** :
```bash
# Analyser les raw_json existants
python scripts/analyze_highlight_binary.py --gamertag MonGT --analyze-json

# Télécharger et analyser les chunks binaires
python scripts/analyze_highlight_binary.py --match-id <GUID> --analyze-binary

# Générer un rapport complet
python scripts/analyze_highlight_binary.py --gamertag MonGT --report
```

**Résultats de l'analyse (match 7f1bbf06)** :
- 187 events trouvés dans la DB SQLite legacy
- 6 kills par JGtm identifiés
- **AUCUN champ weapon_id** dans le JSON parsé
- Medal "Gunslinger" obtenue → confirme utilisation Sidekick
- Tous les kills ont `medal_value: 0` et `type_hint: 50` (pas de différenciation)

**Conclusion** : L'arme n'est PAS dans les données JSON parsées par SPNKr.
Il faut analyser les **bytes binaires bruts** des chunks de film.

**Plan d'action créé** : `.ai/research/BINARY_CHUNK_ANALYSIS_PLAN.md`

**Suivi** :
- [x] Recherche documentée ✅
- [x] Script d'analyse créé ✅
- [x] Analyse des raw_json ✅ (aucun champ weapon)
- [x] Plan d'analyse binaire créé ✅
- [ ] Configuration tokens API (utilisateur)
- [ ] Téléchargement chunks bruts
- [ ] Analyse binaire des bytes non documentés
- [ ] Corrélation avec armes connues (via medals)

---

### [2026-02-02] - Nettoyage colonnes objectives (19 colonnes supprimées du schéma)

**Contexte** :
Comme pour `weapon_stats`, des colonnes objectives ont été ajoutées au schéma en anticipation de données que l'API Halo Infinite ne fournit pas réellement. Ces 19 colonnes étaient toujours NULL.

**Colonnes supprimées** :

| Catégorie | Colonnes |
|-----------|----------|
| Expected | `expected_kills`, `expected_deaths` |
| Objectives | `objectives_completed` |
| Zone/Stronghold | `zone_captures`, `zone_defensive_kills`, `zone_offensive_kills`, `zone_secures`, `zone_occupation_time` |
| CTF | `ctf_flag_captures`, `ctf_flag_grabs`, `ctf_flag_returners_killed`, `ctf_flag_returns`, `ctf_flag_carriers_killed`, `ctf_time_as_carrier_seconds` |
| Oddball | `oddball_time_held_seconds`, `oddball_kills_as_carrier`, `oddball_kills_as_non_carrier` |
| Stockpile | `stockpile_seeds_deposited`, `stockpile_seeds_collected` |

**Actions réalisées** :

| Fichier | Action |
|---------|--------|
| `src/data/sync/models.py` | Supprimé 19 attributs de `MatchStatsRow` |
| `scripts/migrate_player_to_duckdb.py` | Retiré 19 colonnes du CREATE TABLE |
| `scripts/migrate_add_columns.py` | Ajouté `COLUMNS_TO_DROP` avec logique DROP COLUMN |
| `tests/test_cache_integrity.py` | Retiré références `expected_kills`/`expected_deaths` |

**Migration exécutée** :
```
Joueurs traités: 4
Colonnes ajoutées: 52 (13 × 4 joueurs)
Tables weapon_stats supprimées: 4
```

Note : Les colonnes objectives n'existaient pas encore dans les bases (elles n'avaient jamais été ajoutées via migration), donc aucune suppression de colonne n'était nécessaire.

**Schéma final match_stats** (colonnes conservées) :
```
match_id, start_time, playlist_id, playlist_name, map_id, map_name,
pair_id, pair_name, game_variant_id, game_variant_name, outcome, team_id,
rank, kills, deaths, assists, kda, accuracy, headshot_kills, max_killing_spree,
time_played_seconds, avg_life_seconds, my_team_score, enemy_team_score,
team_mmr, enemy_mmr, damage_dealt, damage_taken, shots_fired, shots_hit,
grenade_kills, melee_kills, power_weapon_kills, score, personal_score,
mode_category, is_ranked, is_firefight, left_early,
session_id, session_label, performance_score, teammates_signature,
known_teammates_count, is_with_friends, friends_xuids, created_at, updated_at
```

**Suivi** :
- [x] Modèle MatchStatsRow nettoyé ✅
- [x] Schéma CREATE TABLE nettoyé ✅
- [x] Script migration avec DROP COLUMN ✅
- [x] Audit code obsolète ✅
- [x] Migration bases existantes ✅

---

### [2026-02-02] - Tests complets des fonctions de visualisation (74 tests)

**Contexte** :
Aucun test fonctionnel n'existait pour les 27+ fonctions de visualisation. Seuls des tests d'import existaient dans `test_phase6_refactoring.py`.

**Raisonnement** :
Les graphiques sont une partie critique de l'application. Sans tests, les bugs peuvent passer inaperçus (DataFrames vides, NaN, colonnes manquantes).

**Actions réalisées** :

| Action | Détail |
|--------|--------|
| Plan créé | `.ai/test_visualizations_plan.md` — inventaire complet des 27 fonctions |
| Tests créés | `tests/test_visualizations.py` — 74 tests couvrant toutes les fonctions |
| Bugs corrigés | `radar_chart.py` ne gérait pas les listes vides (2 fonctions corrigées) |
| CI mis à jour | `.github/workflows/ci.yml` — étape dédiée aux tests de visualisation |
| Marker ajouté | `pyproject.toml` — marker `visualization` enregistré |

**Fonctions testées** :

| Module | Fonctions | Tests |
|--------|-----------|-------|
| `distributions.py` | 10 | 28 |
| `timeseries.py` | 7 | 16 |
| `maps.py` | 2 | 4 |
| `match_bars.py` | 2 | 5 |
| `trio.py` | 1 | 3 |
| `radar_chart.py` | 3 | 7 |
| `chart_annotations.py` | 2 | 5 |
| **Module imports** | 7 | 7 |
| **Total** | **27** | **74** |

**Bugs découverts et corrigés** :

| Fonction | Bug | Fix |
|----------|-----|-----|
| `create_stats_per_minute_radar()` | `max()` sur liste vide | Ajout gestion cas vide |
| `create_performance_radar()` | `max()` sur liste vide | Ajout gestion cas vide |
| `plot_timeseries()` | Ne gère pas empty DataFrame | Test accepte l'exception (à corriger plus tard) |

**Exécution** :
```bash
pytest tests/test_visualizations.py -v -m visualization
# 74 passed in 2.50s
```

**Suivi** :
- [x] Tests créés et validés ✅
- [x] CI mis à jour ✅
- [x] Bugs radar corrigés ✅
- [ ] TODO : Corriger `plot_timeseries()` pour gérer DataFrames vides proprement

---

### [2026-02-02] - PLAN : Suppression table `weapon_stats` et ajout colonnes manquantes

**Contexte** :
La table `weapon_stats` est vide et inutile. Elle était conçue pour stocker des statistiques par arme individuelle (BR, AR, Sniper, etc.), mais l'API Halo Infinite ne fournit pas ces données détaillées par arme.

Les seules données de tir disponibles via l'API sont :
- `shots_fired` (tirs totaux par match)
- `shots_hit` (tirs au but par match)
- `accuracy` (déjà calculée)

Ces données appartiennent à `match_stats`, pas à une table séparée.

**Problème identifié** :
1. Table `weapon_stats` : Vide et inutile (données par arme non disponibles)
2. Colonnes manquantes dans `match_stats` : Le modèle `MatchStatsRow` contient `shots_fired`, `shots_hit`, `damage_dealt`, etc. mais le schéma DuckDB ne les a pas

**Décision** :
Nettoyer le code et aligner le schéma avec les données réellement disponibles.

---

#### Phase 1 : Nettoyage du code `weapon_stats`

| Fichier | Action |
|---------|--------|
| `src/data/sync/models.py` | Supprimer `WeaponStatsRow` et `WeaponAggregateRow` |
| `src/data/sync/transformers.py` | Supprimer `extract_weapon_stats()`, `has_weapon_stats()`, `_find_weapon_stats_dict()` |
| `src/data/sync/__init__.py` | Retirer les exports `extract_weapon_stats`, `has_weapon_stats` |
| `src/data/repositories/duckdb_repo.py` | Supprimer méthodes `get_weapon_stats()`, `get_global_accuracy()` |
| `src/data/infrastructure/database/duckdb_engine.py` | Supprimer TODO/commentaires liés aux armes |
| `scripts/migrate_player_to_duckdb.py` | Supprimer création table `weapon_stats` |

---

#### Phase 2 : Ajout colonnes manquantes à `match_stats`

| Colonne | Type | Description |
|---------|------|-------------|
| `shots_fired` | INTEGER | Nombre total de tirs |
| `shots_hit` | INTEGER | Tirs au but |
| `damage_dealt` | FLOAT | Dégâts infligés |
| `damage_taken` | FLOAT | Dégâts reçus |
| `score` | INTEGER | Score du match |
| `personal_score` | INTEGER | Score personnel |
| `grenade_kills` | INTEGER | Kills grenade |
| `melee_kills` | INTEGER | Kills mêlée |
| `power_weapon_kills` | INTEGER | Kills armes lourdes |

**Fichiers impactés** :
- `scripts/migrate_player_to_duckdb.py` : Ajouter colonnes au CREATE TABLE

---

#### Phase 3 : Migration des données existantes

| Action | Détail |
|--------|--------|
| Script ALTER TABLE | Ajouter colonnes manquantes aux bases existantes |
| DROP TABLE weapon_stats | Supprimer la table inutile |

---

#### Résumé des fichiers à modifier

| Fichier | Suppressions | Ajouts |
|---------|--------------|--------|
| `src/data/sync/models.py` | 2 classes | - |
| `src/data/sync/transformers.py` | 3 fonctions (~150 lignes) | - |
| `src/data/sync/__init__.py` | 2 exports | - |
| `src/data/repositories/duckdb_repo.py` | 2 méthodes | - |
| `src/data/infrastructure/database/duckdb_engine.py` | Commentaires | - |
| `scripts/migrate_player_to_duckdb.py` | CREATE weapon_stats | 9 colonnes match_stats |

**Suivi** :
- [x] Phase 1 : Nettoyage code weapon_stats ✅ (2026-02-02)
- [x] Phase 2 : Ajout colonnes match_stats ✅ (2026-02-02)
- [x] Phase 3 : Migration données existantes ✅ (2026-02-02)

**Résumé des modifications** :

| Fichier | Action |
|---------|--------|
| `src/data/sync/models.py` | Supprimé `WeaponStatsRow`, `WeaponAggregateRow` |
| `src/data/sync/transformers.py` | Supprimé `extract_weapon_stats()`, `has_weapon_stats()`, `_find_weapon_stats_dict()` |
| `src/data/sync/__init__.py` | Retiré exports weapon_stats |
| `src/data/repositories/duckdb_repo.py` | Supprimé `get_top_weapons()`, `get_total_shots_stats()` |
| `src/data/infrastructure/database/duckdb_engine.py` | Supprimé `get_kd_evolution_by_weapon()` |
| `scripts/migrate_player_to_duckdb.py` | Supprimé CREATE TABLE weapon_stats, ajouté 32 colonnes à match_stats |
| `scripts/migrate_add_columns.py` | **NOUVEAU** - Script migration pour bases existantes |

---

### [2026-02-01] - Phase 6 COMPLETE - Documentation & Branding LevelUp

**Contexte** :
Phase 5 (Enrichissement Visuel) terminée. Passage à la Phase 6 : Documentation complète et branding "LevelUp".

**Objectif** :
Mise à jour de toute la documentation pour refléter l'architecture DuckDB v4 et le nouveau nom "LevelUp".

**Actions réalisées** :

#### Sprint 6.1 : README & Documentation Utilisateur

| Tâche | Fichier | Description |
|-------|---------|-------------|
| S6.1.1 | `README.md` | Réécriture complète avec branding LevelUp |
| S6.1.2 | `docs/INSTALL.md` | Guide d'installation détaillé |
| S6.1.3 | `docs/CONFIGURATION.md` | Guide de configuration tokens/profils |
| S6.1.4 | `docs/FAQ.md` | Questions fréquentes |

#### Sprint 6.2 : Documentation Technique

| Tâche | Fichier | Description |
|-------|---------|-------------|
| S6.2.1 | `docs/ARCHITECTURE.md` | Architecture DuckDB unifiée |
| S6.2.2 | `docs/DATA_ARCHITECTURE.md` | Schéma des données v4 |
| S6.2.3 | `docs/SQL_SCHEMA.md` | Déjà à jour |
| S6.2.4 | `docs/SYNC_GUIDE.md` | Nouveau guide de synchronisation |

#### Sprint 6.3 : Branding & Renommage

| Tâche | Fichier | Description |
|-------|---------|-------------|
| S6.3.1 | Global | Renommage OpenSpartan → LevelUp |
| S6.3.2 | `pyproject.toml` | name="levelup-halo", version="3.0.0" |

#### Sprint 6.4 : Documentation Agent/IA

| Tâche | Fichier | Description |
|-------|---------|-------------|
| S6.4.1 | `CLAUDE.md` | MAJ avec architecture DuckDB |
| S6.4.2 | `.cursorrules` | MAJ avec stack DuckDB |
| S6.4.3 | `.ai/project_map.md` | MAJ cartographie |
| S6.4.4 | `.ai/data_lineage.md` | MAJ flux de données |
| S6.4.5 | `.ai/archive/` | Archivage ancien thought_log |

#### Sprint 6.5 : GitHub & CI/CD

| Tâche | Fichier | Description |
|-------|---------|-------------|
| S6.5.1 | `.github/copilot-instructions.md` | MAJ instructions |
| S6.5.2 | `.github/workflows/ci.yml` | Ajout tests DuckDB |
| S6.5.3 | `CONTRIBUTING.md` | Nouveau guide de contribution |

**Fichiers créés/modifiés** :

```
README.md                        # Réécriture complète
CONTRIBUTING.md                  # Nouveau
CLAUDE.md                        # MAJ
.cursorrules                     # MAJ
pyproject.toml                   # MAJ (name, version)
docs/INSTALL.md                  # Nouveau
docs/CONFIGURATION.md            # Nouveau
docs/FAQ.md                      # Nouveau
docs/SYNC_GUIDE.md               # Nouveau
docs/ARCHITECTURE.md             # MAJ
docs/DATA_ARCHITECTURE.md        # MAJ
.ai/project_map.md               # MAJ
.ai/data_lineage.md              # MAJ
.ai/archive/thought_log_pre_phase6.md  # Archive
.github/copilot-instructions.md  # MAJ
.github/workflows/ci.yml         # MAJ
```

**Décisions** :

| Décision | Justification |
|----------|---------------|
| Nom "LevelUp" | Plus moderne et parlant que "OpenSpartan Graph" |
| Version 3.0.0 | Reflète l'architecture DuckDB unifiée |
| Archivage thought_log | Fichier trop long, repartir frais |

**Suivi** :
- [x] Sprint 6.1 : README & Documentation Utilisateur ✅
- [x] Sprint 6.2 : Documentation Technique ✅
- [x] Sprint 6.3 : Branding & Renommage ✅
- [x] Sprint 6.4 : Documentation Agent/IA ✅
- [x] Sprint 6.5 : GitHub & CI/CD ✅

**Phase 6 terminée** ✅

---

## Format des Entrées

```
### [DATE] - [SUJET]
**Contexte** : Situation initiale
**Raisonnement** : Pourquoi cette approche
**Décision** : Ce qui a été fait
**Suivi** : Ce qui reste à faire ou à vérifier
```

---

<!-- Les nouvelles entrées sont ajoutées ici, les plus récentes en haut -->
