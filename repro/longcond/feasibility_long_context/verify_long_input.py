"""Audit saved real inputs, positions, noise and output frames for long/sparse runs."""
import argparse,json
import av,numpy as np,torch
from long_input_common import *
from long_input_controls import canonical_positions,bank_positions
from ltx_core.components.patchifiers import VideoLatentPatchifier

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--example');ap.add_argument('--allow-partial',action='store_true');a=ap.parse_args()
    report={'status':'passed','plan_sha256':sha256(PLAN),'checks':[],'examples':[]};patch=VideoLatentPatchifier(1)
    for e in plan()['examples']:
        name=e['example_id']
        if a.example and name!=a.example:continue
        cache=cache_dir(name);base={}
        for kind in ['local','history','native','text']:
            info=json.loads((cache/(kind+'.json')).read_text());path=cache/(kind+'.pt')
            assert info['status']=='completed' and info['plan_sha256']==sha256(PLAN) and info['file_sha256']==sha256(path)
            base[kind]=torch.load(path,map_location='cpu',weights_only=True)
            assert {k:th(v) for k,v in base[kind].items()}==info['tensor_hashes']
        assert json.loads((cache/'text.json').read_text())['prompt']==e['prompt']
        d=data_dir(name);meta=json.loads((d/'metadata.json').read_text());assert meta['plan_sha256']==sha256(PLAN)
        rgb=np.load(d/'history_rgb.npy',mmap_mode='r');assert tuple(rgb.shape)==(768,288,512,3)
        for k,r in [('native',rgb),('history',rgb[:720]),('local',rgb[-48:])]:
            assert hashlib.sha256(r.tobytes()).hexdigest()==json.loads((cache/(k+'.json')).read_text())['input_rgb_sha256']
        assert all(e['history_start']<=t<e['target_start'] for t in meta['history']['source_frame_seconds'])
        assert set(meta['history']['source_frame_seconds']).isdisjoint(meta['gt']['source_frame_seconds'])
        cells=[];audio_positions=None;actual_target_positions=None;actual_full_reference_positions=None
        for cell in CELLS:
            out=output_dir(name,cell);path=out/'config.json'
            if not path.exists():
                if a.allow_partial:continue
                raise ValueError(f'Missing {path}')
            c=json.loads(path.read_text())
            if c['status']!='completed':
                if a.allow_partial:continue
                raise ValueError(f'Incomplete {path}')
            assert c['plan_sha256']==sha256(PLAN) and c['prompt']==e['prompt'] and c['seed']==42 and c['physical_gpu'] in [0,1,2]
            assert c['controls_sha256']==sha256(ROOT/'long_input_controls.py') and c['script_sha256']==sha256(ROOT/'run_long_input.py')
            assert c['text_hashes']=={k:th(v) for k,v in base['text'].items()}
            n=97 if cell=='native_full' else 7;start=n*144;stop=(n+9)*144
            pos=torch.load(out/'video_positions.pt',weights_only=True,map_location='cpu')
            clean=torch.load(out/'clean_tokens.pt',weights_only=True,map_location='cpu');mask=torch.load(out/'denoise_mask.pt',weights_only=True,map_location='cpu')
            full=torch.load(out/'full_model_latent.pt',weights_only=True,map_location='cpu');tail=torch.load(out/'generated_latent.pt',weights_only=True,map_location='cpu')
            expected=base['native' if cell=='native_full' else 'local']['latent']
            assert torch.equal(full[:,:,:n],expected) and torch.equal(tail,full[:,:,-16:])
            assert torch.equal(clean[:,:start],patch.patchify(expected))
            # CPU division and CUDA reciprocal multiplication differ by up to one fp32 ULP.
            # The causal comparison must use actual saved GPU positions, bit-for-bit.
            target_positions=pos[:,:,start:stop]
            cpu_delta=float((target_positions-canonical_positions()[:,:,97*144:]).abs().max())
            assert cpu_delta<=4e-6
            if actual_target_positions is None:actual_target_positions=target_positions
            else:assert torch.equal(actual_target_positions,target_positions)
            assert mask[:,:start].count_nonzero()==0 and mask[:,stop:].count_nonzero()==0 and bool((mask[:,start:stop]==1).all())
            assert clean[:,start:stop].count_nonzero()==0
            idx=list(range(91)) if cell=='full_reference' else e['oracle_indices' if cell=='oracle_sparse' else 'uniform_indices'] if cell in ['oracle_sparse','uniform_sparse'] else []
            if idx:
                z=base['history']['latent'][:,:,idx].contiguous()
                assert torch.equal(clean[:,stop:],patch.patchify(z))
                assert float((pos[:,:,stop:]-bank_positions(idx)).abs().max())<=4e-6
                if cell=='full_reference':actual_full_reference_positions=pos[:,:,stop:]
                elif actual_full_reference_positions is not None:
                    ids=(torch.tensor(idx)[:,None]*144+torch.arange(144)[None,:]).flatten()
                    assert torch.equal(pos[:,:,stop:],actual_full_reference_positions.index_select(2,ids))
            else:assert clean.shape[1]==stop
            apose=torch.load(out/'audio_positions.pt',weights_only=True,map_location='cpu')
            if audio_positions is None:audio_positions=apose
            else:assert torch.equal(audio_positions,apose)
            assert c['audio_shape']==[1,126,128] and c['actual_video_tokens']==stop+144*len(idx)
            initial=torch.load(out/'target_initial_noise.pt',weights_only=True,map_location='cpu')
            observed=torch.load(out/'target_initial_state.pt',weights_only=True,map_location='cpu')
            assert torch.equal(initial,observed)
            steps=torch.load(out/'target_step_noises.pt',weights_only=True,map_location='cpu');assert len(steps)==7
            for seed,z in [(42,initial),*[(10042+2*i,z) for i,z in enumerate(steps)]]:
                expected_noise=torch.randn((1,1296,128),generator=torch.Generator().manual_seed(seed),dtype=torch.bfloat16)
                assert torch.equal(z,expected_noise)
            audio_rows=[r for r in c['noise_audit']['initial']+c['noise_audit']['ancestral'] if r['modality']=='audio']
            for row in audio_rows:
                z=torch.randn(row['shape'],generator=torch.Generator().manual_seed(row['seed']),dtype=torch.bfloat16);assert th(z)==row['sha256']
            assert len(c['denoising_trace'])==8 and all(r['frozen_max_abs_error']==0 for r in c['denoising_trace']) and c['final_frozen_max_abs_error']==0
            assert c['no_gt_loaded'] and len(c['sigmas'])==9
            videos=[]
            for kind,info in c['outputs'].items():
                vp=Path(info['path']);assert sha256(vp)==info['sha256'];count=0;h=hashlib.sha256()
                with av.open(str(vp)) as con:
                    for f in con.decode(video=0):
                        assert abs(float(f.time)-count/24)<1e-5 and (f.width,f.height)==(512,288)
                        h.update(f.to_ndarray(format='rgb24').tobytes());count+=1
                assert count==info['frames']=={'target':72,'continuation':120,'decoded_full':121}[kind]
                videos.append({'kind':kind,'frames':count,'decoded_rgb_sha256':h.hexdigest()})
            cells.append({'cell':cell,'checks':'cache/source subset, clean prefix, actual initial state, 7 noises, exact actual GPU positions, audio, 8-step freeze, all video frames passed','cpu_recomputed_position_max_abs_error_seconds':cpu_delta,'config_sha256':sha256(path),'videos':videos})
        report['examples'].append({'example_id':name,'cells':cells,'same_observed_rgb_native_H_Local':True,'gt_disjoint':True})
    report['completed_conditions']=sum(len(e['cells']) for e in report['examples'])
    if not a.allow_partial:assert report['completed_conditions']==(5 if a.example else 25)
    REPORT.mkdir(parents=True,exist_ok=True)
    dest=REPORT/('verification_'+a.example+'.json' if a.example else 'artifact_verification.json')
    write_json(dest,report);print('PASS',report['completed_conditions'],'conditions',dest)

if __name__=='__main__':main()
