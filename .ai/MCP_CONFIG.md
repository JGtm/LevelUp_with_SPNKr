# Configuration MCP pour Cursor

## Comment configurer

1. Ouvrir **Cursor Settings** (Ctrl+,)
2. Aller dans **Features > MCP Servers**
3. Cliquer sur **+ Add new MCP server** ou éditer le JSON
4. Coller la configuration ci-dessous

---

## Configuration JSON à copier

```json
{
  "duckdb": {
    "command": "C:\\Users\\Guillaume\\AppData\\Local\\Python\\pythoncore-3.14-64\\Scripts\\duckdb-mcp-server.exe",
    "args": [
      "--db-path",
      ":memory:"
    ]
  }
}
```

---

## Outils disponibles après configuration

### MCP DuckDB
Permet d'exécuter du SQL directement sur les données Halo :

```sql
-- Lire les Parquet
SELECT * FROM read_parquet('C:/Users/Guillaume/Downloads/Scripts/Openspartan-graph/data/warehouse/match_facts/**/*.parquet') LIMIT 10;

-- Attacher SQLite
ATTACH 'C:/Users/Guillaume/Downloads/Scripts/Openspartan-graph/data/warehouse/metadata.db' AS meta (TYPE sqlite);

-- Jointure Parquet + SQLite
SELECT p.name_fr, COUNT(*) as matches
FROM read_parquet('C:/Users/Guillaume/Downloads/Scripts/Openspartan-graph/data/warehouse/match_facts/**/*.parquet') f
JOIN meta.playlists p ON f.playlist_id = p.uuid
GROUP BY p.name_fr;
```

---

## Note sur le serveur Filesystem

Le serveur `@modelcontextprotocol/server-filesystem` nécessite Node.js/npm.
Cursor a déjà accès aux fichiers via ses outils intégrés (Read, Write, etc.).
Le MCP filesystem est **optionnel** pour ce projet.

---

## Vérification

Après avoir ajouté la configuration :
1. Redémarrer Cursor
2. Ouvrir une nouvelle conversation
3. Demander : "Utilise le MCP duckdb pour exécuter SELECT 1"
