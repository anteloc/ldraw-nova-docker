# The Tidal Observatory

An original coastal science institute by OpenAI, created for an open-ended building request.

## Final model
- Editable, self-contained LDraw file: tidal-observatory.mpd
- 2,734 physical placements in 20 embedded assembly sections
- Footprint: 48 x 40 studs; approximate overall dimensions: 38.4 x 32.0 x 35.7 cm
- Limestone hall, sand-green copper dome, glazed weather lantern, dark-blue hipped roof, entrance portico, furnished rear cutaways, rooftop telescope and planted harbor terrace
- Three chart desks with nautical maps, archive shelves, chairs, lamps, floor inlays and three static telescopes

Open the MPD in an LDraw-compatible editor. The published chat model provides interactive viewing and source STEP playback. The source steps are assembly groups, not a fully tested printed building manual.

## Files
- tidal-observatory.plan.json: editable placement plan, including all generated sections
- tidal-observatory-generate.py: reproducible parameterized source
- tidal-observatory-design-brief.md: original design intent
- tidal-observatory-module-contracts.md: planned module envelopes and interfaces
- tidal-observatory-sources.json: attribution and reference-study manifest; no copied OMR assemblies are embedded in this model
- tidal-observatory-visual-review.md: images opened, revisions and final assessment
- tidal-observatory-verification.md: check coverage, remaining warnings and physical limitations
- tidal-observatory.validation.json: final all-contact geometry report
- tidal-final-module-checks/: ten final local contact reports
- tidal-observatory.bom.json and tidal-observatory-review/leocad-bom.csv: parts lists
- tidal-observatory.bom-comparison.json: exact agreement of Python and LeoCAD inventories
- tidal-observatory.cad-check.json: syntax/reference and LeoCAD import smoke test
- tidal-observatory-review/: six final exterior views
- tidal-upper-hall-final/ and tidal-ground-hall-final/: furnished interior previews
- tidal-lantern-cap-review/: final roof-corner close-ups
- tidal-observatory-delivery-manifest.json: file hashes for the packaged revision

The separate reference-catalog folder is study evidence only, not a dependency of the final MPD. Discovery queries and availability evidence are included for provenance. Earlier draft images/reports are not included in this package.

## Reproduce in the LDraw Astra toolkit
Place the generator and plan in the toolkit's output directory. Run from the repository root:

```sh
.venv/bin/python output/tidal-observatory-generate.py
./ldraw-agent build output/tidal-observatory.plan.json --output output/tidal-observatory.mpd --force --detail summary
./ldraw-agent validate output/tidal-observatory.mpd --geometry --contacts all --detail summary
./ldraw-agent render output/tidal-observatory.mpd --outdir output/tidal-observatory-review --views home front back right top bottom
./ldraw-agent compare-bom output/tidal-observatory.mpd --csv output/tidal-observatory-review/leocad-bom.csv
```

The generator writes its plans beside itself; use the generator rather than editing only the MPD if changes must survive a rebuild. An installed LDraw library and LeoCAD are required by the toolkit but are not bundled.

## Verification and limitations
The final all-contact geometry check and ten module inspections pass their selected checks; the Python and LeoCAD inventories both count 2,734 placements with no differences. Geometry resolution is complete. The final report retains two warnings for fragmented connector evidence and general material-collision review. See the verification document for specific parts and explanations.

Physical validity remains not proven: no bricks were assembled, and strength, clutch, insertion access and retail part/color availability are not certified. The dome is a closed decorative cap, the telescopes are static, and no internal stairs or lighting electronics are represented. Rear cutaways are intentional. Prototype the dome, glazing, lamp collars and telescope mounts before ordering parts.

Final MPD SHA-256: 4ac1340f73cbba19eaa69f3995dfde0e75427137bad11b5e197dc782aeaccccc
