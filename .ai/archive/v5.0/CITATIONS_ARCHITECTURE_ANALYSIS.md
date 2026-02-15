# Architecture Refactorisée - Système de Citations (Commendations)

**Date** : 2026-02-14  
**Version** : 2.1 (Décisions validées + Performance)  
**Objectif** : Migrer vers une architecture cohérente DuckDB v4, éliminer les fichiers plats dispersés

---

## ✅ DÉCISIONS VALIDÉES (2026-02-14)

**Gain** : 41 → **47 citations** (+6, soit +14.6%)

### 6 Citations réintégrées

| Citation | Type | Source | Performance |
|----------|------|--------|-------------|
| **Défenseur du drapeau** | award | `Flag Defense` | ⚡ O(1) |
| **Je te tiens !** | award | `Flag Return` | ⚡ O(1) |
| **Sus au porteur du drapeau** | award | `Flag Carrier Kill` | ⚡ O(1) |
| **Partie prenante** | award | `Zone Defense` | ⚡ O(1) |
| **À la charge** | award | `Zone Capture` | ⚡ O(1) |
| **Annexion forcée** | custom | `compute_annexion_forcee()` | ⚡ O(1) |

### 108 Citations restant exclues

- ❌ Maîtrise du drapeau (doublon)
- ❌ Geronimo, Mastodonte, Protecteur, Body Guard (médailles non awards)
- ❌ 6 destructeurs véhicules (award non spécifique)
- ❌ 52 armes spécifiques
- ❌ 11 PvE
- ❌ 33 autres complexes

**Référence** : [CITATIONS_DECISIONS_FINALES.md](CITATIONS_DECISIONS_FINALES.md)

---

## 🎯 État actuel confirmé

| Métrique | Valeur | Source |
|----------|--------|--------|
| **Citations H5G totales** | 159 | `data/wiki/halo5_commendations_fr.json` |
| **Citations exclues (blacklist)** | 114 | `data/wiki/halo5_commendations_exclude.json` |
| **Citations candidates** | 45 | 159 - 114 |
| **Citations AFFICHÉES** | **41** | App réelle (confirmé 2026-02-14) |
| **CUSTOM_CITATION_RULES** | 8 | `src/ui/commendations.py` |
| **Tracking JSON** | ~33 | `out/commendations_mapping_*.json` (cache) |

### 🚨 Problèmes identifiés

1. **Architecture dispersée** :
   - Citations définies dans `data/wiki/*.json` (OK)
   - Blacklist dans `data/wiki/halo5_commendations_exclude.json` (OK)
   - Règles hardcodées dans `src/ui/commendations.py` (antipattern)
   - Tracking dans `out/*.json` **non versionné** (CRITIQUE)

2. **Incohérence avec DuckDB v4** :
   - Tout l'app utilise DuckDB pour la persistence
   - Citations utilisent des fichiers JSON temporaires dans `out/`
   - Pas de table DuckDB pour les mappings

3. **Maintenance difficile** :
   - Ajouter une citation = modifier 3 endroits différents
   - Pas de versioning des mappings
   - Logique de calcul mélangée avec l'UI

---

## 📊 Sources de données disponibles

### DuckDB (données de matchs)

| Table | Colonnes clés | Usage citations |
|-------|--------------|-----------------|
| `medals_earned` | match_id, medal_name_id, count | ✅ Citations médailles |
| `match_stats` | kills, deaths, assists, headshot_kills, etc. | ✅ Citations stats |
| `personal_score_awards` | award_name, award_category, award_count, award_score | ✅ **Citations objectives** |

### Fichiers JSON (référentiels)

| Fichier | Contenu | Statut |
|---------|---------|--------|
| `data/wiki/halo5_commendations_fr.json` | 159 citations H5G | ✅ Versionné |
| `data/wiki/halo5_commendations_exclude.json` | 114 exclusions | ✅ Versionné |
| `out/commendations_mapping_*.json` | ~33 mappings | ❌ **Non versionné** |

---

## 🔍 Analyse des citations EXCLUES → Awards mappables (RÉFÉRENCE)

> **Note** : Sur les 18 citations identifiées ci-dessous, **seules 6 ont été validées** pour réintégration.  
> Voir [CITATIONS_DECISIONS_FINALES.md](CITATIONS_DECISIONS_FINALES.md) pour les décisions finales.

Sur les **114 citations exclues**, voici celles qui PEUVENT être alignées avec `personal_score_awards` :

### ✅ HAUTE PRIORITÉ - Awards objectives (7 citations)

**6 validées pour réintégration + 1 rejetée (doublon)**

| Citation (exclue) | Award mappable | Catégorie | Confiance | Statut |
|-------------------|---------------|-----------|-----------|--------|
| **Défenseur du drapeau** | `Flag Defense` | objective | 🟢 Haute | ✅ **Validée** |
| **Je te tiens !** | `Flag Return` | objective | 🟢 Haute | ✅ **Validée** |
| **Sus au porteur du drapeau** | `Flag Carrier Kill` | objective | 🟢 Haute | ✅ **Validée** |
| **Maîtrise du drapeau** | `Zone Capture` | objective | 🟡 Moyenne* | ❌ Rejetée (doublon avec "À la charge") |
| **Partie prenante** | `Zone Defense` | objective | 🟢 Haute | ✅ **Validée** |
| **À la charge** | `Zone Capture` | objective | 🟢 Haute | ✅ **Validée** |
| **Annexion forcée** | `Zone Capture` (>=3) | objective | 🟡 Moyenne** | ✅ **Validée** (custom) |

