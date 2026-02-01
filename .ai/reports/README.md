# Reports - Rapports des Sub-Agents

Ce dossier contient les rapports générés par les sub-agents spécialisés.

## Fichiers Attendus

| Fichier | Agent | Contenu |
|---------|-------|---------|
| `tdd-discovery.md` | tdd-discovery | Analyse des tests existants |
| `architecture-proposal.md` | requirements-architect | Design proposé |
| `devils-advocate.md` | devils-advocate | Challenges et edge cases |
| `security-audit.md` | security-specialist | Vulnérabilités identifiées |
| `fagan-round-N.md` | fagan-inspector | Résultats round N |
| `fagan-consolidated.md` | PM (Opus) | Synthèse finale Fagan |

## Cycle de Vie

1. **Génération** : Sub-agent crée le rapport
2. **Consolidation** : PM agrège les rapports
3. **Action** : Issues → Micro-sprints
4. **Archivage** : Après completion, move vers `archive/`

## Convention de Nommage

```
{agent}-{date}-{scope}.md

Exemples:
- security-audit-2026-02-01-full.md
- fagan-round-3-2026-02-01.md
- devils-advocate-2026-02-01-sync-feature.md
```
