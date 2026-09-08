"""Review actual contiguous 32-second candidate histories before generation."""
import json
from pathlib import Path
from preview_candidates import preview
from run_generation import ROOT, write_json

def main():
    examples=json.loads((ROOT/'configs/five_case_examples.json').read_text())['examples']
    dest=ROOT/'reports/long_input_selection'
    dest.mkdir(parents=True,exist_ok=True)
    records=[]
    for e in examples:
        start=e['target_start']-32
        times=[start+i for i in range(35)]
        source=ROOT/'data/finevideo_candidates'/e['candidate_id']/'source.mp4'
        sheet=dest/(e['example_id']+'_32s.jpg')
        frames=preview(source,times,sheet)
        records.append({'example_id':e['example_id'],'source':str(source),'target_start':e['target_start'],
                        'sheet':str(sheet),'frames':frames,'review':'pending visual inspection'})
        print(sheet,flush=True)
    write_json(dest/'initial_review.json',records)

if __name__=='__main__':main()
