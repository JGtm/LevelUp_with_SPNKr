# Plan : Dossier de captures par joueur + partage par match_id

**Date** : 2026-02-07  
**Statut** : ✅ Implémenté  
**Objectif** : Changer la logique des médias pour que chaque joueur ait son dossier de captures ; l’association au match se fait uniquement dans la base du même joueur ; si le match est partagé avec d’autres joueurs, la capture apparaît aussi dans leur onglet Médias.

---

## 1. État actuel (résumé)

### 1.1 Configuration

- **Paramètres** : `media_screens_dir` et `media_videos_dir` (deux chemins globaux, éventuellement partagés).
- **Emplacement** : `AppSettings` dans `src/ui/settings.py`, utilisés dans `streamlit_app.py` et `media_library.py`.

### 1.2 Scan et stockage

- **Qui scanne** : `MediaIndexer(db_path)` avec `db_path` = DB du joueur **courant** (profil sélectionné).
- **Où** : `scan_and_index(videos_dir, screens_dir)` parcourt récursivement les **deux** dossiers (vidéos + captures).
- **Où sont écrites les données** : dans **la DB du joueur courant** uniquement (`self.db_path`).
  - Table `media_files` : tous les fichiers trouvés dans ces deux dossiers.
  - En pratique, si on change de profil, une nouvelle indexation indexe les **mêmes** dossiers dans l’**autre** DB → duplication des `file_path` dans plusieurs DB.

### 1.3 Association capture ↔ match

- **Méthode** : `associate_with_matches(tolerance_minutes)`.
- **Logique** :
  1. Prend les médias **sans** association dans la DB courante.
  2. Pour chaque média, cherche un match **parmi toutes les DB joueurs** (`_get_all_player_dbs`), en comparant `mtime` du média à `start_time` / fin du match.
  3. Retient le **match le plus proche** (une seule paire `(match_id, xuid)` par média).
  4. Écrit dans **la DB courante** une ligne par joueur ayant ce match : `(media_path, match_id, xuid)` dans `media_match_associations`.
- **Conséquence** : une même capture (même `file_path`) peut être associée à plusieurs `xuid` dans la même DB ; l’affichage « mine » vs « teammate » vient de ce `xuid` par rapport au `current_xuid`.

### 1.4 Affichage (load_media_for_ui)

- **Entrée** : `db_path` (DB du joueur courant), `current_xuid`.
- **Source** : **une seule** DB (`db_path`). Requête : `media_files` LEFT JOIN `media_match_associations`, filtre `status = 'active'`.
- **Sections** :
  - **mine** : association où `xuid` = `current_xuid`.
  - **teammate** : association où `xuid` ≠ `current_xuid`.
  - **unassigned** : pas d’association.
- Aucune lecture des autres DB pour construire la liste des médias affichés.

### 1.5 Problèmes / complexité actuelle

- Dossiers **globaux** : on ne sait pas « à qui » appartient un fichier sans passer par l’association (et la recherche multi-DB).
- Association **multi-DB** : pour chaque média sans association, on interroge **toutes** les DB pour trouver un match, puis on écrit plusieurs lignes (un xuid par joueur ayant ce match) dans la DB courante.
- Duplication potentielle : si on indexe avec le profil A puis avec le profil B, les mêmes chemins sont enregistrés dans deux DB différentes.

### 1.6 Correctifs déjà en place (à ne pas réintroduire)

Deux problèmes avaient été corrigés et doivent rester garantis dans la nouvelle logique :

**Association (ordre déterministe)**  
- On parcourait les BDD joueurs dans un ordre **non déterministe** (`iterdir()`). Pour chaque média on ne créait qu’**une seule** association (le premier joueur dont la BDD contenait un match dans la fenêtre). Selon l’ordre du jour, le « propriétaire » affiché changeait et le propriétaire du profil n’était pas prioritaire.  
- **Correctif actuel** : pour chaque média sans association, on récupère **tous** les candidats (match + distance) dans toutes les BDD joueurs ; on choisit **un seul** match (le plus proche en temps) ; on insère une ligne `(media_path, match_id, xuid)` **pour chaque** joueur dont la BDD contient ce match. Ordre déterministe : `_get_all_player_dbs()` avec `sorted(..., key=lambda p: p.name)` et `_get_all_player_dbs_current_first()` pour mettre la BDD courante en premier.

**Affichage (une seule section par capture)**  
- Une même capture pouvait avoir **plusieurs lignes** (une par xuid). L’UI affichait alors la même capture dans **plusieurs** sections selon l’ordre des lignes.  
- **Correctif actuel** : une seule ligne par média en sortie de `load_media_for_ui` : priorité « mine » > « teammate » > « unassigned », puis tri stable par gamertag. Chaque capture n’apparaît que dans **une** section (en priorité « Mes captures » si le joueur courant est associé).

