# Fagan Inspection Reviewer - OpenSpartan Graph

> Méthodologie de revue de code formelle inspirée de Michael Fagan (IBM, 1976).
> Ce fichier définit le protocole de revue structurée pour les agents IA.

| Attribut | Valeur |
|----------|--------|
| Nom | fagan-inspection-reviewer |
| Objectif | Revue de code systématique avec détection précoce des défauts |

---

## Rôles Fagan Adaptés à l'IA

Dans le contexte d'un agent IA, les rôles traditionnels sont consolidés :

| Rôle Fagan | Adaptation IA | Responsabilité |
|------------|---------------|----------------|
| Moderator | Agent principal | Orchestre le processus, contrôle le scope |
| Author | Humain (développeur) | Répond aux questions, valide les findings |
| Reader | Agent | Parcourt et décrit le code systématiquement |
| Recorder | Agent | Documente les défauts dans `.ai/review_report.md` |
| Inspector | Agent | Applique les critères d'inspection |

---

## Processus d'Inspection en 6 Étapes

### Étape 1 : Planification (30s)

```yaml
Entrées:
  - Fichiers à revoir (--staged, --recent, ou explicites)
  - Critères de revue applicables
  
Actions:
  - Identifier le scope (nombre de fichiers, lignes)
  - Vérifier si le scope est raisonnable (< 500 lignes idéal)
  - Lire .ai/project_map.md pour le contexte architectural
  
Sortie:
  - Liste des fichiers avec priorité
```

### Étape 2 : Vue d'Ensemble (1-2 min)

```yaml
Actions:
  - Lire les fichiers en entier (pas de skip)
  - Identifier le but général du code
  - Noter les dépendances (imports, appels externes)
  - Comprendre le flux de données
  
Questions à répondre:
  - Quel problème ce code résout-il?
  - Comment s'intègre-t-il à l'architecture existante?
  - Y a-t-il des tests associés?
```

### Étape 3 : Préparation Individuelle (Analyse Systématique)

Pour chaque fichier, appliquer cette checklist **dans l'ordre** :

#### 3.1 Défauts Logiques (Critiques)

```markdown
□ Conditions inversées ou incomplètes
□ Off-by-one errors dans les boucles
□ Null/None non gérés
□ Race conditions potentielles
□ Ressources non libérées (fichiers, connexions)
□ Exceptions avalées silencieusement
□ Données mutées de façon inattendue
```

#### 3.2 Défauts Fonctionnels (Majeurs)

```markdown
□ Cas limites non gérés (liste vide, valeur max/min)
□ Comportement incorrect avec données invalides
□ État incohérent après erreur
□ Contrats d'interface non respectés
□ Validation d'entrées manquante
```

#### 3.3 Défauts de Performance (Majeurs)

```markdown
□ Requêtes N+1 (boucle avec requête DB)
□ Chargement de données excessif (SELECT * sans LIMIT)
□ Opérations O(n²) évitables
□ Pas de lazy loading quand applicable
□ Cache ignoré pour données répétitives
□ Pandas au lieu de Polars pour gros volumes
```

#### 3.4 Défauts de Sécurité (Critiques)

```markdown
□ Secrets hardcodés (API keys, passwords)
□ SQL injection (string formatting au lieu de params)
□ Path traversal (input utilisateur dans chemins)
□ Permissions trop larges
□ Données sensibles loggées
□ CORS/Auth bypassable
```

#### 3.5 Défauts de Maintenabilité (Mineurs)

```markdown
□ Fonctions > 50 lignes
□ Nesting > 3 niveaux
□ Magic numbers sans constantes
□ Code dupliqué (DRY violation)
□ Nommage ambigu
□ Couplage fort entre modules
```

#### 3.6 Conformité Standards OpenSpartan

```markdown
□ Types Pydantic v2 pour validation
□ Polars pour DataFrames volumineux
□ DuckDB pour requêtes analytiques
□ Respect de src/ structure
□ Tests dans tests/
□ Cohérence avec .ai/data_lineage.md
```

### Étape 4 : Réunion d'Inspection (Synthèse)

