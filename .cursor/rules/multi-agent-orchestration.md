# Multi-Agent Orchestration - OpenSpartan Graph

> Architecture d'orchestration multi-agents pour tâches complexes.
> Basé sur les patterns avancés de la communauté Claude Code.

| Attribut | Valeur |
|----------|--------|
| Nom | multi-agent-orchestration |
| Objectif | Parallélisation maximale avec qualité garantie |

---

## Architecture Hiérarchique

```
┌─────────────────────────────────────────────────────────┐
│                    PM / SR Lead (Opus)                  │
│         Orchestration, Planning, Consolidation          │
└─────────────────────────┬───────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│  Sub-Agent 1  │ │  Sub-Agent 2  │ │  Sub-Agent N  │
│   (Sonnet)    │ │   (Sonnet)    │ │   (Sonnet)    │
│  Micro-task   │ │  Micro-task   │ │  Micro-task   │
└───────────────┘ └───────────────┘ └───────────────┘
```

**Règle** : Maximum 6 sub-agents parallèles par batch.

---

## Sub-Agents Spécialisés

### 1. TDD Discovery Agent

```yaml
Nom: tdd-discovery
Modèle: Sonnet (fast)
Mission: Comprendre les tests existants avant modification

Prompt:
  Analyse le répertoire tests/ et identifie :
  1. Structure des tests (pytest, fixtures, mocks)
  2. Couverture actuelle par module
  3. Patterns de test utilisés
  4. Tests critiques à ne pas casser
  
  Output: .ai/reports/tdd-discovery.md
```

### 2. Requirements Architect Agent

```yaml
Nom: requirements-architect
Modèle: Sonnet
Mission: Designer le changement technique

Prompt:
  Pour la feature demandée :
  1. Analyse l'architecture existante (.ai/project_map.md)
  2. Identifie les modules impactés
  3. Propose un design avec interfaces
  4. Liste les dépendances et risques
  
  Output: .ai/reports/architecture-proposal.md
```

### 3. Technical Documentation Writer

```yaml
Nom: tech-doc-writer
Modèle: Sonnet (fast)
Mission: Maintenir la documentation à jour

Prompt:
  Après chaque changement :
  1. Mettre à jour les docstrings modifiées
  2. Synchroniser .ai/project_map.md
  3. Mettre à jour .ai/data_lineage.md si flux changé
  4. Ajouter entrée dans .ai/thought_log.md
  
  Output: Fichiers .ai/ mis à jour
```

### 4. Devil's Advocate Reviewer

```yaml
Nom: devils-advocate
Modèle: Sonnet
Mission: Challenger le plan et l'implémentation

Prompt:
  Pour le plan/code proposé :
  1. Quels sont les edge cases non gérés ?
  2. Que se passe-t-il si X échoue ?
  3. Est-ce que c'est over-engineered ?
  4. Y a-t-il une solution plus simple ?
  5. Quels tests manquent ?
  
  Format: Liste numérotée de challenges avec sévérité
  Output: .ai/reports/devils-advocate.md
```

### 5. Security SWE Specialist

```yaml
Nom: security-specialist
Modèle: Sonnet
Mission: Audit et implémentation sécurité

Checklist:
  □ Secrets hardcodés (API keys, tokens)
  □ SQL injection (params vs string format)
  □ Path traversal (user input dans chemins)
  □ SSRF (URLs externes non validées)
  □ Auth/AuthZ bypass
  □ Data exposure dans logs
  □ Dépendances vulnérables
  
  Output: .ai/reports/security-audit.md
```

### 6. Fagan Inspector Reviewer

```yaml
Nom: fagan-inspector
Modèle: Opus (pour consolidation multi-rounds)
Mission: Revue formelle exhaustive

Voir: .cursor/rules/fagan-reviewer.md

Spécificité multi-rounds:
  - 6 sub-agents par round
  - Minimum 4 rounds
  - Consolidation PM entre rounds
  - Élimination des false positives
```

---

## Workflow Micro-Sprints

### Phase 1 : Audit Initial

```
PM (Opus):
  1. Lancer tdd-discovery
  2. Lancer security-specialist
  3. Attendre rapports
  4. Consolider issues prioritaires
```

### Phase 2 : Fagan Multi-Rounds

