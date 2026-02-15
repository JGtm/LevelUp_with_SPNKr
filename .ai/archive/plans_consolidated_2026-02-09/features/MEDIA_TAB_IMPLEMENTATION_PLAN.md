# Planification détaillée – Onglet « Médias »

> Remplace l’onglet « Bibliothèque de médias ». **Refonte complète à partir de zéro.**

**Date** : 2026-02-07  
**Statut** : Planification  
**Dernière mise à jour** : 2026-02-07

---

## 0. Principe : démarrage de zéro

L’onglet actuel « Bibliothèque de médias » est chaotique et non acceptable en l’état (UI/UX).  
**Aucune réutilisation du code existant** ; certains algorithmes peuvent être analysés pour s’en inspirer, mais l’implémentation sera entièrement nouvelle.

---

## 1. Vue d’ensemble

| Point | Besoin | Réponse |
|-------|--------|---------|
| 1 | Dossiers configurés dans Paramètres | Inchangé (`media_screens_dir`, `media_videos_dir`) |
| 2 | BDD avec métadonnées enrichies | Nouveau schéma `media_files` + scan delta |
| 3 | Mise à jour delta au lancement | Indexation incrémentale uniquement |
| 4 | Thumbnail animé par vidéo | GIF généré (ffmpeg), nom stocké en BDD |
| 5 | Animation du thumbnail au survol | Composant HTML/JS |
| 6 | Clic → affichage plein écran | **Lightbox** (overlay fullscreen) |
| 7 | Grille alignée, taille uniforme | CSS + layout fixe |
| 8 | Association capture ↔ match (dates, fuseaux) | Fenêtre temporelle, match **le plus proche** si plusieurs |
| 9 | Bouton « Ouvrir le match » | Redirection vers onglet Match + `match_id` |
| 10 | Nom de carte + date courte au-dessus | Via associations, format court |
| 11 | Section « Sans correspondance » | Captures non associées après recherche dans **toutes** les BDD joueurs |
| 12 | BDD de capture par utilisateur | `data/players/{gamertag}/stats.duckdb` |
| 13 | Section « Captures de XXX » | Groupement par joueur associé |
| 14 | Aucune capture orpheline | Si pas de match chez l’utilisateur → chercher chez **autres joueurs** |
| 15 | Capture multi-joueurs | Une capture peut être associée à plusieurs xuid |

### Décisions validées (2026-02-07)

| # | Décision |
|---|----------|
| 1 | **Orphelines** : une capture sans match chez l’utilisateur doit être cherchée dans les BDD des autres joueurs. « Sans correspondance » = aucune correspondance trouvée chez personne. |
| 2 | **Multi-matchs** : associer au match **le plus proche** temporellement. |
| 3 | **Fichiers supprimés** : marquer `deleted` en BDD, **ne pas afficher**. |
| 4 | **Mode plein écran** : **Lightbox** HTML pour consulter les médias. |
| 5 | **Animation survol** : composant **HTML/JS**. |
| 6 | **Images** : générer une **miniature dédiée** (plus rapide à charger). |
| 7 | **Sous-dossiers** : scan récursif. **NAS** : prévu à terme (même NAS que l’app), latences disque mineures. |

---

## 2. Schéma BDD

### 2.1 Emplacement

Chaque joueur : `data/players/{gamertag}/stats.duckdb`  
Dossier de captures partagé entre utilisateurs ; chaque utilisateur a sa propre BDD de capture.

### 2.2 Table `media_files`