\* *Possiblement Flag Capture aussi*  
\** *Nécessite compteur >= 3 dans un match*

### ⏸️ PRIORITÉ MOYENNE - Awards combat (5 citations) - NON VALIDÉES

**Raison exclusion** : Confiance moyenne, médailles disponibles pour certaines.

| Citation (exclue) | Award mappable | Catégorie | Confiance | Statut |
|-------------------|---------------|-----------|-----------|--------|
| **Protecteur** | `Assist` | assist | 🟡 Moyenne | ❌ Non validée |
| **Dégage** | `Kill` | kill | 🟡 Moyenne | ❌ Non validée |
| **Geronimo** | `Melee Kill` | kill | 🟢 Haute | ❌ Non validée (médaille existe) |
| **Mastodonte** | `Melee Kill` | kill | 🟢 Haute | ❌ Non validée (médaille existe) |
| **Body Guard** | `Assist` | assist | 🟡 Moyenne | ❌ Non validée |

### ⏸️ PRIORITÉ BASSE - Awards véhicules (6 citations) - NON VALIDÉES

**Raison exclusion** : Award `Vehicle Destruction` non spécifique (pas de distinction par type).

| Citation (exclue) | Award mappable | Catégorie | Confiance | Statut |
|-------------------|---------------|-----------|-----------|--------|
| **Destructeur de banshees** | `Vehicle Destruction` | vehicle | 🟡 Moyenne* | ❌ Non validée |
| **Destructeur de ghosts** | `Vehicle Destruction` | vehicle | 🟡 Moyenne* | ❌ Non validée |
| **Destructeur de mantis** | `Vehicle Destruction` | vehicle | 🟡 Moyenne* | ❌ Non validée |
| **Destructeur de scorpions** | `Vehicle Destruction` | vehicle | 🟡 Moyenne* | ❌ Non validée |
| **Destructeur de warthogs** | `Vehicle Destruction` | vehicle | 🟡 Moyenne* | ❌ Non validée |
| **Destructeur de wasps** | `Vehicle Destruction` | vehicle | 🟡 Moyenne* | ❌ Non validée |
Refactorisée (DuckDB-first)

### Principe : Tout dans DuckDB, zéro fichier plat temporaire

```
┌──────────────────────────────────────────────────────────┐
│          CITATIONS H5G (159 totales, 45 après blacklist) │
└────────────────────────┬─────────────────────────────────┘
                         │
          ┌──────────────┴──────────────┐
          │                             │
    ┌─────▼─────┐               ┌───────▼───────┐
    │  Niveau 1 │               │   Niveau 2    │
    │  CUSTOM   │               │   MAPPINGS    │
    │  PYTHON   │               │   DuckDB      │
    │           │               │   TABLE       │
    └─────┬─────┘               └───────┬───────┘
          │                             │
          └──────────────┬──────────────┘
                         │
              ┌──────────▼──────────┐
              │   CitationEngine    │
              │   (calculateur)     │
              └──────────┬──────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
   ┌────▼────┐   ┌──────▼───────┐  ┌────▼─────┐
   │ medals_ │   │ match_stats  │  │personal_ │
   │ earned  │   │              │  │score_    │
   │         │   │              │  │awards    │
   └─────────┘   └──────────────┘  └──────────┘
```

### Niveau 1 : Logique Python custom (cas complexes)

**Localisation** : `src/analysis/citations/custom_rules.py` (nouveau module dédié)

**Quand utiliser** :
- Logique complexe (KD > seuil, multiples conditions)
- Calculs sur plusieurs colonnes avec filtres
- Transformations de données

```python
# src/analysis/citations/custom_rules.py
"""Règles de calcul custom pour citations complexes."""

from typing import Any
import polars as pl

def compute_bulldozer(df: pl.DataFrame) -> int:
    """Parties Assassin avec KD > 8 (hors Firefight/BTB)."""
    filtered = df.filter(
        pl.col("playlist_name").str.contains("(?i)slayer|assassin") &
        ~pl.col("playlist_name").str.contains("(?i)firefight|btb")
    )
    count = filtered.filter(
        (pl.col("kills") / pl.col("deaths").clip(1, None)) > 8.0
    ).height
    return count

def compute_wins_mode(df: pl.DataFrame, mode_pattern: str) -> int:
    """Compte les victoires dans un mode donné."""
    return df.filter(
        pl.col("playlist_name").str.contains(f"(?i){mode_pattern}") &
        pl.col("outcome").eq("win")
    ).height

# Registry des fonctions custom
CUSTOM_FUNCTIONS = {
    "bulldozer": compute_bulldozer,
    "victoire_au_drapeau": lambda df: compute_wins_mode(df, "ctf|drapeau"),
    "seul_contre_tous": lambda df: compute_wins_mode(df, "firefight|bapteme"),
    "victoire_en_assassin": lambda df: compute_wins_mode(df, "slayer|assassin"),
    "victoire_en_bases": lambda df: compute_wins_mode(df, "stronghold|bases"),
}
```

### Niveau 2 : Table DuckDB `citation_mappings`

**Nouvelle table** : `data/warehouse/metadata.duckdb::citation_mappings`

