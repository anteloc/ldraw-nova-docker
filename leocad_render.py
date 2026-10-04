"""
Thin wrapper around the `leocad` CLI, for other Python code in this container
to import.

Assumes a persistent Xvfb is already running and DISPLAY is already set —
that's handled once, for the whole container, by /usr/local/bin/entrypoint.sh.
Because of that, each call here is an ordinary subprocess call with no extra
virtual-display startup cost, so it's fine to call this many times in a loop
or from a long-running worker/service process.

Also runnable by hand, e.g. from a `docker exec` shell:

    python3 /app/leocad_render.py /opt/models-gallery/copper-bean.mpd
    # -> /data/output/copper-bean.png
"""
from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence, Tuple

# Host ./data is mounted here. (LDRAW_NOVA_DATA_DIR only exists to point tests elsewhere.)
#   generated/  the model collection: flat, each model next to its .png snapshot and .csv BOM
#   output/     work area: agents keep one folder per chat here; CLI renders default here
DATA_DIR = Path(os.environ.get("LDRAW_NOVA_DATA_DIR", "/data"))
GENERATED_DIR = DATA_DIR / "generated"
OUTPUT_DIR = DATA_DIR / "output"

MODEL_SUFFIXES = (".mpd", ".ldr", ".dat")


def list_models(folder: str | Path = GENERATED_DIR) -> list[Path]:
    """LDraw models directly inside `folder` (not in subfolders)."""
    folder = Path(folder)
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in MODEL_SUFFIXES)


def snapshot_path_for(model_path: str | Path) -> Path:
    """A model's snapshot: the sibling .png with the same base name (car.mpd -> car.png)."""
    return Path(model_path).with_suffix(".png")


def render_snapshot(model_path: str | Path, width: int = 1024, height: int = 768, timeout: int = 300) -> Path:
    """Render a model's snapshot from LeoCAD's default "home" view."""
    return render_image(model_path, snapshot_path_for(model_path), width=width, height=height,
                        camera_angles=None, extra_args=["--viewpoint", "home"], timeout=timeout)


def bom_path_for(model_path: str | Path) -> Path:
    """A model's bill of materials: the sibling .csv with the same base name (car.mpd -> car.csv)."""
    return Path(model_path).with_suffix(".csv")


BOM_HEADER = "Part Name,Color,Quantity,Part ID,Color Code\n"