**Backfill**  
- `_backfill_media_associations_missing_xuids()` : pour chaque `(media_path, match_id)` déjà présent, on ajoute les xuid manquants (autres joueurs qui ont ce match dans leur BDD).

Dans la **nouvelle** logique (dossier par joueur, association mono-DB), on n’a plus de recherche multi-DB pour l’association, donc pas de risque d’ordre non déterministe côté association. En revanche, **load_media_for_ui** devra continuer à garantir **une seule ligne (une seule section) par capture** lorsqu’on agrège les médias de la DB courante + les médias des autres DB pour « Captures de XXX ».

---

## 2. Nouvelle logique demandée

### 2.1 Règle dossier = joueur

- **Un seul dossier (ou base) de captures**, avec **un sous-dossier par joueur**.
- Exemple : `D:/Captures/` avec `D:/Captures/PlayerA/`, `D:/Captures/PlayerB/`.
- Convention : le nom du sous-dossier = **gamertag** du joueur (aligné sur `data/players/{gamertag}/stats.duckdb`).

### 2.2 Association uniquement dans la base du même joueur

- Pour le joueur **A** :
  - On ne scanne que le dossier **A** (ex. `base/A/`).
  - Les entrées vont dans la DB **A** (`media_files` + associations).
  - Pour associer au match : on cherche le match **uniquement dans la DB A** (`match_stats` de A). Plus de recherche dans les autres DB.
- Même chose pour B, C, etc. : chaque joueur a ses fichiers dans son dossier et ses associations dans sa propre DB.

### 2.3 Partage par match_id (affichage cross-DB)

- Si une capture de **A** est associée au match **M** (dans la DB A), et que le joueur **P** (profil courant) a aussi le match **M** dans sa DB :
  - Cette capture doit **apparaître dans l’onglet Médias de P**, dans une section du type « Captures de A » (ou équivalent).
- Donc : pour **affichage** uniquement, on fait du **cross-DB** :
  - **Mes captures** : médias de la DB P (fichiers dans le dossier P).
  - **Captures de XXX** : médias des **autres** DB (dossier XXX) dont le `match_id` associé existe dans la DB P (match joué par P).
  - **Sans correspondance** : médias de la DB P sans association (pas de match trouvé dans la DB P).

---

## 3. Impacts par composant

### 3.1 Paramètres (settings)

- **Option A** : un seul paramètre `media_captures_base_dir` (ex. `D:/Captures`). Les sous-dossiers sont déduits : `base_dir / gamertag` pour chaque joueur connu.
- **Option B** : garder `media_screens_dir` et `media_videos_dir` mais les interpréter comme des **bases** : on scanne `media_screens_dir / gamertag` et `media_videos_dir / gamertag`.
- **Recommandation** : Option A (une base, structure `base_dir / {gamertag}/` avec images et vidéos dedans) pour simplifier.

- **Rétrocompatibilité** : prévoir une migration des réglages (si `media_screens_dir` / `media_videos_dir` sont renseignés, proposer une base commune ou ignorer l’ancien format après migration).

### 3.2 MediaIndexer – scan

- **Entrée** : au lieu de `(videos_dir, screens_dir)` globaux, on passe le **dossier du joueur** pour ce `db_path` (ex. `base_dir / gamertag`).
- **Résolution du gamertag** : à partir de `db_path` → `data/players/{gamertag}/stats.duckdb` ⇒ `gamertag = Path(db_path).parent.name`. Déjà disponible via `get_gamertag_from_duckdb_v4_path(db_path)` dans `src/ui/multiplayer.py`.
- **Comportement** : `scan_and_index(player_captures_dir)` (ou deux sous-dossiers `player_captures_dir/screens`, `player_captures_dir/videos` selon convention) :
  - Parcourir uniquement ce dossier (ou ces sous-dossiers).
  - Insérer / mettre à jour / marquer `deleted` dans **cette** DB uniquement.
- **Signature** : soit une seule racine `player_media_root: Path`, soit `player_videos_dir` + `player_screens_dir` dérivés de `base_dir` + `gamertag`.

### 3.3 MediaIndexer – association

- **associate_with_matches** :
  - Ne plus appeler `_get_all_player_dbs()` pour la **recherche** du match.
  - Pour chaque média sans association (dans cette DB), chercher le match le plus proche **uniquement** dans `match_stats` de **cette** DB.
  - Écrire une seule ligne par média : `(media_path, match_id, xuid)` avec `xuid` = le joueur propriétaire de cette DB (pas une liste de tous les coéquipiers).
