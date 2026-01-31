# Commande /plan

Crée un plan d'implémentation structuré avant de coder.

## Étapes

1. **Lire le contexte** :
   - `.ai/project_map.md`
   - `.ai/thought_log.md`
   - Documentation existante dans `.ai/features/`

2. **Analyser** la demande et identifier :
   - Fichiers à modifier
   - Nouvelles dépendances nécessaires
   - Risques et impacts

3. **Produire un plan** dans `.ai/plans/[date]-[sujet].md` :
   ```markdown
   # Plan: [sujet]
   Date: YYYY-MM-DD

   ## Objectif
   [Description claire]

   ## Tâches
   - [ ] Tâche 1
   - [ ] Tâche 2

   ## Fichiers impactés
   - `path/file.py` : modification X

   ## Tests à écrire
   - test_xxx

   ## Risques
   - Risque 1 : mitigation
   ```

4. **Attendre validation** avant d'implémenter
