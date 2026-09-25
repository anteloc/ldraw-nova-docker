"""
Thin wrapper around the `leocad` CLI, for other Python code in this container
to import.

Assumes a persistent Xvfb is already running and DISPLAY is already set —
that's handled once, for the whole container, by /usr/local/bin/entrypoint.sh.
Because of that, each call here is an ordinary subprocess call with no extra
virtual-display startup cost, so it's fine to call this many times in a loop
or from a long-running worker/service process.

Also runnable by hand, e.g. from a `docker exec` shell:

    python3 /app/leocad_render.py /opt/models-annotated/8303-1.mpd
    # -> /data/output/8303-1.png
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence, Tuple

# Host ./data is mounted here. Everything under DATA_DIR is input; rendered
# images go to OUTPUT_DIR.
DATA_DIR = Path("/data")
OUTPUT_DIR = DATA_DIR / "output"


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