- **Suppression** : plus besoin de `_backfill_media_associations_missing_xuids` pour « ajouter les autres joueurs ayant ce match » dans la **même** DB : la propagation se fera à l’**affichage** en lisant les autres DB.

### 3.4 MediaIndexer – load_media_for_ui (affichage)

- **Entrée** : inchangée `(db_path, current_xuid)` (DB du profil courant, xuid du joueur courant).
- **Étapes** :
  1. **Mes captures** : comme aujourd’hui, depuis la DB courante : `media_files` JOIN `media_match_associations` où `xuid` = current_xuid (ou « propriétaire » = ce joueur). Les fichiers sont dans le dossier de ce joueur.
  2. **Matchs du joueur courant** : récupérer l’ensemble des `match_id` présents dans la DB courante (ex. `SELECT DISTINCT match_id FROM match_stats`).
  3. **Captures des autres joueurs** : pour chaque autre joueur (autres DB dans `data/players/`), ouvrir sa DB et récupérer les médias dont le `match_id` (dans `media_match_associations`) est dans l’ensemble des match_id du joueur courant. Ces lignes forment « Captures de XXX ».
  4. **Sans correspondance** : médias de la DB courante sans association (ou sans match_id).
- **Performance** : une requête par autre joueur (ou une requête agrégée si on veut optimiser). Pas de modification des tables, seulement lecture cross-DB.

### 3.5 Indexation en arrière-plan (streamlit_app.py)

- **Qui indexe** : pour chaque DB joueur connue (ou seulement le profil courant selon la politique choisie).
  - Si « indexer tous les joueurs au démarrage » : boucle sur `_get_all_player_dbs()` (ou équivalent), pour chaque `(db_path, xuid)` dériver le gamertag, construire `base_dir / gamertag`, lancer `scan_and_index` + `associate_with_matches` pour cette DB.
  - Si « indexer uniquement le profil courant » : comme aujourd’hui, mais en passant le dossier du joueur courant (`base_dir / gamertag`) au lieu des deux dossiers globaux.
- **Paramètre** : utiliser `media_captures_base_dir` (ou équivalent) et dériver les dossiers par joueur.

### 3.6 Paramètres UI (Paramètres → Médias)

- **Migration** : si l’utilisateur a déjà `media_screens_dir` et/ou `media_videos_dir`, **proposer une base commune** (ex. parent commun des deux chemins) et préremplir `media_captures_base_dir` ; mettre à jour la section dédiée dans les paramètres en conséquence.
- Remplacer (ou compléter) les deux champs « Dossier captures » / « Dossier vidéos » par un seul « Dossier de base des captures » (avec explication : un sous-dossier par joueur, nommé comme le gamertag).
- Documenter la convention : `{base}/{gamertag}/` contient les captures (et éventuellement sous-dossiers `screens`, `videos` si on garde une séparation).

### 3.7 Reset de la BDD médias

- **Objectif** : permettre de repartir de zéro (tables médias vides) avant ou après un changement de logique (ex. passage au dossier par joueur), ou après une réorganisation des dossiers.
- **Implémentation** :
  - **Option A** : vider les tables sans toucher au schéma : `DELETE FROM media_match_associations` puis `DELETE FROM media_files` (ou `TRUNCATE` si DuckDB le supporte). Conserver le schéma pour la réindexation.
  - **Option B** : supprimer et recréer les tables `media_files` et `media_match_associations` via `ensure_schema()` après drop.
- **Point d’entrée** :
  - Soit un **bouton / action dans Paramètres → Médias** : « Réinitialiser l’index médias » (avec confirmation), qui vide les tables médias **de la DB du joueur courant** (ou de toutes les DB joueurs si on veut un reset global).
  - Soit un **script** : `python scripts/reset_media_db.py [--gamertag X] [--all]` qui vide (et éventuellement réindexe) les tables concernées.
- **Périmètre** : par DB joueur (chaque `data/players/{gamertag}/stats.duckdb` a ses propres `media_files` et `media_match_associations`). Le reset peut être ciblé (un joueur) ou global (tous les joueurs).
- À prévoir dans le **plan d’implémentation** (voir § 5).

### 3.8 Scripts et autres appels

- **scripts/index_media.py** : accepter un `--gamertag` ou un `--db-path` et ne scanner que le dossier correspondant ; associer uniquement dans cette DB.
- **media_library.py** (ancien onglet) : si on le garde, appliquer la même logique (dossier par joueur + association mono-DB + affichage cross-DB).

---

## 4. Schéma de données (inchangé côté tables)

