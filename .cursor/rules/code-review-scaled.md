# Scaled Code Review - LevelUp

> Revue de code avec agents parallèles, adaptée à la taille des changements.
> Basé sur les patterns Reddit + architecture existante LevelUp.

| Attribut | Valeur |
|----------|--------|
| Nom | code-review-scaled |
| Argument | [scope|plan-path] optionnel |
| Objectif | Revue exhaustive avec profondeur proportionnelle |

---

## 0. Déclenchement Automatique

### Quand déclencher automatiquement

| Taille Changement | Lignes | Comportement |
|-------------------|--------|--------------|
| **Petit** | < 100 lignes, < 5 fichiers | Pas de revue auto (optionnelle) |
| **Moyen** | 100-500 lignes OU 5-15 fichiers | Tests + Revue avant livraison |
| **Gros** | > 500 lignes OU > 15 fichiers | Tests + Revue obligatoire |

### Workflow Automatique (Moyen/Gros)

```
1. Code terminé
       │
       ▼
2. Lancer pytest sur fichiers impactés
       │
       ├── ❌ Tests échouent → Corriger d'abord
       │
       ▼ ✅ Tests passent
3. Lancer revue de code (agents parallèles)
       │
       ├── 🔴 Signal Fort → Corriger avant livraison
       │
       ▼ ✅ Pas de bloquant
4. Livrer (considérer comme terminé)
```

### Détection Automatique

L'agent DOIT vérifier la taille des changements après implémentation :

```bash
# Compter les lignes modifiées
git diff --stat HEAD | tail -1
# Exemple: "11 files changed, 726 insertions(+), 441 deletions(-)"
```

**Règle** : Si `insertions + deletions > 100` OU `files changed >= 5` → déclencher le workflow automatique.

### Comportement Agent

Après avoir terminé une implémentation moyenne/grosse :

1. **Annoncer** : "Mise à jour moyenne détectée (X fichiers, Y lignes). Lancement tests + revue..."
2. **Tests** : `pytest tests/ -v --tb=short` sur modules impactés
3. **Revue** : Lancer le workflow de revue (sections suivantes)
4. **Rapport** : Présenter résultats avant de considérer la tâche terminée

---

## 1. Déterminer le Scope

Inférer automatiquement ce qu'il faut revoir (par priorité) :

1. **Changements conversation** (défaut) : Fichiers modifiés cette session
2. **Changements non-commités** : Staged + unstaged si pas d'historique conversation
3. **Changements branche** : Commits depuis divergence de main (feature branches)
4. **Dernier commit** : HEAD (fallback)

**Règles d'inférence** :
- Historique conversation + fichiers modifiés → revoir changements conversation
- Feature branch + commits ahead of main → revoir branche
- Changements non-commités uniquement → revoir ceux-ci
- Si signaux conflictuels → spawner agent explore pour analyser état git

**Demander à l'utilisateur UNIQUEMENT si vraiment ambigu** (ex: branche dev, pas d'historique, changements non-commités qui pourraient aller dans les deux sens).

---

## 2. Collecter le Contexte

Un agent explore collecte :

- Fichiers `CLAUDE.md` dans les répertoires impactés
- Règles `.cursor/rules/*.md` applicables
- `.ai/project_map.md` pour le contexte architectural
- `.ai/data_lineage.md` si flux de données concernés
- Plan associé si fourni en argument

**Output attendu** : Toutes les instructions, règles et guidelines pertinentes au code revu.

---

## 3. Préoccupations de Revue

Toutes les revues DOIVENT couvrir ces préoccupations :

| Préoccupation | Focus LevelUp |
|---------------|---------------|
| **Edge Cases** | Null/empty/boundary, branches conditionnelles manquantes |
| **Code Mort/Bloat** | Code inutilisé, duplication, logique redondante |
| **Chemins d'Erreur** | Fallbacks utiles ? Bonnes exceptions ? Gestion erreurs manquante ? |
| **Conformité** | Respect CLAUDE.md/rules, ou plan si fourni |
| **Bugs Logiques** (opus) | Logique incorrecte, mauvaises conditions, off-by-one, bugs d'état |
| **Sécurité** (opus) | Injection SQL, tokens exposés, path traversal, SSRF |
| **Code Smells** | Anti-patterns, complexité excessive, mauvaise séparation |
| **Cohérence Patterns** | Nommage, architecture, conventions vs codebase |
| **Code Idiomatique** | Idiomes Python, Polars vs Pandas, patterns modernes |

