"""
Example worker: make sure every model in /data/generated has a snapshot and a BOM.

/data/generated is the model collection (flat: no subfolders). Each model
(.mpd/.ldr/.dat) gets two siblings with the same base name:
  <name>.png  snapshot, rendered from LeoCAD's home view
  <name>.csv  bill of materials, from LeoCAD's CSV export
Models that already have them are skipped, so it's cheap to re-run; delete a
.png or .csv to have it regenerated. The web app's Models page does the same
thing automatically when you open it.

Run:
    docker compose exec ldraw-astra-app python3 /app/example.py
"""
from leocad_render import (GENERATED_DIR, bom_part_count, bom_path_for, export_bom, list_models,
                           render_snapshot, snapshot_path_for)


def main() -> None:
    models = list_models(GENERATED_DIR)
    if not models:
        print(f"No .mpd/.ldr/.dat files in {GENERATED_DIR} — add some and re-run.")
        return

    for model in models:
        for kind, path, make in (("snapshot", snapshot_path_for(model), render_snapshot),
                                 ("BOM", bom_path_for(model), export_bom)):
            if path.exists():
                continue
            print(f"{model.name}: writing {kind} {path.name}", flush=True)
            try:
                make(model)
            except Exception as exc:  # noqa: BLE001 - example script, keep it simple
                print(f"  FAILED: {exc}")
        parts = bom_part_count(bom_path_for(model))
        print(f"{model.name}: {parts if parts is not None else '?'} parts")


if __name__ == "__main__":
    main()
