"""Prepare separately measured native/history/local VAE and text caches."""
import argparse,json,time,sys,shlex
import numpy as np
from long_input_common import *

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--example',required=True);ap.add_argument('--kind',choices=['local','history','native','text'],required=True);ap.add_argument('--gpu',type=int,choices=[0,1,2],default=0)
    a=ap.parse_args();configure(a.gpu)
    torch,device,dtype=torch_setup()
    from ltx_core.loader.registry import DummyRegistry
    from ltx_core.tiling import TileSizeConfig,DimensionSizeConfig
    from ltx_pipelines.utils.blocks import ImageConditioner,PromptEncoder
    e=entry(a.example);d=data_dir(a.example);out=cache_dir(a.example);out.mkdir(parents=True,exist_ok=True)
    record=out/(a.kind+'.json');dest=out/(a.kind+'.pt')
    if record.exists():
        cfg=json.loads(record.read_text());assert cfg['status']=='completed' and sha256(dest)==cfg['file_sha256'] and cfg['plan_sha256']==sha256(PLAN);print('reuse',record);return
    paths,info=models();cfg={'status':'running','example_id':a.example,'kind':a.kind,'plan_sha256':sha256(PLAN),'models':info,'physical_gpu':a.gpu,'command':shlex.join([sys.executable,*sys.argv]),'script_sha256':sha256(Path(__file__)),'no_gt_loaded':True}
    write_json(record,cfg);watch=WatchGPU(a.gpu,out/(a.kind+'_gpu.csv')).start();started=time.monotonic()
    try:
        with torch.inference_mode():
            torch.manual_seed(0);torch.cuda.reset_peak_memory_stats()
            if a.kind=='text':
                t=time.monotonic()
                (context,)=PromptEncoder(paths,dtype,device,registry=DummyRegistry())([e['prompt']],enhance_first_prompt=False)
                tensors={'video_context':context.video_encoding.cpu(),'audio_context':context.audio_encoding.cpu()}
                cfg.update(prompt=e['prompt'],encode_including_load_seconds=time.monotonic()-t)
            else:
                t=time.monotonic();rgb=np.load(d/'history_rgb.npy')
                if a.kind=='local':rgb=rgb[-48:]
                elif a.kind=='history':rgb=rgb[:720]
                padded=np.concatenate([rgb[:1],rgb])
                x=torch.from_numpy(padded.copy()).permute(3,0,1,2).unsqueeze(0).to(dtype=dtype)
                x=(x/127.5-1).contiguous();cfg['cpu_input_prepare_seconds']=time.monotonic()-t
                cfg['input_rgb_sha256']=hashlib.sha256(rgb.tobytes()).hexdigest();cfg['input_frames']=len(padded)
                cfg['input_frame_convention']='Duplicate first RGB once; only observed past; whole logical sequence, native VAE tiling'
                tiling=TileSizeConfig(frames=DimensionSizeConfig(tile_size=80,overlap=24))
                cfg['tiling']={'frames_tile_size_pixels':80,'frames_overlap_pixels':24,'spatial_tiling':False,'api':'VideoEncoder.tiled_encode'}
                load_start=time.monotonic()
                def encode(enc):
                    torch.cuda.synchronize();cfg['model_load_seconds']=time.monotonic()-load_start
                    cfg['weight_baseline_allocated_gib']=torch.cuda.memory_allocated()/2**30
                    torch.cuda.reset_peak_memory_stats();t=time.monotonic()
                    z=enc.tiled_encode(x,tiling)
                    torch.cuda.synchronize();cfg['encode_seconds']=time.monotonic()-t
                    cfg['encode_peak_allocated_gib']=torch.cuda.max_memory_allocated()/2**30
                    cfg['encode_peak_reserved_gib']=torch.cuda.max_memory_reserved()/2**30
                    return z.cpu()
                z=ImageConditioner(paths.video_vae(),dtype,device,registry=DummyRegistry())(encode)
                expected={'local':7,'history':91,'native':97}[a.kind]
                assert tuple(z.shape)==(1,128,expected,9,16)
                tensors={'latent':z}
            assert all(torch.isfinite(v).all() for v in tensors.values())
            torch.save(tensors,dest)
            cfg.update(status='completed',file_sha256=sha256(dest),tensor_hashes={k:th(v) for k,v in tensors.items()},shapes={k:list(v.shape) for k,v in tensors.items()},file_bytes=dest.stat().st_size,total_seconds=time.monotonic()-started,cpu_peak_rss_gib=rss_gib())
    except Exception as ex:
        cfg.update(status='failed',error=str(ex),error_type=type(ex).__name__);raise
    finally:
        cfg['device_monitor']=watch.stop();write_json(record,cfg)
    print(a.example,a.kind,cfg['total_seconds'],flush=True)

if __name__=='__main__':main()
