# Verification record

Final source: tidal-observatory.mpd
SHA-256: 4ac1340f73cbba19eaa69f3995dfde0e75427137bad11b5e197dc782aeaccccc

## Passed operations
- Builder assembly profile: valid references, unique embedded section names, proper rigid transforms, resolved colors, no coincident duplicates and no reported curated rectangular-body overlaps.
- Final validate --geometry --contacts all: checks_passed=true; complete=true; all 2,734 physical placements resolved; 14,339 inferred contacts computed. Contacts were NOT skipped on the final whole model.
- Ten final module contact inspections, in tidal-final-module-checks/: quay, both halls, dome roof, both masonry tower stages, tower collar, lantern, lantern roof and telescope. Every inspection passes its selected checks and computes contacts.
- check-model.sh: Python syntax/reference checks and LeoCAD snapshot/BOM import smoke test pass.
- Python/LeoCAD BOM comparison: 2,734 versus 2,734 placements, exact agreement by part, color and quantity, zero differences.
- Final exterior home/front/back/right/top/bottom views and both furnished interior top views were opened. The lantern cap and difficult dome/telescope interfaces received additional close and construction-step review.

## Coverage and remaining warnings
physical_validity is intentionally not_proven. The final geometry report has two warnings: assembly.disconnected_evidence and coverage.collision_review. Neither has been suppressed.

### Connection evidence
The whole-model optimistic graph has 32 groups: one main group of 2,678 placements and 31 small groups totaling 56 placements. The confirmed graph has 1,737 groups because many ordinary socket matches are inference-level evidence. These are not 1,737 independent floating assemblies.

The small optimistic groups were mapped back to the generated placements:
- Twelve window/pane inserts (six 57895 and six 60608): actual measured insert offsets in dedicated frames; frame and insert bounds nest by design. Glazing retention is not established by the connector matcher and still needs a physical trial.
- Four 48092 round collar quarters: their three underside socket locations at (70,24,-10), (50,24,-50), (10,24,-70) align exactly with the 87559 top studs after the 24-LDU vertical stack. Their shadow ports are typed pin_hole, not ordinary socket, so the contact graph does not merge them. Verify the physical collar assembly before purchase.
- Four 4589 finials: body bottoms are at the supporting dish/jumper planes, but the inspected cone metadata exposes its top stud and lacks an ordinary underside socket. Seating was reviewed visually, not physically tested.
- Three desk inkwells, three desk-lamp groups and two quay-lamp upper groups: the 6141 underside is represented as pin_hole and can remain separate from a stud-supported chain. Exact stud positions and 8-LDU plate/24-LDU brick stacks are used. There is no modeled electrical lighting.
- Three six-part telescope upper groups: the 4733 mount body bottom meets the pedestal top and is centered on a real pedestal stud at (+10,+10). The tube parts connect to its front side stud using a proper rigid rotation. The mount's underside connector coverage does not merge with the ordinary pedestal in this graph. These are static stud-connected display instruments, not verified mechanisms.

### Collision review
The all-scene report includes every overlap candidate (overlaps_truncated=false). Material intersection for arbitrary parts is not proven. All final candidates deeper than ordinary stud engagement were inspected by role:
- Windows/door occupy their intended hollow frames; checked against measured origins and rendered detail views.
- Dome core bounds overlap the bounding boxes of the hollow circular 87559/48092 quarters. The central 4x4-stud core reaches radius about 56.6 LDU; the collar's inner radius is 60 LDU. The actual library ring geometry and opened build-step views show the core inside the hollow rather than inside the ring material. This is geometric reasoning, not a stress/clutch certification.
- Earlier genuine candidates at the tower paving, chair backs and rear foliage were repaired in the generator, rebuilt and rechecked; they do not remain in the final deep-candidate list.

### Report detail limits
Final instance/component/overlap lists are complete. The stored contact list is capped at 5,000 entries (contacts_truncated=true), but all 14,339 contacts were computed for the graph and checks. This truncates report detail, not analysis. Module summary reports omit instance/contact lists while retaining results and coverage.

## Build/inventory limitations
No physical build, load test, clutch test, or manufacturing inventory audit was performed. Long lintels, tiled-floor bonds, base rigidity when lifting, dome retention and the portico should be prototyped. Storeys and roofs are separate stud-connected modules, not low-clutch tiled modular-building connections. Rear cutaways and the lack of an internal staircase are deliberate display-model choices. Part/color availability and cost remain unchecked; renderable LDraw colors do not guarantee purchasable elements.
