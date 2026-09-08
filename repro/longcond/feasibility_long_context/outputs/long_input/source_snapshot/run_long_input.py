"""Generate one controlled long/sparse condition, with separated cost measurements."""
import argparse,json,logging,shlex,subprocess,sys,time
from datetime import datetime,timezone
from long_input_common import *

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--example',required=True);ap.add_argument('--cell',choices=CELLS,required=True);ap.add_argument('--gpu',type=int,choices=[0,1,2],default=0)
    a=ap.parse_args();configure(a.gpu);torch,device,dtype=torch_setup()
    from ltx_core.components.diffusion_steps import EulerAncestralDiffusionStep
    from ltx_core.conditioning.types.latent_cond import VideoConditionByLatentIndex
    from ltx_core.loader.registry import DummyRegistry
    from ltx_core.model.transformer.attention import PytorchAttention
    from ltx_pipelines.utils.blocks import DiffusionStage
    from ltx_pipelines.utils.constants import DISTILLED_SIGMAS
    from ltx_pipelines.utils.denoisers import SimpleDenoiser
    from ltx_pipelines.utils.samplers import euler_ancestral_denoising_loop
    from ltx_pipelines.utils.types import ModalitySpec
    from reference_controls import PairedNoiser,ShiftTime
    from long_input_controls import CanonicalBase,AppendBank,TargetNoise,canonical_positions,bank_positions
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    out=output_dir(a.example,a.cell);out.mkdir(parents=True,exist_ok=True);cfgpath=out/'config.json'
    if cfgpath.exists():raise ValueError(f'Preserve prior attempt before retry: {out}')
    paths,modelinfo=models();e=entry(a.example);native=a.cell=='native_full';prefix=97 if native else 7;frames=841 if native else 121;base=(prefix+9)*144;first=prefix*144
    cfg={'status':'running','example_id':a.example,'example':str(data_dir(a.example)),'cell':a.cell,'mode':'local' if a.cell=='local' else 'oracle','seed':42,'decoder_seed':20042,'physical_gpu':a.gpu,'cuda_visible_devices':str(a.gpu),
      'plan_sha256':sha256(PLAN),'script_sha256':sha256(Path(__file__)),'controls_sha256':sha256(ROOT/'long_input_controls.py'),'models':modelinfo,
      'prompt':e['prompt'],'prompt_enhancement':False,'fps':24,'width':512,'height':288,'target_frames':72,'prefix_latent_frames':prefix,'base_video_tokens':base,'target_token_slice':[first,base],
      'native_model_pixel_frames':frames,'decoder_tail_pixel_frames':121,'decoder_tail_conditioning_latent_frames':7,'sigmas':DISTILLED_SIGMAS.tolist(),'sampler':'Euler ancestral','eta':1.0,'s_noise':1.0,'precision':'bfloat16','guidance':'SimpleDenoiser; no CFG/STG/LoRA','attention_backend':'PytorchAttention / torch SDPA',
      'audio_policy':'Same 121/24-second jointly generated audio, shifted +30s; no source audio or audio decode','no_gt_loaded':True,
      'command':shlex.join([sys.executable,*sys.argv]),'cwd':str(Path.cwd()),'started_at_utc':datetime.now(timezone.utc).isoformat(),'environment':{'torch':torch.__version__,'cuda':torch.version.cuda,'gpu':torch.cuda.get_device_name(0)},'outputs':{}}
    write_json(cfgpath,cfg);watch=WatchGPU(a.gpu,out/'gpu_denoising.csv').start();total_start=time.monotonic()
    try:
      with torch.inference_mode():
        torch.manual_seed(42);load_t=time.monotonic();cpu={};cache=cache_dir(a.example);used={}
        for kind in (['native','text'] if native else ['local','text']+(['history'] if a.cell!='local' else [])):
            info=json.loads((cache/(kind+'.json')).read_text());path=cache/(kind+'.pt')
            assert info['status']=='completed' and info['plan_sha256']==sha256(PLAN) and info['file_sha256']==sha256(path) and info['models']==modelinfo
            cpu[kind]=torch.load(path,map_location='cpu',weights_only=True)
            assert {k:th(v) for k,v in cpu[kind].items()}==info['tensor_hashes']
            used[kind]={'file_sha256':info['file_sha256'],'metadata_sha256':sha256(cache/(kind+'.json'))}
        cfg['cache_load_and_verify_seconds']=time.monotonic()-load_t;cfg['input_caches']=used
        t=time.monotonic();selected=None;indices=[]
        if not native and a.cell!='local':
            indices=list(range(91)) if a.cell=='full_reference' else e['oracle_indices' if a.cell=='oracle_sparse' else 'uniform_indices']
            selected=cpu['history']['latent'].index_select(2,torch.tensor(indices)).contiguous()
            cfg['reference_latent_sha256']=th(selected);cfg['reference_indices']=indices
            del cpu['history']
        cfg['cpu_gather_seconds']=time.monotonic()-t
        t=time.monotonic();condition=cpu['native' if native else 'local']['latent'].to(device)
        contexts={k:v.to(device) for k,v in cpu['text'].items()};reference=selected.to(device) if selected is not None else None
        torch.cuda.synchronize();cfg['h2d_seconds']=time.monotonic()-t
        cfg['condition_latent_sha256']=th(condition);cfg['text_hashes']={k:th(v) for k,v in contexts.items()};cfg['reference_tokens']=len(indices)*144
        conditions=[CanonicalBase(native),VideoConditionByLatentIndex(condition,1.0,0)]
        if reference is not None:conditions.append(AppendBank(reference,indices))
        initial=TargetNoise(42,first,base);step_noise=TargetNoise(10042,first,base)
        simple=SimpleDenoiser(contexts['video_context'],contexts['audio_context']);trace=[];audit_time=0.0
        def check(state):
            mask=(state.denoise_mask==0).expand_as(state.latent)
            error=float((state.latent-state.clean_latent).abs()[mask].max())
            assert error==0 and torch.isfinite(state.latent).all() and int(state.denoise_mask.count_nonzero())==1296
            return error
        def wrapper(model,tools):
            torch.cuda.synchronize();cfg['transformer_load_seconds']=time.monotonic()-stage_start
            cfg['resident_baseline_allocated_gib']=torch.cuda.memory_allocated()/2**30
            cfg['resident_baseline_reserved_gib']=torch.cuda.memory_reserved()/2**30
            cfg['resident_baseline_scope']='Loaded transformer plus already transferred text/condition inputs; before latent-state building'
            torch.cuda.reset_peak_memory_stats();return model
        def denoise(transformer,video_state,audio_state,sigmas,step_index):
            nonlocal audit_time
            t=time.monotonic();error=check(video_state)
            if step_index==0:
                assert torch.equal(video_state.positions[:,:,first:base],canonical_positions(device)[:,:,97*144:])
                if indices:assert torch.equal(video_state.positions[:,:,base:],bank_positions(indices,device))
                torch.save(video_state.positions.cpu(),out/'video_positions.pt');torch.save(audio_state.positions.cpu(),out/'audio_positions.pt')
                torch.save(video_state.clean_latent.cpu(),out/'clean_tokens.pt');torch.save(video_state.denoise_mask.cpu(),out/'denoise_mask.pt')
                torch.save(video_state.latent[:,first:base].cpu(),out/'target_initial_state.pt')
                cfg['target_positions_sha256']=th(video_state.positions[:,:,first:base]);cfg['audio_positions_sha256']=th(audio_state.positions);cfg['audio_shape']=list(audio_state.latent.shape)
                cfg['actual_video_tokens']=video_state.latent.shape[1]
            torch.cuda.synchronize();audit_time+=time.monotonic()-t
            begin=torch.cuda.Event(enable_timing=True);end=torch.cuda.Event(enable_timing=True)
            wall=time.monotonic();begin.record();result=simple(transformer,video_state,audio_state,sigmas,step_index);end.record();torch.cuda.synchronize()
            wall_seconds=time.monotonic()-wall;gpu_seconds=begin.elapsed_time(end)/1000
            t=time.monotonic();assert torch.isfinite(result[0].denoised).all();torch.cuda.synchronize();audit_time+=time.monotonic()-t
            trace.append({'step':step_index,'frozen_max_abs_error':error,'forward_wall_seconds':wall_seconds,'forward_cuda_seconds':gpu_seconds})
            print(a.example,a.cell,f'step {step_index+1}/8 {wall_seconds:.3f}s',flush=True)
            return result
        def loop(**kwargs):
            nonlocal audit_time
            torch.cuda.synchronize();start=time.monotonic()
            vs,aus=euler_ancestral_denoising_loop(**kwargs,noise_seed=10042,new_noise_fn=step_noise,model_dtype=dtype)
            torch.cuda.synchronize();cfg['sampler_wall_seconds_including_audits']=time.monotonic()-start
            cfg['sampler_audit_seconds']=audit_time
            cfg['sampler_seconds_excluding_audits']=cfg['sampler_wall_seconds_including_audits']-audit_time
            cfg['noise_cpu_bookkeeping_seconds']=step_noise.overhead_seconds
            cfg['denoising_peak_allocated_gib']=torch.cuda.max_memory_allocated()/2**30;cfg['denoising_peak_reserved_gib']=torch.cuda.max_memory_reserved()/2**30
            cfg['final_frozen_max_abs_error']=check(vs)
            return vs,aus
        stage=DiffusionStage.from_checkpoint(paths.transformer(),dtype,device,registry=DummyRegistry()).with_attention(PytorchAttention()).with_model_wrapper(wrapper)
        stage_start=time.monotonic()
        state,audio=stage(denoiser=denoise,sigmas=DISTILLED_SIGMAS.to(device),noiser=PairedNoiser(initial),width=512,height=288,frames=frames,fps=24,
            audio_fps=frames*24/121,video=ModalitySpec(context=contexts['video_context'],conditionings=conditions),audio=ModalitySpec(context=contexts['audio_context'],conditionings=[ShiftTime(30)]),
            stepper=EulerAncestralDiffusionStep(eta=1.0,s_noise=1.0),loop=loop)
        assert initial.calls==2 and step_noise.calls==14 and torch.equal(state.latent[:,:,:prefix],condition)
        torch.save(state.latent.cpu(),out/'full_model_latent.pt');torch.save(state.latent[:,:,-16:].cpu(),out/'generated_latent.pt')
        torch.save(initial.targets[0],out/'target_initial_noise.pt');torch.save(step_noise.targets,out/'target_step_noises.pt')
        cfg['noise_audit']={'initial':initial.audit,'ancestral':step_noise.audit};cfg['denoising_trace']=trace
        cfg['forward_cuda_seconds']=sum(r['forward_cuda_seconds'] for r in trace);cfg['forward_wall_seconds']=sum(r['forward_wall_seconds'] for r in trace)
        cfg['incremental_peak_allocated_gib']=cfg['denoising_peak_allocated_gib']-cfg['resident_baseline_allocated_gib']
        cfg['generation_process_seconds_before_decode']=time.monotonic()-total_start;cfg['cpu_peak_rss_gib']=rss_gib();cfg['status']='denoised'
        cfg['device_monitor']=watch.stop();watch=None
        write_json(cfgpath,cfg)
        del state,audio,condition,contexts,reference,conditions;torch.cuda.empty_cache()
      start=time.monotonic()
      subprocess.run([sys.executable,str(ROOT/'decode_five_case_latent.py'),'--config',str(cfgpath),'--output-dir',str(out)],check=True)
      decoded=json.loads((out/'decoder_result.json').read_text());assert decoded['input_latent_file_sha256']==sha256(out/'generated_latent.pt')
      cfg.update(status='completed',outputs=decoded['outputs'],decoder_seconds=decoded['seconds'],decoder_process_wall_seconds=time.monotonic()-start,decoder_peak_allocated_gib=decoded['peak_gpu_allocated_gib'],decoder_result_sha256=sha256(out/'decoder_result.json'),total_process_seconds=time.monotonic()-total_start,finished_at_utc=datetime.now(timezone.utc).isoformat())
      write_json(cfgpath,cfg)
    except Exception as ex:
      cfg.update(status='failed',error=str(ex),error_type=type(ex).__name__)
      if watch is not None:cfg['device_monitor']=watch.stop()
      write_json(cfgpath,cfg);raise

if __name__=='__main__':main()
