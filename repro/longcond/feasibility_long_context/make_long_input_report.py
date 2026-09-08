"""Readable full-input provenance, blind comparison panels and measured costs."""
import argparse,csv,html,json,os,random,statistics,subprocess
import numpy as np
from imageio_ffmpeg import get_ffmpeg_exe
from PIL import Image,ImageDraw,ImageFont
from long_input_common import *
from run_generation import read_rgb,write_video

def url(p):return os.path.relpath(p,REPORT)
def esc(s):return html.escape(str(s))
def numeric(x):return '—' if x is None else f'{x:.3f}'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--assets',action='store_true');a=ap.parse_args();REPORT.mkdir(parents=True,exist_ok=True)
    rows=[];cards=[];blind={};asset_records={}
    metric_path=REPORT/'dino_metrics.json';metrics=json.loads(metric_path.read_text()) if metric_path.exists() else {}
    review_path=REPORT/'review.json';review=json.loads(review_path.read_text()) if review_path.exists() else {}
    previous_manifest=REPORT/'report_manifest.json'
    if previous_manifest.exists() and not a.assets:
        asset_records=json.loads(previous_manifest.read_text()).get('assets',{})
    for e in plan()['examples']:
        name=e['example_id'];d=data_dir(name);asset=REPORT/name;asset.mkdir(exist_ok=True)
        order=list(CELLS);random.Random('long-input-blind-v1-'+name).shuffle(order)
        blind[name]={chr(65+i):cell for i,cell in enumerate(order)}
        configs={}
        for cell in CELLS:
            p=output_dir(name,cell)/'config.json'
            if p.exists():
                c=json.loads(p.read_text())
                if c['status']=='completed':configs[cell]=c
        for cell,c in configs.items():
            row={'example_id':name,'cell':cell,'video_tokens':c['actual_video_tokens'],'reference_tokens':c['reference_tokens'],
                'denoising_seconds':c['sampler_seconds_excluding_audits'],'forward_cuda_seconds':c['forward_cuda_seconds'],
                'peak_allocated_gib':c['denoising_peak_allocated_gib'],'resident_baseline_gib':c['resident_baseline_allocated_gib'],
                'incremental_peak_gib':c['incremental_peak_allocated_gib'],'peak_reserved_gib':c['denoising_peak_reserved_gib'],
                'device_peak_gib':c['device_monitor']['peak_device_used_gib'],'transformer_load_seconds':c['transformer_load_seconds'],
                'decoder_seconds':c['decoder_seconds'],'execution_body_seconds_including_audits':c['total_process_seconds'],
                'config':str(output_dir(name,cell)/'config.json')}
            kinds=['native','text'] if cell=='native_full' else ['local','text']+(['history'] if cell!='local' else [])
            preparation=[json.loads((cache_dir(name)/(k+'.json')).read_text()) for k in kinds]
            row['vae_text_prepare_seconds_including_load']=sum(x['total_seconds'] for x in preparation)
            row['prepared_plus_execution_component_sum_seconds']=row['vae_text_prepare_seconds_including_load']+row['execution_body_seconds_including_audits']
            row['dino_gt_cosine']=metrics.get(name,{}).get(cell,{}).get('dino_gt_mean') if e['gt_dino_valid_for_requested_view'] else None
            rows.append(row)
        if a.assets and len(configs)==5:
            videos={cell:read_rgb(Path(c['outputs']['target']['path']),512,288) for cell,c in configs.items()}
            times=[0,8,16,24,40,56,71];sheet=Image.new('RGB',(7*256,5*170),'#131923');draw=ImageDraw.Draw(sheet);font=ImageFont.load_default(size=16)
            for i,cell in enumerate(order):
                code=chr(65+i)
                Image.fromarray(videos[cell][32]).save(asset/(code+'_poster.jpg'),quality=95)
                for j,t in enumerate(times):
                    sheet.paste(Image.fromarray(videos[cell][t]).resize((256,144)),(j*256,i*170+26));draw.text((j*256+5,i*170+3),f'{code} | {t/24:.2f}s',font=font,fill='white')
            sheet.save(asset/'blind_frames.jpg',quality=96)
            # Every frame is available in a contact sheet, in addition to playable videos.
            for i,cell in enumerate(order):
                code=chr(65+i);scan=Image.new('RGB',(12*192,6*128),'#131923');dr=ImageDraw.Draw(scan)
                for t,rgb in enumerate(videos[cell]):
                    x,y=(t%12)*192,(t//12)*128;scan.paste(Image.fromarray(rgb).resize((192,108)),(x,y+20));dr.text((x+3,y+2),f'{code} {t/24:.3f}s',fill='white',font=ImageFont.load_default(size=13))
                scan.save(asset/(code+'_all72.jpg'),quality=94)
            comp=asset/'comparison.mp4'
            if not comp.exists():
                local=read_rgb(d/'local_context.mp4',384,216)
                arrays={c:np.concatenate([local,np.stack([np.asarray(Image.fromarray(x).resize((384,216))) for x in videos[c]])]) for c in order}
                combined=[]
                for t in range(120):
                    im=Image.new('RGB',(1920,240),'#131923');dr=ImageDraw.Draw(im)
                    for i,c in enumerate(order):
                        im.paste(Image.fromarray(arrays[c][t]),(i*384,24));dr.text((i*384+5,3),f'{chr(65+i)} | '+('Local' if t<48 else 'Generated')+f' {(t if t<48 else t-48)/24:.2f}s',font=font,fill='white')
                    combined.append(np.asarray(im))
                artifact=write_video(comp,np.stack(combined),24);write_json(asset/'comparison.json',artifact)
            asset_records[name]={'comparison':url(comp),'blind_frames':url(asset/'blind_frames.jpg')}
        # Provenance and all inputs are visible before revealing output condition names.
        inputs=''
        for label,p in [('연속 과거 32초',d/'history_32s.mp4'),('Local 2초',d/'local_context.mp4'),('Oracle 선택 3초',d/'oracle_context.mp4'),('Uniform 선택 3초',d/'uniform_context.mp4'),('원본 후속 3초'+(' · 요청한 display 구도의 GT 아님' if not e['gt_dino_valid_for_requested_view'] else ' · 평가 전용'),d/'gt_target.mp4')]:
            input_poster=asset/('input_'+p.stem+'.jpg')
            if a.assets and not input_poster.exists():
                midpoint=16 if p.stem=='history_32s' else 1 if p.stem=='local_context' else 1.5
                subprocess.run([get_ffmpeg_exe(),'-v','error','-y','-ss',str(midpoint),'-i',str(p),'-frames:v','1','-q:v','2',str(input_poster)],check=True)
            poster_attr=f' poster="{url(input_poster)}"' if input_poster.exists() else ''
            inputs+=f'<figure><figcaption>{esc(label)}</figcaption><video controls preload="none"{poster_attr} src="{url(p)}"></video></figure>'
        h=e['history_start'];T=e['target_start'];bar='<div class="timeline"><span class="localmark" style="left:93.75%;width:6.25%">Local</span>'
        for kind,col in [('oracle','#e5a950'),('uniform','#6ba5dd')]:
            s,t=e[kind+'_nominal_source_interval'];bar+=f'<span title="{kind}: {s:.3f}–{t:.3f}s" style="left:{(s-h)/32*100}%;width:{(t-s)/32*100}%;background:{col};top:{0 if kind=="oracle" else 26}px">{kind}</span>'
        bar+='</div>'
        panels=''
        for i,cell in enumerate(order):
            code=chr(65+i);c=configs.get(cell)
            if c:
                poster=f' poster="{url(asset/(code+"_poster.jpg"))}"' if (asset/(code+'_poster.jpg')).exists() else ''
                video=f'<video class="output" controls preload="none"{poster} src="{url(Path(c["outputs"]["continuation"]["path"]))}"></video>'
                row=next(r for r in rows if r['example_id']==name and r['cell']==cell)
                cost=f'<div class="revealed"><b>{LABELS[cell]}</b><br>Denoise {row["denoising_seconds"]:.2f}s<br>Peak {row["peak_allocated_gib"]:.2f} GiB · 추가 {row["incremental_peak_gib"]:.2f} GiB<br>Video tokens {row["video_tokens"]:,}<br><a href="{url(output_dir(name,cell)/"config.json")}" download>실제 설정 저장</a></div>'
                extra=f'<a href="{url(asset/(code+"_all72.jpg"))}">72프레임 전체 보기</a>' if (asset/(code+'_all72.jpg')).exists() else ''
            else:video='<p>실행 대기</p>';cost='';extra=''
            panels+=f'<div><b>{code}</b>{video}{cost}{extra}</div>'
        links=''
        if (asset/'comparison.mp4').exists():links=f'<p><a href="{url(asset/"comparison.mp4")}">5조건 동기 비교 영상</a> · <a href="{url(asset/"blind_frames.jpg")}">7개 시점 비교</a></p>'
        case_review=review.get('examples',{}).get(name)
        if case_review:
            links+='<details><summary>Assistant 정성 검토 보기 · 조건명 포함</summary><p>'+esc(case_review['summary_ko'])+'</p><ul>'
            for cell in CELLS:
                rr=case_review['cells'][cell]
                links+=f'<li><b>{esc(LABELS[cell])} ({rr["blind_code"]})</b>: {esc(rr["observation_ko"])}</li>'
            links+='</ul><p>전체 72프레임 sheet 검토이며 독립 사람/실시간 재생 평가는 아닙니다. 외관 정확도·세부 동작은 실제 영상을 함께 확인하세요.</p></details>'
        cards.append(f'<article id="{name}"><h2>{esc(e["title_ko"])}</h2><p>원본 {h:.3f}–{T:.3f}s → 생성 {T:.3f}–{T+3:.3f}s. Oracle: {e["oracle_nominal_source_interval"][0]:.3f}–{e["oracle_nominal_source_interval"][1]:.3f}s.</p>{bar}<div class="inputs">{inputs}</div><details><summary>전체 prompt · 평가 속성 · 구간 변경과 한계</summary><p>{esc(e["prompt"])}</p><p>평가 속성(프롬프트 입력 아님): {esc(" / ".join(e["attributes"]))}</p><p>{esc(e["selection_reason"])}</p><ul>'+''.join(f'<li>{esc(x)}</li>' for x in e['limitations'])+f'</ul><p>Oracle/Uniform 겹친 latent index: {esc(e["uniform_oracle_index_overlap"])}</p></details><div class="buttons"><button onclick="playCase(this,2)">생성 3초부터 동기 재생</button><button onclick="playCase(this,0)">Local부터 재생</button><button onclick="pauseCase(this)">일시 정지</button><button onclick="this.closest(\'article\').classList.toggle(\'show\')">조건·비용 보기</button></div><div class="results">{panels}</div>{links}</article>')
    pairs=[]
    for e in plan()['examples']:
        p={r['cell']:r for r in rows if r['example_id']==e['example_id']}
        if all(c in p for c in ['native_full','full_reference','oracle_sparse']):
            o=p['oracle_sparse'];pairs.append({'example_id':e['example_id'],**{f'{b}_speedup':p[b]['denoising_seconds']/o['denoising_seconds'] for b in ['native_full','full_reference']},**{f'{b}_total_memory_reduction':1-o['peak_allocated_gib']/p[b]['peak_allocated_gib'] for b in ['native_full','full_reference']},**{f'{b}_incremental_memory_reduction':1-o['incremental_peak_gib']/p[b]['incremental_peak_gib'] for b in ['native_full','full_reference']}})
    summary={'status':'completed' if len(rows)==25 else 'in_progress','completed':len(rows),'planned':25,'formal_total_including_previous':95+len(rows),'plan_sha256':sha256(PLAN),'rows':rows,'paired_costs':pairs,'quality_review_status':'See review.json when available; images alone are not final quality verdicts','cost_scope':'Denoising subtracts measured audit sections. Execution body includes loading/audits/decoder, excludes Python startup. Preparation+execution is a sum of separately measured components, not a single end-to-end request measurement. Source ingest is separate. No retrieval/memory-network cost.'}
    if review:summary['quality_review_status']='Completed assistant review: all25 full72 frame sheets; see review.json. Independent human and real-time playback rating not performed.'
    write_json(REPORT/'summary.json',summary);write_json(REPORT/'blind_mapping.json',blind)
    if rows:
        with (REPORT/'results.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    top=f'<p class="badge">신규 완료 {len(rows)} / 25 · seed 42 · 정식 누적 {95+len(rows)}회</p>'
    if review:
        top+='<details><summary>전체 결과 해석 보기 · 먼저 영상을 비교하려면 닫아 두세요</summary><p>Oracle은 직원·로봇·차량의 필요한 외관을 더 잘 드러냈고, 로봇은 새 display 구도와 결합했습니다. 학생은 모든 조건에서 실패했고 보존 작업자는 얼굴 전체가 잘렸습니다. 직원·차량에는 참조 구도 재현이 남습니다. 전체 peak allocated VRAM 감소는 약 7%, 상주 baseline 대비 증가분 감소는 약 76%입니다.</p><p><a href="../../LONG_INPUT_RESULT.html">결과·비용 측정 범위·한계</a> · <a href="qualitative_scores.csv" download>정성 검토 CSV</a> · <a href="dino_metrics.json" download>보조 DINO 수치</a></p></details>'
    if pairs:
        top+=f'<p>완료된 {len(pairs)}개 쌍의 median denoising: Native→Oracle {statistics.median(p["native_full_speedup"] for p in pairs):.2f}×, Full-reference→Oracle {statistics.median(p["full_reference_speedup"] for p in pairs):.2f}×. 품질 판정은 별도입니다.</p>'
    style='body{background:#131923;color:#e9edf5;font:16px/1.7 system-ui,sans-serif;margin:0}main{max-width:1500px;margin:auto;padding:25px}a{color:#92d6ff}h1{font-size:28px}article{border-top:1px solid #465368;margin-top:35px;padding-top:20px}video{width:100%;background:#080b10;display:block;aspect-ratio:16/9}figure{margin:0}figcaption{font-size:14px}.inputs,.results{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px}.inputs{margin:20px 0}.results>div{background:#1f2838;padding:10px}.revealed{display:none}.show .revealed{display:block}button{padding:9px 14px;margin:8px 8px 8px 0;background:#29415d;color:white;border:1px solid #7191b0;border-radius:5px;cursor:pointer}.timeline{height:53px;background:#263347;position:relative}.timeline span{position:absolute;height:24px;color:#111;text-align:center;overflow:hidden;font:12px/24px sans-serif}.timeline .localmark{height:53px;background:#b8cfb0;top:0}.badge{background:#263a3b;padding:12px}details{background:#1c2633;padding:12px;margin:15px 0}li{margin:8px 0}@media(max-width:900px){.inputs,.results{grid-template-columns:repeat(2,minmax(0,1fr))}}'
    script="async function playCase(b,t){const vs=[...b.closest('article').querySelectorAll('video.output')];for(const v of vs){v.pause();if(v.readyState<1){v.load();await new Promise(r=>{v.addEventListener('loadedmetadata',r,{once:true});v.addEventListener('error',r,{once:true})})}v.currentTime=t;}await Promise.allSettled(vs.map(v=>v.play()));}function pauseCase(b){b.closest('article').querySelectorAll('video.output').forEach(v=>v.pause())}"
    page=f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>긴 입력과 Sparse 비교</title><style>{style}</style></head><body><main><nav><a href="../../report.html">기존 보고서</a> · <a href="../../LONG_INPUT_VS_SPARSE_PROTOCOL.html">실험 설계</a> · <a href="../../LONG_INPUT_RESULT.html">결과 해석</a> · <a href="summary.json" download>전체 수치</a> · <a href="results.csv" download>CSV 저장</a></nav><h1>연속 과거 32초와 선택 chunk의 비교</h1>{top}<p>영상 앞 2초는 Local, 뒤 3초가 새 생성입니다. 결과 A–E는 사례별로 섞었습니다. 먼저 정성 결과를 보고 ‘조건·비용 보기’로 이름을 확인할 수 있습니다. 입력 아래 주황은 Oracle, 파랑은 Uniform 위치입니다.</p><p>O/U는 Full-reference의 동일 VAE bank에서 같은 latent와 시간 좌표를 선택합니다. Native는 연속 인코딩 prefix이므로 Local 경계 latent가 다를 수 있습니다. Peak는 denoising의 PyTorch allocated 메모리이며 GPU device/reserved 수치는 JSON/CSV에 있습니다. 모델 로딩·bank 구축·검증 비용을 denoising speedup에 섞지 않습니다.</p>'+''.join(cards)+f'</main><script>{script}</script></body></html>'
    (REPORT/'index.html').write_text(page,encoding='utf-8');write_json(REPORT/'report_manifest.json',{'assets':asset_records,'report_sha256':sha256(REPORT/'index.html'),'summary_sha256':sha256(REPORT/'summary.json'),'completed':len(rows)})
    print(REPORT/'index.html',len(rows),'completed')

if __name__=='__main__':main()
