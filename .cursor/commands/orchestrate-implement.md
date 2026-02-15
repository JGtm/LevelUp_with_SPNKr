# Commande /orchestrate-implement

Exécute le plan de correction en micro-sprints parallélisés.

**Protocole** : `.cursor/rules/multi-agent-orchestration.md`

## Prérequis

- `.ai/sprints/backlog.md` existe (généré par `/orchestrate-audit`)
- Ou `.ai/sprints/micro-sprints/sprint-*.md` existent

## Usage

```bash
/orchestrate-implement              # Exécute tous les sprints
/orchestrate-implement --sprint 001 # Exécute sprint spécifique
/orchestrate-implement --dry-run    # Planifie sans exécuter
```

## Étapes

### 1. Chargement du Backlog

```yaml
Actions:
  1. Lire .ai/sprints/backlog.md
  2. Si micro-sprints n'existent pas → les créer
  3. Prioriser: Security > Critical > Major > Minor
  4. Grouper en batches de 6 tâches max
```

### 2. Génération Micro-Sprints

```yaml
Pour chaque batch de 6 issues:
  Créer .ai/sprints/micro-sprints/sprint-XXX.md avec:
    - Contexte (issues adressées)
    - 6 tâches parallèles max
    - Checklist de validation par tâche
    - Critères de completion du sprint
```

### 3. Exécution Parallèle

```yaml
Pour chaque sprint:
  1. Lancer jusqu'à 6 sub-agents (Sonnet) en parallèle
     
     Affectation des agents:
       - Code changes → implementor agent
       - Test updates → tdd-agent
       - Doc updates → tech-doc-writer
       - Security fixes → security-specialist
     
     Si slots libres (< 6 agents):
       → Affecter tech-doc-writer pour docs
  
  2. Attendre completion de tous les agents
  
  3. Collecter les résultats:
     - Fichiers modifiés
     - Tests créés/modifiés
     - Erreurs rencontrées
  
  4. Valider contre checklist:
     - [ ] Code compiles
     - [ ] Tests passent
     - [ ] Pas de régression
     - [ ] Linting OK (ruff check)
  
  5. Si échec:
     a. Analyser l'erreur
     b. Créer mini-sprint de correction
     c. Relancer avec contexte enrichi
  
  6. Si succès:
     a. Marquer sprint comme Done
     b. Mettre à jour .ai/thought_log.md
     c. Passer au sprint suivant
```

### 4. Validation Batch

```yaml
Après chaque 3 sprints:
  1. Lancer tests complets: pytest tests/ -v
  2. Vérifier coverage
  3. Lancer ruff check src/
  4. Si problèmes → créer sprint de correction
```

### 5. Documentation Continue

```yaml
Pendant l'exécution:
  - tech-doc-writer met à jour .ai/project_map.md
  - Chaque sprint complété → entrée thought_log.md
  - Changements d'architecture → data_lineage.md
```

## Template Prompt Sub-Agent

```markdown
## Contexte
Tu es un sub-agent spécialisé dans [SPÉCIALITÉ].
Sprint: [SPRINT_ID]
Task: [TASK_ID]

## Fichiers à Lire
- [Liste des fichiers contexte]

## Action Requise
[Description précise de la tâche]

## Contraintes
- Ne modifier QUE les fichiers listés
- Respecter les patterns existants
- Ajouter/modifier les tests correspondants

## Checklist de Completion
- [ ] Critère 1
- [ ] Critère 2
- [ ] Tests passent

## Output Attendu
Résumé des modifications en 3-5 lignes.
```

## Gestion des Erreurs

| Erreur | Action |
|--------|--------|
| Test fail | Analyser, créer mini-sprint fix |
| Lint error | Auto-fix avec ruff --fix |
| Import error | Vérifier dépendances, installer si manquant |
| Timeout agent | Relancer avec scope réduit |
| Conflit de merge | PM résout manuellement |

## Output Final

```
.ai/sprints/micro-sprints/
├── sprint-001.md  ✅ Done
├── sprint-002.md  ✅ Done
├── sprint-003.md  🔄 In Progress
└── sprint-004.md  ⏳ Pending

.ai/reports/
└── implementation-summary.md
```

## Checklist de Sortie

- [ ] Tous les sprints exécutés
- [ ] Tests passent (pytest)
- [ ] Linting OK (ruff)
- [ ] Documentation mise à jour
- [ ] thought_log.md mis à jour
- [ ] Résumé d'implémentation généré
