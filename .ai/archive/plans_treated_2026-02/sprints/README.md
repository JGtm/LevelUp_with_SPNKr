# Sprints - Gestion des Micro-Sprints

Ce dossier contient les plans d'exécution pour l'orchestration multi-agents.

## Structure

```
sprints/
├── README.md                    # Ce fichier
└── micro-sprints/
    ├── sprint-001.md           # Premier sprint
    ├── sprint-002.md           # Deuxième sprint
    └── ...
```

## Format d'un Sprint

Chaque fichier sprint suit le template défini dans `.cursor/rules/multi-agent-orchestration.md`.

## Workflow

1. **PM crée les sprints** : Décompose les issues en micro-tâches
2. **Agents exécutent** : 6 tâches parallèles max par sprint
3. **PM valide** : Checklist de completion
4. **Passage au suivant** : Si validation OK

## Commandes

- `/orchestrate-audit` : Génère les issues
- `/orchestrate-implement` : Exécute les sprints
- `/orchestrate-full` : Cycle complet
