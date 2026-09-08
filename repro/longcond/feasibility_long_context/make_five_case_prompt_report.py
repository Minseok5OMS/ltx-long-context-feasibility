"""Readable input provenance and synchronized P0-P3 comparisons, including live progress."""
import html
import json
import os
from pathlib import Path
import shutil

from five_case_prompt_common import ROOT, REPORT, PLAN_PATH, VARIANTS, CELLS, load_plan, output_path, now
from run_generation import sha256, write_json


def esc(s):
    return html.escape(str(s),quote=True)


def href(path):
    return esc(os.path.relpath(path,REPORT))


def video(path,poster=None,attrs=''):
    poster_attr=f' poster="{href(poster)}"' if poster and poster.exists() else ''
    return f'<video controls playsinline preload="none"{poster_attr} {attrs}><source src="{href(path)}" type="video/mp4"></video>'


def main():
    plan=load_plan()
    REPORT.mkdir(parents=True,exist_ok=True)
    summary_path=REPORT/'summary.json'
    summary=json.loads(summary_path.read_text()) if summary_path.exists() else None
    review_path=REPORT/'review.json'
    review=json.loads(review_path.read_text()) if review_path.exists() else None
    labels={'P0':'기존 prompt','P1':'출력 지시 구체화','P2':'P1 + 연속성','P3':'P2 + 참조 역할'}
    cells={'local':'Local-only','image_past':'Image / Past','video_past':'Video / Past'}
    cases=[]
    completed=0
    for e in plan['examples']:
        name=e['example_id']; directory=REPORT/name
        metadata=json.loads((ROOT/'data'/name/'metadata.json').read_text())
        configs={}
        for v in ['P0',*VARIANTS]:
            for cell in CELLS:
                p=output_path(name,v,cell)/'config.json'
                cfg=json.loads(p.read_text()) if p.exists() else None
                if cfg and cfg['status']=='completed':
                    configs[(v,cell)]=cfg
                    completed += v!='P0'
        old=ROOT/'reports/five_case_grid/seed42'/name
        image=ROOT/'outputs'/name/'five_case_inputs_512x288/oracle_image.png'
        parts=[f'<section id="{name}"><h2>{esc(e["title_ko"])}</h2>',
               f'<p>원본 Oracle {metadata["oracle_start"]:.2f}–{metadata["oracle_end"]:.2f}s · Local {metadata["local_start"]:.2f}–{metadata["local_end"]:.2f}s · GT {metadata["target_start"]:.2f}–{metadata["target_end"]:.2f}s · 원본 의존 간격 {metadata["dependency_gap_seconds"]:.2f}s</p>',
               '<div class="inputs">',
               '<article><h3>Local 입력 · 2초</h3>'+video(ROOT/'data'/name/'local_context.mp4',directory/'local_input_poster.jpg')+'</article>',
               '<article><h3>Image/Past 실제 입력 · 144 token</h3>'+f'<a href="{href(image)}"><img src="{href(image)}" alt="실제 과거 이미지"></a><p>Oracle clip frame 36 · 원본 {metadata["oracle_image_source_seconds"]:.2f}s</p></article>',
               '<article><h3>Video/Past 원본 입력 · 1,440 token</h3>'+video(ROOT/'data'/name/'oracle_context.mp4',image)+'<p>72프레임 앞에 첫 장을 복제해 73프레임으로 VAE 인코딩.</p></article>',
               '<article><h3>GT · 평가 전용</h3>'+video(ROOT/'data'/name/'gt_target.mp4',old/'gt_poster.jpg')+'<p>생성 조건에 넣지 않음. 새 prompt는 GT와 다른 컷·행동을 요청할 수 있음.</p></article></div>',
               '<div class="toolbar">같은 조건에서 P0–P3 비교: ']
        for cell in CELLS:
            parts.append(f'<button onclick="syncSet(\'{name}\',null,\'{cell}\')">{cells[cell]}</button>')
        parts += ['<button onclick="pauseAll()">모두 정지</button></div>',
                  '<p class="hint">함께 재생 버튼은 공통 Local 2초 이후의 생성 구간부터 시작합니다. 각 영상의 전체 길이는 Local 2초 + 생성 3초입니다. 개별 재생·확대도 가능합니다.</p>',
                  '<div class="table-scroll"><table><thead><tr><th>Prompt</th>'+''.join(f'<th>{cells[c]}</th>' for c in CELLS)+'</tr></thead><tbody>']
        for v in ['P0',*VARIANTS]:
            prompt=e['P0_original'] if v=='P0' else e[VARIANTS[v]]
            parts.append(f'<tr><th>{v}<br>{esc(labels[v])}<br><button onclick="syncSet(\'{name}\',\'{v}\',null)">세 조건 재생</button></th>')
            for cell in CELLS:
                cfg=configs.get((v,cell))
                if not cfg:
                    parts.append('<td><p>생성 대기</p></td>'); continue
                poster=directory/f'{v}_{cell}_poster.jpg'
                parts.append('<td>'+video(Path(cfg['outputs']['continuation']['path']),poster,
                    f'data-generated="1" data-variant="{v}" data-cell="{cell}"')+f'<p>{v} · {cells[cell]}'+(' · 기존 결과 재사용' if v=='P0' else ' · 신규 생성')+'</p>')
                if summary:
                    row=next(r for r in summary['rows'] if (r['example_id'],r['variant'],r['cell'])==(name,v,cell))
                    parts.append(f'<p class="metric">GT DINO {row["dino_gt_cosine"]:.4f} · 1초 이후 {row["dino_gt_cosine_after_1s"]:.4f}</p>')
                parts.append(f'<a download href="{href(output_path(name,v,cell)/"config.json")}">실행 설정 JSON 저장</a></td>')
            parts.append('</tr><tr class="prompt-row"><td colspan="4"><details><summary>'+v+' 실제 입력 prompt</summary><p lang="en">'+esc(prompt)+'</p>')
            if v in ('P2','P3'):
                extra=e['P2_added_sentence'] if v=='P2' else e['P3_added_sentences']
                parts.append('<p>앞 버전에 추가한 문장:</p><blockquote lang="en">'+esc(extra)+'</blockquote>')
            parts.append('</details>')
            comparison=directory/f'comparison_{v}.mp4'
            if comparison.exists():
                parts.append(f'<a href="{href(comparison)}">{v}의 GT + 세 조건을 한 영상으로 보기</a>')
            parts.append('</td></tr>')
        parts.append('</tbody></table></div>')
        if review and name in review.get('cases',{}):
            case_review=review['cases'][name]
            parts.append('<h3>정성 관찰</h3><p>'+esc(case_review['summary_ko'])+'</p>')
            for v,note in case_review.get('variants',{}).items():
                parts.append('<p><strong>'+v+'</strong> '+esc(note)+'</p>')
        links=[(directory/f'{c}_prompt_frames.jpg',cells[c]) for c in CELLS]
        if all(p.exists() for p,_ in links):
            parts.append('<p>시간별 프레임 비교: '+' · '.join(f'<a href="{href(p)}">{label}</a>' for p,label in links)+'</p>')
        parts.append('</section>')
        cases.append(''.join(parts))
    status='생성 완료 · 평가 완료' if summary else ('생성 완료 · 평가 준비 중' if completed==45 else '실행 중')
    intro=f'''<h1>원본 Past 참조 × prompt 3종 비교</h1><p class="status">{status} · 신규 {completed}/45개 · 기존 P0 15개 재사용</p>
<p>5개 사례 · P0/P1/P2/P3 × Local-only/Image-Past/Video-Past · seed 42. 원본 과거 프레임과 VAE cache를 유지하고 positive prompt만 변경했습니다.</p>
<nav><a href="../../../PROMPT_CONTROL_PROPOSAL.html">실제 prompt·비교 설계</a><a href="../../../NEXT_STAGE.html">다음 단계</a><a href="../../five_case_grid/seed42/index.html">이전 2×2</a></nav>
<p>배경도 필요한 증거일 수 있습니다. 과거 정보 유지와 요청한 새 시점·동작을 함께 확인하고, 새 요청을 막는 과거 구도·컷 재현을 구분합니다. GT DINO는 보조 점수이며 외관 정확도나 prompt 준수 점수가 아닙니다.</p>
<details><summary>참조는 어떻게 주입되었나</summary><p>Local 48프레임 앞에 첫 장을 복제해 49프레임으로 인코딩한 7개 latent frame을 생성 시퀀스 앞에 고정합니다. 새 Target은 72프레임입니다. 원본 전체 Oracle 이미지 1장 또는 영상 73프레임을 독립 VAE 인코딩하고 깨끗한 참조 token으로 추가합니다. 참조 token은 decoding 전에 제거합니다.</p>
<p>Local 모델 시간 [97/24,146/24)초 · Target [146/24,218/24)초. 이미지 Past [0,1/24)초 · 영상 Past [0,73/24)초. 이 좌표는 위 원본 timestamp와 다릅니다. P0–P3에서 좌표·실제 초기 및 step noise·Local·참조 내용은 같습니다. Mask·전처리 시트·IC-LoRA·CFG/STG를 추가하지 않았습니다.</p></details>
<p>사례 바로가기: {" · ".join(f'<a href="#{e["example_id"]}">{esc(e["title_ko"])}</a>' for e in plan['examples'])}</p>'''
    if summary:
        intro += '<p><a href="results.csv" download>60조건 CSV 저장</a> · <a href="summary.json" download>평가 JSON 저장</a> · <a href="artifact_verification.json" download>입력·출력 검증 저장</a></p>'
    result_doc=ROOT/'PROMPT_CONTROL_RESULT.html'
    if result_doc.exists():
        intro += '<p><a href="../../../PROMPT_CONTROL_RESULT.html">결과 해석 읽기</a></p>'
    js='''let activeGroup=[];function pauseAll(){document.querySelectorAll('video').forEach(v=>v.pause());activeGroup=[];}
async function syncSet(id,variant,cell){pauseAll();const section=document.getElementById(id);const group=[...section.querySelectorAll('video[data-generated]')].filter(v=>(!variant||v.dataset.variant===variant)&&(!cell||v.dataset.cell===cell));if(!group.length)return;try{await Promise.all(group.map(v=>new Promise((resolve,reject)=>{if(v.readyState>=1)return resolve();const timer=setTimeout(()=>reject(new Error('영상 로딩 시간을 초과했습니다. 개별 재생으로 확인해주세요.')),15000);v.addEventListener('loadedmetadata',()=>{clearTimeout(timer);resolve()},{once:true});v.addEventListener('error',()=>{clearTimeout(timer);reject(new Error('영상을 불러오지 못했습니다.'))},{once:true});v.load();})));group.forEach(v=>{v.currentTime=2;v.playbackRate=1;});activeGroup=group;await Promise.all(group.map(v=>v.play()));}catch(e){document.getElementById('player-status').textContent=e.message;}}
setInterval(()=>{if(activeGroup.length<2)return;const first=activeGroup[0];if(first.paused)return;for(const v of activeGroup.slice(1)){if(!v.paused&&Math.abs(v.currentTime-first.currentTime)>.12)v.currentTime=first.currentTime;}},250);'''
    css='''*{box-sizing:border-box}body{margin:0;background:#141923;color:#e8edf5;font:16px/1.7 system-ui,sans-serif}main{max-width:1720px;padding:24px;margin:auto}a{color:#91d5ff}nav,.toolbar{display:flex;gap:16px;flex-wrap:wrap;margin:18px 0}h1,h2{line-height:1.4}section{border-top:2px solid #4a5970;margin-top:40px;padding-top:18px}.inputs{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px}article{background:#1c2534;padding:12px}video,img{display:block;width:100%;aspect-ratio:16/9;object-fit:contain;background:black}button{cursor:pointer;background:#2a4162;border:1px solid #7399c4;color:white;border-radius:5px;padding:8px 12px;margin:3px;font:inherit}.table-scroll{overflow-x:auto}table{width:100%;border-collapse:collapse;table-layout:fixed;min-width:1050px}th,td{border:1px solid #45536a;padding:10px;vertical-align:top}thead th:first-child{width:155px}details{padding:10px;background:#202c3e}summary{cursor:pointer}blockquote{border-left:3px solid #91d5ff;padding:8px 16px;margin:10px 0}.status{background:#224c43;padding:12px}.metric,.hint{color:#c9d7ed}.prompt-row td{background:#192130}#player-status{color:#ffcc99}@media(max-width:850px){.inputs{grid-template-columns:repeat(2,minmax(0,1fr))}main{padding:12px}}'''
    page='<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Past 참조 · P0–P3 비교</title><style>'+css+'</style></head><body><main>'+intro+'<p id="player-status" aria-live="polite"></p>'+''.join(cases)+'<p>갱신: '+esc(now())+'</p></main><script>'+js+'</script></body></html>'
    (REPORT/'index.html').write_text(page,encoding='utf-8')
    write_json(REPORT/'report_manifest.json',{'generated_at_utc':now(),'new_generations_completed':completed,
               'evaluation_available':bool(summary),'review_available':bool(review),
               'script_sha256':sha256(Path(__file__)),'report_sha256':sha256(REPORT/'index.html')})
    print(f'Prompt report: {completed}/45 new, evaluation={bool(summary)}, review={bool(review)}')


if __name__=='__main__':
    main()
