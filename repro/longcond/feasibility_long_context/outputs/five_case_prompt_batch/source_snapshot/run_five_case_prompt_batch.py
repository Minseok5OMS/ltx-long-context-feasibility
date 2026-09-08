"""Freeze, prepare, or run 45 prompt comparison cells in fresh processes on GPUs 0-2."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import queue
import shlex
import subprocess
import sys
import threading

from five_case_prompt_common import (ROOT, BATCH, REPORT, PLAN_PATH, PROPOSAL_PATH, VARIANTS, CELLS,
                                    SOURCE_FILES, freeze_sources, load_plan, output_path, now)
from run_generation import sha256, write_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--phase', choices=['preflight', 'prepare', 'generate'], required=True)
    p.add_argument('--max-jobs', type=int, default=0, help='Limit pending jobs, e.g. first three-cell smoke test.')
    args = p.parse_args()
    os.environ['CUDA_VISIBLE_DEVICES'] = ''  # Parent does no GPU work; each child explicitly sets one allowed GPU.
    os.environ['HF_HUB_OFFLINE'] = '1'
    BATCH.mkdir(parents=True, exist_ok=True)
    REPORT.mkdir(parents=True, exist_ok=True)
    if not PLAN_PATH.exists():
        assert args.phase == 'preflight', 'Run preflight first'
        plan = json.loads(PROPOSAL_PATH.read_text())
        plan.update(status='frozen_for_execution', frozen_at_utc=now(), proposal_sha256=sha256(PROPOSAL_PATH),
                    authorization_ko='사용자의 실행해 요청: 5사례 × 3조건 × P1/P2/P3 생성·평가·보고서.',
                    reused_grid_audit_sha256=sha256(ROOT / 'reports/five_case_grid/seed42/artifact_verification.json'),
                    reused_grid_summary_sha256=sha256(ROOT / 'reports/five_case_grid/seed42/summary.json'))
        write_json(PLAN_PATH, plan)
    plan = load_plan()
    freeze_sources()
    if args.phase == 'preflight':
        import torch
        from five_case_grid_artifacts import audit_grid
        torch.set_num_threads(8)
        configs, audit = audit_grid()
        prior_path = ROOT / 'reports/five_case_grid/seed42/artifact_verification.json'
        assert sha256(prior_path) == plan['reused_grid_audit_sha256']
        assert audit == json.loads(prior_path.read_text()), 'Prior grid audit no longer reproduces'
        assert sha256(ROOT / 'reports/five_case_grid/seed42/summary.json') == plan['reused_grid_summary_sha256']
        for e in plan['examples']:
            name = e['example_id']
            assert e['P0_original'] == configs[name]['local']['prompt']
            assert e['P2_continuity'] == e['P1_explicit_shot_action'] + ' ' + e['P2_added_sentence']
            assert e['P3_reference_role'] == e['P2_continuity'] + ' ' + e['P3_added_sentences']
        write_json(BATCH / 'preflight.json', {'status':'passed', 'plan_sha256':sha256(PLAN_PATH),
                   'reused_grid_audit_identical':True, 'reused_grid_audit_sha256':sha256(prior_path),
                   'command':shlex.join([sys.executable,*sys.argv]), 'verified_at_utc':now(),
                   'source_hashes':{f:sha256(ROOT / f) for f in SOURCE_FILES}})
        print('Preflight passed: full previous grid audit reproduced; plan and code frozen.', flush=True)
        return
    preflight = json.loads((BATCH / 'preflight.json').read_text())
    assert preflight['status'] == 'passed' and preflight['plan_sha256'] == sha256(PLAN_PATH)
    jobs, skipped = [], []
    for e in plan['examples']:
        name = e['example_id']
        if args.phase == 'prepare':
            result_path = BATCH / f'{name}_text_preparation.json'
            if result_path.exists():
                prepared = json.loads(result_path.read_text())
                assert prepared['status'] == 'completed' and prepared['plan_sha256'] == sha256(PLAN_PATH)
                skipped.append({'example_id':name})
            else:
                jobs.append({'example_id':name})
        else:
            for variant in VARIANTS:
                for cell in CELLS:
                    job = {'example_id':name, 'variant':variant, 'cell':cell}
                    cfg_path = output_path(name, variant, cell) / 'config.json'
                    if cfg_path.exists():
                        cfg = json.loads(cfg_path.read_text())
                        assert cfg['status'] == 'completed', f'Preserve/recover incomplete attempt first: {cfg_path}'
                        assert cfg['prompt_plan_sha256'] == sha256(PLAN_PATH)
                        assert cfg['script_sha256'] == sha256(ROOT / 'run_five_case_prompt.py')
                        assert all(sha256(Path(a['path'])) == a['sha256'] for a in cfg['outputs'].values())
                        skipped.append(job)
                    else:
                        jobs.append(job)
    if args.max_jobs:
        jobs = jobs[:args.max_jobs]
    pending = queue.Queue()
    for job in jobs:
        pending.put(job)
    records, lock = [], threading.Lock()
    batch_start = now()
    ledger_path = BATCH / (f'{args.phase}_smoke_ledger.json' if args.max_jobs else f'{args.phase}_ledger.json')

    def save_ledger(status):
        write_json(ledger_path, {'status':status, 'phase':args.phase, 'started_at_utc':batch_start,
                   'records':records, 'previously_completed':skipped, 'requested_jobs_this_invocation':len(jobs),
                   'plan_sha256':sha256(PLAN_PATH), 'command':shlex.join([sys.executable,*sys.argv])})

    def worker(gpu):
        while True:
            try:
                job = pending.get_nowait()
            except queue.Empty:
                return
            if args.phase == 'prepare':
                command = [sys.executable, str(ROOT / 'prepare_five_case_prompts.py'), '--example', job['example_id'], '--gpu', str(gpu)]
                tag = job['example_id'] + '_prepare'
            else:
                command = [sys.executable, str(ROOT / 'run_five_case_prompt.py'), '--example',
                           str(ROOT / 'data' / job['example_id']), '--variant', job['variant'], '--cell', job['cell'], '--gpu', str(gpu)]
                tag = '_'.join(job.values())
            log = BATCH / f'{tag}.log'
            record = {**job, 'physical_gpu':gpu, 'command':shlex.join(command), 'log':str(log), 'started_at_utc':now()}
            print(f'Start GPU {gpu}: {tag}', flush=True)
            with log.open('a', encoding='utf-8') as stream:
                result = subprocess.run(command, cwd=ROOT.parent, stdout=stream, stderr=subprocess.STDOUT)
            record.update(returncode=result.returncode, finished_at_utc=now())
            with lock:
                records.append(record)
                save_ledger('running' if result.returncode == 0 else 'failed')
            if result.returncode:
                raise RuntimeError(f'Failed {tag}; see {log}')
            print(f'Complete GPU {gpu}: {tag} ({len(records)}/{len(jobs)})', flush=True)
    save_ledger('running')
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(worker, gpu) for gpu in (0,1,2)]
        for future in futures:
            future.result()
    save_ledger('completed')
    print(f'{args.phase}: {len(records)} newly completed, {len(skipped)} already completed', flush=True)


if __name__ == '__main__':
    main()