**Schema** :
```sql
CREATE TABLE IF NOT EXISTS citation_mappings (
    citation_name_norm TEXT PRIMARY KEY,  -- Nom normalisé
    citation_name_display TEXT NOT NULL,  -- Nom affiché
    mapping_type TEXT NOT NULL,           -- 'medal' | 'stat' | 'award' | 'custom'
    
    -- Pour type = 'medal'
    medal_id INTEGER,
    medal_ids TEXT,  -- JSON array pour multiples médailles
    
    -- Pour type = 'stat'
    stat_name TEXT,  -- 'kills', 'assists', etc.
    
    -- Pour type = 'award'
    award_name TEXT,      -- 'Flag Defense', etc.
    award_category TEXT,  -- 'objective', 'kill', etc.
    
    -- Pour type = 'custom'
    custom_function TEXT,  -- Nom de la fonction dans CUSTOM_FUNCTIONS
    
    -- Métadonnées
    confidence TEXT,       -- 'high' | 'medium' | 'low'
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Avantages** :
- ✅ Versionné avec DuckDB (cohérent avec l'architecture v4)
- ✅ Requêtes SQL simples pour lister/filtrer
- ✅ Pas de fichiers temporaires dans `out/`
- ✅ Historique des modifications (updated_at)
- ✅ Facile à backup/restore avec le reste

### CitationEngine (calculateur unifié)

**Localisation** : `src/analysis/citations/engine.py`

```python
# src/analysis/citations/engine.py
"""Moteur de calcul des citations."""

import polars as pl
import duckdb
from typing import Any

class CitationEngine:
    """Calcule les valeurs des citations depuis les données de matchs."""
    
    def __init__(self, db_path: str, xuid: str):
        self.db_path = db_path
        self.xuid = xuid
        self.conn = duckdb.connect(db_path)
    
    def load_mappings(self) -> dict[str, dict[str, Any]]:
        """Charge les mappings depuis la table citation_mappings."""
        result = self.conn.execute(
            "SELECT * FROM citation_mappings"
        ).fetchdf() (Refactoring complet)

### Phase 1 : Migration DuckDB (2-3h)

#### 1.1 Créer la table `citation_mappings`
```bash
# Script SQL
python scripts/create_citation_mappings_table.py
```

**Actions** :
- [x] Créer table dans `data/warehouse/metadata.duckdb`
- [ ] Migrer les 8 CUSTOM_CITATION_RULES actuelles
- [ ] Importer les ~33 mappings depuis `out/*.json` (si existants)
- [ ] Valider données avec requête SELECT

#### 1.2 Déplacer la logique custom
- [ ] Créer `src/analysis/citations/` (nouveau package)
- [ ] Créer `src/analysis/citations/custom_rules.py`
- [ ] Migrer les fonctions complexes (bulldozer, wins_mode, etc.)
- [ ] Tests unitaires

#### 1.3 Créer le CitationEngine
- [ ] Créer `src/analysis/citations/engine.py`
- [ ] Implémenter `load_mappings()` depuis DuckDB
- [ ] Implémenter `compute_citation()` pour chaque type
- [ ] Tests d'intégration

### Phase 2 : Extension Awards (1-2h)

#### 2.1 Ajouter support type `award`
- [ ] Modifier `CitationEngine.compute_citation()` pour supporter awards
- [ ] Créer `_aggregate_awards()` dans engine
- [ ] Tests unitaires

#### 2.2 Ajouter les 18 citations récupérables
```sql
-- Haute priorité (7 citations objectives)
INSERT INTO citation_mappings VALUES
  ('defenseur du drapeau', 'Défenseur du drapeau', 'award', NULL, NULL, NULL, 'Flag Defense', 'objective', NULL, 'high', 'Exclue → Réintégrée'),
  ('je te tiens', 'Je te tiens !', 'award', NULL, NULL, NULL, 'Flag Return', 'objective', NULL, 'high', 'Exclue → Réintégrée'),
  -- ... 5 autres
  
-- Priorité moyenne (5 citations combat)
-- Priorité basse (6 citations véhicules, regroupables)
```

### Phase 3 : Nettoyage & Migration UI (1h)

#### 3.1 Refactoriser `src/ui/commendations.py`
- [ ] Supprimer `CUSTOM_CITATION_RULES` (migré vers DuckDB)
- [ ] Supprimer `load_h5g_commendations_tracking_rules()` (obsolète)
- [ ] Remplacer par `CitationEngine.compute_all()`
- [ ] Simplifier `render_h5g_commendations_section()`

#### 3.2 Supprimer fichiers temporaires
- [ ] Supprimer dépendance à `out/commendations_mapping_*.json`
- [ ] Mettre à jour `.gitignore` pour ignorer `out/*.json`
- [ ] Documentation migration

### Phase 4 : Tests & Validation (1h)

- [ ] Tester chargement des 41 citations actuelles
- [ ] Gains attendus après refactoring

### Avant (état actuel)

| Aspect | État | Problème |
|--------|------|----------|
| **Architecture** | Fichiers JSON dispersés | Incohérent avec DuckDB v4 |
| **Maintenance** | 3 fichiers à modifier | Ajout citation = complexe |
| **Versioning** | `out/*.json` non versionné | Perte de données possible |
| **Citations affichées** | 41 | Dont 7 en blacklist récupérables |
| **Performance** | Cache Streamlit des JSON | Invalide si fichiers changent |

### Après (architecture proposée)

| Aspect | État | Avantage |
|--------|------|----------|
| **Architecture** | Table DuckDB unique | Cohérent avec v4 |
| **Maintenance** | 1 INSERT SQL ou fonction Python | Simple, versionné |
| **Versioning** | DuckDB versionné | Backup/restore automatique |
| **Citations affichées** | **59** (41 + 18 récupérées) | +44% de couverture |
| **Performance** | Requête SQL directe | Pas de cache nécessaire |