| Colonne | Type | Description |
|---------|------|-------------|
| `file_path` | VARCHAR PRIMARY KEY | Chemin absolu du fichier |
| `file_hash` | VARCHAR NOT NULL | Hash MD5 pour détection de changement |
| `file_name` | VARCHAR NOT NULL | Nom du fichier |
| `file_size` | BIGINT NOT NULL | Taille en octets |
| `file_ext` | VARCHAR NOT NULL | Extension |
| `kind` | VARCHAR NOT NULL | `image` ou `video` |
| `capture_start_utc` | TIMESTAMP | Début de capture (métadonnées ou déduit) |
| `capture_end_utc` | TIMESTAMP NOT NULL | Fin de capture (= mtime ou métadonnées) |
| `duration_seconds` | DOUBLE | Durée (vidéos) ; NULL pour images |
| `title` | VARCHAR | Titre si présent en métadonnées |
| `thumbnail_path` | VARCHAR | Chemin du thumbnail (GIF vidéo, miniature image) |
| `mtime` | DOUBLE | mtime système (epoch) |
| **`status`** | VARCHAR | `active` \| `deleted` — si fichier absent du disque → `deleted` |
| `first_seen_at` | TIMESTAMP | Première indexation |
| `last_scan_at` | TIMESTAMP | Dernier scan |
| `scan_version` | INTEGER | Version du schéma |

Logique des dates :

- `capture_end_utc` : métadonnées si dispo, sinon mtime.
- `capture_start_utc` : métadonnées si dispo, sinon `capture_end_utc - duration_seconds` (vidéos), ou = `capture_end_utc` (images).

### 2.3 Table `media_match_associations`

| Colonne | Type | Description |
|---------|------|-------------|
| `media_path` | VARCHAR | FK → `media_files.file_path` |
| `match_id` | VARCHAR | ID du match Halo |
| `xuid` | VARCHAR | Joueur dont le match est associé |
| `match_start_time` | TIMESTAMP | Début du match |
| `map_id` | VARCHAR | Carte |
| `map_name` | VARCHAR | Nom de la carte |
| `association_confidence` | DOUBLE | 1.0 par défaut |
| `associated_at` | TIMESTAMP | Date d’association |

Clé primaire : `(media_path, match_id, xuid)`  
Une capture peut avoir plusieurs associations (multi-joueurs). Pour une capture donnée et un match donné, on associe au **match le plus proche** parmi les candidats.

### 2.4 Fichiers supprimés

Lors du scan delta : si le fichier n’existe plus sur le disque → `UPDATE media_files SET status = 'deleted'`.  
Filtre d’affichage : `WHERE status = 'active'` (ou équivalent).

---

## 3. Extraction des métadonnées

### 3.1 Vidéos

- **ffprobe** : durée, dates si disponibles.
- Fallback : mtime pour `capture_end_utc`, durée ffprobe pour déduire `capture_start_utc`.

### 3.2 Images

- EXIF (`DateTimeOriginal`, `CreateDate`) via PIL/ExifTool.
- Fallback : mtime pour `capture_end_utc`, `capture_start_utc` = `capture_end_utc`.

---

## 4. Scan delta

1. Scanner récursivement les dossiers configurés (`os.walk` ou équivalent).
2. Pour chaque fichier trouvé :
   - Nouveau → INSERT.
   - Existant et mtime inchangé → skip.
   - Existant et mtime modifié → UPDATE métadonnées.
3. Fichiers en BDD non présents sur le disque → `status = 'deleted'`.
4. À l’affichage : exclure `status = 'deleted'`.

---

## 5. Thumbnails

### 5.1 Vidéos

- GIF animé (ffmpeg), stocké dans `{media_videos_dir}/thumbs/`.
- Référence dans `media_files.thumbnail_path`.

### 5.2 Images

- **Miniature dédiée** générée (redimensionnement) — plus rapide que charger l’image complète.
- Stockage : sous-dossier `thumbs` du dossier captures ou chemin dédié.

### 5.3 Animation au survol

Composant **HTML/JS** : au survol, afficher la version animée du thumbnail (GIF pour vidéo, ou image complète si pertinent).

---

## 6. Lightbox

- **Lightbox HTML** : overlay fullscreen au clic sur le thumbnail.
- Lecture vidéo ou affichage image en grand.
- Fermeture par clic hors zone ou bouton.

---

## 7. Association capture ↔ match

### 7.1 Recherche multi-joueurs (point 14)

Ordre de recherche :

1. Matchs du joueur actuel (BDD actuelle).
2. Si aucune correspondance → matchs des **autres joueurs** (lecture des autres `stats.duckdb`).

