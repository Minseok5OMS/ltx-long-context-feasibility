"""Build GitHub-native Markdown and animated previews from archived results.

CPU only. Requires PyAV, Pillow, imageio-ffmpeg, markdown-it-py.
Does not modify original MP4s, experiment records, or generate model outputs.
"""
import concurrent.futures
import html
import json
import os
from pathlib import Path
import re
import subprocess

from PIL import Image
import imageio_ffmpeg
from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / 'results/gallery.json').read_text())
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def rel(path, page):
    return Path(os.path.relpath(ROOT / path, page.parent)).as_posix()


def make_gif(asset):
    dest = ROOT / 'media/previews' / (asset['sha256'] + '.gif')
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([FFMPEG, '-nostdin', '-v', 'error', '-i', str(ROOT / asset['path']),
                        '-filter_complex', 'fps=8,scale=256:144:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer',
                        '-filter_complex_threads', '1', '-threads', '1', '-loop', '0', str(dest)], check=True)
    with Image.open(dest) as gif:
        duration = sum((gif.seek(i), gif.info.get('duration', 0))[1] for i in range(gif.n_frames))
        count = gif.n_frames
    assert abs(duration / 1000 - asset['frames'] / asset['fps']) < .13, dest
    return asset['sha256'], {'path': dest.relative_to(ROOT).as_posix(), 'source': asset['path'],
                             'source_sha256': asset['sha256'], 'frames': count, 'duration_ms': duration,
                             'width': 256, 'height': 144, 'fps': 8}


def preview(asset, page, caption):
    gif = PREVIEWS.get(asset['sha256'])
    image = gif['path'] if gif else asset['poster']
    return f'[![{caption}]({rel(image, page)})]({rel(asset["path"], page)})'


def time_range(value):
    return '[' + ', '.join(f'{v:.4f}' for v in value) + ') s' if value else '원본 config 참조'


