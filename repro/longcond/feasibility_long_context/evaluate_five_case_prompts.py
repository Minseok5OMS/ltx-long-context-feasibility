"""Audit and evaluate all 60 P0/P1/P2/P3 by Local/Image-Past/Video-Past outputs."""
import argparse
import csv
import json
import os
from pathlib import Path
import shlex
import shutil
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from five_case_prompt_common import ROOT, REPORT, BATCH, PLAN_PATH, VARIANTS, CELLS, load_plan, output_path, configure_env
from run_generation import read_rgb, sha256, write_json, write_video

VARIANT_ORDER = ['P0', *VARIANTS]
LABELS = {'gt':'GT (evaluation only)', 'local':'Local-only', 'image_past':'Image / Past', 'video_past':'Video / Past'}


def export_assets(directory, videos, local, oracle, reference):
    directory.mkdir(parents=True, exist_ok=True)
    font = ImageFont.load_default(size=18)
    small = ImageFont.load_default(size=14)
    artifacts = {}
    for variant in VARIANT_ORDER:
        keys = ['gt', *CELLS]
        sequences = {'gt':np.concatenate([local,videos['gt']])}
        sequences.update({c:np.concatenate([local,videos[f'{variant}_{c}']]) for c in CELLS})
        frames = []
        for i in range(120):
            canvas = Image.new('RGB',(1024,624),'#141923')
            draw = ImageDraw.Draw(canvas)
            phase,t = ('Local',i/24) if i<48 else ('Target',(i-48)/24)
            for j,key in enumerate(keys):
                x,y = (j%2)*512,(j//2)*312
                canvas.paste(Image.fromarray(sequences[key][i]),(x,y+24))
                draw.text((x+5,y+2),f'{variant} | {LABELS[key]} | {phase} {t:.2f}s',fill='white',font=font)
            frames.append(np.asarray(canvas))
        artifacts[variant] = write_video(directory/f'comparison_{variant}.mp4', np.stack(frames),24)
        Image.fromarray(frames[80]).save(directory/f'comparison_{variant}_poster.jpg',quality=94)
    times = [0,8,16,24,40,56,71]
    for cell in CELLS:
        # Rows: exact reference video, GT, and four prompt outputs; columns: target times.
        rows = [('Oracle selection',oracle),('GT',videos['gt'])] + [(v,videos[f'{v}_{cell}']) for v in VARIANT_ORDER]
        sheet = Image.new('RGB',(256*len(times),170*len(rows)),'#141923')
        draw = ImageDraw.Draw(sheet)
        for r,(label,sequence) in enumerate(rows):
            for c,i in enumerate(times):
                x,y = c*256,r*170
                sheet.paste(Image.fromarray(sequence[i]).resize((256,144)),(x,y+26))
                draw.text((x+4,y+3),f'{label} | {cell} | {i/24:.2f}s',fill='white',font=small)
        sheet.save(directory/f'{cell}_prompt_frames.jpg',quality=96)
    Image.fromarray(reference).save(directory/'oracle_image.jpg',quality=96)
    for key,sequence in videos.items():
        Image.fromarray(sequence[32]).save(directory/f'{key}_poster.jpg',quality=94)
    Image.fromarray(local[24]).save(directory/'local_input_poster.jpg',quality=94)
    Image.fromarray(oracle[36]).save(directory/'oracle_video_poster.jpg',quality=94)
    return artifacts


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--gpu',type=int,choices=[0,1,2],default=2)
    args = p.parse_args()
    configure_env(args.gpu)
    os.environ['XFORMERS_DISABLED']='1'
    import torch
    from five_case_prompt_artifacts import audit_prompts
    torch.set_num_threads(8)
    plan = load_plan()
    REPORT.mkdir(parents=True,exist_ok=True)
    configs,audit = audit_prompts()
    write_json(REPORT/'artifact_verification.json',audit)
    print('All 60 output audits passed',flush=True)
    repo = Path('/home/minseok/.cache/torch/hub/facebookresearch_dinov2_main')
    weights = Path('/home/minseok/.cache/torch/hub/checkpoints/dinov2_vitb14_pretrain.pth')
    sys.path.insert(0,str(repo))
    from dinov2.hub.backbones import dinov2_vitb14
    model = dinov2_vitb14(pretrained=False)
    model.load_state_dict(torch.load(weights,map_location='cpu',weights_only=True),strict=True)
    model = model.eval().cuda()
    indices = np.linspace(0,71,12).round().astype(int)
    after = torch.tensor(indices>=24)
    mean = torch.tensor([0.485,0.456,0.406]).view(1,3,1,1).cuda()
    std = torch.tensor([0.229,0.224,0.225]).view(1,3,1,1).cuda()
    def features(frames):
        arrays=[]
        for rgb in frames:
            img=Image.fromarray(rgb)
            ratio=256/min(img.size)
            img=img.resize((round(img.width*ratio),round(img.height*ratio)),Image.Resampling.BICUBIC)
            x,y=(img.width-224)//2,(img.height-224)//2
            arrays.append(np.asarray(img.crop((x,y,x+224,y+224))))
        batch=torch.from_numpy(np.stack(arrays).copy()).permute(0,3,1,2).cuda().float()/255
        with torch.inference_mode():
            encoded=model((batch-mean)/std)
        return torch.nn.functional.normalize(encoded.float(),dim=-1).cpu()
    rows,embeddings,diagnostics,comparisons=[],{},{},{}
    for e in plan['examples']:
        name=e['example_id']
        data=ROOT/'data'/name
        local=read_rgb(data/'local_context.mp4',512,288)
        oracle=read_rgb(data/'oracle_context.mp4',512,288)
        reference=np.asarray(Image.open(ROOT/'outputs'/name/'five_case_inputs_512x288/oracle_image.png'))
        videos={'gt':read_rgb(data/'gt_target.mp4',512,288)}
        for v in VARIANT_ORDER:
            for cell in CELLS:
                cfg=configs[name][v][cell]
                videos[f'{v}_{cell}']=read_rgb(Path(cfg['outputs']['target']['path']),512,288)
        assert all(len(video)==72 for video in videos.values())
        em={k:features(video[indices]) for k,video in videos.items()}
        em['oracle_image']=features([reference])
        em['oracle_video']=features(oracle[indices])
        embeddings[name]=em
        diagnostics[name]={}
        for key,video in videos.items():
            scores=(em[key]*em['gt']).sum(dim=-1)
            adjacent=np.abs(np.diff(video.astype(np.float32),axis=0)).mean(axis=(1,2,3))
            diagnostics[name][key]={'dino_gt_frame_cosines':scores.tolist(),
                'oracle_image_feature_cosines':(em[key]@em['oracle_image'].T).flatten().tolist(),
                'oracle_video_max_feature_cosine_mean':float((em[key]@em['oracle_video'].T).max(dim=1).values.mean()),
                'adjacent_pixel_mae_0_255':float(adjacent.mean()),
                'near_static_pair_fraction_mae_below_0_1':float((adjacent<0.1).mean()),
                'boundary_pixel_mae_0_255':float(np.abs(local[-1].astype(np.float32)-video[0]).mean())}
            if key=='gt':
                continue
            variant,cell=key.split('_',1)
            cfg=configs[name][variant][cell]
            rows.append({'example_id':name,'title_ko':e['title_ko'],'variant':variant,'cell':cell,'seed':42,
                'reused':variant=='P0','reference_tokens':cfg['reference_tokens'],
                'source_dependency_gap_seconds':cfg['source_dependency_gap_seconds'],
                'dino_gt_cosine':float(scores.mean()),'dino_gt_cosine_after_1s':float(scores[after].mean()),
                'dino_oracle_image_cosine':float((em[key]@em['oracle_image'].T).mean()),
                'dino_oracle_video_max_cosine':diagnostics[name][key]['oracle_video_max_feature_cosine_mean'],
                'adjacent_pixel_mae_0_255':float(adjacent.mean()),
                'generation_seconds_including_load':cfg['total_seconds'],'peak_gpu_allocated_gib':cfg['peak_gpu_allocated_gib'],
                'config_path':str(output_path(name,variant,cell)/'config.json')})
        comparisons[name]=export_assets(REPORT/name,videos,local,oracle,reference)
        print(f'Evaluated and exported {name}: 12 outputs',flush=True)
    previous=json.loads((ROOT/'reports/five_case_grid/seed42/summary.json').read_text())
    anchor_checks=[]
    for r in rows:
        if r['variant']!='P0':
            continue
        old=next(x for x in previous['rows'] if x['example_id']==r['example_id'] and x['mode']==r['cell'])
        for metric in ('dino_gt_cosine','dino_gt_cosine_after_1s'):
            diff=r[metric]-old[metric]
            assert abs(diff)<1e-6,(r['example_id'],r['cell'],metric,diff)
            anchor_checks.append({'example_id':r['example_id'],'cell':r['cell'],'metric':metric,'difference':diff})
    metrics=('dino_gt_cosine','dino_gt_cosine_after_1s','dino_oracle_image_cosine','dino_oracle_video_max_cosine')
    contrasts={}
    for e in plan['examples']:
        name=e['example_id']
        pair={(r['variant'],r['cell']):r for r in rows if r['example_id']==name}
        contrasts[name]={}
        for v in VARIANT_ORDER:
            contrasts[name][v]={}
            for m in metrics:
                effects={c:pair[(v,c)][m]-pair[(v,'local')][m] for c in CELLS if c!='local'}
                old_effects={c:pair[('P0',c)][m]-pair[('P0','local')][m] for c in effects}
                contrasts[name][v][m]={'oracle_minus_local':effects,
                    'cell_minus_same_P0_cell':{c:pair[(v,c)][m]-pair[('P0',c)][m] for c in CELLS},
                    'oracle_benefit_change_vs_P0':{c:effects[c]-old_effects[c] for c in effects}}
    means={v:{c:{m:float(np.mean([r[m] for r in rows if r['variant']==v and r['cell']==c])) for m in metrics}
                  for c in CELLS} for v in VARIANT_ORDER}
    torch.save(embeddings,REPORT/'dino_features.pt')
    summary={'examples':5,'seed':42,'new_generations':45,'reused_generations':15,'outputs_compared':60,
        'plan_sha256':sha256(PLAN_PATH),'command':shlex.join([sys.executable,*sys.argv]),
        'evaluation_script_sha256':sha256(Path(__file__)),'audit_script_sha256':sha256(ROOT/'five_case_prompt_artifacts.py'),
        'metric':{**previous['metric'],'weights_sha256':sha256(weights)},
        'rows':rows,'condition_means':means,'contrasts':contrasts,'pixel_diagnostics':diagnostics,
        'anchor_metric_checks':anchor_checks,'comparison_videos':comparisons,
        'scope':'Full-frame Past evidence, positive prompt only; no masks, adapters, Target positions, learning, or additional seeds.',
        'limitations':['Whole-frame DINO is auxiliary, not identity or prompt-compliance accuracy.',
                      'P1-P3 request controlled cuts/actions that can differ from GT.',
                      'One seed and five appearance cases do not validate general background/state/event reasoning.',
                      'Role sentences also change length and repetition; no claim of attention mechanism.']}
    write_json(REPORT/'summary.json',summary)
    with (REPORT/'results.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    snapshot=REPORT/'evaluation_snapshot'
    snapshot.mkdir(exist_ok=True)
    for filename in ('evaluate_five_case_prompts.py','five_case_prompt_artifacts.py'):
        shutil.copyfile(ROOT/filename,snapshot/filename)
    print(json.dumps({'condition_means':means,'P0_metric_checks':len(anchor_checks)},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