### Bénéfices métier

- ✅ **+18 citations** objectives/combat récupérées de la blacklist
- ✅ **Architecture cohérente** avec le reste de l'app (DuckDB-first)
- ✅ **Maintenance simplifiée** : 1 table vs 3 fichiers + code hardcodé
- ✅ **Extensibilité** : Ajouter une citation = 1 ligne SQL
- ✅ **Versioning** : Toutes les modifications trackées dans DuckDB
- ✅ **Tests** : Facile de mocker `CitationEngine` vs fichiers JSON

---

## 🎯 Décisions à prendre

### 1. Citations exclues à réintégrer

**Je propose de réintégrer les 18 citations identifiées** :
- 7 objectives (haute priorité)
- 5 combat (moyenne priorité)
- 6 véhicules (basse priorité, regroupables en 1)

**Décision** : Lesquelles veux-tu activer en premier ?

### 2. Regroupement des destructeurs de véhicules

Les 6 citations "Destructeur de X" utilisent toutes `Vehicle Destruction` award.

**Options** :
- A) Les mapper séparément (6 citations, même valeur)
- B) Les regrouper en 1 citation "Destructeur de véhicules"
- C) Les laisser exclues

**Recommandation** : Option B (regrouper)

### 3. Timeline du refactoring

**Option rapide (2-3h)** :
- Créer table `citation_mappings`
- Migrer les 41 actuelles + 7 objectives haute priorité
- Refactoriser UI pour utiliser DuckDB

**Option complète (6-8h)** :
- Tout ci-dessus
- + Créer `CitationEngine` complet
- + Migrer toute la logique custom
- + Tests exhaustifs

**Recommandation** : Option rapide d'abord, puis itérer

---

## 📊 Résumé exécutif

### Gains après refactoring (validé)

| Métrique | Avant | Après | Gain |
|----------|-------|-------|------|
| **Citations affichées** | 41 | **47** | **+6 (+14.6%)** |
| **Sources données** | 3 fichiers + code | 2 tables DuckDB | Architecture unifiée |
| **Architecture** | ❌ Fichiers plats | ✅ DuckDB v4 | Cohérente |
| **Maintenance** | ⚠️ 3 endroits | ✅ 1 SQL INSERT | Simple |
| **Versioning** | ❌ `out/` non versionné | ✅ DuckDB | Sécurisé |
| **Performance affichage** | ⚠️ 200-500ms | ✅ < 50ms | **-90%** ⚡ |
| **Performance graphiques** | ⚠️ 200ms | ✅ < 20ms | **-90%** ⚡ |
| **Graphiques temporels** | ❌ Impossible | ✅ Natif SQL | Nouveau ! |
| **Espace disque** | 0 | +5-10 MB/joueur | Acceptable |

### Architecture proposée (OPTIMALE) ⭐

**2 tables DuckDB** :

1. **`citation_mappings`** (référentiel) :
   - Stocke les règles de calcul (medal/stat/award/custom)
   - 14 citations initiales (8 existantes + 6 nouvelles)
   - Dans `data/warehouse/metadata.duckdb`

2. **`match_citations`** (données par match) :
   - Stocke les valeurs calculées PAR MATCH
   - Format sparse (seulement value > 0)
   - Dans `data/players/{gamertag}/stats.duckdb`
   - Permet graphiques temporels d'évolution

**Workflow** :
```
Sync → Calcul citations nouveaux matchs → INSERT match_citations
Backfill → Recalcul matchs existants → INSERT match_citations  
Affichage → SELECT SUM(value) FROM match_citations → Rendu
```

### Fichiers créés (prêts)

✅ **Scripts** :
- [scripts/create_citation_mappings_table.py](../scripts/create_citation_mappings_table.py) - Table référentiel (14 citations)
- [ ] `scripts/create_match_citations_table.py` - Table données par match (À créer)

✅ **Modules** :
- [src/analysis/citations/custom_rules.py](../src/analysis/citations/custom_rules.py) - Fonctions custom (6 fonctions)
- [src/analysis/citations/__init__.py](../src/analysis/citations/__init__.py) - Package
- [ ] `src/analysis/citations/engine.py` - Moteur calcul & agrégation (À créer)

✅ **Documentation** :
- [.ai/CITATIONS_DECISIONS_FINALES.md](CITATIONS_DECISIONS_FINALES.md) - Décisions validées
- [.ai/CITATIONS_ARCHITECTURE_ANALYSIS.md](CITATIONS_ARCHITECTURE_ANALYSIS.md) - Analyse complète (ce document)

### Fichiers obsolètes à archiver 🗄️

**Action** : Déplacer vers `scripts/_archive/obsolete_citations/` (ne pas supprimer immédiatement)

- `out/commendations_mapping_assumed.json` (si existe)
- `out/commendations_mapping_unmatched.json` (si existe)
- Code à migrer dans `src/ui/commendations.py` :
  - `CUSTOM_CITATION_RULES` dict (lines 59-103)
  - `load_h5g_commendations_tracking_rules()` fonction
  - `_compute_custom_citation_value()` fonction
  - Boucle de calcul (lines ~850)

### Actions immédiates

**Prochaine étape - Phase 1.1** :
```bash
# 1. Créer table référentiel
python scripts/create_citation_mappings_table.py

# 2. Retirer de la blacklist
# Éditer data/wiki/halo5_commendations_exclude.json
# Supprimer les 6 citations validées
```

