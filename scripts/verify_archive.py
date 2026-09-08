"""Verify the portable archive. Optional full video decode requires PyAV."""
import argparse
import json
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from refresh_manifest import digest

ROOT = Path(__file__).resolve().parents[1]


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        self.links.extend(v for k, v in attrs if k in {'href', 'src', 'poster'} and v)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--decode', action='store_true')
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'results/archive_manifest.json').read_text())
    for item in manifest['files']:
        path = ROOT / item['path']
        assert path.is_file(), f'Missing: {path}'
        assert path.stat().st_size == item['bytes'], f'Size mismatch: {path}'
        assert digest(path) == item['sha256'], f'Hash mismatch: {path}'
    data = json.loads((ROOT / 'results/gallery.json').read_text())
    assert len(data['runs']) == 120
    assert sum(g['new_count'] for g in data['groups']) == 120
    assert sum(len(g['entries']) for g in data['groups']) == 151
    assert sum(e['reused'] for g in data['groups'] for e in g['entries']) == 31
    new = Counter(e['run'] for g in data['groups'] for e in g['entries'] if not e['reused'])
    assert set(new) == set(data['runs']) and all(n == 1 for n in new.values())
    assert (ROOT / 'site/data.js').read_text(encoding='utf-8') == 'window.ARCHIVE = ' + json.dumps(data, ensure_ascii=False) + ';\n'
    assets = {}
    for run in data['runs'].values():
        config = json.loads((ROOT / run['config']).read_text())
        assert config['status'] == 'completed'
        assert run['target']['frames'] == 72 and run['continuation']['frames'] == 120
        for kind in ['target', 'continuation']:
            asset = run[kind]
            assert (ROOT / asset['poster']).is_file()
            assert digest(ROOT / asset['path']) == asset['sha256']
            assets[asset['path']] = asset
        if run['reference_asset']:
            assert (ROOT / run['reference_asset']).is_file()
    for case in data['cases'].values():
        assert (ROOT / case['metadata']).is_file()
        for asset in case['inputs'].values():
            assert (ROOT / asset['poster']).is_file()
            assets[asset['path']] = asset
        for asset in case['stills'].values():
            assert (ROOT / asset['path']).is_file()
    link_count = 0
    for page in ROOT.rglob('*.html'):
        links = Links()
        links.feed(page.read_text(encoding='utf-8'))
        for href in links.links:
            url = urlsplit(href)
            if url.scheme or url.netloc or not url.path:
                continue
            target = page.parent / unquote(url.path)
            assert target.is_file(), f'Broken link in {page.relative_to(ROOT)}: {href}'
            link_count += 1
    markdown_links = 0
    for page in [ROOT / 'README.md', *ROOT.glob('docs/*.md'), *ROOT.glob('browse/**/*.md')]:
        for href in re.findall(r'!?\[[^\]\n]*\]\(([^)\n]+)\)', page.read_text(encoding='utf-8')):
            url = urlsplit(href)
            if url.scheme or url.netloc or not url.path:
                continue
            assert (page.parent / unquote(url.path)).is_file(), f'Broken Markdown link: {page}: {href}'
            markdown_links += 1
    preview_file = ROOT / 'results/github_previews.json'
    if preview_file.exists():
        previews = json.loads(preview_file.read_text())['previews']
        for run in data['runs'].values():
            assert run['target']['sha256'] in previews
        for checksum, preview in previews.items():
            assert digest(ROOT / preview['source']) == checksum
            assert (ROOT / preview['path']).read_bytes()[:6] in {b'GIF87a', b'GIF89a'}
    frozen = ROOT / 'repro/longcond/feasibility_long_context/configs/long_input_cases.json'
    assert digest(frozen) == 'bdba61857111a43b2576f725d2be1dc262ee88480e40f30a49f712df5060d75f'
    frames = 0
    if args.decode:
        import av
        for name, asset in sorted(assets.items()):
            with av.open(str(ROOT / name)) as container:
                count = sum(1 for _ in container.decode(video=0))
            assert count == asset['frames'], f'Decode count mismatch: {name}: {count}'
            frames += count
    print(json.dumps({'status': 'passed', 'files_hashed': len(manifest['files']),
                      'formal_runs': 120, 'comparison_entries': 151, 'reused_entries': 31,
                      'html_links_checked': link_count, 'markdown_links_checked': markdown_links, 'unique_mp4': len(assets),
                      'full_decode': args.decode, 'decoded_frames': frames}, indent=2))


if __name__ == '__main__':
    main()
