# Design brief — Bradbury Building, Los Angeles

## Identity and story
The Bradbury Building (George Wyman, 1893) at Broadway and 3rd, Los Angeles: a plain
reddish-brown-and-buff brick commercial block whose ordinary street elevation hides one of
the most extraordinary interiors in America — a five-storey glass-roofed light court of
open-cage elevators, ornamental iron railings and oak stairs. The model must tell exactly
that story: **a sober, repetitive, workmanlike exterior that opens to reveal a luminous
ornamental atrium.** That contrast is the design, not an afterthought.

## Silhouette
One five-storey rectangular mass on a corner site, with a **45° chamfered corner bay**
carrying a vertical black blade sign. Flat roofline terminated by a heavy projecting
cornice. Above the roof deck, a large glazed light-court skylight and a small stair
bulkhead. The two street wings are of unequal length (Broadway long, 3rd Street shorter),
so the thumbnail silhouette reads as an L-shaped corner block, never a symmetric box.

## Dimensions (LDU; negative Y is up; sidewalk top = Y 0)
- Bay pitch 80 (2-stud pier + 2-stud window). Storey 96 (4 brick courses).
- Window opening 40 wide x 72 tall (1:1.8, matching the real tall narrow windows).
- Broadway elevation 7 bays; 3rd Street elevation 6 bays; corner 1 chamfered bay.
- Overall building approx. 640 x 560 LDU footprint, approx. 520 LDU to cornice cap.
- Base plate approx. 800 x 720 LDU of sidewalk, kerb and roadway strip.

## Focal hierarchy
1. **Primary:** the chamfered corner — recessed "300" entrance below, stacked windows,
   top-floor round-arch pair, and the black BRADBURY blade sign projecting over the street.
2. **Supporting A:** the top-floor round-arch arcade running the full length of both
   façades over a corbelled belt course, terminated by the deep ornamented cornice.
3. **Supporting B:** the interior light court, visible when upper storeys are lifted and
   through the glazed roof — balconies, stairs, open ironwork and the warm oak floor.
4. Accents: black zigzag fire escape on the 3rd Street wing; street lamps, traffic signal,
   pedestrian rail and planter on the sidewalk.

## Palette roles
| Role | Colour | Use |
|---|---|---|
| Body brick field | Tan / Dark Tan | Wall panels between piers (buff brick) |
| Trim / structure | Reddish Brown | Piers, arch voussoirs, belt courses, cornice |
| Stone base | Light Bluish Gray / White | Ground-floor pilasters and shopfront surrounds |
| Glazing (exterior) | Black + Trans-Light Blue | Deep-recessed window reveals read dark |
| Metalwork | Black | Fire escape, blade sign, signal, railings |
| Atrium warmth | Tan / Reddish Brown / Pearl Gold | Oak stair and floor, ornamental iron |
| Skylight | Trans-Clear | Light-court roof |
| Ground plane | Light/Dark Bluish Gray | Sidewalk slabs, kerb, roadway |

Large surfaces get at most two colours. Metal accents stay small and purposeful.

## Depth strategy (the core construction idea)
A **two-layer perimeter wall**: a continuous inner backing layer in dark colour, and an
outer coloured layer with the window cells left open. Windows are therefore genuinely
recessed a full stud and read dark. The layers are cross-bonded by 2-wide plate belt
courses that also project outward as sills and string courses at every floor line. This
produces real shadow lines and real bonding, not painted-on detail.

## Detail vocabulary (kept deliberately narrow)
Round-arch heads; corbel rows under the cornice; projecting plate string courses;
pier/window alternation at a constant 4-stud rhythm; black ironwork. Repeated, with
variation only where function changes (corner bay, entrance arch, arcade floor).

## Quiet surfaces (reserved; must stay uncluttered)
The roof deck away from the skylight; the rear/party walls; most of the sidewalk paving;
the middle storeys' brick fields between windows.

## Physical subassemblies and build order
1. `bradbury-base` — sidewalk, kerb, roadway strip, street furniture anchors.
2. `bradbury-ground` — stone base storey, shopfronts, Broadway arched entrance, corner door.
3. `bradbury-storey` — typical floor (x3), instantiated with anchors.
4. `bradbury-arcade` — top floor with round-arch heads.
5. `bradbury-cornice` — corbels, projecting layers, frieze, cap.
6. `bradbury-roof` — deck, light-court skylight, stair bulkhead.
7. `bradbury-court-*` — atrium floor, balconies, stairs, ironwork, elevator cage.
8. Details — corner bay, entrance arch, fire escape, blade sign, lamps, signal, planter.

## What will make this attractive
Rhythm and restraint on the outside; concentrated ornament and warm colour inside. The
model earns its interest from the constant 4-stud pier rhythm, three sharp horizontal
events (string course, arcade, cornice) and the single diagonal of the chamfered corner —
then rewards a second look with the light court.

## Review method
Open home/front/left/right/top/back renders plus interior views with upper storeys removed.
Compare against the reference photograph for pier rhythm, cornice weight, window proportion
and corner legibility. Record specific problems and revisions in visual-review.md.
Do not assign a numeric beauty score.