### Préoccupations Spécifiques LevelUp

| Préoccupation | Focus |
|---------------|-------|
| **DuckDB/Polars** | Pas de Pandas pour gros volumes, pas de N+1, utiliser repositories |
| **Architecture v4** | Respect structure `data/players/`, `DuckDBRepository` pour accès données |
| **Streamlit** | Cache approprié (`@st.cache_data`), pas de state global incorrect |
| **Pydantic v2** | Validation via Pydantic, pas de dicts bruts pour données structurées |

---

## 4. Scaling et Allocation des Agents

Choisir la stratégie selon taille et structure des changements :

### Petits changements (<10 fichiers, domaine unique)

- **3-4 agents**, chacun couvrant plusieurs préoccupations
- Exemple :
  - Agent 1 (fast) : Conformité + Patterns + Code idiomatique
  - Agent 2 (fast) : Bugs logiques + Sécurité
  - Agent 3 (fast) : Code smells + Edge cases + Erreurs + Bloat

### Changements moyens (10-25 fichiers, domaines mixtes)

- **6-8 agents**
- Diviser par préoccupation OU par slice vertical
- Bugs et sécurité obtiennent TOUJOURS des agents dédiés
- Exemple :
  - 2 agents dédiés (bugs logiques, sécurité)
  - 4 agents généraux (conformité, patterns, smells, edge-cases+erreurs+bloat)

### Gros changements (>25 fichiers, features multiples)

- **8-12 agents**
- Préférer les **slices verticaux** : chaque agent revoit TOUTES les préoccupations pour un module/feature
- PLUS agents dédiés bugs/sécurité sur l'ensemble
- Ne pas surcharger un agent — diviser les sets de fichiers si nécessaire

### Principes Directeurs

| Type Agent | Max Fichiers | Notes |
|------------|--------------|-------|
| Détection bugs | 10-15 | Analyse profonde requise |
| Slice vertical | 8-10 | Toutes préoccupations |
| Focus préoccupation | 15-20 | Moins de profondeur |

**Modèles** :
- `fast` pour edge cases, conformité, patterns, smells
- Modèle principal pour bugs logiques et sécurité (analyse plus profonde)

### Output Attendu des Agents

- **Terse pour code propre** : Si une préoccupation est OK → 1 ligne max ("Edge cases: correctement gérés")
- **Détail UNIQUEMENT pour les problèmes** : Explication complète, fichier:ligne, preuves seulement si problème détecté
- NE PAS expliquer pourquoi le code correct est correct — expliquer uniquement ce qui est faux et pourquoi

---

## 5. Valider les Issues

### Stratégie de Validation

- ~1 agent validateur pour 3 issues trouvées
- Regrouper les issues par fonctionnalité/fichiers pour éviter de re-lire le même code
- Chaque validateur se concentre sur un cluster

### Validation par Type

| Type Issue | Validateur | Vérifie |
|------------|------------|---------|
| Bugs/Sécurité | Agent principal | Issue réelle et exploitable/cassée |
| Conformité | Agent fast | Règle applicable ET réellement violée |
| Smells/Patterns/Idiomes | Agent fast | Significatif (pas un nitpick subjectif) |
| Edge Cases/Erreurs | Agent fast | Chemin réellement atteignable et non géré |

---

## 6. Output Final

```markdown
## Code Review (scope: <type>, <N> fichiers)

### Signal Fort (bloquant)
<à corriger obligatoirement — bugs, sécurité, violations conformité claires>

### Signal Moyen (recommandé)
<devrait corriger — smells, violations patterns, gestion erreurs manquante>

### Signal Faible (optionnel)
<à considérer — idiomes, incohérences mineures>

---
Trouvé X issues: Y fort, Z moyen, W faible.
Lancer `/review-fix` pour adresser.
```

### Format par Issue

```
- **[CONCERN]** Description brève
  - `fichier.py:42` — référence précise
  - Pour conformité: citation exacte de la règle violée
```

---