def main():
    global PREVIEWS
    assets = {r['target']['sha256']: r['target'] for r in DATA['runs'].values()}
    for c in DATA['cases'].values():
        for a in c['inputs'].values():
            if a['frames'] / a['fps'] <= 3.1:
                assets[a['sha256']] = a
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        PREVIEWS = dict(pool.map(make_gif, assets.values()))
    rootpage = ROOT / 'browse/README.md'
    rootpage.parent.mkdir(exist_ok=True)
    overview = ['# GitHub에서 입력·생성 결과 보기', '', '[전체 요약](../README.md)', '',
                '별도 서버나 GitHub Pages 설정 없이 이 Markdown 페이지에서 결과를 탐색합니다. 움직이는 미리보기는 **256×144, 8 FPS의 GIF**이며 원래 3초 길이를 유지합니다. 클릭하면 저장소의 원본 MP4 파일로 이동합니다. GIF에는 재생·정지 버튼이 없으며 미세한 외관·동작 평가는 512×288, 24 FPS MP4를 사용합니다.', '',
                '정식 생성은 **120회**, 비교 표시는 **151개**입니다. 재사용 31개를 신규 생성에 더하지 않습니다. 각 사례에서 Local·참조·원본 후속과 실제 prompt/좌표를 확인할 수 있습니다.', '',
                '| 실험 | 신규 생성 | 비교 표시 |', '|---|---:|---:|']
    page_count = 0
    for g in DATA['groups']:
        folder = ROOT / 'browse' / ('experiment_' + g['id'])
        folder.mkdir(exist_ok=True)
        overview.append(f'| [{g["id"]}. {g["title"]}](experiment_{g["id"]}/README.md) | {g["new_count"]} | {len(g["entries"])} |')
        group_lines = [f'# {g["id"]}. {g["title"]}', '', '[전체 실험](../README.md) · [연구 요약](../../README.md)', '', g['summary'], '',
                       f'신규 {g["new_count"]}회 / 비교 {len(g["entries"])}개. 사례를 선택하면 페이지 안에서 움직이는 미리보기와 실제 입력을 볼 수 있습니다.', '']
        ids = list(dict.fromkeys(DATA['runs'][e['run']]['case_id'] for e in g['entries']))
        for cid in ids:
            c = DATA['cases'][cid]
            page = folder / (cid + '.md')
            entries = [e for e in g['entries'] if DATA['runs'][e['run']]['case_id'] == cid]
            group_lines.append(f'- [{c["title"]}]({cid}.md) — {len(entries)}조건')
            lines = [f'# {g["title"]} · {c["title"]}', '', '[이 실험의 사례 목록](README.md) · [전체 실험](../README.md) · [입력 방식](../../docs/METHODS.md)', '',
                     g['summary'], '', c['observation'] or '관찰·해석은 [실험별 결과](../../docs/EXPERIMENTS.md)를 함께 확인하세요.', '',
                     '**GIF는 축소 미리보기(8 FPS)입니다.** 모든 생성 Target은 원본 3초입니다. 미리보기 또는 MP4 링크를 클릭하면 저장소 파일을 열 수 있습니다. 재사용 표시는 같은 원실행을 다시 비교했다는 뜻입니다.', '',
                     '## 실제 입력과 평가용 후속', '', c['note'], '']
            names = {'local_context':'Local · 고정 생성 조건', 'oracle_context':'Oracle · 과거 증거', 'random_context':'Random · 무관한 과거 구간',
                     'history_32s':'연속 과거 32초 · 정지 미리보기', 'uniform_context':'Uniform · 중앙 구간', 'gt_target':'원본 후속 · 생성 입력 제외'}
            for kind, a in c['inputs'].items():
                lines += [f'### {names[kind]}', '', preview(a, page, names[kind]), '',
                          f'{a["note"]} · [MP4 파일]({rel(a["path"],page)}) · [원본 열기/다운로드]({rel(a["path"],page)}?raw=true)', '']
            for kind, a in c['stills'].items():
                lines += [f'### {kind.capitalize()} 이미지 · 실제 frame {a["frame_index"]}', '',
                          f'![실제 이미지 참조]({rel(a["path"],page)})', '', '이미지 조건은 이 한 장을 인코딩했습니다. 영상 조건과 구분합니다.', '']
            lines += [f'원본: {c["source_title"]} · [구간·출처 metadata]({rel(c["metadata"],page)})', '', '## 생성 결과', '']
            for e in entries:
                r = DATA['runs'][e['run']]
                label = e.get('label') or r['label']
                variant = e.get('variant') or ''
                lines += [f'### {variant} {label} · seed {r["seed"]}'.strip(), '',
                          f'**{"재사용" if e["reused"] else "신규 실행"} · {r["id"]}**', '', preview(r['target'], page, label), '',
                          f'[Target MP4]({rel(r["target"]["path"],page)}) · [원본 열기/다운로드]({rel(r["target"]["path"],page)}?raw=true) · [Local + Target 5초]({rel(r["continuation"]["path"],page)}) · [원실행 config]({rel(r["config"],page)})', '',
                          f'참조: {r["reference_label"]}. {r["condition_note"]}', '']
                if r['reference_asset']:
                    lines += [f'[이 조건의 참조 파일]({rel(r["reference_asset"],page)})', '']
                if r['cost']:
                    lines += [f'Denoising **{r["cost"]["denoising_seconds"]:.3f} s**, peak allocated **{r["cost"]["peak_allocated_gib"]:.3f} GiB**.', '']
                lines += ['<details>', '<summary>Prompt · 시간 좌표 · 원실행</summary>', '',
                          '```text', r['prompt'], '```', '',
                          f'- 참조 모델 좌표: `{time_range(r["reference_time"])}`',
                          f'- Target 모델 좌표: `{time_range(r["target_time"])}`',
                          f'- 원본 참조 구간: `{time_range(r["source_interval"])}`',
                          f'- 추가 참조 token: {r["reference_tokens"]}',
                          f'- 원실행: `{r["source_config"]}`', '', '</details>', '']
            page.write_text('\n'.join(lines).replace('../../..//', '../../../'), encoding='utf-8')
            page_count += 1
        (folder / 'README.md').write_text('\n'.join(group_lines)+'\n', encoding='utf-8')
    overview += ['', '[마지막 32초 비교의 5사례부터 보기](experiment_9/README.md)', '',
                 '## MP4를 README 안의 재생 플레이어로 넣고 싶다면', '',
                 'GitHub의 첨부 업로드가 반환한 영상 URL을 Markdown 본문에 넣는 경로가 있습니다. 저장소에 commit한 상대 MP4 링크를 첨부 URL과 동일하게 취급하지 않습니다. 이 저장소는 첨부 서비스 없이 Git에 보관되는 GIF 미리보기와 원본 MP4 링크를 기본으로 제공합니다. [GitHub 첨부 안내](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/attaching-files)', '']
    rootpage.write_text('\n'.join(overview), encoding='utf-8')
    readme = ROOT / 'README.md'
    text = readme.read_text(encoding='utf-8')
    start = text.index('## 먼저 볼 결과') if '## 먼저 볼 결과' in text else text.index('## GitHub에서 바로 결과 보기')
    end = text.index('마지막 실험은', start)
    intro = '''## GitHub에서 바로 결과 보기

**[마지막 32초 비교 · 5사례](browse/experiment_9/README.md)** · **[전체 9개 실험 · 120회 결과](browse/README.md)**

영상 파일은 이 저장소의 `media/videos/`에 포함되어 있습니다. 아래와 각 사례 페이지의 움직이는 미리보기는 **GIF(256×144, 8 FPS)**이며, 클릭하면 원본 MP4를 엽니다. 별도 웹서버나 GitHub Pages 설정이 필요하지 않습니다. 정밀 평가는 원본 MP4(512×288, 24 FPS)를 사용하세요.

### 로봇 예시 · 같은 Local과 prompt, 다른 과거 입력

'''
    robot = [r for r in DATA['runs'].values() if r['case_id']=='long_002_robot_head']
    chosen = [next(r for r in robot if r['label'].startswith(prefix)) for prefix in ['Local-only','Native-Full','Oracle-sparse']]
    intro += '| Local-only | Native-Full · 연속 32초 | Oracle-sparse · 선택 chunk |\n|---|---|---|\n'
    intro += '| '+' | '.join(preview(r['target'],readme,r['label']) for r in chosen)+' |\n\n'
    intro += 'Oracle은 각진 helmet·금색 앞면을 손 없는 새 display와 결합했습니다. 초반 dissolve는 남아 있습니다. [실제 입력·5조건·prompt 확인](browse/experiment_9/long_002_robot_head.md)\n\n'
    intro += '성공 사례와 함께 [학생의 공동 실패](browse/experiment_9/long_003_student_return.md), [차량의 주행 실패](browse/experiment_9/long_004_van_exterior.md), [보존 작업자의 부분 노출](browse/experiment_9/long_005_conservator.md)을 확인하세요.\n\n'
    readme.write_text(text[:start]+intro+text[end:],encoding='utf-8')
    for page in (ROOT/'docs').glob('*.md'):
        text=page.read_text(encoding='utf-8').replace('[갤러리](../index.html)','[GitHub 결과 페이지](../browse/README.md)')
        if page.name=='REPRODUCING.md' and '## GitHub에서 바로 확인' not in text:
            text=text.replace('## 모델 없이 확인','## GitHub에서 바로 확인\n\n[전체 실험 페이지](../browse/README.md)를 열면 입력과 생성 결과의 GIF를 바로 볼 수 있습니다. 영상은 이미 저장소에 포함되어 있으며 MP4 링크로 원본을 열 수 있습니다. 페이지 탐색에 서버 실행은 필요 없습니다.\n\n## 로컬 HTML 갤러리와 무결성 확인')
        if page.name=='DATA_AND_ARTIFACTS.md' and '| `browse/`' not in text:
            text=text.replace('| `index.html`, `site/` |','| `browse/`, `media/previews/` | GitHub용 실험·사례별 Markdown과 움직이는 축소 GIF |\n| `index.html`, `site/` |')
        page.write_text(text,encoding='utf-8')
    # Keep the optional local HTML entry documents current; browse itself is Markdown-native.
    md=MarkdownIt('commonmark', {'html':True}).enable('table')
    for page in [readme]+list((ROOT/'docs').glob('*.md')):
        body=md.render(page.read_text(encoding='utf-8'))
        def rewrite(match):
            path=match[1]
            target=page.parent / path
            return 'href="'+path+('.html' if target.with_suffix('.html').exists() else '.md')+(match[2] or '')+'"'
        body=re.sub(r'href="([^":#?]+)\.md(#[^"]*)?"', rewrite, body)
        prefix='../' if page.parent.name=='docs' else ''
        page.with_suffix('.html').write_text(f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(page.stem)} · LTX Feasibility</title><link rel="stylesheet" href="{prefix}site/style.css"></head><body><header class="doc"><nav><a href="{prefix}index.html">로컬 HTML 갤러리</a><a href="{page.name}">Markdown 원문</a></nav></header><main class="doc">{body}</main></body></html>',encoding='utf-8')
    (ROOT/'results/github_previews.json').write_text(json.dumps({'format':'GIF','purpose':'Reduced display previews, not new generations or evaluation inputs',
        'previews':PREVIEWS,'case_pages':page_count,'formal_runs':120,'comparison_entries':151},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Created {len(PREVIEWS)} animated previews and {page_count} case pages.')


if __name__=='__main__':
    main()
