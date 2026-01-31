# Commande /ingest

Lance l'ingestion des données Halo JSON vers le stockage hybride.

## Étapes

1. Exécuter le script d'ingestion :
   ```bash
   python scripts/ingest_halo_data.py --action all -v
   ```

2. Vérifier le résultat dans la console

3. Mettre à jour `.ai/data_lineage.md` avec les nouvelles stats