## 7. Exclusions False Positives

NE PAS signaler :

- Issues pré-existantes (non introduites par ces changements)
- Issues détectables par linter (ruff, mypy s'en chargent)
- Préférences de style subjectives
- Violations silencées (commentaires `# noqa`, `type: ignore`)
- Problèmes spéculatifs "pourrait être"
- Code mort qui est en fait utilisé (vérifier avant de signaler)
- Code legacy documenté comme tel dans `.ai/` ou CLAUDE.md

---

## 8. Intégration LevelUp

### Fichiers de Contexte à Toujours Consulter

```
CLAUDE.md                        # Règles globales projet
.ai/project_map.md               # Cartographie modules
.ai/data_lineage.md              # Flux de données
docs/DATA_ARCHITECTURE.md        # Architecture v4
```

### Patterns Spécifiques à Vérifier

| Pattern | Correct | Incorrect |
|---------|---------|-----------|
| Accès données | `DuckDBRepository(path, xuid)` | `sqlite3.connect()` direct |
| DataFrames gros volumes | `polars.read_parquet()` | `pandas.read_csv()` |
| Validation | `class MyModel(BaseModel)` | `dict` brut |
| Cache Streamlit | `@st.cache_data(ttl=300)` | Variables globales |
| Chemins | `from src.utils.paths import *` | Hardcodé `"data/players/"` |

### Commandes Associées

```bash
# Revue rapide (< 10 fichiers, 3-4 agents)
/review-scaled

# Revue branche complète
/review-scaled branch

# Revue avec référence au plan
/review-scaled .ai/sprints/sprint-5.md

# Appliquer les corrections
/review-fix
```

---

## 9. Workflow Complet

```
┌─────────────────────────────────────────────────────────────┐
│  1. SCOPE                                                   │
│     Déterminer automatiquement ou demander si ambigu        │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  2. CONTEXT (1 agent explore)                               │
│     Collecter CLAUDE.md, rules, project_map, data_lineage   │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  3. REVIEW (N agents parallèles)                            │
│     Scaling: 3-4 (small) | 6-8 (medium) | 8-12 (large)      │
│     Output terse si OK, détaillé si problème                │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  4. VALIDATE (N/3 agents)                                   │
│     Éliminer false positives, vérifier exploitabilité       │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  5. REPORT                                                  │
│     Signal Fort | Moyen | Faible avec fichier:ligne         │
└─────────────────────────────────────────────────────────────┘
```

---

## 10. Exemple Concret

**Scénario** : PR avec 15 fichiers modifiés (nouveau endpoint API + refactor UI)

**Allocation** :

```yaml
# Phase Review (6 agents parallèles)
Agent 1 (fast): src/data/sync/*.py - Conformité + DuckDB patterns
Agent 2 (fast): src/ui/pages/*.py - Streamlit patterns + UI smells
Agent 3: src/data/repositories/*.py - Bugs logiques
Agent 4: Tous fichiers - Sécurité (tokens, SQL injection)
Agent 5 (fast): tests/*.py - Couverture + edge cases tests
Agent 6 (fast): Tous - Conformité CLAUDE.md + code mort

# Phase Validation (2 agents)
Validateur 1: Issues backend (sync, repositories)
Validateur 2: Issues frontend (UI, tests)
```

**Output attendu** :

```markdown
## Code Review (scope: branch, 15 fichiers)

### Signal Fort (bloquant)
- **[SÉCURITÉ]** Token API exposé dans log
  - `src/data/sync/engine.py:142` — `logger.info(f"Token: {token}")`
  - Règle: CLAUDE.md interdit logging de secrets

### Signal Moyen (recommandé)
- **[DuckDB]** Accès SQLite direct au lieu de repository
  - `src/ui/pages/new_page.py:88` — `sqlite3.connect(db_path)`
- **[PATTERN]** Pandas utilisé pour 5000+ lignes
  - `src/analysis/new_feature.py:45` — Utiliser Polars

### Signal Faible (optionnel)
- **[IDIOME]** F-string préférable à .format()
  - `src/utils/helpers.py:23`

---
Trouvé 4 issues: 1 fort, 2 moyen, 1 faible.
```

---

*Dernière mise à jour : 2026-02-02*