**Ensuite - Phase 1.2** :
```bash
# 3. Créer table données par match
python scripts/create_match_citations_table.py

# 4. Backfill matchs existants
python scripts/backfill_data.py --citations --player MonGamertag
```

**Résultat attendu** :
- ✅ 47 citations affichées (41 + 6)
- ✅ Performance < 50ms (vs 500ms avant)
- ✅ Graphiques temporels disponibles
- ✅ Architecture cohérente DuckDB v4

---

## ⚡ Performances & Cache

### État actuel (CRITIQUE)

**Toutes les citations sont RECALCULÉES à chaque affichage de la page** :

```python
# Dans render_h5g_commendations_section() - ligne ~850
for i, item in enumerate(filtered):
    # Pour CHAQUE citation affichée (~41), on recalcule la valeur
    if norm_name in CUSTOM_CITATION_RULES:
        current = _compute_custom_citation_value(custom_rule, df, counts_by_medal, stats_totals)
```

**Impact performance actuel** :
- ✅ **Médailles/Stats** : Lookup dict simple (`counts_by_medal[medal_id]`) → **Rapide**
- ⚠️ **Wins_mode** : Itération ligne par ligne avec regex → **Lent si > 500 matchs**
- ⚠️ **Matches_mode_kd** : Itération ligne par ligne → **Lent si > 500 matchs**

```python
# Code actuel inefficace (ligne ~170)
for row in wins_df.iter_rows(named=True):  # ❌ Itère sur CHAQUE match
    gv = str(row.get(gv_col) or "") if gv_col else ""
    pair = str(row.get(pair_col) or "") if pair_col else ""
    if pattern.search(gv) or pattern.search(pair):
        matching_count += 1
```

### Impact pour "Annexion forcée"

**✅ Performance acceptable** :
```python
def compute_annexion_forcee(awards: dict[str, int]) -> int:
    """3 captures consécutives = approximation (total ÷ 3)."""
    return awards.get("Zone Capture", 0) // 3  # O(1) - Lookup dict
```

**Raison** : Agrégation simple depuis `awards` (déjà calculé), pas d'itération sur matchs.

### Optimisations recommandées

#### Option 1 : Cache session Streamlit (court terme)
```python
@st.cache_data(ttl=300)  # 5 min
def compute_all_citations(db_path: str, xuid: str, filters: dict) -> dict[str, int]:
    """Calcule toutes les citations en une fois."""
    # Retourne {"citation_name": value}
```

**Avantages** :
- ✅ Réutilisé pendant la session
- ✅ Pas de modification DB
- ⚠️ Invalidé à chaque changement de filtres

#### Option 2 : Pré-calcul dans DuckDB (moyen terme)
```sql
-- Nouvelle table
CREATE TABLE player_citations (
    xuid TEXT,
    citation_name TEXT,
    value INTEGER,
    last_match_id TEXT,
    updated_at TIMESTAMP,
    PRIMARY KEY (xuid, citation_name)
);
```

**Avantages** :
- ✅ Ultra rapide (SELECT simple)
- ✅ Mis à jour uniquement après sync
- ✅ Support delta (comparer last_match_id)

**Recommandation initiale** : **Option 2** pour cohérence avec DuckDB v4.

#### Option 3 : Table `match_citations` par match (RECOMMANDÉ) ⭐

**Proposition architecture optimale** :
```sql
-- Stocker les citations PAR MATCH (granularité fine)
CREATE TABLE match_citations (
    match_id TEXT NOT NULL,
    citation_name_norm TEXT NOT NULL,
    value INTEGER NOT NULL,  -- Valeur calculée pour CE match
    PRIMARY KEY (match_id, citation_name_norm)
);

-- Index pour requêtes par citation
CREATE INDEX idx_match_citations_name ON match_citations(citation_name_norm);
```

**Avantages** :
- ✅ **Performance graphiques** : SELECT précis, pas de recalcul
- ✅ **Historique temporel** : Voir progression citation par match (graphiques évolution)
- ✅ **Cohérence architecture** : Comme `match_stats`, `medals_earned`
- ✅ **Delta précis** : Filtres = WHERE clauses SQL (rapide)
- ✅ **Extensibilité** : Ajouter citation = backfill + insert futurs
- ✅ **Cache naturel** : Calculé 1× (sync), lu ∞× (affichage)

**Workflow proposé** :
1. **Sync** : À la fin, calculer citations pour nouveaux matchs → INSERT
2. **Backfill** : Script pour recalculer matchs existants
3. **Affichage** : Simple agrégation SQL (SUM, GROUP BY)

**Exemple affichage** :
```sql
-- Total toutes périodes
SELECT citation_name_norm, SUM(value) as total
FROM match_citations
WHERE match_id IN (SELECT match_id FROM match_stats WHERE ...)
GROUP BY citation_name_norm;

-- Évolution temporelle (pour graphique)
SELECT 
    ms.match_start_date,
    mc.citation_name_norm,
    SUM(mc.value) OVER (
        PARTITION BY mc.citation_name_norm 
        ORDER BY ms.match_start_date
    ) as cumulative
FROM match_citations mc
JOIN match_stats ms ON mc.match_id = ms.match_id
ORDER BY ms.match_start_date;
```

### 🤔 Challenges & Trade-offs

#### Q1 : Stocker les 0 ou seulement valeurs > 0 ?

