# Optimisation de l'Indexation des Médias

> **Date**: 2026-02-04  
> **Auteur**: Analyse PM  
> **Statut**: Recommandations

---

## Contexte

La page "Médias" (`src/ui/pages/media_library.py`) scanne actuellement les dossiers de médias à chaque affichage avec un cache Streamlit de 120s. L'association média → match se fait via proximité temporelle (mtime vs fenêtre temporelle du match).

**Problèmes identifiés** :
- Scan disque répétitif même avec cache
- Pas de stockage persistant des associations
- Pas de génération automatique de thumbnails pour nouveaux contenus
- Performance dégradée avec de gros volumes de médias

---

## Recommandations

### ✅ **OUI** - Scanner au lancement et stocker en BDD

**Avantages** :
- ⚡ **Performance** : Scan unique au démarrage vs scan à chaque affichage
- 💾 **Persistance** : Associations conservées entre sessions
- 🔍 **Requêtes rapides** : Indexation en BDD permet filtres/joins efficaces
- 📊 **Métadonnées enrichies** : Possibilité d'ajouter tags, notes, etc.

**Architecture proposée** :
- Table `media_files` dans DuckDB joueur (`data/players/{gamertag}/stats.duckdb`)
- Scan incrémental : ne traiter que les fichiers modifiés depuis `last_scan_at`
- Hook d'initialisation dans `streamlit_app.py` ou module dédié

### ✅ **OUI** - Génération automatique de thumbnails

**Avantages** :
- 🎬 **UX améliorée** : Prévisualisation immédiate dans la grille
- ⚡ **Performance UI** : Pas besoin de charger la vidéo complète pour aperçu
- 🔄 **Automatisation** : Script existant (`scripts/generate_thumbnails.py`) déjà prêt

**Intégration proposée** :
- Sous-processus asynchrone pour ne pas bloquer le démarrage
- Utiliser le script existant en mode "scan-only-new"
- Stocker le chemin du thumbnail dans la table `media_files`

---

## Architecture Technique

### 1. Schéma de Table DuckDB

```sql
CREATE TABLE IF NOT EXISTS media_files (
    -- Identifiants
    file_path TEXT PRIMARY KEY,
    file_hash TEXT NOT NULL,  -- Hash MD5 du contenu pour détecter modifications
    
    -- Métadonnées fichier
    file_name TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    file_ext TEXT NOT NULL,
    kind TEXT NOT NULL,  -- 'image' | 'video'
    mtime REAL NOT NULL,  -- Timestamp epoch (compatible avec code actuel)
    
    -- Association match
    match_id TEXT,  -- NULL si non associé
    match_start_time TIMESTAMP,
    association_confidence REAL,  -- Score de confiance (0-1)
    
    -- Thumbnails
    thumbnail_path TEXT,  -- Chemin vers thumbnail (GIF pour vidéos)
    thumbnail_generated_at TIMESTAMP,
    
    -- Métadonnées scan
    first_seen_at TIMESTAMP DEFAULT (datetime('now')),
    last_scan_at TIMESTAMP DEFAULT (datetime('now')),
    scan_version INTEGER DEFAULT 1,  -- Pour migrations futures
    
    -- Index pour requêtes fréquentes
    INDEX idx_media_match_id ON media_files(match_id),
    INDEX idx_media_mtime ON media_files(mtime DESC),
    INDEX idx_media_kind ON media_files(kind),
    INDEX idx_media_match_time ON media_files(match_id, match_start_time)
);
```

### 2. Module d'Indexation

**Fichier** : `src/data/media_indexer.py`

```python
class MediaIndexer:
    """Gère l'indexation des médias et l'association avec les matchs."""
    
    def scan_and_index(
        self,
        videos_dir: Path | None,
        screens_dir: Path | None,
        db_path: Path,
        xuid: str,
        *,
        force_rescan: bool = False,
    ) -> ScanResult:
        """Scanne les dossiers et met à jour l'index en BDD.
        
        Returns:
            ScanResult(n_scanned, n_new, n_updated, n_associated)
        """
        
    def associate_with_matches(
        self,
        db_path: Path,
        xuid: str,
        tolerance_minutes: int = 5,
    ) -> int:
        """Associe les médias non associés avec les matchs.
        
        Returns:
            Nombre de médias associés.
        """
        
    def generate_thumbnails_for_new(
        self,
        videos_dir: Path,
        *,
        max_concurrent: int = 2,
    ) -> tuple[int, int]:
        """Génère les thumbnails pour les vidéos sans thumbnail.
        
        Returns:
            (generated, errors)
        """
```

### 3. Hook d'Initialisation

**Option A** : Dans `streamlit_app.py` (recommandé)

```python
def main() -> None:
    st.set_page_config(page_title="LevelUp", layout="wide")
    
    # ... code existant ...
    
    # Indexation médias en arrière-plan (non-bloquant)
    if settings.media_enabled:
        _background_media_indexing(settings, db_path, xuid)
    
    # ... reste du code ...
```

**Option B** : Module dédié avec thread pool

```python
# src/app/media_background.py
def start_media_indexing_worker(settings, db_path, xuid):
    """Lance l'indexation en arrière-plan."""
    import threading
    
    def worker():
        try:
            indexer = MediaIndexer()
            indexer.scan_and_index(...)
            indexer.associate_with_matches(...)
            indexer.generate_thumbnails_for_new(...)
        except Exception as e:
            logger.error(f"Media indexing failed: {e}")
    
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
```

### 4. Adaptation de la Page Médias

