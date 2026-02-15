"""Script de vérification des imports après migration Polars."""

import sys

modules = [
    ("src.ui.cache", ["load_df_optimized", "_to_polars"]),
    ("src.ui.formatting", ["format_date_fr", "to_paris_naive", "_parse_datetime"]),
    ("src.ui.commendations", ["render_h5g_commendations_section", "_to_polars"]),
    ("src.ui.perf", ["perf_dataframe", "render_perf_panel", "_to_polars"]),
]

all_ok = True
for mod_name, funcs in modules:
    try:
        mod = __import__(mod_name, fromlist=funcs)
        for func in funcs:
            if hasattr(mod, func):
                print(f"[OK] {mod_name}.{func}")
            else:
                print(f"[MISSING] {mod_name}.{func}")
                all_ok = False
    except Exception as e:
        print(f"[FAIL] {mod_name}: {e}")
        all_ok = False

if all_ok:
    print("\n=== Tous les imports sont OK ===")
    sys.exit(0)
else:
    print("\n=== Des erreurs ont été détectées ===")
    sys.exit(1)
