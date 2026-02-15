# Commande /orchestrate-audit

Lance un audit complet multi-rounds du projet.

**Protocole** : `.cursor/rules/multi-agent-orchestration.md`

## Usage

```bash
/orchestrate-audit              # Audit complet
/orchestrate-audit --security   # Focus sécurité uniquement
/orchestrate-audit --quick      # 2 rounds au lieu de 4
```

## Étapes

### 1. Lancement Sub-Agents Initiaux (Parallèle)

```yaml
Agents à lancer simultanément:
  - tdd-discovery → .ai/reports/tdd-discovery.md
  - security-specialist → .ai/reports/security-audit.md
```

### 2. Fagan Multi-Rounds

```yaml
Pour round in 1..4:
  1. Diviser le codebase en 6 sections:
     - src/data/
     - src/app/
     - src/ui/
     - src/analysis/
     - src/visualization/
     - scripts/
  
  2. Lancer 6 fagan-inspectors parallèles (Sonnet)
     Chaque agent reçoit:
       - Section à auditer
       - Checklist Fagan (.cursor/rules/fagan-reviewer.md)
       - Focus spécifique du round
  
  3. Collecter .ai/reports/fagan-round-{N}-section-{X}.md
  
  4. Consolider en .ai/reports/fagan-round-{N}-consolidated.md
     - Éliminer duplicates
     - Identifier false positives
     - Prioriser par sévérité
  
  5. Identifier zones non couvertes → input round suivant
```

### 3. Consolidation Finale

```yaml
Actions:
  1. Merge tous les rapports:
     - tdd-discovery.md
     - security-audit.md
     - fagan-round-4-consolidated.md
  
  2. Créer .ai/reports/audit-final.md avec:
     - Score global
     - Issues par catégorie
     - Priorisation recommandée
  
  3. Générer backlog dans .ai/sprints/backlog.md
```

### 4. Devil's Advocate Review

```yaml
Agent: devils-advocate
Input: .ai/reports/audit-final.md

Questions:
  - Les issues critiques sont-elles vraiment critiques ?
  - Y a-t-il des false positives ?
  - Quels edge cases manquent ?
  - Le plan de correction est-il réaliste ?

Output: .ai/reports/devils-advocate.md
```

## Output Final

```
.ai/reports/
├── tdd-discovery.md
├── security-audit.md
├── fagan-round-1-consolidated.md
├── fagan-round-2-consolidated.md
├── fagan-round-3-consolidated.md
├── fagan-round-4-consolidated.md
├── audit-final.md
└── devils-advocate.md

.ai/sprints/
└── backlog.md
```

## Checklist de Sortie

- [ ] tdd-discovery complété
- [ ] security-audit complété
- [ ] 4 rounds Fagan exécutés
- [ ] Consolidation finale générée
- [ ] Devil's advocate review fait
- [ ] Backlog généré et priorisé
