from pathlib import Path
import json, hashlib, zipfile
out = Path('output')
files = [out / n for n in [
    'tidal-observatory.mpd', 'tidal-observatory.plan.json', 'tidal-observatory-generate.py',
    'tidal-observatory-README.md', 'tidal-observatory-design-brief.md',
    'tidal-observatory-module-contracts.md', 'tidal-observatory-sources.json',
    'tidal-observatory-visual-review.md', 'tidal-observatory-verification.md',
    'tidal-observatory.validation.json', 'tidal-observatory.build.json',
    'tidal-observatory.bom.json', 'tidal-observatory.bom-comparison.json',
    'tidal-observatory.publication-bom-comparison.json', 'tidal-observatory.cad-check.json',
    'jev-availability.json', 'observatory-references.json', 'dome-parts.json', 'window-parts.json'
]]
for dirname in ['tidal-observatory-review', 'tidal-upper-hall-final', 'tidal-ground-hall-final',
                'tidal-lantern-cap-review', 'tidal-step-review', 'tidal-final-module-checks',
                'reference-catalog/model-e00b558893c77e962a0c3b4c']:
    files.extend(p for p in (out / dirname).rglob('*') if p.is_file() and p.suffix != '.log')
files = sorted(set(files))
assert all(p.is_file() for p in files)
source_hash = hashlib.sha256((out/'tidal-observatory.mpd').read_bytes()).hexdigest()
assert source_hash == '4ac1340f73cbba19eaa69f3995dfde0e75427137bad11b5e197dc782aeaccccc'
manifest = {'model': 'tidal-observatory.mpd', 'sha256': source_hash, 'physical_placements': 2734,
            'files': [{'path': str(p.relative_to(out)), 'bytes': p.stat().st_size,
                       'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]}
manifest_path = out/'tidal-observatory-delivery-manifest.json'
manifest_path.write_text(json.dumps(manifest, indent=2)+'\n')
archive = out/'tidal-observatory-complete.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
    for p in files+[manifest_path]:
        z.write(p, arcname=str(p.relative_to(out)))
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
print(json.dumps({'archive': str(archive), 'bytes': archive.stat().st_size,
                  'files': len(files)+1, 'source_sha256': source_hash, 'zip_integrity': 'passed'}, indent=2))
with (out/'NOTES.md').open('a') as f:
    f.write('\nPackage finished: tidal-observatory-complete.zip contains the final model, generator/plan, provenance, reports and reviewed previews; ZIP integrity verified. Final MPD hash remains unchanged. Ready for final response.\n')