"""
Example worker: render every .ldr/.mpd file found anywhere under /data into
/data/output, mirroring the input's sub-folder layout.

/data is where you bind-mount a host folder (see README.md / docker-compose.yml),
so anything written to /data/output here is immediately visible on the host,
and any other process in this container (or another container sharing the
same mount) can read it too.

Run:
    docker run --rm --init -v "$PWD/data:/data" leocad-app python3 /app/example.py
"""
from leocad_render import DATA_DIR, OUTPUT_DIR, render_image

MODEL_SUFFIXES = {".ldr", ".mpd"}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Everything under /data is input, except our own output.
    models = sorted(
        p for p in DATA_DIR.rglob("*")
        if p.is_file() and p.suffix.lower() in MODEL_SUFFIXES and OUTPUT_DIR not in p.parents
    )
    if not models:
        print(f"No .ldr/.mpd files found under {DATA_DIR} — add some and re-run.")
        return

    for model in models:
        # data/a/b/car.ldr -> data/output/a/b/car.png (keeps same-named models apart)
        out_path = OUTPUT_DIR / model.relative_to(DATA_DIR).with_suffix(".png")
        print(f"Rendering {model.relative_to(DATA_DIR)} -> {out_path.relative_to(DATA_DIR)}")
        try:
            render_image(model, out_path)
        except Exception as exc:  # noqa: BLE001 - example script, keep it simple
            print(f"  FAILED: {exc}")


if __name__ == "__main__":
    main()
