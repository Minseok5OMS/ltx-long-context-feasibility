"""Frozen prompt comparison paths and immutable inputs; no GPU imports."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil

from run_generation import ROOT, sha256, write_json

PLAN_PATH = ROOT / 'configs/five_case_prompt.json'
PROPOSAL_PATH = ROOT / 'configs/five_case_prompt_proposal.json'
BATCH = ROOT / 'outputs/five_case_prompt_batch'
REPORT = ROOT / 'reports/five_case_prompt/seed42'
VARIANTS = {'P1': 'P1_explicit_shot_action', 'P2': 'P2_continuity', 'P3': 'P3_reference_role'}
CELLS = ('local', 'image_past', 'video_past')
SOURCE_FILES = ('five_case_prompt_common.py', 'prepare_five_case_prompts.py', 'run_five_case_prompt.py',
                'run_five_case_prompt_batch.py', 'reference_controls.py', 'temporal_controls.py',
                'decode_five_case_latent.py', 'run_generation.py')


def configure_env(gpu):
    assert gpu in (0, 1, 2)
    os.environ.update(CUDA_VISIBLE_DEVICES=str(gpu), HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                      TOKENIZERS_PARALLELISM='false')
    for key, folder in [('TORCHINDUCTOR_CACHE_DIR', 'inductor'), ('TRITON_CACHE_DIR', 'triton'),
                        ('CUDA_CACHE_PATH', 'cuda'), ('TORCH_EXTENSIONS_DIR', 'torch_extensions')]:
        path = ROOT / '.cache' / folder
        path.mkdir(parents=True, exist_ok=True)
        os.environ[key] = str(path)


def load_plan():
    plan = json.loads(PLAN_PATH.read_text())
    assert plan['status'] == 'frozen_for_execution'
    assert plan['cohort_config_sha256'] == sha256(ROOT / 'configs/five_case_examples.json')
    assert plan['proposal_sha256'] == sha256(PROPOSAL_PATH)
    assert plan['primary_matrix']['planned_new_generations'] == 45
    assert plan['primary_matrix']['conditions'] == list(CELLS)
    assert plan['primary_matrix']['new_prompts'] == list(VARIANTS.values())
    assert len(plan['examples']) == 5
    return plan


def freeze_sources():
    snapshot = BATCH / 'source_snapshot'
    snapshot.mkdir(parents=True, exist_ok=True)
    for path in [*(ROOT / f for f in SOURCE_FILES), PLAN_PATH, PROPOSAL_PATH, ROOT / 'configs/five_case_examples.json']:
        target = snapshot / path.name
        if target.exists():
            assert sha256(target) == sha256(path), f'Frozen source changed: {path}'
        else:
            shutil.copyfile(path, target)


def prompt_cache(name, variant):
    return ROOT / 'outputs' / name / 'prompt_text_inputs_512x288' / variant


def output_path(name, variant, cell):
    if variant == 'P0':
        if cell in ('local', 'image_past'):
            return ROOT / 'outputs' / name / 'image_past_seed42' / ('local' if cell == 'local' else 'oracle')
        return ROOT / 'outputs' / name / 'reference_grid_seed42' / cell
    assert variant in VARIANTS and cell in CELLS
    return ROOT / 'outputs' / name / 'prompt_control_seed42' / variant / cell


def now():
    return datetime.now(timezone.utc).isoformat()