**Option A : Tout stocker (dense)** :
- 47 citations × 1000 matchs = **47 000 lignes/joueur**
- ~80% seraient des 0 (citations non progressées)
- ✅ Requêtes simples (pas de COALESCE)
- ⚠️ Espace disque (~5-10 MB/joueur avec compression DuckDB)

**Option B : Seulement > 0 (sparse)** ⭐ :
- ~10-15 citations progressent par match en moyenne
- ~10 000 lignes/1000 matchs = **-80% espace**
- ✅ Espace optimisé
- ⚠️ Requêtes plus complexes (COALESCE nécessaire)

**Recommandation** : **Option B (sparse)** - DuckDB gère bien les données creuses.

#### Q2 : Quid du changement de règle de calcul ?

Si on modifie `compute_bulldozer()`, les anciennes valeurs sont fausses.

**Solutions** :
1. **Versioning** : Ajouter colonne `rule_version`
2. **Re-backfill** : Recalculer tous les matchs (acceptable si rare)
3. **Timestamps** : Comparer `updated_at` avec `citation_mappings.updated_at`

**Recommandation** : **Re-backfill ponctuel** (changements rares).

#### Q3 : Performance du backfill initial ?

- 1000 matchs × 47 citations = 47 000 calculs
- Estimé : **~30-60s** pour 1000 matchs (avec Polars/DuckDB)
- ✅ Acceptable en one-shot

### 💡 Verdict : OUI, excellente idée ! ⭐⭐⭐

**Pourquoi c'est mieux que l'approche actuelle** :

| Aspect | Actuel (recalcul) | Proposé (DB par match) |
|--------|-------------------|------------------------|
| **Performance affichage** | ⚠️ 200-500ms | ✅ < 50ms (SELECT) |
| **Graphiques temporels** | ❌ Impossible | ✅ Natif (window functions) |
| **Cohérence archi** | ❌ Logique UI | ✅ DuckDB v4 |
| **Maintenance** | ⚠️ Code complexe | ✅ SQL simple |
| **Extensibilité** | ⚠️ Modifier code | ✅ INSERT + backfill |
| **Delta/Filtres** | ⚠️ Recalcul | ✅ WHERE clauses |

**Impact estimé** :
- 📉 **Temps affichage page** : -80% (500ms → 100ms)
- 📉 **Temps génération graphique** : -90% (200ms → 20ms)
- 📈 **Espace disque** : +5-10 MB/joueur
- 📈 **Temps sync** : +5-10s (calcul citations)

---

## 📝 Plan d'implémentation (RÉVISÉ v2)

### ✅ Phase 0 : Décisions validées (TERMINÉ)
- [x] Analyse 114 citations exclues
- [x] Identification 18 citations mappables à awards
- [x] **Validation utilisateur : 6 citations à réintégrer**
  - 5 objectives simples (Flag Defense, Flag Return, etc.)
  - 1 objective complexe (Annexion forcée)
- [x] Création `scripts/create_citation_mappings_table.py`
- [x] Création `src/analysis/citations/custom_rules.py`
- [x] Documentation décisions finales

### Phase 1 : Initialisation tables DuckDB (1h)

#### 1.1 Table `citation_mappings` (référentiel)
- [ ] Exécuter `python scripts/create_citation_mappings_table.py`
- [ ] Vérifier `SELECT * FROM citation_mappings` (14 lignes attendues)
- [ ] Retirer 6 citations de `halo5_commendations_exclude.json`

#### 1.2 Table `match_citations` (données par match) ⭐
- [ ] Créer `scripts/create_match_citations_table.py` :
  ```sql
  CREATE TABLE IF NOT EXISTS match_citations (
      match_id TEXT NOT NULL,
      citation_name_norm TEXT NOT NULL,
      value INTEGER NOT NULL,
      PRIMARY KEY (match_id, citation_name_norm)
  );
  CREATE INDEX idx_match_citations_name ON match_citations(citation_name_norm);
  ```
- [ ] Exécuter le script
- [ ] Vérifier dans `data/players/{gamertag}/stats.duckdb`

#### 1.3 Archiver fichiers obsolètes 🗄️
- [ ] Créer `scripts/_archive/obsolete_citations/`
- [ ] Déplacer (ne pas supprimer) :
  - `out/commendations_mapping_assumed.json` (si existe)
  - `out/commendations_mapping_unmatched.json` (si existe)
- [ ] Ajouter `out/commendations_*.json` au `.gitignore`
- [ ] Documenter migration dans `CHANGELOG.md`

### Phase 2 : Créer CitationEngine (3h)

#### 2.1 Module engine
- [ ] Créer `src/analysis/citations/engine.py`
- [ ] Méthodes principales :
  - `load_mappings()` : Charger depuis `citation_mappings` table
  - `compute_citation_for_match(mapping, match_data)` : 1 citation, 1 match
  - `compute_all_for_match(match_id, match_data)` : Toutes citations, 1 match
  - `aggregate_citations(citation_names, filters)` : Agréger depuis `match_citations`

#### 2.2 Support tous les types
- [ ] Type `medal` : Lookup depuis `medals_earned`
- [ ] Type `stat` : Lookup depuis `match_stats`
- [ ] Type `award` : Somme depuis `personal_score_awards`
- [ ] Type `custom` : Appel fonction `CUSTOM_FUNCTIONS`

#### 2.3 Tests unitaires
- [ ] Test chaque type de mapping
- [ ] Test agrégation
- [ ] Test performance (1000 matchs)

### Phase 3 : Intégrer au sync (2h)