Aucune capture orpheline : on cherche partout avant de placer en « Sans correspondance ».

### 7.2 Match le plus proche (point 2 validé)

Si plusieurs matchs candidats : choisir celui dont la fenêtre temporelle est **la plus proche** du timestamp de la capture (distance minimale).

### 7.3 Fuseaux

- Captures : mtime local (Paris) converti en UTC pour comparaison.
- Matchs : `start_time` UTC (API Halo).
- Comparaison en epoch UTC.

---

## 8. Sections d’affichage

1. **Mes captures** : associations où `xuid` = joueur actuel.
2. **Captures de XXX** : associations où `xuid` = autre joueur (gamertag ou alias).
3. **Sans correspondance** : captures sans association après recherche dans **toutes** les BDD joueurs.

---

## 9. Fichiers cibles (nouvelle implémentation)

| Fichier | Rôle |
|---------|------|
| `src/data/media_indexer.py` | Nouveau module (ou réécrit de zéro) : schéma, scan delta, associations |
| `src/ui/pages/media_tab.py` | Nouvelle page (remplace `media_library.py`) |
| `src/ui/components/media_thumbnail.py` | Composant thumbnail avec survol HTML/JS |
| `src/ui/components/media_lightbox.py` | Composant lightbox HTML |
| `scripts/generate_thumbnails.py` | Réutilisé pour vidéos ; étendre pour images ou nouveau script |
| `streamlit_app.py` | Branche vers `render_media_tab` au lieu de `render_media_library_page` |

---

# Sprints

## Règle OBLIGATOIRE : tests

**À chaque sprint**, l’agent doit :

1. **Créer** tous les tests nécessaires (unitaires, intégration, etc.).
2. **Exécuter** ces tests lui-même — **OBLIGATOIRE**, sans exception.

L’exécution des tests par l’agent est **obligatoire**. Aucun sprint ne peut être considéré comme terminé sans création ET exécution réussie des tests.

---

## Sprint 1 : Fondations BDD et scan delta ✅

**Objectif** : Schéma BDD, scan delta, métadonnées de base.

**Livrables** :

1. Schéma `media_files` (colonnes `capture_start_utc`, `capture_end_utc`, `duration_seconds`, `title`, `thumbnail_path`, `status`).
2. Schéma `media_match_associations` (avec `map_id`, `map_name`).
3. Module `media_indexer` : scan récursif, delta (nouveaux/modifiés/deleted), métadonnées ffprobe/EXIF.
4. Intégration au lancement : `_background_media_indexing` (thread daemon) dans streamlit_app.py.
5. Tests : test_media_indexer.py (ensure_schema, scan_and_index, scan_marks_deleted, etc.).

**Statut** : Livré (déjà en place, documenté dans thought_log 2026-02-07). Estimation : 2–3 jours.

---

## Sprint 2 : Association capture ↔ match (multi-joueurs) ✅

**Objectif** : Associer chaque capture au match le plus proche, en cherchant dans toutes les BDD joueurs.

**Livrables** : associate_with_matches(), fenêtre temporelle, match le plus proche, _get_all_player_dbs, map_id/map_name. Tests : closest_match, multi_players, map_id_map_name, search_all_player_dbs.

**Statut** : Livré (déjà en place, thought_log 2026-02-07). Estimation : 2–3 jours.

---

## Sprint 3 : Thumbnails (vidéos + images) ✅

**Objectif** : Génération des thumbnails et enregistrement en BDD.

**Livrables** : generate_thumbnails_for_new(), GIF vidéo (ffmpeg), miniatures images (PIL), stockage thumbs/, mise à jour thumbnail_path. Gestion erreurs (ffmpeg/PIL absents). Tests : test_generate_image_thumbnails, test_generate_thumbnails_no_ffmpeg_skips_videos, test_generate_thumbnails_empty_dirs.

**Statut** : Livré (thought_log 2026-02-07). Estimation : 1–2 jours.

---

## Sprint 4 : Composants UI – Thumbnail et Lightbox ✅

**Objectif** : Composants réutilisables pour l’affichage des médias.

**Livrables** :