def _has_parts(model_path: str | Path) -> bool:
    """Whether the model, with its submodels expanded, references any part.

    LeoCAD's CSV export never returns for a model without parts (it waits on a
    dialog nobody can close), so export_bom() checks this first."""
    files: dict[Optional[str], list[str]] = {}
    order: list[str] = []
    current: Optional[str] = None
    with open(model_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            words = line.split()
            if len(words) >= 3 and words[0] == "0" and words[1] == "FILE":
                current = line.split("FILE", 1)[1].strip().lower()
                files.setdefault(current, [])
                order.append(current)
            elif len(words) >= 15 and words[0] == "1":
                ref = line.split(None, 14)[14].strip().lower().replace("\\", "/")
                files.setdefault(current, []).append(ref)
    stack, seen = [order[0] if order else None], set()
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        for ref in files.get(name, []):
            if ref not in files:
                return True          # not one of the file's own submodels: a part (even an unknown one)
            stack.append(ref)
    return False


def export_bom(model_path: str | Path, output_path: Optional[str | Path] = None, timeout: int = 60) -> Path:
    """Write the model's parts list with LeoCAD's CSV export
    (columns: Part Name, Color, Quantity, Part ID, Color Code)."""
    output_path = Path(output_path) if output_path else bom_path_for(model_path)
    if not _has_parts(model_path):
        output_path.write_text(BOM_HEADER)       # empty BOM; LeoCAD would hang on this model
        return output_path
    subprocess.run(["leocad", str(model_path), "--export-csv", str(output_path)],
                   check=True, capture_output=True, text=True, timeout=timeout)
    if not output_path.exists():
        raise RuntimeError(f"leocad exited 0 but did not create {output_path}")
    return output_path


def bom_part_count(bom_path: str | Path) -> Optional[int]:
    """Total number of parts in a BOM written by export_bom(), or None if unreadable."""
    try:
        with open(bom_path, newline="", encoding="utf-8", errors="replace") as fh:
            reader = csv.DictReader(fh)
            if "Quantity" not in (reader.fieldnames or []):
                return None
            return sum(int(row["Quantity"]) for row in reader)
    except (OSError, KeyError, ValueError):
        return None


def render_image(
    model_path: str | Path,
    output_path: str | Path,
    width: int = 1280,
    height: int = 720,
    camera_angles: Optional[Tuple[float, float]] = (30, 40),
    orthographic: bool = False,
    submodel: Optional[str] = None,
    step: Optional[int] = None,
    libpath: Optional[str | Path] = None,
    extra_args: Optional[Sequence[str]] = None,
    timeout: int = 120,
) -> Path:
    """Render a single LDraw model (.ldr/.mpd) to an image with LeoCAD.

    `libpath` is normally left as None: the container already sets LEOCAD_LIB
    to the full LDraw library baked into the image, so LeoCAD finds parts
    without any extra flag. Pass `libpath` only if you need to point a
    specific call at a different parts library.

    Raises:
        subprocess.CalledProcessError: leocad exited non-zero.
        subprocess.TimeoutExpired: render took longer than `timeout` seconds.
        RuntimeError: leocad exited 0 but produced no output file (usually a
            bad model path, or a submodel/step that doesn't exist).
    """
    model_path = Path(model_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "leocad", str(model_path),
        "-i", str(output_path),
        "-w", str(width),
        "-h", str(height),
    ]
    if libpath is not None:
        cmd += ["-l", str(libpath)]
    if camera_angles is not None:
        cmd += ["--camera-angles", str(camera_angles[0]), str(camera_angles[1])]
    if orthographic:
        cmd.append("--orthographic")
    if submodel:
        cmd += ["-s", submodel]
    if step is not None:
        cmd += ["-f", str(step), "-t", str(step)]
    if extra_args:
        cmd += list(extra_args)

    subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=timeout)

    if not output_path.exists():
        raise RuntimeError(
            f"leocad exited 0 but did not create {output_path} "
            f"(check the model path, submodel name, or step number)"
        )
    return output_path


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=f"Render LDraw models (.ldr/.mpd) to PNG with LeoCAD. "
                    f"Images go to {OUTPUT_DIR} unless -o is given.",
    )
    parser.add_argument("models", nargs="+", type=Path, help="model file(s) to render")
    parser.add_argument("-o", "--output-dir", type=Path, default=OUTPUT_DIR,
                        help="directory for the rendered <model-name>.png files (default: %(default)s)")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--camera-angles", type=float, nargs=2, metavar=("LAT", "LON"),
                        default=(30, 40), help="orbit camera angles in degrees (default: 30 40)")
    parser.add_argument("--orthographic", action="store_true")
    parser.add_argument("-s", "--submodel")
    parser.add_argument("--step", type=int, help="render only this build step")
    args = parser.parse_args(argv)

    failed = 0
    for model in args.models:
        out_path = args.output_dir / f"{model.stem}.png"
        print(f"Rendering {model} -> {out_path}", flush=True)
        try:
            render_image(
                model, out_path,
                width=args.width, height=args.height,
                camera_angles=tuple(args.camera_angles),
                orthographic=args.orthographic,
                submodel=args.submodel, step=args.step,
            )
        except subprocess.CalledProcessError as exc:
            failed += 1
            print(f"  FAILED (leocad exit {exc.returncode}): {exc.stderr.strip()}", file=sys.stderr)
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            failed += 1
            print(f"  FAILED: {exc}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
