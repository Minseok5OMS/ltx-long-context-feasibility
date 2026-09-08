"""Shared definitions for the isolated long-history comparison."""
from pathlib import Path
import hashlib,json,os,subprocess,time
from run_generation import ROOT,LTX_ROOT,sha256,write_json

PLAN=ROOT/'configs/long_input_cases.json'
WORK=ROOT/'outputs/long_input'
REPORT=ROOT/'reports/long_input'
CELLS=('local','native_full','full_reference','oracle_sparse','uniform_sparse')
LABELS={'local':'Local-only','native_full':'Native-Full','full_reference':'Full-reference','oracle_sparse':'Oracle-sparse','uniform_sparse':'Uniform-sparse'}
def configure(gpu):
    assert gpu in (0,1,2)
    os.environ.update(CUDA_VISIBLE_DEVICES=str(gpu),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
    for key,folder in [('TORCHINDUCTOR_CACHE_DIR','inductor'),('TRITON_CACHE_DIR','triton'),('CUDA_CACHE_PATH','cuda'),('TORCH_EXTENSIONS_DIR','torch_extensions')]:
        p=ROOT/'.cache'/folder;p.mkdir(parents=True,exist_ok=True);os.environ[key]=str(p)
def plan():return json.loads(PLAN.read_text())
def entry(name):return next(e for e in plan()['examples'] if e['example_id']==name)
def data_dir(name):return ROOT/'data/long_input'/name
def cache_dir(name):return WORK/'cache'/name
def output_dir(name,cell):return WORK/'seed42'/name/cell
def th(t):
    import torch
    if not t.numel():return hashlib.sha256(b'').hexdigest()
    return hashlib.sha256(t.detach().cpu().contiguous().reshape(-1).view(torch.uint8).numpy().tobytes()).hexdigest()
def models():
    from ltx_pipelines.utils.model_paths import ModelPaths
    r=LTX_ROOT/'models/ltx-2.5'
    paths=ModelPaths.from_split(transformer_path=str(r/'diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors'),video_vae_path=str(r/'vae/ltx-2.5-video-vae-bf16.safetensors'),text_encoder_path=str(r/'text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors'))
    info={n:{'path':p,'bytes':Path(p).stat().st_size,'mtime_ns':Path(p).stat().st_mtime_ns} for n,p in [('transformer',paths.transformer()),('video_vae',paths.video_vae()),('text_encoder',paths.text_encoder())]}
    return paths,info
def torch_setup():
    import torch
    torch.set_num_threads(8);torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
    assert torch.cuda.is_available();torch.cuda.set_device(0)
    return torch,torch.device('cuda:0'),torch.bfloat16
def rss_gib():
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20
class WatchGPU:
    def __init__(self,gpu,path):self.gpu=gpu;self.path=path
    def start(self):
        self.file=self.path.open('w')
        self.proc=subprocess.Popen(['nvidia-smi','-i',str(self.gpu),'--query-gpu=timestamp,memory.used,utilization.gpu,temperature.gpu','--format=csv,noheader,nounits','-lms','100'],stdout=self.file,stderr=subprocess.DEVNULL)
        return self
    def stop(self):
        self.proc.terminate();self.proc.wait(timeout=10);self.file.close()
        rows=[]
        for line in self.path.read_text().splitlines():
            try:
                v=line.split(',');rows.append({'timestamp':v[0].strip(),'used_mib':float(v[1]),'utilization':float(v[2]),'temperature':float(v[3])})
            except (ValueError,IndexError):pass
        return {'samples':len(rows),'sample_interval_ms':100,'peak_device_used_gib':max((r['used_mib']/1024 for r in rows),default=None),'temperature_c_range':[min((r['temperature'] for r in rows),default=None),max((r['temperature'] for r in rows),default=None)],'scope':'whole isolated process including loading/audits; device total, not process allocator'}