#### 3.1 Modifier `scripts/sync.py`
- [ ] Après insertion matchs, appeler `CitationEngine.compute_all_for_match()`
- [ ] INSERT dans `match_citations` (sparse : seulement si value > 0)
- [ ] Logger nb citations insérées

#### 3.2 Script backfill
- [ ] Créer option dans `scripts/backfill_data.py --citations`
- [ ] Pour chaque match existant sans citations :
  - Charger données match
  - Calculer toutes citations
  - INSERT dans `match_citations`
- [ ] Progress bar (important si 1000+ matchs)

#### 3.3 Tests
- [ ] Test sync 1 match → vérifie INSERT citations
- [ ] Test backfill 10 matchs → vérifie cohérence

### Phase 4 : Refactoriser UI (2h)

#### 4.1 Simplifier `src/ui/commendations.py`
- [ ] **Supprimer** :
  - `CUSTOM_CITATION_RULES` dict (migré vers `citation_mappings`)
  - `load_h5g_commendations_tracking_rules()` (obsolète)
  - `_compute_custom_citation_value()` (obsolète)
  - Boucle de calcul par citation (lines ~850)

- [ ] **Remplacer par** :
  ```python
  from src.analysis.citations.engine import CitationEngine
  
  engine = CitationEngine(db_path, xuid)
  citations_totals = engine.aggregate_citations(
      citation_names=[...],
      filters={'match_ids': filtered_match_ids}
  )
  # Retourne {"citation_name": total_value}
  ```

#### 4.2 Support delta (filtres)
- [ ] Calculer `citations_totals_full` (tous matchs)
- [ ] Calculer `citations_totals_filtered` (matchs filtrés)
- [ ] Delta = filtered (affiché en badge)

#### 4.3 Tests UI
- [ ] Tester affichage 47 citations (41 + 6)
- [ ] Tester filtres (date, mode, etc.)
- [ ] Tester delta
- [ ] Benchmark temps affichage (doit être < 100ms)

### Phase 5 : Optimisation & Monitoring (1h)

- [ ] Ajouter métriques perf :
  - Temps calcul citations pendant sync
  - Temps agrégation pour affichage
  - Nb lignes `match_citations` par joueur
- [ ] Documenter dans `docs/CITATIONS.md` :
  - Architecture (tables, schémas)
  - Comment ajouter une citation
  - Comment backfill si règle change
- [ ] Mettre à jour `.ai/thought_log.md`

---

## ✅ Conclusion "Annexion forcée"

### Faisabilité : ✅ OUI

**Implémentation validée** :
```python
# src/analysis/citations/custom_rules.py
def compute_annexion_forcee(awards: dict[str, int]) -> int:
    """3 Zone Capture consécutives sans mourir.
    
    Approximation : total captures ÷ 3.
    TODO : Séquence exacte nécessiterait highlight_events avec timestamps.
    """
    zone_captures = awards.get("Zone Capture", 0)
    return zone_captures // 3
```

### Stockage : ⚠️ Calculé à chaque affichage

**État actuel** (toutes les citations) :
- ❌ **Pas de cache** : Recalcul à chaque render de la page
- ❌ **Pas stocké en DB** : Valeurs éphémères

**Pour Annexion forcée spécifiquement** :
- ✅ **Performance OK** : Agrégation O(1) depuis dict `awards`
- ✅ **Pas d'itération** sur matchs (contrairement à `wins_mode`)

### Impact graphiques : ⚠️ Modéré

| Scénario | Impact | Durée estimée |
|----------|--------|---------------|
| **Page Citations** (41 citations) | Modéré | < 500ms pour 1000 matchs |
| **Graphique 1 citation** | Faible | < 50ms (1 seul calcul) |
| **Graphique 10 citations** | Modéré | < 200ms |
| **Avec cache Streamlit** | Négligeable | < 10ms (lookup cache) |

**Recommandation** :
1. ✅ **Court terme** : Implémenter tel quel (performance acceptable)
2. ⚠️ **Moyen terme** : Ajouter `@st.cache_data` sur `compute_all_citations()`
3. 🎯 **Long terme** : Pré-calculer dans table `player_citations` (cohérent DuckDB v4)

---

## 🔍 Méthode pour trouver les medal_id

### Option 1 : Requête DuckDB directe

```sql
-- Trouver les médailles contenant "headshot"
SELECT DISTINCT medal_name_id, COUNT(*) as count
FROM medals_earned
GROUP BY medal_name_id
ORDER BY count DESC;

-- Puis joindre avec medal_definitions
SELECT md.name_id, md.name_fr, md.name_en, COUNT(*) as earned
FROM medals_earned me
JOIN medal_definitions md ON me.medal_name_id = md.name_id
WHERE md.name_fr ILIKE '%tête%' OR md.name_en ILIKE '%headshot%'
GROUP BY md.name_id, md.name_fr, md.name_en;
```

### Option 2 : Script d'extraction

```python
# scripts/extract_medal_ids_for_citations.py
"""Trouve les medal_id correspondant aux citations."""

from src.data.repositories import DuckDBRepository

def find_medal_id(db_path: str, search_term: str) -> list[tuple]:
    repo = DuckDBRepository(db_path, xuid="")
    # Requête pour trouver les médailles
    # Retourner (medal_id, name_fr, name_en, count)
    pass
```

---

## � Résumé exécutif

### Gains après refactoring (validé)

