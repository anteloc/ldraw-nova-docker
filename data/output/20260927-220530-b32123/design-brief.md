# Azure Sprint — design brief and provenance

Compact six-stud-wide racing coupe, front toward -Z, road at Y=0. A long, curved azure bonnet with paired white racing stripes is the focal point; a low smoked-glass cabin with black rounded roof and four matching wheel arches support the silhouette. White flank blades and rear marker tie the livery together. Black grille and bumpers, clear front lamps and red tail lamps distinguish the ends. Quiet azure rear deck prevents the accents from becoming noisy. Display cabin only; no claimed minifigure capacity or dynamic steering.

Envelope X=-60..60, Z=-208..208, Y=-126..0 LDU. Axles Z=±100, wheelbase 200, tyre centres X=±46 and Y=-25, track 92; wheel radius 25. Body width 120 LDU; bonnet, cabin and rear deck are separate visible masses. Seven embedded sections: two wheel-pin axles, bonded chassis, body/wheel arches, front and rear fascia, cabin, main. Construction order: wheels and spine, deck and arches, fascia, transparent cabin, roof and decorative surface.

## Attribution

The measured chassis, touring wheel/rim/tyre transforms, fender interface, body deck, fascia and glazing placements are **adapted**, not original, from `examples/vehicle-atlas/grand-tourer/scene.plan.json` (author `ldraw-astra vehicle examples`). Azure Sprint's generator renames sections, changes the colour composition, adds the paired white curved-bonnet stripe, white waistline/rear marker, dark grille and bumpers, and adjusts the cabin surround. The atlas grand-tourer preview was opened; the separate annotated car-transporter model 6753-1 was found in a model reference search but not copied. Part search returned 50950 curved slopes; official library geometry and the installed wheel recipe were inspected. No reference MPD asset or custom DAT was copied, so there is no extract manifest. The generator records the actual adapted source path.

## Module review

- Touring axles: measured holder/rim/tyre interfaces; wheel road check passes.
- Chassis: narrow plate spine and joined deck under the body; bottom image reviewed.
- Body: all four arch envelopes and continuous white shoulder; side image reviewed.
- Fascias: separate lamps and grilles; front/back images reviewed.
- Cabin: glass and roof for a display silhouette; actual figure fit and interior access unverified.
