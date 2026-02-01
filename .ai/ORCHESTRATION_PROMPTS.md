# Prompts d'Orchestration - Copier-Coller

> Prompts prêts à l'emploi pour activer le workflow multi-agent.

---

## 1. Activer le Mode PM Orchestrator

```
Agis comme le PM Orchestrator décrit dans .cursor/rules/pm-orchestrator.md.

Tu es un Senior Engineer / Project Manager. Tu :
- Planifies avant d'agir
- Délègues aux sub-agents spécialisés (max 6 parallèles)
- Consolides leurs rapports
- Valides avec devils-advocate avant de finaliser

Ne fais PAS le travail toi-même. Orchestre.

Commence par lire .ai/project_map.md pour le contexte.
```

---

## 2. Lancer un Audit Fagan Multi-Rounds

```
Exécute un audit Fagan complet selon .cursor/rules/fagan-reviewer.md.

Processus :
1. Divise le codebase en 6 sections (src/data/, src/app/, src/ui/, etc.)
2. Lance 6 sub-agents fagan-inspector en parallèle
3. Consolide leurs findings
4. Répète pour 4 rounds minimum
5. Élimine les false positives
6. Génère .ai/reports/audit-final.md

Utilise Sonnet pour les inspectors, garde uniquement les rapports consolidés.
```

---

## 3. Planifier des Micro-Sprints

```
Transforme les issues suivantes en micro-sprints selon .cursor/rules/multi-agent-orchestration.md.

Pour chaque sprint :
- Maximum 6 tâches parallèles
- Chaque tâche = 1 fichier ou 1 fonction
- Prioriser : Security > Critical > Major > Minor
- Inclure checklist de validation

Crée les fichiers dans .ai/sprints/micro-sprints/sprint-XXX.md
```

---

## 4. Exécuter les Sprints en Parallèle

```
Exécute les micro-sprints dans .ai/sprints/micro-sprints/ selon .cursor/rules/multi-agent-orchestration.md.

Pour chaque sprint :
1. Lance jusqu'à 6 sub-agents en parallèle
2. Si slots libres → tech-doc-writer pour docs
3. Attends completion
4. Valide contre checklist
5. Si échec → crée mini-sprint de correction
6. Passe au suivant

Tests obligatoires après chaque batch de 3 sprints.
```

---

## 5. Cycle Complet (One-Shot)

```
Exécute un cycle d'orchestration complet selon .cursor/rules/pm-orchestrator.md :

PHASE 1 - AUDIT
- Lancer tdd-discovery + security-specialist
- Fagan 4 rounds (6 agents × 4)
- Générer backlog

PHASE 2 - PLANNING
- Prioriser issues (Security first)
- Créer micro-sprints (6 tâches max chacun)

PHASE 3 - EXÉCUTION
- 6 agents parallèles par sprint
- Validation PM entre chaque batch
- tech-doc-writer en continu

PHASE 4 - VALIDATION
- devils-advocate final
- security re-audit
- pytest + ruff
- Mise à jour .ai/thought_log.md

Garde uniquement les rapports finaux dans ton contexte.
```

---

## 6. Devils Advocate Review

```
Agis comme un devils-advocate sur le plan/code suivant.

Questions à poser :
1. Quels edge cases ne sont pas gérés ?
2. Que se passe-t-il si X échoue ?
3. Est-ce over-engineered ? Y a-t-il plus simple ?
4. Quels tests manquent ?
5. Quelles hypothèses sont fausses ?

Sois critique, pas complaisant. Le but est de trouver les failles.

Output : Liste numérotée avec sévérité (Critical/Major/Minor).
```

---

## 7. Security Specialist Audit

```
Effectue un audit sécurité complet selon .cursor/rules/fagan-reviewer.md section 3.4.

Checklist :
□ Secrets hardcodés (API keys, tokens, passwords)
□ SQL injection (string format vs params)
□ Path traversal (user input dans chemins)
□ SSRF (URLs externes non validées)
□ Auth/AuthZ bypass possibles
□ Données sensibles dans logs
□ Dépendances vulnérables (check pyproject.toml)

Output : .ai/reports/security-audit.md avec findings par sévérité.
```

---

## 8. TDD Discovery

```
Analyse les tests existants du projet.

Actions :
1. Parcourir tests/ récursivement
2. Identifier :
   - Structure (pytest, fixtures, mocks utilisés)
   - Couverture par module
   - Patterns de test
   - Tests critiques à ne pas casser
3. Lister les zones non testées

Output : .ai/reports/tdd-discovery.md
```

---

## 9. Documentation Update

```
Agis comme tech-doc-writer.

Après les changements effectués, mets à jour :
1. .ai/project_map.md si architecture modifiée
2. .ai/data_lineage.md si flux de données changé
3. .ai/thought_log.md avec entrée datée
4. Docstrings des fonctions modifiées

Assure-toi que la documentation reflète l'état actuel du code.
```

---

## 10. Prompt Sub-Agent Générique

```
## Contexte
Tu es un sub-agent spécialisé [TYPE].
Projet: OpenSpartan Graph (dashboard Halo Infinite)
Architecture: SQLite (métadonnées) + Parquet (matchs) + DuckDB (requêtes)

## Fichiers à Lire d'Abord
- .ai/project_map.md
- [fichiers spécifiques]

## Ta Mission Unique
[Description précise]

## Contraintes
- Ne modifier QUE [fichiers listés]
- Respecter les patterns existants (lire fichiers voisins)
- Code en anglais, commentaires en français
- Utiliser Pydantic v2 pour validation
- Polars (pas Pandas) pour gros volumes

## Checklist de Completion
- [ ] Critère 1
- [ ] Critère 2
- [ ] Tests passent

## Format de Rapport
status: Done | Failed | Blocked
files_modified: [liste]
summary: [3-5 lignes]
issues: [si applicable]
```

---

## Notes d'Utilisation

1. **Copier le prompt approprié** dans un nouveau chat
2. **Ajouter le contexte spécifique** (fichiers, issues, etc.)
3. **Utiliser Opus** pour le PM, **Sonnet** pour les sub-agents
4. **Garder le chat principal propre** : seuls les rapports finaux y restent

---

## Voir Aussi

- `.cursor/rules/pm-orchestrator.md` - Rôle du PM
- `.cursor/rules/multi-agent-orchestration.md` - Protocole complet
- `.cursor/rules/fagan-reviewer.md` - Méthodologie Fagan
- `.cursor/rules/output-style.md` - Style de communication