**Avant** (actuel) :
```python
def render_media_library_page(*, df_full: pd.DataFrame, settings: AppSettings):
    media_df = _index_all_media(settings)  # Scan disque
    windows_df = _compute_match_windows(df_full, settings)
    assoc_df = _associate_media_to_matches(media_df, windows_df)  # Calcul à chaque fois
```

**Après** (optimisé) :
```python
def render_media_library_page(*, df_full: pd.DataFrame, settings: AppSettings):
    # Charger depuis BDD (ultra-rapide)
    media_df = load_media_from_db(db_path, xuid)
    
    # Optionnel : re-associer si matchs récents ajoutés
    if should_reassociate_media():
        associate_media_background(db_path, xuid)
```

---

## Plan d'Implémentation

### Phase 1 : Infrastructure BDD ✅
- [ ] Créer table `media_files` dans schéma DuckDB
- [ ] Ajouter migration pour DB existantes
- [ ] Tests unitaires schéma

### Phase 2 : Module Indexer ✅
- [ ] Implémenter `MediaIndexer.scan_and_index()`
- [ ] Implémenter `MediaIndexer.associate_with_matches()`
- [ ] Intégrer avec logique existante (`_compute_match_windows`, `_associate_media_to_matches`)
- [ ] Tests unitaires indexation

### Phase 3 : Génération Thumbnails ✅
- [ ] Intégrer `scripts/generate_thumbnails.py` dans `MediaIndexer`
- [ ] Mode "scan-only-new" pour éviter régénération
- [ ] Stocker chemin thumbnail en BDD
- [ ] Tests génération thumbnails

### Phase 4 : Hook Initialisation ✅
- [ ] Ajouter hook dans `streamlit_app.py`
- [ ] Mode non-bloquant (thread/async)
- [ ] Indicateur de progression dans UI (optionnel)
- [ ] Tests intégration

### Phase 5 : Migration Page Médias ✅
- [ ] Adapter `media_library.py` pour lire depuis BDD
- [ ] Garder fallback sur scan disque si BDD vide
- [ ] Bouton "Re-scanner" pour forcer refresh
- [ ] Tests UI

### Phase 6 : Tests E2E ✅
- [ ] Test avec gros volume (1000+ fichiers)
- [ ] Test association correcte matchs
- [ ] Test génération thumbnails
- [ ] Test performance (temps de scan)

---

## Points d'Attention

### ⚠️ Performance
- **Scan incrémental** : Ne traiter que fichiers modifiés depuis `last_scan_at`
- **Hash de contenu** : Utiliser `file_hash` pour détecter modifications même si mtime inchangé
- **Limite de fichiers** : Garder limite raisonnable (ex: 12000) pour éviter timeout

### ⚠️ Synchronisation
- **Fichiers supprimés** : Marquer comme `deleted_at` plutôt que supprimer de BDD (audit)
- **Fichiers déplacés** : Détecter via hash si même fichier à nouveau chemin
- **Conflits** : Gérer cas où fichier modifié pendant scan

### ⚠️ Association Match
- **Confiance** : Stocker `association_confidence` pour permettre révision manuelle
- **Ré-association** : Permettre re-association si matchs ajoutés après scan
- **Tolérance** : Paramètre configurable (`media_tolerance_minutes`)

### ⚠️ Thumbnails
- **Échecs** : Logger erreurs mais ne pas bloquer indexation
- **Espace disque** : Surveiller taille dossier `thumbs/`
- **Format** : Garder compatibilité avec script existant (GIF animé)

---

## Métriques de Succès

| Métrique | Avant | Cible |
|----------|-------|-------|
| Temps chargement page Médias | ~2-5s (scan disque) | <500ms (lecture BDD) |
| Temps scan initial | N/A | <30s pour 1000 fichiers |
| Taux association média→match | ~80% | >90% |
| Thumbnails générés | 0% | >95% des vidéos |

---

## Alternatives Considérées

### ❌ Scan à la demande uniquement
- **Rejeté** : Performance dégradée avec gros volumes

### ❌ Stockage dans fichier JSON
- **Rejeté** : Pas de requêtes efficaces, pas de jointures avec matchs

### ❌ Watcher système (inotify/FSEvents)
- **Considéré** : Complexité élevée, dépendances OS
- **Décision** : Garder pour phase future si besoin temps réel

---

## Références

- Code existant :
  - `src/ui/pages/media_library.py` : Page Médias actuelle
  - `src/ui/pages/match_view_helpers.py` : Fonction `index_media_dir()`
  - `scripts/generate_thumbnails.py` : Script thumbnails existant
- Architecture :
  - `src/db/schema.py` : Schémas tables DuckDB
  - `src/data/repositories/duckdb_repo.py` : Repository pattern

---

## Questions Ouvertes

1. **Fréquence scan** : Au démarrage uniquement ou périodique (ex: toutes les heures) ?
2. **UI feedback** : Afficher indicateur "Indexation en cours..." ?
3. **Thumbnails images** : Générer aussi pour captures d'écran ou seulement vidéos ?
4. **Multi-joueurs** : Table globale ou par joueur ? (Recommandation: par joueur)

---

## Conclusion

**Recommandation finale** : ✅ **IMPLÉMENTER**

Les gains en performance et UX justifient l'effort d'implémentation. L'architecture proposée est :
- ✅ Cohérente avec l'existant (DuckDB, patterns repository)
- ✅ Évolutive (facile d'ajouter métadonnées)
- ✅ Testable (modules isolés)
- ✅ Non-bloquante (tâches en arrière-plan)

**Prochaine étape** : Valider l'architecture avec l'équipe, puis démarrer Phase 1.
