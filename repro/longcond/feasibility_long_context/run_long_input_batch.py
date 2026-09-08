"""Run isolated preparation/generation jobs serially on authorized GPU 0."""
import argparse,subprocess,sys,time,json
from datetime import datetime,timezone
from long_input_common import *

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=['cache','generate'],required=True);ap.add_argument('--example');ap.add_argument('--cell',choices=CELLS);ap.add_argument('--max-jobs',type=int);ap.add_argument('--gpu',type=int,choices=[0,1,2],default=0)
    a=ap.parse_args();configure(a.gpu);jobs=[];examples=plan()['examples']
    if a.example:examples=[e for e in examples if e['example_id']==a.example]
    if a.phase=='cache':
        for e in examples:
            for kind in ['local','history','native','text']:
                jobs.append((e['example_id'],kind,'prepare_long_input_cache.py',['--kind',kind],cache_dir(e['example_id'])/(kind+'.json')))
    else:
        # Rotate condition order across cases; serialize all measured jobs.
        for i,e in enumerate(examples):
            order=list(CELLS[i:]+CELLS[:i]);order=[c for c in order if not a.cell or c==a.cell]
            for c in order:jobs.append((e['example_id'],c,'run_long_input.py',['--cell',c],output_dir(e['example_id'],c)/'config.json'))
    batch=WORK/'batch';batch.mkdir(parents=True,exist_ok=True)
    label=a.phase+'_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    ledger=[];done=0
    for name,kind,script,extra,result in jobs:
        if result.exists() and json.loads(result.read_text()).get('status')=='completed':
            ledger.append({'example':name,'kind':kind,'status':'reused_completed','result':str(result)});continue
        if a.max_jobs is not None and done>=a.max_jobs:break
        log=batch/(label+'_'+name+'_'+kind+'.log')
        cmd=[sys.executable,str(ROOT/script),'--example',name,*extra,'--gpu',str(a.gpu)]
        start=time.monotonic();print('RUN',name,kind,flush=True)
        with log.open('w') as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
        row={'example':name,'kind':kind,'status':'completed' if r.returncode==0 else 'failed','returncode':r.returncode,'command':cmd,'seconds':time.monotonic()-start,'log':str(log),'result':str(result)}
        ledger.append(row);write_json(batch/(label+'_ledger.json'),{'phase':a.phase,'jobs':ledger,'plan_sha256':sha256(PLAN)})
        if r.returncode:raise RuntimeError(f'Job failed; see {log}')
        done+=1;print('DONE',name,kind,round(row['seconds'],2),flush=True)
    write_json(batch/(label+'_ledger.json'),{'phase':a.phase,'jobs':ledger,'plan_sha256':sha256(PLAN)})

if __name__=='__main__':main()