- **media_files** : inchangé (file_path, métadonnées, etc.). Les `file_path` seront tous sous `base_dir / gamertag / ...`.
- **media_match_associations** : on peut garder une seule ligne par (media_path, match_id, xuid) avec **xuid = propriétaire de la DB** (celui dont le dossier a été scanné). Plus besoin d’une ligne par coéquipier dans cette table ; le partage est géré à l’affichage.

---

## 5. Plan d’implémentation (ordre suggéré)

| Étape | Action | Fichiers principaux |
|-------|--------|----------------------|
| 1 | Ajouter `media_captures_base_dir` dans `AppSettings` et UI Paramètres ; garder temporairement les anciens champs pour migration. | `src/ui/settings.py`, `src/ui/pages/settings.py` |
| 2 | Adapter le scan : dériver le dossier joueur à partir de `db_path` + base_dir ; modifier `scan_and_index` pour accepter un seul dossier (ou deux sous-chemins dérivés). | `src/data/media_indexer.py` |
| 3 | Simplifier `associate_with_matches` : recherche du match **uniquement** dans la DB courante ; une seule association (media_path, match_id, xuid du propriétaire). Supprimer / simplifier `_backfill_media_associations_missing_xuids`. | `src/data/media_indexer.py` |
| 4 | Réécrire `load_media_for_ui` : « mine » depuis la DB courante ; récupérer les match_id de la DB courante ; pour chaque autre DB joueur, charger les médias dont match_id dans ce set → « Captures de XXX ». | `src/data/media_indexer.py` |
| 5 | Adapter l’indexation en arrière-plan : utiliser `media_captures_base_dir` + gamertag ; décider si on indexe tous les joueurs ou seulement le courant ; appeler le scan/association par DB. | `streamlit_app.py` |
| 6 | Mettre à jour scripts (index_media, etc.) et ancien onglet media_library si encore utilisé. | `scripts/index_media.py`, `src/ui/pages/media_library.py` |
| 7 | **Reset BDD médias** : action « Réinitialiser l’index médias » (Paramètres → Médias) et/ou script `scripts/reset_media_db.py` ; vider `media_files` et `media_match_associations` par DB (joueur courant ou --all). | `src/ui/pages/settings.py` ou page Médias, `scripts/reset_media_db.py`, `src/data/media_indexer.py` (méthode `reset_media_tables` ou équivalent) |
| 8 | Tests : scan par joueur, association mono-DB, load_media_for_ui avec captures « partagées » (même match_id dans deux DB), reset. | `tests/test_media_indexer.py`, nouveaux tests `load_media_for_ui` cross-DB |

---

## 6. Décisions prises (points tranchés)

1. **Convention du dossier joueur** : une seule racine `base_dir / gamertag` pour tout (images + vidéos) dans le même dossier joueur. Pas de sous-dossiers screens/videos obligatoires (optionnel si on veut).
2. **Indexation** : **au démarrage, indexer tous les joueurs** qui ont un dossier sous la base (tous les `base_dir / gamertag` existants pour les gamertags connus dans `data/players/`).
3. **Migration** : **proposer une base commune** à partir de `media_screens_dir` et `media_videos_dir` (ex. parent commun) et **mettre à jour la section dédiée** dans les Paramètres (nouveau champ + texte d’aide).
4. **Affichage** : conserver la règle **une seule ligne (une seule section) par capture** dans `load_media_for_ui` (priorité mine > teammate > unassigned, tri stable), y compris quand on agrège les médias des autres DB pour « Captures de XXX ».
5. **Reset** : prévoir un reset des tables médias (par DB joueur ou global) avant/après migration ou pour forcer une réindexation complète.

---

## 7. Résumé

- **Dossier** : un sous-dossier par joueur sous une base (ex. `base_dir / gamertag`).
- **Scan** : par DB joueur, uniquement le dossier de ce joueur → écriture dans sa DB.
- **Association** : uniquement dans la DB du joueur ; recherche du match dans **cette** DB uniquement.
- **Affichage** : « Mes captures » = DB courante ; « Captures de XXX » = médias des autres DB dont le `match_id` est dans les matchs de la DB courante ; « Sans correspondance » = DB courante sans association. **Une seule ligne (une seule section) par capture** (priorité mine > teammate > unassigned).
- **Indexation au démarrage** : tous les joueurs ayant un dossier sous la base.
- **Migration paramètres** : proposer une base commune à partir des anciens champs et mettre à jour la section Paramètres → Médias.
- **Reset BDD médias** : action et/ou script pour vider `media_files` et `media_match_associations` (par joueur ou global), afin de repartir de zéro ou après changement de logique.
- **Aucun changement de schéma** des tables ; changements dans la config, le scan, l’association, la requête d’affichage et le reset.
