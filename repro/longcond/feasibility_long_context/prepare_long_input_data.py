"""Extract actual 32-second histories, with shared RGB for native/history/local."""
import json,sys,time
import numpy as np
from prepare_clips import extract
from preview_candidates import preview
from run_generation import read_rgb,write_video
from long_input_common import *

def main():
    p=plan()
    for e in p['examples']:
        d=data_dir(e['example_id']);d.mkdir(parents=True,exist_ok=True)
        if (d/'metadata.json').exists():continue
        source=ROOT/'data/finevideo_candidates'/e['candidate_id']/'source.mp4'
        provenance=json.loads((source.parent/'provenance.json').read_text())
        assert sha256(source)==provenance['sha256']
        t=time.monotonic();hist=extract(source,d/'history_source.mp4',e['history_start'],e['history_end'],24)
        rgb=read_rgb(d/'history_source.mp4',512,288);assert rgb.shape==(768,288,512,3)
        np.save(d/'history_rgb.npy',rgb)
        ingest=time.monotonic()-t
        views={}
        views['history']=write_video(d/'history_32s.mp4',rgb,24)
        views['local']=write_video(d/'local_context.mp4',rgb[-48:],24)
        for kind in ['oracle','uniform']:
            frames=np.concatenate([rgb[(i-1)*8:i*8] for i in e[kind+'_indices']])
            assert len(frames)==72
            views[kind]=write_video(d/(kind+'_context.mp4'),frames,24)
        gt=extract(source,d/'gt_target.mp4',e['target_start'],e['target_end'],24)
        assert all(e['history_start']<=t<e['target_start'] for t in hist['source_frame_seconds'])
        assert set(hist['source_frame_seconds']).isdisjoint(gt['source_frame_seconds'])
        report=ROOT/'reports/long_input_selection'
        for kind in ['local','oracle','uniform','gt_target']:
            path=d/('gt_target.mp4' if kind=='gt_target' else kind+'_context.mp4')
            preview(path,[i*(1.95 if kind=='local' else 2.95)/7 for i in range(8)],report/(e['example_id']+'_'+kind+'.jpg'))
        write_json(d/'metadata.json',{**e,'plan_sha256':sha256(PLAN),'source_provenance':provenance,
            'history':hist,'gt':gt,'views':views,'history_rgb_sha256':sha256(d/'history_rgb.npy'),
            'history_ingest_seconds':ingest,'rgb_shape':list(rgb.shape),
            'rgb_policy':'Native=768 shared resized frames; H=first720; Local=last48. VAE uses NPY, report videos have an extra lossy encode.',
            'no_target_in_history':True})
        print(e['example_id'],f'ingest {ingest:.2f}s',flush=True)

if __name__=='__main__':main()