```yaml
Actions:
  - Consolider tous les défauts trouvés
  - Classer par sévérité (Critical > Major > Minor > Info)
  - Éliminer les faux positifs évidents
  - Prioriser par impact business
  
Règle des 3:
  - Si > 3 défauts critiques → STOP, corriger d'abord
  - Si > 10 défauts totaux → Scope trop large, diviser
```

### Étape 5 : Rapport Structuré

Générer `.ai/review_report.md` avec ce format exact :

```markdown
# Revue Fagan - [DATE]

## Méta-données
| Métrique | Valeur |
|----------|--------|
| Fichiers analysés | N |
| Lignes de code | M |
| Durée d'inspection | X min |
| Inspecteur | Agent IA |

## Score Global

| Catégorie | Score | Seuil |
|-----------|-------|-------|
| Logique | X/10 | ≥7 |
| Fonctionnel | X/10 | ≥7 |
| Performance | X/10 | ≥6 |
| Sécurité | X/10 | ≥8 |
| Maintenabilité | X/10 | ≥6 |
| **TOTAL** | X/50 | ≥35 (Pass) |

**Verdict**: ✅ PASS / ❌ FAIL / ⚠️ CONDITIONNEL

## Défauts Critiques 🔴

| ID | Fichier:Ligne | Description | Impact |
|----|---------------|-------------|--------|
| C1 | `path/file.py:42` | Description concise | Élevé |

## Défauts Majeurs 🟠

| ID | Fichier:Ligne | Description | Effort Fix |
|----|---------------|-------------|------------|
| M1 | `path/file.py:88` | Description | Moyen |

## Défauts Mineurs 🟡

| ID | Fichier:Ligne | Description |
|----|---------------|-------------|
| m1 | `path/file.py:12` | Description |

## Points Positifs 🟢

- Bonne séparation des responsabilités
- Tests exhaustifs pour les cas limites
- Documentation claire des fonctions publiques

## Recommandations

### Corrections Obligatoires (avant merge)
1. [C1] Corriger la gestion du null en ligne 42
2. [M1] Ajouter validation d'entrée

### Améliorations Suggérées (optionnel)
1. [m1] Extraire magic number en constante
2. Considérer lazy loading pour améliorer perf

## Prochaines Étapes

- [ ] Corriger défauts critiques
- [ ] Re-review après corrections
- [ ] Valider avec tests
```

### Étape 6 : Suivi (Follow-up)

```yaml
Actions:
  - Vérifier que les corrections sont faites
  - Re-exécuter les checks automatiques (ruff, pytest)
  - Valider que les nouveaux tests passent
  - Mettre à jour le rapport si nécessaire
  
Critères de clôture:
  - 0 défauts critiques
  - Tous les majeurs adressés ou justifiés
  - Tests passent à 100%
```

---

## Métriques de Qualité Fagan

### Densité de Défauts

```
Défauts/KLOC = (Total défauts / Lignes de code) × 1000

Seuils OpenSpartan:
  - < 5/KLOC : Excellent
  - 5-15/KLOC : Acceptable
  - > 15/KLOC : Révision nécessaire
```

### Taux de Détection

```
Efficacité = Défauts trouvés en revue / Total défauts (incl. prod)

Cible: > 70%
```

---

## Commandes d'Invocation

```bash
# Revue Fagan complète sur fichiers staged
/review --fagan --staged

# Revue rapide (steps 1-4 seulement, pas de rapport)
/review --quick src/data/

# Revue focalisée sécurité
/review --focus security --staged

# Revue avec génération de fixes automatiques
/review --auto-fix src/app/
```

---

## Intégration avec Workflow OpenSpartan

1. **Avant commit** : `/review --quick --staged`
2. **Avant PR** : `/review --fagan --staged`
3. **Après merge en main** : `/review --fagan src/` (régression)
4. **Mensuel** : `/review --fagan --full` (audit complet)

---

## Anti-Patterns de Revue

| À éviter | Pourquoi | Faire plutôt |
|----------|----------|--------------|
| Revue > 500 lignes | Fatigue cognitive | Diviser en sessions |
| Ignorer les tests | Bugs cachés | Toujours inclure `tests/` |
| Nitpicking style | Perte de temps | Laisser le linter gérer |
| Revue sans contexte | Findings hors sujet | Lire `.ai/` d'abord |
| Pas de priorisation | Tout semble urgent | Classer Critical > Major > Minor |
