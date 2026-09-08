"""Audit exact text, raw evidence, noise, positions and all decoded prompt outputs."""
from fractions import Fraction
import hashlib
import json
from pathlib import Path

import av
import torch

from five_case_prompt_common import (ROOT, BATCH, PLAN_PATH, VARIANTS, CELLS, SOURCE_FILES,
                                    load_plan, output_path, prompt_cache)
from reference_controls import tensor_hash
from run_generation import sha256


def audit_prompts(allow_partial=False):
    torch.set_num_threads(8)
    plan = load_plan()
    snapshot = BATCH / 'source_snapshot'
    for name in SOURCE_FILES:
        assert sha256(ROOT / name) == sha256(snapshot / name)
    assert sha256(PLAN_PATH) == sha256(snapshot / PLAN_PATH.name)
    preflight = json.loads((BATCH / 'preflight.json').read_text())
    assert preflight['status'] == 'passed' and preflight['plan_sha256'] == sha256(PLAN_PATH)
    prior_path = ROOT / 'reports/five_case_grid/seed42/artifact_verification.json'
    assert sha256(prior_path) == plan['reused_grid_audit_sha256']
    prior = json.loads(prior_path.read_text())
    assert sha256(ROOT / 'reports/five_case_grid/seed42/summary.json') == plan['reused_grid_summary_sha256']
    fields = [f for f in prior['common_fields_checked_against_reused_image_past']
              if f not in ('prompt', 'prompt_context_hashes', 'physical_gpu', 'cuda_visible_devices')]
    configs, provenance, reused, pending = {}, [], [], []
    total_target, total_all = 0, 0
    for e in plan['examples']:
        name = e['example_id']
        data = ROOT / 'data' / name
        metadata = json.loads((data / 'metadata.json').read_text())
        cache = ROOT / 'outputs' / name / 'five_case_inputs_512x288'
        cache_info = json.loads((cache / 'inputs.json').read_text())
        assert sha256(cache / 'inputs.pt') == cache_info['inputs_sha256']
        assert sha256(data / 'metadata.json') == cache_info['fingerprint']['metadata_sha256']
        tensors = torch.load(cache / 'inputs.pt', map_location='cpu', weights_only=True)
        assert {k:tensor_hash(v) for k,v in tensors.items()} == cache_info['tensor_hashes']
        video_cache = ROOT / 'outputs' / name / 'five_case_video_inputs_512x288'
        video_info = json.loads((video_cache / 'inputs.json').read_text())
        assert sha256(video_cache / 'inputs.pt') == video_info['inputs_sha256']
        video = torch.load(video_cache / 'inputs.pt', map_location='cpu', weights_only=True)['oracle_video']
        assert tensor_hash(video) == video_info['tensor_hashes']['oracle_video']
        p0 = {cell:json.loads((output_path(name,'P0',cell) / 'config.json').read_text()) for cell in CELLS}
        configs[name] = {'P0':p0}
        baseline = p0['image_past']
        old_initial = torch.load(output_path(name,'P0','image_past') / 'target_initial_noise.pt', map_location='cpu', weights_only=True)
        old_steps = torch.load(output_path(name,'P0','image_past') / 'target_step_noises.pt', map_location='cpu', weights_only=True)
        expected_positions = {cell:torch.load(output_path(name,'P0',cell) / 'video_positions.pt', map_location='cpu', weights_only=True) for cell in CELLS}
        for variant in ['P0', *VARIANTS]:
            text_info = None
            if variant != 'P0':
                text_dir = prompt_cache(name,variant)
                if allow_partial and not (text_dir / 'inputs.json').exists():
                    pending.extend({'example_id':name,'variant':variant,'cell':c} for c in CELLS)
                    continue
                text_info = json.loads((text_dir / 'inputs.json').read_text())
                assert sha256(text_dir / 'inputs.pt') == text_info['inputs_sha256']
                text_tensors = torch.load(text_dir / 'inputs.pt', map_location='cpu', weights_only=True)
                assert {k:tensor_hash(v) for k,v in text_tensors.items()} == text_info['tensor_hashes']
                assert text_info['fingerprint']['prompt'] == e[VARIANTS[variant]]
                assert text_info['fingerprint']['plan_sha256'] == sha256(PLAN_PATH)
                assert text_info['fingerprint']['parent_cache_sha256'] == cache_info['inputs_sha256']
                assert text_info['fingerprint']['encoding_batch_size'] == 1
                assert not text_info['gt_video_opened'] and not text_info['visual_inputs_opened']
                configs[name][variant] = {}
            for cell in CELLS:
                directory = output_path(name,variant,cell)
                cfg_path = directory / 'config.json'
                if allow_partial and not cfg_path.exists():
                    pending.append({'example_id':name,'variant':variant,'cell':cell})
                    continue
                cfg = json.loads(cfg_path.read_text())
                assert cfg['status'] == 'completed' and not cfg['gt_video_opened']
                assert cfg['physical_gpu'] in (0,1,2) and cfg['cuda_visible_devices'] == str(cfg['physical_gpu'])
                if variant == 'P0':
                    if cell == 'video_past':
                        old = next(r for r in prior['provenance'] if r['example_id']==name and r['cell']==cell)
                    else:
                        old = next(r for r in prior['reused_provenance'] if r['example_id']==name and r['mode']==('local' if cell=='local' else 'oracle'))
                    assert sha256(cfg_path) == old['config_sha256']
                    assert cfg['prompt'] == e['P0_original']
                    reused.append({'example_id':name,'cell':cell,'config_sha256':sha256(cfg_path)})
                else:
                    for key in fields:
                        assert cfg[key] == baseline[key], (name,variant,cell,key)
                    assert cfg['prompt_variant'] == variant and cfg['layout'] == cell
                    assert cfg['prompt'] == e[VARIANTS[variant]]
                    assert cfg['prompt_plan_sha256'] == sha256(PLAN_PATH)
                    assert cfg['script_sha256'] == sha256(snapshot / 'run_five_case_prompt.py')
                    assert cfg['common_script_sha256'] == sha256(snapshot / 'five_case_prompt_common.py')
                    assert cfg['prompt_preparation_script_sha256'] == sha256(snapshot / 'prepare_five_case_prompts.py')
                    assert cfg['prompt_context_hashes'] == text_info['tensor_hashes']
                    assert cfg['prompt_text_inputs_sha256'] == text_info['inputs_sha256']
                    assert cfg['video_inputs_sha256'] == video_info['inputs_sha256']
                count = {'local':0,'image_past':144,'video_past':1440}[cell]
                pixels = {'local':0,'image_past':1,'video_past':73}[cell]
                assert cfg['reference_tokens'] == count and cfg['reference_frames'] == pixels
                if variant != 'P0':
                    assert cfg['reference_model_time_range'] == [0.0,pixels/24]
                if cell == 'local':
                    assert cfg['mode']=='local' and cfg['reference_source'] is None
                else:
                    assert cfg['mode']=='oracle'
                    assert cfg['reference_source']['selection_interval'] == [metadata['oracle_start'], metadata['oracle_end']]
                actual_ref = torch.load(directory / 'reference_clean_tokens.pt',map_location='cpu',weights_only=True)
                ref = video if cell=='video_past' else tensors['oracle_still']
                expected_ref = ref.permute(0,2,3,4,1).flatten(1,3)[:, :count]
                assert torch.equal(actual_ref,expected_ref)
                if variant != 'P0' and cell != 'local':
                    assert cfg['reference_input_tensor_sha256']==tensor_hash(ref)
                positions = torch.load(directory/'video_positions.pt',map_location='cpu',weights_only=True)
                assert torch.equal(positions,expected_positions[cell])
                assert tensor_hash(positions[:,:,:2304])==cfg['base_video_positions_sha256']
                if variant != 'P0':
                    before = torch.load(directory/'video_positions_before_translation.pt',map_location='cpu',weights_only=True)
                    assert torch.equal(before,positions), 'Past position must remain unchanged'
                audio = torch.load(directory/'audio_positions.pt',map_location='cpu',weights_only=True)
                assert tensor_hash(audio)==baseline['audio_positions_sha256']
                initial = torch.load(directory/'target_initial_noise.pt',map_location='cpu',weights_only=True)
                steps = torch.load(directory/'target_step_noises.pt',map_location='cpu',weights_only=True)
                assert torch.equal(initial,old_initial) and len(steps)==7
                assert all(torch.equal(a,b) for a,b in zip(steps,old_steps))
                assert cfg['noise_audit']==baseline['noise_audit']
                assert len(cfg['denoising_trace'])==8 and cfg['final_frozen_max_abs_error']==0
                assert all(r['frozen_max_abs_error']==0 for r in cfg['denoising_trace'])
                latent = torch.load(directory/'generated_latent.pt',map_location='cpu',weights_only=True)
                assert tuple(latent.shape)==(1,128,16,9,16) and torch.isfinite(latent).all()
                assert torch.equal(latent[:,:,:7],tensors['local'])
                decoder = json.loads((directory/'decoder_result.json').read_text())
                assert sha256(directory/'decoder_result.json')==cfg['decoder_result_sha256']
                assert decoder['input_latent_file_sha256']==sha256(directory/'generated_latent.pt')
                assert decoder['outputs']==cfg['outputs'] and decoder['decoder_seed']==20042
                assert decoder['decoder_script_sha256']==sha256(snapshot/'decode_five_case_latent.py')
                counts = {}
                for key,a in cfg['outputs'].items():
                    assert sha256(Path(a['path']))==a['sha256']
                    with av.open(a['path']) as container:
                        frames = list(container.decode(video=0))
                    assert len(frames)=={'target':72,'continuation':120,'decoded_full':121}[key]
                    assert all(f.pts*f.time_base==Fraction(i,24) and (f.width,f.height)==(512,288) for i,f in enumerate(frames))
                    counts[key]=len(frames)
                total_target += counts['target']
                total_all += sum(counts.values())
                provenance.append({'example_id':name,'variant':variant,'cell':cell,'config_sha256':sha256(cfg_path),
                    'positions_tensor_sha256':tensor_hash(positions),'reference_tokens_sha256':tensor_hash(actual_ref) if actual_ref.numel() else hashlib.sha256(b'').hexdigest(),
                    'latent_tensor_sha256':tensor_hash(latent),'decoded_frames':counts})
                configs[name].setdefault(variant,{})[cell]=cfg
    new_count = sum(r['variant']!='P0' for r in provenance)
    if not allow_partial:
        assert new_count==45 and len(reused)==15 and not pending
    return configs, {'status':'passed', 'partial':allow_partial, 'new_generations':new_count,
        'reused_generations':len(reused),'pending':pending, 'plan_sha256':sha256(PLAN_PATH),
        'common_fields_equal_to_P0_except_text_and_gpu':fields, 'actual_text_cache_matches_each_exact_prompt':True,
        'all_initial_and_seven_step_noises_match_P0':True,'actual_reference_content_and_positions_match_P0':True,
        'all_frozen_errors':0,'target_frames_fully_decoded':total_target,'all_output_frames_fully_decoded':total_all,
        'provenance':provenance,'reused_provenance':reused}
