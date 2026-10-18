"""Build explicit extension and legacy archives without publishing."""
from pathlib import Path
import hashlib
import json
import zipfile

root = Path(__file__).resolve().parents[1]
paths = [root / x for x in ('__init__.py', 'baking.py', 'validation.py', 'quality.py', 'blender_manifest.toml', 'README.md')]
paths += sorted((root / 'docs').glob('*.md'))
out = root / 'dist'
out.mkdir(exist_ok=True)
records = []
for legacy in (False, True):
    name = 'quick_cloth-1.1.0' + ('-legacy' if legacy else '') + '.zip'
    target = out / name
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            entry = path.relative_to(root).as_posix()
            archive.write(path, ('quick_cloth/' if legacy else '') + entry)
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(set(archive.namelist()))
    records.append({'file': name, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'files': len(paths)})
(out / 'checksums.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
for record in records:
    print(record)