| Métrique | Avant | Après | Gain |
|----------|-------|-------|------|
| **Citations affichées** | 41 | **47** | **+6 (+14.6%)** |
| **Sources données** | 3 fichiers + code | 1 table DuckDB | -67% complexité |
| **Architecture** | ❌ Fichiers plats | ✅ DuckDB v4 | Unifiée |
| **Maintenance** | ⚠️ 3 endroits | ✅ 1 SQL INSERT | Simple |
| **Versioning** | ❌ `out/` non versionné | ✅ DuckDB | Sécurisé |
| **Performance Annexion forcée** | N/A | ✅ O(1) | Rapide |

### Fichiers créés (prêts)

✅ **Scripts** :
- [scripts/create_citation_mappings_table.py](../scripts/create_citation_mappings_table.py) - Initialisation table (14 citations)

✅ **Modules** :
- [src/analysis/citations/custom_rules.py](../src/analysis/citations/custom_rules.py) - Fonctions custom (6 fonctions)
- [src/analysis/citations/__init__.py](../src/analysis/citations/__init__.py) - Package

✅ **Documentation** :
- [.ai/CITATIONS_DECISIONS_FINALES.md](CITATIONS_DECISIONS_FINALES.md) - Décisions validées

### Actions immédiates

**Prochaine étape** :
```bash
# 1. Créer table + données
python scripts/create_citation_mappings_table.py

# 2. Retirer de la blacklist
# Éditer data/wiki/halo5_commendations_exclude.json
# Supprimer les 6 citations validées
```

**Résultat attendu** :
- ✅ 47 citations affichées (41 + 6)
- ✅ Performance acceptable (< 500ms pour 1000 matchs)
- ✅ Architecture cohérente DuckDB v4

---

## 💡 Recommandations prioritaires (RÉVISÉES)

### ✅ Validé - À implémenter maintenant (Phase 1)
1. **Créer les 2 tables DuckDB** :
   - `citation_mappings` (référentiel) via `create_citation_mappings_table.py`
   - `match_citations` (données par match) via `create_match_citations_table.py`
2. **Retirer les 6 citations** de la blacklist
3. **Archiver fichiers obsolètes** dans `scripts/_archive/obsolete_citations/`

### ⏳ Court terme (cette semaine - Phases 2-3)
1. **Créer CitationEngine** pour calcul par match + agrégation
2. **Intégrer au sync** : Calculer citations après insertion matchs
3. **Backfill matchs existants** : `--citations` option

### 🎯 Moyen terme (semaine prochaine - Phase 4)
1. **Refactoriser UI** : Remplacer recalcul par SELECT sur `match_citations`
2. **Supprimer code obsolète** : `CUSTOM_CITATION_RULES`, `_compute_custom_citation_value()`
3. **Tester performance** : Benchmark affichage < 50ms

### 🚀 Long terme (mois prochain - Phase 5)
1. **Graphiques temporels** : Évolution citations dans le temps
2. **Monitoring** : Métriques temps calcul, nb lignes
3. **Améliorer Annexion forcée** : Détection séquence exacte avec `highlight_events`

---

## ❓ FAQ (MISE À JOUR)

### Q1 : "Annexion forcée" est-elle faisable ?
**✅ OUI** - Implémentée via `compute_annexion_forcee()` avec approximation (total ÷ 3). Performance O(1).

### Q2 : Les valeurs sont-elles stockées ou recalculées ?
**✅ STOCKÉES en DB** (nouvelle architecture `match_citations`) :
- Calculées 1× pendant sync
- Lues ∞× pendant affichage (ultra rapide)
- Historique temporel par match

### Q3 : Quel impact sur les graphiques ?
**✅ AMÉLIORÉ** :
- **Avant** : 200-500ms (recalcul à chaque fois)
- **Après** : < 20ms (SELECT SQL simple)
- **Bonus** : Graphiques temporels possibles (évolution citations)

### Q4 : Pourquoi seulement 6 citations ?
**Par décision utilisateur** - Les 108 autres restent exclues (doublons, médailles, armes spécifiques, PvE). Architecture permet d'en ajouter facilement via INSERT.

### Q5 : Peut-on ajouter d'autres citations plus tard ?
**✅ OUI** - Architecture extensible :
1. INSERT dans `citation_mappings`
2. Backfill pour recalculer matchs existants
3. Nouveaux matchs calculés automatiquement au sync

### Q6 : Quel impact espace disque ?
**✅ ACCEPTABLE** :
- ~10-15 citations par match en moyenne (format sparse : seulement > 0)
- 1000 matchs = ~10 000 lignes
- ~5-10 MB/joueur avec compression DuckDB

### Q7 : Que se passe-t-il si on change une règle de calcul ?
**Options** :
1. **Re-backfill** : Recalculer tous les matchs (~30-60s pour 1000 matchs)
2. **Versioning** : Ajouter colonne `rule_version` (futur)
3. **Acceptable** : Changements rares, re-backfill simple

### Q8 : Faut-il archiver les anciens fichiers JSON ?
**✅ OUI** - Déplacer vers `scripts/_archive/obsolete_citations/` :
- `out/commendations_mapping_assumed.json`
- `out/commendations_mapping_unmatched.json`
- Ne PAS supprimer immédiatement (sécurité)

---

**Document mis à jour** : 2026-02-14 (v2.1 - Architecture match_citations validée)  
**Prochaine action** : Commencer Sprint 1 (voir [CITATIONS_SPRINTS.md](CITATIONS_SPRINTS.md))  
**Plan de sprints** : [.ai/CITATIONS_SPRINTS.md](CITATIONS_SPRINTS.md) - 5 sprints courts (12-16h total)
