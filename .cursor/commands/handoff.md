# Commande /handoff

Prépare un document de passation pour la prochaine session.

## Quand l'utiliser
- Avant de terminer une session longue
- Quand le contexte devient trop chargé
- Avant un changement de sujet majeur

## Étapes

1. **Résumer** l'état actuel du travail
2. **Documenter** dans `.ai/thought_log.md` :
   ```markdown
   ### [YYYY-MM-DD] - [Sujet]
   **Contexte** : Ce qui a été demandé
   **Raisonnement** : Pourquoi cette approche
   **Décision** : Ce qui a été fait
   **Suivi** : Ce qui reste à faire
   ```

3. **Lister** les fichiers modifiés
4. **Indiquer** les prochaines étapes claires

## Le prochain agent pourra
- Lire `.ai/thought_log.md` pour reprendre le contexte
- Continuer sans perdre l'historique des décisions
