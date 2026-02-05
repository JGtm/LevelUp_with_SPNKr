-- Script SQL pour corriger les métadonnées NULL dans match_stats
-- Utilisation: ATTACH 'data/warehouse/metadata.duckdb' AS meta; puis exécuter ce script

-- 1. Résoudre map_name depuis metadata.duckdb
UPDATE match_stats
SET map_name = (
    SELECT public_name
    FROM meta.maps
    WHERE meta.maps.asset_id = match_stats.map_id
    LIMIT 1
)
WHERE map_name IS NULL
  AND map_id IS NOT NULL
  AND EXISTS (SELECT 1 FROM meta.maps WHERE meta.maps.asset_id = match_stats.map_id);

-- 2. Fallback sur map_id si pas trouvé dans metadata
UPDATE match_stats
SET map_name = map_id
WHERE map_name IS NULL
  AND map_id IS NOT NULL;

-- 3. Résoudre playlist_name depuis metadata.duckdb
UPDATE match_stats
SET playlist_name = (
    SELECT public_name
    FROM meta.playlists
    WHERE meta.playlists.asset_id = match_stats.playlist_id
    LIMIT 1
)
WHERE playlist_name IS NULL
  AND playlist_id IS NOT NULL
  AND EXISTS (SELECT 1 FROM meta.playlists WHERE meta.playlists.asset_id = match_stats.playlist_id);

-- 4. Fallback sur playlist_id si pas trouvé dans metadata
UPDATE match_stats
SET playlist_name = playlist_id
WHERE playlist_name IS NULL
  AND playlist_id IS NOT NULL;

-- 5. Résoudre pair_name depuis metadata.duckdb (essayer les deux noms de table possibles)
UPDATE match_stats
SET pair_name = (
    SELECT public_name
    FROM meta.map_mode_pairs
    WHERE meta.map_mode_pairs.asset_id = match_stats.pair_id
    LIMIT 1
)
WHERE pair_name IS NULL
  AND pair_id IS NOT NULL
  AND EXISTS (SELECT 1 FROM information_schema.tables
              WHERE table_schema = 'meta' AND table_name = 'map_mode_pairs')
  AND EXISTS (SELECT 1 FROM meta.map_mode_pairs WHERE meta.map_mode_pairs.asset_id = match_stats.pair_id);

-- Alternative pour playlist_map_mode_pairs si map_mode_pairs n'existe pas
UPDATE match_stats
SET pair_name = (
    SELECT public_name
    FROM meta.playlist_map_mode_pairs
    WHERE meta.playlist_map_mode_pairs.asset_id = match_stats.pair_id
    LIMIT 1
)
WHERE pair_name IS NULL
  AND pair_id IS NOT NULL
  AND EXISTS (SELECT 1 FROM information_schema.tables
              WHERE table_schema = 'meta' AND table_name = 'playlist_map_mode_pairs')
  AND EXISTS (SELECT 1 FROM meta.playlist_map_mode_pairs
              WHERE meta.playlist_map_mode_pairs.asset_id = match_stats.pair_id);

-- 6. Fallback sur pair_id si pas trouvé dans metadata
UPDATE match_stats
SET pair_name = pair_id
WHERE pair_name IS NULL
  AND pair_id IS NOT NULL;

-- 7. Résoudre game_variant_name depuis metadata.duckdb
UPDATE match_stats
SET game_variant_name = (
    SELECT public_name
    FROM meta.game_variants
    WHERE meta.game_variants.asset_id = match_stats.game_variant_id
    LIMIT 1
)
WHERE game_variant_name IS NULL
  AND game_variant_id IS NOT NULL
  AND EXISTS (SELECT 1 FROM meta.game_variants
              WHERE meta.game_variants.asset_id = match_stats.game_variant_id);

-- 8. Fallback sur game_variant_id si pas trouvé dans metadata
UPDATE match_stats
SET game_variant_name = game_variant_id
WHERE game_variant_name IS NULL
  AND game_variant_id IS NOT NULL;
