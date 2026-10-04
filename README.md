# ldraw-nova-docker

> [!IMPORTANT]
> **Want to try the ldraw-nova web app? Start at the [ldraw-nova repo](https://github.com/anteloc/ldraw-nova#installation).**
>
> This repo is the Docker packaging of [ldraw-nova](https://github.com/anteloc/ldraw-nova). It turns that toolset into a web app you can run. It isn't meant to be used on its own: the Docker image is built from both repos, cloned side by side at the same tag.
>
> The project's landing page, demo video and installation steps are all in **ldraw-nova**. This README will only cover the technical side of the Docker image, and it's being rewritten.
>
> 👉 **[Go to ldraw-nova and install the web app](https://github.com/anteloc/ldraw-nova#installation)**

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
## My Parts and inventory fitting

Open **My Parts** in the sidebar to add the pieces you own:

- Download the public set catalog once, then search locally by set number or name. Each result links to LEGO instructions and the BrickLink catalog. Add one or several copies of a set.
- Paste a LEGO product/instructions URL, a BrickLink set URL, or a set number to import its indexed inventory. Public CSV/XML export URLs on the supported catalog hosts and `raw.githubusercontent.com` are also accepted. Sign-in-only downloads must be exported in your browser and uploaded.
- Upload a UTF-8 CSV or BrickLink inventory XML (2 MB maximum). CSV accepts Nova BOM columns (`part_id,color_code,quantity`), Rebrickable (`part_num,color_id,quantity`), and BrickLink (`ItemID,ColorID,Qty`). Select the export's ID system; Nova BOM color columns explicitly identify LDraw IDs. XML always uses BrickLink IDs and supports `QTY`/`MINQTY`; upload physical part lots, not set/minifigure items.
- Search the installed LDraw library to add loose pieces or correct unknown imports. Imported lots with an unknown part or color remain visible and do not enter the usable budget. Imports append quantities; edit lots to correct quantities. Inventory supports 10,000 lots and 1,000,000 pieces.

The catalog is indexed from [Rebrickable's public downloads](https://rebrickable.com/downloads/), with BrickLink color names from its [official color guide](https://v2.bricklink.com/en-us/catalog/color-guide). No API key is required. Latest set inventories include nested sets and minifigure inventories; spare parts are excluded. LEGO and BrickLink URLs identify sets; their web pages are not scraped for authenticated inventory. Color IDs are mapped by explicit names to the installed LDraw palette, never by assuming that different catalogs share numeric IDs. Part IDs must resolve in that installed library; printed or variant IDs that do not resolve need manual mapping. If BrickLink's color guide is unavailable, basic color mappings remain available and other lots can be mapped manually.

Select **Use my parts** in the chat composer to give Nova a fixed inventory snapshot for that turn. Nova receives instructions to design or revise against the snapshot and check its fitting report, with up to three redesign attempts for shortages. The backend enforces the same fitting step at every publication. Alternatively, **Use my parts** on a saved model fits and renders a new version directly, without a provider request. It preserves your source model.

Fitting reserves all exact part/color matches first, then chooses available colors, then tries quantity-bounded, exact-footprint splits of known plain rectangular studded bricks or plates with the same height. Nova expands physical occurrences, preserves their world transforms and build steps, and checks the fitted model with its structural and geometry validators before publication. A missing piece remains in the design and appears in an explicit shortage report. The bounded search is best effort, not a global optimum; it does not substitute arbitrary complex shapes or prove physical buildability. Inputs are limited to 5,000 physical placements; custom assembly geometry and transform metadata that cannot survive flattening are rejected. Output is capped at 10,000 placements.

Matched/missing counts, color changes, splits, and shortages are saved with each fitted model and bound to its file revision. Inventory is a planning budget, and fitting never consumes stock. Quantities and the searchable catalog are separate SQLite databases under private `data/parts/`; they are not a shared user database or exposed as downloadable files. The authoritative per-turn stock snapshot is backend-owned; the agent's editable guidance copy cannot increase the fitting budget. Refreshing the catalog replaces it atomically, preserving existing data on failure.

Run inventory tests with `npm test` in `web/frontend`, and the backend's `tests/test_owned_parts.py` and `tests/test_inventory_fit.py` inside the app container as described in `web/backend/tests/conftest.py`. The latter includes real Nova validation, LeoCAD rendering, and BOM comparison.
