# Plan : Section Carrière — Progression vers le rang Héros

> Planification uniquement — pas de modification de code dans ce document.  
> Date : 2026-02-07

---

## 1. Objectif

Ajouter une **section Carrière** avec une **nouvelle rangée** affichant :
1. Un cercle de progression en pourcentage jusqu’au rang **Héros** (rang 272, le dernier)
2. Des cases indicatrices : XP gagnée, XP restante jusqu’à Héros, total requis, rang actuel / max

---

## 2. Contexte Halo Infinite — Rangs de carrière

| Élément | Valeur |
|--------|--------|
| Rangs totaux | 1 → 272 |
| Rang Héros | **272** (dernier rang) |
| Rang max | 272 |
| Cible de la progression | Rang 272 (Héros) |

- **Rang 1** : Recruit (base)
- **Rangs 2–46** : Bronze (Cadet à General, 3 grades chacun) — 45 rangs
- **Rangs 47–91** : Silver — 45 rangs
- **Rangs 92–136** : Gold — 45 rangs
- **Rangs 137–181** : Platinum — 45 rangs
- **Rangs 182–226** : Diamond — 45 rangs
- **Rangs 227–271** : Onyx — 45 rangs
- **Rang 272** : Héros (grade final)

*Source : [Halopedia — Rank (Halo Infinite)](https://www.halopedia.org/Rank_(Halo_Infinite)). Chaque tier comporte 15 grades militaires × 3 sous-grades = 45 rangs.*

---

## 3. Données disponibles

### 3.1 Sources existantes

| Source | Fichier / Table | Données utiles |
|--------|-----------------|----------------|
| API Economy | `api_client.get_career_rank_progression(xuid)` | `Rank`, `PartialProgress` (XP partiel), `CareerRankData` |
| BDD locale | `career_progression` | `rank`, `current_xp`, `xp_for_next_rank`, `xp_total`, `recorded_at` |
| Métadonnées | `data/cache/career_ranks_metadata.json` | `Ranks[]` avec `Rank`, `XpRequiredForRank` par rang |
| Helper | `career_ranks.py` | `get_rank_info(272)`, `get_all_ranks()`, `get_rank_for_xp(total_xp)` |

### 3.2 XP total et rang Héros

- L’API ne renvoie pas l’XP total ; il est **estimé** via `_compute_total_xp(rank, partial_xp)` dans `api_client.py`.
- **XP cumulée pour atteindre le rang 272 (Héros)** : **9 319 350** (somme des `XpRequiredForRank` des rangs 1 à 272).

---

## 4. Calcul du pourcentage de progression

### 4.1 Deux approches possibles

| Approche | Formule | Avantages | Inconvénients |
|----------|---------|-----------|---------------|
| **A. Par rang** | `(current_rank - 1) / 271 × 100` | Simple, déterministe | Les rangs n’ont pas tous la même difficulté XP |
| **B. Par XP** | `current_xp_total / XP_HERO_TOTAL × 100` | Proche du vrai effort du joueur | XP total estimé |

**Recommandation** : approche **B (par XP)** car plus cohérente avec la notion de progression.

### 4.2 Formule détaillée (approche B)

```
XP_HERO_TOTAL = 9_319_350   # XP cumulée pour atteindre le rang 272 (officiel)
current_xp = xp_total depuis career_progression ou CareerRankData
percentage = min(100, (current_xp / XP_HERO_TOTAL) * 100)
xp_restante = max(0, XP_HERO_TOTAL - current_xp)
```

- Si `current_rank >= 272` → `percentage = 100`, `xp_restante = 0`
- Si métadonnées indisponibles pour fallback → utiliser l’approche A (par rang)

---

## 5. Positionnement UI

### 5.1 Emplacement proposé

- **Zone** : Partie **Carrière** de l’application (nouvelle section ou page dédiée).
- **Layout** : Une **nouvelle rangée** (row) dans cette partie, contenant plusieurs cases sur une même ligne.

### 5.2 Intégration dans le flux

- La section Carrière est rendue dans la partie appropriée (page Carrière ou section dédiée).
- Elle reçoit : `xuid`, `db_path`, `settings`.

---

## 6. Spécifications de la rangée Carrière

### 6.1 Contenu de la rangée (5 cases)

| # | Case | Label | Valeur affichée |
|---|------|-------|-----------------|
| 1 | **XP gagnée** | « XP gagnée » | Nombre : XP totale actuelle du joueur (ex. 1 234 567) |
| 2 | **XP restante** | « XP restante jusqu’à Héros » | Nombre : `XP_HERO_TOTAL - current_xp` (ex. 8 084 783) |
| 3 | **Total requis** | « Total requis pour Héros » | Nombre fixe : 9 319 350 |
| 4 | **Rang** | « Rang » | Texte : « Rang actuel / 272 » (ex. « 150 / 272 ») |
| 5 | **Progression** | « Progression » | Cercle de progression : pourcentage 0–100 %, style donut/gauge |

### 6.2 Disposition

- Une **rangée unique** avec les 5 cases alignées (ex. `st.columns(5)` ou mise en page équivalente).
- Chaque case : titre + valeur mise en forme (nombre avec séparateurs de milliers, ex. 9 319 350).

### 6.3 Comportement

- **Données manquantes** : si pas de `career_progression` et pas d’API → afficher un message discret (ex. « Sync pour afficher la progression ») ou masquer la rangée.
- **Joueur déjà Héros (rang 272)** : cercle à 100 %, XP restante = 0.
- **Fallback** : sans données XP fiables, utiliser l’approche par rang (approche A).

### 6.4 Choix technique pour le cercle (case 5)

Streamlit n’a pas de composant circulaire natif. **Plotly gauge** recommandé, déjà utilisé ailleurs (radars).

---

## 7. Architecture technique prévue

### 7.1 Nouveaux fichiers

| Fichier | Rôle |
|---------|------|
| `src/ui/components/career_progress_circle.py` | Composant réutilisable : cercle + calcul du pourcentage |
| (optionnel) `src/app/career_section.py` | Section carrière (chargement données + rendu) |

### 7.2 Constantes et fonctions à créer

```text
# Constantes
XP_HERO_TOTAL = 9_319_350   # XP cumulée pour atteindre le rang 272
RANK_MAX = 272              # Rang max = Héros

# Dans career_progress_circle.py
def compute_career_progress_percent(
    current_rank: int,
    xp_total: int | None,
    *,
    use_xp_based: bool = True,
) -> float:
    """Calcule le pourcentage de progression vers le rang 272.
    Returns: 0.0 à 100.0
    """

def compute_xp_remaining(xp_total: int) -> int:
    """Retourne l'XP restante jusqu'à Héros. max(0, XP_HERO_TOTAL - xp_total)"""

def render_career_progress_circle(
    percentage: float,
    *,
    current_rank: int | None = None,
    rank_label: str | None = None,
    size: int = 120,
) -> None:
    """Affiche le cercle de progression (Plotly gauge)."""

def format_xp_number(value: int) -> str:
    """Formate un nombre XP (ex. 9319350 → '9 319 350' ou '9,3M')."""
```

### 7.3 Cas de la rangée Carrière

La section `render_career_section()` affiche une **rangée** avec 5 cases :
1. XP gagnée (current_xp_total)
2. XP restante jusqu’à Héros (XP_HERO_TOTAL - current_xp)
3. Total requis (9 319 350)
4. Rang actuel / 272
5. Cercle de progression (%)

### 7.4 Chargement des données

| Priorité | Source | Méthode |
|----------|--------|---------|
| 1 | BDD | `DuckDBRepository` ou `DuckDBSyncEngine.get_latest_career_rank()` sur `career_progression` |
| 2 | API | Si BDD vide et tokens OK → `api_client.get_career_rank_progression(xuid)` |
| 3 | Aucune | Ne pas afficher la case ou afficher un message d’attente |

- Pour DuckDB v4 : le chemin DB du joueur est `data/players/{gamertag}/stats.duckdb`.
- La sync career rank est faite via `sync_career_rank()` dans l’engine ; s’assurer qu’elle est bien appelée lors de la sync (ou lors du premier affichage si besoin).

---

## 8. Dépendances et conditions

### 8.1 Prérequis

- Constante `XP_HERO_TOTAL = 9_319_350` utilisée pour le calcul du pourcentage (voir § 4.2).
- Au moins une des sources : `career_progression` en BDD ou API Economy accessible.

### 8.2 Sync career

- Vérifier que `sync_career_rank()` est invoquée dans le flux de synchronisation (`sync.py` / engine) pour que `career_progression` soit alimentée.
- Si ce n’est pas le cas, ajouter cette étape au plan de sync (hors périmètre du présent plan UI).

---

## 9. Points de décision (validés)

1. **Cible** : Rang **272** (Héros, dernier rang).
2. **Emplacement** : Nouvelle **rangée** dans la partie **Carrière** (pas la sidebar).
3. **Données** : BDD en priorité, puis API si vide.
4. **Fallback** : utiliser la progression par rang (approche A) si besoin.

---

## 10. Checklist d’implémentation (ordre suggéré)

- [ ] 1. Créer `career_progress_circle.py` avec constantes, `compute_career_progress_percent()`, `compute_xp_remaining()`, `format_xp_number()`, `render_career_progress_circle()`.
- [ ] 2. Vérifier / compléter la logique de chargement des données (BDD puis API).
- [ ] 3. Créer `render_career_section(xuid, db_path, settings)` : une **rangée** avec les 5 cases.
- [ ] 4. Intégrer l’appel dans la partie Carrière de l’app.
- [ ] 5. Gérer les cas sans données (message ou masquage).
- [ ] 6. Ajuster le style (formatage nombres, couleurs) pour cohérence avec LevelUp.
- [ ] 7. Vérifier que `sync_career_rank` est bien exécutée lors de la sync.

---

## 11. Sprints d’implémentation

### Sprint 1 : Constantes, calculs et formatage (½ jour)

| # | Tâche | Fichier | Détail |
|---|-------|---------|--------|
| S1.1 | Constantes | `career_progress_circle.py` | `XP_HERO_TOTAL = 9_319_350`, `RANK_MAX = 272` |
| S1.2 | `compute_career_progress_percent()` | `career_progress_circle.py` | Calcul 0–100 vers rang 272, fallback par rang |
| S1.3 | `compute_xp_remaining()` | `career_progress_circle.py` | `max(0, XP_HERO_TOTAL - xp_total)` |
| S1.4 | `format_xp_number()` | `career_progress_circle.py` | Formatage lisible (ex. 9 319 350 ou 9,3M) |
| S1.5 | `render_career_progress_circle()` | `career_progress_circle.py` | Gauge Plotly : cercle, pourcentage central |
| S1.6 | Tests unitaires | `tests/test_career_progress_circle.py` | Rang 1, 135, 272 ; xp_remaining ; cas sans données |

**Livrable** : module isolé testable avec calculs et formatage XP.

---

### Sprint 2 : Chargement des données (½ jour)

| # | Tâche | Fichier | Détail |
|---|-------|---------|--------|
| S2.1 | Lecture `career_progression` | Nouveau helper ou `main_helpers` | `get_latest_career_rank(db_path, xuid)` via DuckDBSyncEngine ou SQL direct |
| S2.2 | Fallback API | Idem | Si BDD vide et tokens OK → `api_client.get_career_rank_progression(xuid)` |
| S2.3 | Vérifier `sync_career_rank` | `sync.py` / engine | S’assurer que la sync appelle `sync_career_rank()` pour alimenter `career_progression` |
| S2.4 | Interface de chargement | `career_section.py` ou `main_helpers` | `load_career_data(db_path, xuid, settings) -> CareerRankData | None` |

**Livrable** : fonction `load_career_data()` qui retourne rank + xp_total (BDD prioritaire, API en secours).

---

### Sprint 3 : Rangée Carrière (5 cases) (¾ jour)

| # | Tâche | Fichier | Détail |
|---|-------|---------|--------|
| S3.1 | `render_career_section()` | `career_section.py` | **Nouvelle rangée** dans la partie Carrière |
| S3.2 | Case 1 — XP gagnée | Idem | Valeur : `current_xp_total` (formatée) |
| S3.3 | Case 2 — XP restante | Idem | Valeur : `XP_HERO_TOTAL - current_xp` (nombre, formaté) |
| S3.4 | Case 3 — Total requis | Idem | Valeur fixe : 9 319 350 (formaté) |
| S3.5 | Case 4 — Rang | Idem | Valeur : « rang_actuel / 272 » (ex. 150 / 272) |
| S3.6 | Case 5 — Cercle | Idem | `render_career_progress_circle(percentage)` |
| S3.7 | Layout | Idem | `st.columns(5)` ou équivalent pour aligner les 5 cases |
| S3.8 | Gestion sans données | Idem | Message « Sync pour afficher » ou masquer la rangée |

**Livrable** : rangée Carrière complète avec les 5 cases sur une ligne.

---

### Sprint 4 : Intégration et polish (½ jour)

| # | Tâche | Fichier | Détail |
|---|-------|---------|--------|
| S4.1 | Intégration partie Carrière | `streamlit_app.py` ou page dédiée | Appel `render_career_section(xuid, db_path, settings)` |
| S4.2 | Style et thème | CSS / Plotly | Couleurs LevelUp, lisibilité des nombres |
| S4.3 | Mise à jour CLAUDE.md / thought_log | `.ai/` | Documenter section Carrière et constantes |

**Livrable** : section Carrière fonctionnelle et documentée.

---

### Récapitulatif

| Sprint | Durée | Objectif |
|--------|-------|----------|
| S1 | ½ j | Constantes, calculs, formatage, cercle |
| S2 | ½ j | Chargement données (BDD + API) |
| S3 | ¾ j | Rangée Carrière (5 cases) |
| S4 | ½ j | Intégration + polish |
| **Total** | **~2,25 j** | |

---

## 12. Références

- `src/data/sync/api_client.py` : `get_career_rank_progression`, `_compute_total_xp`, `_get_rank_info`
- `src/data/sync/engine.py` : `sync_career_rank`, `get_latest_career_rank`, table `career_progression`
- `src/ui/career_ranks.py` : `get_rank_info`, `get_all_ranks`, `get_rank_for_xp`
- `src/app/main_helpers.py` : `render_profile_hero`
- `streamlit_app.py` : structure de l’app et flux de rendu