1. **Composant Thumbnail** (`src/ui/components/media_thumbnail.py`) :
   - Affichage statique par défaut.
   - Au survol : version animée (HTML/JS).
   - Dimensions fixes, ratio uniforme.
2. **Composant Lightbox** (`src/ui/components/media_lightbox.py`) :
   - Overlay fullscreen.
   - Support image et vidéo.
   - Fermeture par clic (hors zone), bouton × ou touche Escape.
3. Intégration Streamlit : `st.components.v1.html()`.
4. Tests : `tests/test_media_components_sprint4.py` (exécution : `pytest tests/test_media_components_sprint4.py -v`).

**Critères de validation** :

- Le survol déclenche l’animation.
- Le clic ouvre le lightbox avec le média correct.
- Comportement identique sur desktop.
- **Tests** : création + exécution OBLIGATOIRES (`pytest tests/ -v` ou tests visuels documentés si non automatisables).

**Statut** : Livré (2026-02-07). Estimation : 2 jours.

---

## Sprint 5 : Page « Médias » – Structure et sections ✅

**Objectif** : Page complète avec grille, sections et navigation.

**Livrables** :

1. **Page `media_tab.py`** :
   - Chargement des médias depuis la BDD (filtre `status = 'active'`) via `MediaIndexer.load_media_for_ui()`.
   - Sections : « Mes captures », « Captures de XXX » (par joueur), « Sans correspondance ».
   - Grille alignée, taille uniforme.
2. **Carte + date** au-dessus de chaque thumbnail.
3. **Bouton « Ouvrir le match »** sous chaque capture associée, redirection vers l’onglet Match (`_pending_page` + `_pending_match_id`).
4. Filtres optionnels : type (image/vidéo), recherche par nom, nombre de colonnes.
5. Remplacement de l’onglet « Bibliothèque médias » par « Médias » dans le routeur (PAGES + dispatch).

**Critères de validation** :

- Les trois sections s’affichent correctement.
- Le bouton « Ouvrir le match » redirige vers le bon match.
- La grille est alignée et lisible.
- Aucun code de l’ancien onglet réutilisé.
- **Tests** : `tests/test_media_indexer.py::test_load_media_for_ui`, `tests/test_media_tab_sprint5.py` — exécution : `pytest tests/test_media_indexer.py tests/test_media_tab_sprint5.py -v`.

**Statut** : Livré (2026-02-07). Estimation : 2–3 jours.

---

## Sprint 6 : Intégration et réglages ✅

**Objectif** : Bouclage, performance, edge cases.

**Livrables** :

1. Intégration du scan delta au démarrage (non bloquant) : déjà en place (_background_media_indexing).
2. Gestion des cas limites : os.walk protégé (OSError pour dossiers inaccessibles) ; erreurs métadonnées par fichier ne bloquent pas le scan.
3. Tests de régression : suite media (test_media_indexer, test_media_tab_sprint5, test_media_components_sprint4).
4. Documentation : project_map (media_indexer, tables media_*), data_lineage (flux 5 Médias), thought_log.
5. media_library.py : conservé avec note (onglet principal = Médias / media_tab.py).

**Statut** : Livré (2026-02-07). Estimation : 1–2 jours.

---

## Récapitulatif des sprints

| Sprint | Focus | Estimation | Statut |
|--------|-------|------------|--------|
| 1 | Fondations BDD et scan delta | 2–3 jours | ✅ (déjà livré) |
| 2 | Association capture ↔ match (multi-joueurs) | 2–3 jours | ✅ (déjà livré) |
| 3 | Thumbnails (vidéos + images) | 1–2 jours | ✅ (déjà livré) |
| 4 | Composants UI – Thumbnail et Lightbox | 2 jours | ✅ 2026-02-07 |
| 5 | Page « Médias » – Structure et sections | 2–3 jours | ✅ 2026-02-07 |
| 6 | Intégration et réglages | 1–2 jours | ✅ 2026-02-07 |
| **Total** | | **10–15 jours** | **Tous livrés** |

---

*Document mis à jour le 2026-02-07.*
