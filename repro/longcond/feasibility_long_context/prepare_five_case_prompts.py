"""Encode one case's three frozen prompts separately, with exact P0 calibration."""
import argparse
import json
import shlex
import sys
import time
from pathlib import Path

from five_case_prompt_common import (BATCH, VARIANTS, PLAN_PATH, configure_env, load_plan, prompt_cache, now)
from run_generation import ROOT, sha256, write_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--example', required=True)
    p.add_argument('--gpu', type=int, choices=[0, 1, 2], required=True)
    args = p.parse_args()
    configure_env(args.gpu)
    import torch
    from ltx_core.loader.registry import DummyRegistry
    from ltx_pipelines.utils.blocks import PromptEncoder
    from ltx_pipelines.utils.model_paths import ModelPaths
    from reference_controls import tensor_hash

    torch.set_num_threads(8)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    device, dtype = torch.device('cuda:0'), torch.bfloat16
    torch.cuda.set_device(device)
    plan = load_plan()
    entry = next(e for e in plan['examples'] if e['example_id'] == args.example)
    cache = ROOT / 'outputs' / args.example / 'five_case_inputs_512x288'
    old = json.loads((cache / 'inputs.json').read_text())
    assert sha256(cache / 'inputs.pt') == old['inputs_sha256']
    metadata_path = ROOT / 'data' / args.example / 'metadata.json'
    metadata = json.loads(metadata_path.read_text())
    assert metadata['prompt'] == entry['P0_original']
    assert old['fingerprint']['metadata_sha256'] == sha256(metadata_path)
    models = old['fingerprint']['models']
    for m in models.values():
        st = Path(m['path']).stat()
        assert (st.st_size, st.st_mtime_ns) == (m['bytes'], m['mtime_ns'])
    paths = ModelPaths.from_split(transformer_path=models['transformer']['path'],
                                 video_vae_path=models['video_vae']['path'],
                                 text_encoder_path=models['text_encoder']['path'])
    registry = DummyRegistry()
    encoder = PromptEncoder(paths, dtype, device, registry=registry)
    started = time.monotonic()
    records = []
    with torch.inference_mode():
        # Batch size one matches the original input preparation exactly.
        for variant, key in [('P0', 'P0_original'), *VARIANTS.items()]:
            torch.manual_seed(0)
            (context,) = encoder([entry[key]], enhance_first_prompt=False)
            tensors = {'video_context': context.video_encoding.cpu(), 'audio_context': context.audio_encoding.cpu()}
            assert all(torch.isfinite(t).all() for t in tensors.values())
            hashes = {k: tensor_hash(t) for k, t in tensors.items()}
            if variant == 'P0':
                assert hashes == {k: old['tensor_hashes'][k] for k in hashes}, 'P0 embedding calibration failed'
                records.append({'variant': variant, 'calibration': 'exact_previous_embedding_hash_match', 'hashes': hashes})
                print(f'{args.example}/P0: exact calibration passed', flush=True)
                continue
            directory = prompt_cache(args.example, variant)
            directory.mkdir(parents=True, exist_ok=True)
            fingerprint = {'plan_sha256': sha256(PLAN_PATH), 'parent_cache_sha256': old['inputs_sha256'],
                           'metadata_sha256': sha256(metadata_path), 'models': models, 'variant': variant,
                           'prompt': entry[key], 'script_sha256': sha256(Path(__file__)),
                           'encoding_batch_size': 1, 'prompt_enhancement': False}
            if (directory / 'inputs.json').exists():
                prior = json.loads((directory / 'inputs.json').read_text())
                assert prior['fingerprint'] == fingerprint
                assert prior['tensor_hashes'] == hashes and sha256(directory / 'inputs.pt') == prior['inputs_sha256']
            else:
                torch.save(tensors, directory / 'inputs.pt')
                write_json(directory / 'inputs.json', {'fingerprint': fingerprint, 'tensor_hashes': hashes,
                    'inputs_sha256': sha256(directory / 'inputs.pt'), 'shapes': {k:list(t.shape) for k,t in tensors.items()},
                    'physical_gpu': args.gpu, 'gt_video_opened': False, 'visual_inputs_opened': False,
                    'command': shlex.join([sys.executable, *sys.argv]), 'created_at_utc': now()})
            records.append({'variant': variant, 'cache': str(directory), 'hashes': hashes})
            print(f'{args.example}/{variant}: text prepared', flush=True)
    write_json(BATCH / f'{args.example}_text_preparation.json', {'status':'completed', 'records':records,
               'physical_gpu': args.gpu, 'seconds':time.monotonic()-started, 'plan_sha256':sha256(PLAN_PATH)})


if __name__ == '__main__':
    main()
