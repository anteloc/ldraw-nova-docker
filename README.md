# ldraw-nova-docker

## GLB to LEGO

On **My Models**, choose **Import GLB**, select a colored `.glb`, name the model
and keep the default **Auto · about 3,000 bricks** or choose a manual detail level.
Auto chooses the voxel world dimensions from the actual repaired, packed brick
count, aiming within 10% of 3,000. The result shows its count and dimensions;
if conversion limits prevent reaching the target, it states that explicitly.
**Convert to LEGO** samples embedded texture/material
and vertex colors with Python Trimesh, maps them to LDraw colors, and uses the
existing sculpture packing and connectivity repair. The result saves to My Models
with a preview, parts list, connected build steps and **Sculpture editor** cells.
Choose **Edit voxels** to adjust it, or open it in the existing viewer/player and
download the MPD. No provider login is needed for an import.

Use an uncompressed, self-contained glTF 2.0 binary with embedded PNG/JPEG textures,
up to 16 MB, 100,000 instanced triangles and 4 megapixels per texture. The longest
manual grid dimension can be 16, 24, 32 or 48 studs; lower detail converts faster
and uses fewer bricks. Auto tries at most five sizes, bounded to 8–96 cells per
axis, 262,144 world cells and 65,536 occupied cells. Models that exceed bounded voxelization or cannot pass
connectivity repair are rejected with an actionable error. Keep the dialog open
while conversion runs. Only one GLB import runs at a time. Part connectivity is
checked; physical stability is not certified.

Build with the paired `ldraw-nova` **codex/glb-to-lego** branch until the companion
PR is included in a matching release. The image's sculpture extra now includes
Trimesh, Pillow and Rtree; it does not use the legacy C++ voxelizer.

> [!IMPORTANT]
> **Want to try the ldraw-nova web app? Start at the [ldraw-nova repo](https://github.com/anteloc/ldraw-nova#installation).**
>
> This repo is the Docker packaging of [ldraw-nova](https://github.com/anteloc/ldraw-nova). It turns that toolset into a web app you can run. It isn't meant to be used on its own: the Docker image is built from both repos, cloned side by side at the same tag.
>
> The project's landing page, demo video and installation steps are all in **ldraw-nova**. This README will only cover the technical side of the Docker image, and it's being rewritten.
>
> 👉 **[Go to ldraw-nova and install the web app](https://github.com/anteloc/ldraw-nova#installation)**

## Optional Sculpture model

Open **Additional settings** beside the prompt and enable **Sculpture model** to
generate a voxel sculpture with connected bricks and deterministic instruction
ordering. It uses the paired
`ldraw-nova` sculpture toolkit and the existing model cards, viewer and step player;
ordinary part-based generation remains the default. Build both companion branches
together until sculpture support is included in a matching release.

Hover or tap the info icon for an example and sculpture-editor help. Completed
sculpture outputs offer **Sculpture editor** on their model card: rotate, add, paint
or erase cells, then **Save model** to rebuild bricks and instructions as a new
version. The original is kept. Editing and rebuilding need no AI request.
The example image is rendered from a
[Pikachu export from BrickBuilderAI](https://brickbuilder.ai/generated-model?id=4121b49f-7e0a-482b-9e4e-7148a5250f04),
rebuilt with the paired toolkit's [example importer](https://github.com/jjohnson5253/ldraw-nova/blob/codex/3d-sculpture-mode/examples/sculpture/README.md).

The editor adapts BrickBuilderAI’s manual voxel viewer; its
[MIT license](web/frontend/public/licenses/BrickBuilderAI-MIT.txt) is included in the web build.

## Overview

COMING SOON

## Build

COMING SOON

## Configuration

COMING SOON

## Development

COMING SOON

## Acknowledgements

COMING SOON
