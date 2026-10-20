# Build notes — crawler-4x4

- Brief: `output/crawler-4x4/brief.md`
- Generator: `output/crawler-4x4/generate.py` (from technic-frame + gear-train + small-car recipes)
- Model: `output/crawler-4x4/crawler-4x4.mpd`

## Search engine
- `jev-rerank` present at /usr/local/bin/jev-rerank, `data/ldraw-info.db` present (26M), `TYPESAFE_API_KEY` present.
- Live Jev check 2026-10-09: `402 Your organization has no available TypeSafe API credits`. → Using **explicit offline FTS** (`--engine fts`) for all discovery, per reference-discovery.md. No repeated Jev retries.

## Modules / progress
- [ ] chassis — pinned ladder frame
- [ ] front-axle + rear-axle — Technic axles + large wheels
- [ ] steering — column + pinion + rack + tie rods
- [ ] driveline — propshaft + 8T/24T reduction
- [ ] engine-v6 — crank + 6 pistons
- [ ] cockpit — floor, seats, dash, wheel
- [ ] cage-body — roll cage, bumpers, light bar, spare
- [ ] details — lights, exhausts

## Checks
- doctor: PASS (2026-10-09)
- kit generate: pending
- check: pending
- look: pending
- deliver: pending

## Next
- Write brief.md, then search parts (offline), ports for beams/gears/wheels, then v1 generator.
