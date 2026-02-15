# Commande /orchestrate-full

Cycle complet d'orchestration : Audit → Planning → Implémentation → Validation.

**Protocole** : `.cursor/rules/multi-agent-orchestration.md`

## Usage

```bash
/orchestrate-full                    # Cycle complet
/orchestrate-full --scope src/data/  # Limité à un scope
/orchestrate-full --skip-audit       # Si audit déjà fait
```

## Vue d'Ensemble

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│    AUDIT     │───▶│   PLANNING   │───▶│   EXECUTE    │───▶│   VALIDATE   │
│  (4 rounds)  │    │ (micro-sprints)│   │  (parallel)  │    │   (final)    │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
     PM + 6              PM                 PM + 6              PM + 3
```

## Phase 1 : Audit (≈ 30 min)

```yaml
Exécuter: /orchestrate-audit

Outputs:
  - .ai/reports/audit-final.md
  - .ai/reports/security-audit.md
  - .ai/sprints/backlog.md
```

## Phase 2 : Planning (≈ 10 min)

```yaml
Actions PM:
  1. Lire .ai/sprints/backlog.md
  
  2. Prioriser les issues:
     Priority 1: Security (CRITIQUE)
     Priority 2: Critical bugs
     Priority 3: Major issues
     Priority 4: Minor improvements
  
  3. Créer micro-sprints:
     - 6 tâches parallèles max par sprint
     - Chaque tâche = 1 fichier ou 1 fonction
     - Checklist de validation explicite
  
  4. Estimer nombre de sprints nécessaires
  
  5. Identifier dépendances inter-sprints

Outputs:
  - .ai/sprints/micro-sprints/sprint-001.md
  - .ai/sprints/micro-sprints/sprint-002.md
  - ...
  - .ai/sprints/execution-plan.md
```

## Phase 3 : Exécution (Variable)

```yaml
Exécuter: /orchestrate-implement

Pour chaque sprint:
  1. 6 sub-agents parallèles
  2. Validation PM
  3. Correction si échec
  4. Passage au suivant

Règles:
  - Security sprints en PREMIER
  - Tests après chaque sprint
  - Doc mise à jour en continu
  - Slots libres → tech-doc-writer
```

## Phase 4 : Validation Finale (≈ 15 min)

```yaml
Sub-agents finaux (parallèle):
  1. security-specialist → Re-audit sécurité
  2. tdd-discovery → Vérifier couverture tests
  3. devils-advocate → Challenge final

Actions PM:
  1. Collecter les 3 rapports
  2. Vérifier:
     - [ ] 0 issues security critiques
     - [ ] Couverture tests ≥ 80%
     - [ ] Pas de régressions
     - [ ] Documentation complète
  
  3. Si problèmes:
     → Créer sprint de correction
     → Relancer Phase 3 partielle
  
  4. Si OK:
     → Générer rapport final
     → Mettre à jour thought_log.md
     → Proposer commit message

Outputs:
  - .ai/reports/final-validation.md
  - .ai/thought_log.md (mise à jour)
```

## Métriques de Succès

| Métrique | Seuil |
|----------|-------|
| Issues Security résolues | 100% |
| Issues Critical résolues | 100% |
| Issues Major résolues | ≥ 90% |
| Tests passent | 100% |
| Couverture | ≥ 80% |
| Linting errors | 0 |

## Gestion du Contexte

```yaml
Chat Principal (PM):
  Contient UNIQUEMENT:
    - Rapports finaux des sub-agents
    - Status des sprints (Done/Failed)
    - Décisions d'orchestration
  
  NE CONTIENT PAS:
    - Détails d'implémentation
    - Logs de debug
    - Code complet des fichiers

Raison:
  Garder le contexte propre = meilleure cohérence sur longs cycles
```

## Fallback Manuel

Si le cycle automatique échoue :

```bash
# 1. Identifier le point d'échec
cat .ai/sprints/micro-sprints/*.md | grep "Failed"

# 2. Corriger manuellement si nécessaire

# 3. Relancer à partir du sprint échoué
/orchestrate-implement --sprint XXX

# 4. Continuer le cycle
/orchestrate-full --skip-audit
```

## Checklist de Sortie

- [ ] Audit 4 rounds complété
- [ ] Micro-sprints planifiés
- [ ] Tous les sprints exécutés
- [ ] Validation finale OK
- [ ] 0 issues security
- [ ] Tests 100% pass
- [ ] Documentation à jour
- [ ] Rapport final généré
- [ ] thought_log.md mis à jour
