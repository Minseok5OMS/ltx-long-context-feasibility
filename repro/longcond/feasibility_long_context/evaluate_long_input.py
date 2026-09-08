"""Existing DINO evaluation only; no new semantic model or retrieval features."""
import argparse,os,sys,json
import numpy as np
from PIL import Image
from long_input_common import *
from run_generation import read_rgb

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--gpu',type=int,choices=[0,1,2],default=2);a=ap.parse_args();configure(a.gpu);os.environ['XFORMERS_DISABLED']='1'
    torch,device,dtype=torch_setup()
    repo=Path('/home/minseok/.cache/torch/hub/facebookresearch_dinov2_main');weights=Path('/home/minseok/.cache/torch/hub/checkpoints/dinov2_vitb14_pretrain.pth')
    sys.path.insert(0,str(repo));from dinov2.hub.backbones import dinov2_vitb14
    model=dinov2_vitb14(pretrained=False);model.load_state_dict(torch.load(weights,map_location='cpu',weights_only=True),strict=True);model=model.eval().to(device)
    ix=np.linspace(0,71,12).round().astype(int);after=torch.tensor(ix>=24)
    mean=torch.tensor([.485,.456,.406],device=device).view(1,3,1,1);std=torch.tensor([.229,.224,.225],device=device).view(1,3,1,1)
    def features(rgb):
        images=[]
        for f in rgb:
            im=Image.fromarray(f);r=256/min(im.size);im=im.resize((round(im.width*r),round(im.height*r)),Image.Resampling.BICUBIC)
            x,y=(im.width-224)//2,(im.height-224)//2;images.append(np.asarray(im.crop((x,y,x+224,y+224))))
        b=torch.from_numpy(np.stack(images).copy()).permute(0,3,1,2).to(device).float()/255
        with torch.inference_mode():z=model((b-mean)/std)
        return torch.nn.functional.normalize(z.float(),dim=-1).cpu()
    scores={};emb={}
    for e in plan()['examples']:
        name=e['example_id'];d=data_dir(name);video={'gt':read_rgb(d/'gt_target.mp4',512,288),'oracle':read_rgb(d/'oracle_context.mp4',512,288)}
        for cell in CELLS:
            c=json.loads((output_dir(name,cell)/'config.json').read_text());assert c['status']=='completed'
            video[cell]=read_rgb(Path(c['outputs']['target']['path']),512,288)
        fs={k:features(v[ix]) for k,v in video.items()};emb[name]=fs;scores[name]={}
        for cell in CELLS:
            gt=(fs[cell]*fs['gt']).sum(-1);oracle=(fs[cell]@fs['oracle'].T).max(dim=1).values
            small=np.stack([np.asarray(Image.fromarray(f).resize((128,72))) for f in video[cell]]).astype(np.float32)
            delta=np.abs(np.diff(small,axis=0)).mean(axis=(1,2,3))
            scores[name][cell]={'dino_gt_mean':float(gt.mean()) if e['gt_dino_valid_for_requested_view'] else None,'dino_gt_after_1s':float(gt[after].mean()) if e['gt_dino_valid_for_requested_view'] else None,
              'gt_metric_eligible':e['gt_dino_valid_for_requested_view'],'dino_oracle_max_mean':float(oracle.mean()),'dino_oracle_max_after_1s':float(oracle[after].mean()),
              'adjacent_pixel_mae_128x72':float(delta.mean()),'near_static_fraction_mae_below_0_1':float((delta<.1).mean()),'oracle_cosines':oracle.tolist()}
        print('Evaluated',name,flush=True)
    REPORT.mkdir(parents=True,exist_ok=True);write_json(REPORT/'dino_metrics.json',scores);torch.save(emb,REPORT/'dino_features.pt')
    write_json(REPORT/'evaluation_provenance.json',{'model':'cached dinov2_vitb14','weights_sha256':sha256(weights),'precision':'float32','frames':ix.tolist(),'resize':'short edge 256 bicubic, centered 224 crop, ImageNet normalization','script_sha256':sha256(Path(__file__)),'physical_gpu':a.gpu,'scope':'Auxiliary frame-global similarity; not identity/attribute accuracy; robot GT excluded before generation','plan_sha256':sha256(PLAN)})

if __name__=='__main__':main()
