"""Identical free-target noise and exact source-bank token/coordinate selection."""
from dataclasses import replace
import time
import torch
from ltx_core.components.patchifiers import VideoLatentPatchifier,get_pixel_coords
from ltx_core.conditioning.item import ConditioningItem
from ltx_core.conditioning.types.keyframe_cond import VideoConditionByKeyframeIndex
from ltx_core.types import VideoLatentShape,SpatioTemporalScaleFactors
from long_input_common import th

def canonical_positions(device='cpu'):
    p=VideoLatentPatchifier(1)
    bounds=p.get_patch_grid_bounds(VideoLatentShape(1,128,106,9,16),device=device)
    positions=get_pixel_coords(bounds,SpatioTemporalScaleFactors(time=8,height=32,width=32),causal_fix=True).float()
    positions[:,0]/=24
    return positions

def bank_positions(indices,device='cpu'):
    p=canonical_positions(device)[:,:,:91*144]
    ti=torch.tensor(indices,device=device)[:,None]*144+torch.arange(144,device=device)[None,:]
    return p.index_select(2,ti.flatten())

class CanonicalBase(ConditioningItem):
    def __init__(self,native):self.native=native
    def apply_to(self,latent_state,latent_tools):
        state,tools=latent_state,latent_tools
        p=canonical_positions(state.positions.device)
        if not self.native:
            first=state.positions[:,:,:144].clone();first[:,0]+=30
            p=torch.cat([first,p[:,:,91*144:]],dim=2)
        assert p.shape==state.positions.shape
        return replace(state,positions=p)

class AppendBank(ConditioningItem):
    def __init__(self,latent,indices):self.latent=latent;self.indices=indices
    def apply_to(self,latent_state,latent_tools):
        state,tools=latent_state,latent_tools
        n=state.latent.shape[1]
        result=VideoConditionByKeyframeIndex(self.latent,frame_idx=0,strength=1.0,num_pixel_frames=8*len(self.indices)+1).apply_to(state,tools)
        positions=result.positions.clone();positions[:,:,n:]=bank_positions(self.indices,positions.device)
        return replace(result,positions=positions)

class TargetNoise:
    def __init__(self,seed,prefix_tokens,base_tokens):
        self.seed=seed;self.prefix=prefix_tokens;self.base=base_tokens;self.calls=0;self.audit=[];self.targets=[];self.overhead_seconds=0
    def __call__(self,tensor,generator=None):
        start=time.monotonic();role=self.calls%2;step=self.calls//2;seed=self.seed+2*step+role
        shape=list(tensor.shape)
        if role==0:shape[1]=9*144
        draw=torch.randn(shape,generator=torch.Generator(device='cpu').manual_seed(seed),dtype=tensor.dtype,device='cpu')
        record={'step':step,'modality':'video' if role==0 else 'audio','seed':seed,'shape':shape,'sha256':th(draw)}
        if role==0:
            assert self.base-self.prefix==9*144
            self.targets.append(draw.clone())
            noise=torch.zeros(tensor.shape,dtype=tensor.dtype,device='cpu');noise[:,self.prefix:self.base]=draw
        else:noise=draw
        self.audit.append(record);self.calls+=1
        self.overhead_seconds+=time.monotonic()-start
        return noise.to(tensor.device)
