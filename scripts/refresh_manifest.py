"""Refresh archive checksums after intentional edits; never changes source records."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'results/archive_manifest.json'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def refresh():
    files = []
    for path in sorted(ROOT.rglob('*')):
        rel = path.relative_to(ROOT)
        if not path.is_file() or any(p in {'.git', '__pycache__', '.venv'} for p in rel.parts):
            continue
        if path == MANIFEST or path.suffix in {'.pyc', '.log'} or rel.name == '.DS_Store':
            continue
        files.append({'path': rel.as_posix(), 'bytes': path.stat().st_size, 'sha256': digest(path)})
    MANIFEST.write_text(json.dumps({'schema': 1, 'scope': 'All archive files except this manifest and runtime/Git files',
                                    'files': files}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Manifest: {len(files)} files, {sum(f["bytes"] for f in files)/1024**2:.1f} MiB')


if __name__ == '__main__':
    refresh()