```
PM (Opus):
  Pour round in 1..4:
    1. Diviser le scope en 6 sections
    2. Lancer 6 fagan-inspectors parallèles
    3. Collecter findings
    4. Consolider et éliminer duplicates/false positives
    5. Identifier zones non couvertes → round suivant
  
  Output: Liste exhaustive des issues
```

### Phase 3 : Planning Micro-Sprints

```
PM (Opus):
  1. Transformer issues en micro-tâches
  2. Prioriser: Security > Critical > Major > Minor
  3. Créer .ai/sprints/micro-sprints/sprint-001.md
  4. Chaque sprint = 6 tâches parallélisables max
```

### Phase 4 : Exécution Parallèle

```
PM (Opus):
  Pour chaque sprint:
    1. Lancer 6 sub-agents (Sonnet) en parallèle
    2. Si slots libres → tech-doc-writer pour docs
    3. Attendre completion
    4. Valider contre checklist
    5. Si échec → relancer avec contexte erreur
    6. Passer au sprint suivant
```

### Phase 5 : Validation Finale

```
PM (Opus):
  1. Lancer devils-advocate sur changements
  2. Lancer security-specialist (re-audit)
  3. Lancer tdd-discovery (vérifier tests)
  4. Consolider et fermer le cycle
```

---

## Template Micro-Sprint

Fichier: `.ai/sprints/micro-sprints/sprint-XXX.md`

```markdown
# Sprint XXX - [Titre]

## Contexte
[Issue(s) adressée(s)]

## Tâches Parallèles (max 6)

### Task 1: [Nom]
- **Agent**: [type]
- **Fichiers**: [liste]
- **Action**: [description précise]
- **Checklist**:
  - [ ] Critère 1
  - [ ] Critère 2
- **Status**: ⏳ Pending | 🔄 In Progress | ✅ Done | ❌ Failed

### Task 2: [Nom]
...

## Validation PM
- [ ] Tous les tasks Done
- [ ] Tests passent
- [ ] Pas de régression
- [ ] Documentation à jour

## Notes
[Observations, blocages, décisions]
```

---

## Commandes d'Orchestration

### /orchestrate-audit

```
Lance un audit complet multi-rounds:
1. Security scan
2. Fagan inspection (6 agents × 4 rounds)
3. Consolidation des issues
4. Génération du plan de correction
```

### /orchestrate-implement

```
Exécute le plan en micro-sprints:
1. Charge .ai/sprints/micro-sprints/*.md
2. Exécute 6 tâches en parallèle
3. Valide chaque batch
4. Documente au fur et à mesure
```

### /orchestrate-full

```
Cycle complet:
1. /orchestrate-audit
2. Planning micro-sprints
3. /orchestrate-implement
4. Validation finale
```

---

## Context Management

**Problème** : Les longs chats accumulent du contexte et dégradent la cohérence.

**Solution** :
- Le PM garde UNIQUEMENT les rapports finaux des sub-agents
- Les sub-agents travaillent dans leur propre contexte isolé
- Chaque micro-sprint a son propre fichier de suivi

```
Chat Principal (PM):
  └── Rapport tdd-discovery ✓
  └── Rapport security-audit ✓
  └── Rapport fagan-round-4 ✓
  └── Status sprint-001 ✓
  └── Status sprint-002 ✓
  ...
```

---

## Best Practices Documents

Pour les implémentations complexes (OAuth, etc.), créer des docs de référence :

```
.ai/references/
  ├── oauth2-best-practices.md      # Récupéré de ChatGPT/Claude
  ├── polars-optimization.md        # Patterns performants
  ├── duckdb-partitioning.md        # Stratégies partitionnement
  └── streamlit-caching.md          # Patterns de cache
```

**Workflow** :
1. Demander à ChatGPT/Claude (interface normale) un doc best practices
2. Réviser manuellement
3. Dropper dans `.ai/references/`
4. Référencer dans le prompt de planning

---

## Anti-Patterns à Éviter

| Pattern | Problème | Solution |
|---------|----------|----------|
| Tout dans un seul agent | Context overflow, incohérence | Hiérarchie PM + sub-agents |
| Tâches trop larges | Échecs fréquents | Micro-sprints atomiques |
| Pas de validation | Accumulation d'erreurs | Checkpoints PM entre sprints |
| Docs ignorées | Dette technique | tech-doc-writer systématique |
| Un seul round de review | Faux négatifs | Multi-rounds Fagan |
| MCP blackbox | Résultats non vérifiables | Docs locales vérifiées |
