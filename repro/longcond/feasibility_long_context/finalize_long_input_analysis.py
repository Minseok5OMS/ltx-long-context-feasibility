"""Persist assistant observations and derive cost tables from the 25 measured runs."""
import csv, json, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / 'reports/long_input'
def save(name, value):
    (REPORT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def main():
    blind = json.loads((REPORT/'review_blind.json').read_text())
    mapping = json.loads((REPORT/'blind_mapping.json').read_text())
    # Evidence, requested view/action, visual continuity. Identity and visibility are separate.
    scores = [
        {'A':(2,1,1),'B':(0,0,2),'C':(0,0,2),'D':(0,0,2),'E':(0,0,2)},
        {'A':(0,0,2),'B':(0,0,2),'C':(0,2,1),'D':(2,2,1),'E':(0,1,2)},
        {c:(0,0,2) for c in 'ABCDE'},
        {'A':(0,0,2),'B':(0,0,2),'C':(0,0,2),'D':(2,1,1),'E':(0,0,2)},
        {'A':(0,2,2),'B':(1,1,1),'C':(0,2,2),'D':(0,0,0),'E':(0,0,0)},
    ]
    visibility = [
        {c:('visible_target' if c=='A' else 'wrong_subject') for c in 'ABCDE'},
        {'A':'not_exposed','B':'not_exposed','C':'visible_wrong_attribute','D':'visible_target','E':'wrong_view_back'},
        {c:'not_exposed' for c in 'ABCDE'},
        {c:('visible_target' if c=='D' else 'not_exposed') for c in 'ABCDE'},
        {'A':'visible_wrong_attribute','B':'partial_cropped','C':'visible_wrong_attribute','D':'not_exposed','E':'not_exposed'},
    ]
    notes = [
        'Oracle만 대상 직원의 외관을 드러낸다. 참조와 비슷한 중간 거리 구도로 돌아가며 요청한 측면 close-up은 약하다.',
        'Oracle은 각진 helmet/금색 앞면을 독립 display 구도와 결합한다. Local은 새 구도를 만들지만 둥근 은색 얼굴로 바뀐다. 긴 입력 두 조건은 손 조작과 머리 잘림을 유지한다.',
        '모든 조건이 교사 앞면/학생 뒷면을 유지한다. 학생 얼굴 미노출이며 identity 오류로 단정하지 않는다. Oracle/Uniform은 9개 중 8개 latent index가 겹친다.',
        'Oracle만 외부 차체를 드러내지만 남성 selfie/주차 구도도 재현한다. 약 1초의 긴 dissolve가 있으며 주행·바퀴 회전 성공은 아니다.',
        'Oracle은 회색 머리/안경 일부가 상단에 잘리고 손/몸통 및 자막을 재현한다. 긴 입력 두 조건은 지속적인 이중 영상이다. Local/Uniform은 더 깨끗한 측면 얼굴을 만들지만 과거의 머리/안경 외관이 다르다.',
    ]
    reviewed = {}
    rows = []
    for i, (name, cells) in enumerate(mapping.items()):
        reviewed[name] = {'summary_ko':notes[i], 'cells':{}}
        for code, cell in cells.items():
            ev, view, quality = scores[i][code]
            entry = {'blind_code':code,'evidence_score':ev,'view_action_score':view,'continuity_score':quality,
                     'visibility':visibility[i][code],'observation_ko':blind['observations'][name][code]}
            reviewed[name]['cells'][cell] = entry
            rows.append({'example_id':name,'cell':cell,**entry})
    save('review.json', {'reviewer':'assistant; provisional qualitative assessment, not human benchmark labels',
        'method_ko':'1차: 조건명을 확인하기 전 25개 영상의 7개 시점 및 8개 결과의 전체 72프레임 sheet 검토. 조건명 매핑 후 나머지 17개 전체 72프레임 sheet도 검토했다. 각 출력 3초의 전체 프레임을 확인했지만 실시간 재생을 직접 관찰한 평가는 아니다. 미세한 외관·동작의 최종 판단은 영상 재생 검토가 필요하다.',
        'rubric':{'evidence_score':'0 absent/wrong, 1 partial/uncertain, 2 clear requested evidence; see visibility field',
                  'view_action_score':'0 failed, 1 partial, 2 requested composition/action after transition; identity scored separately',
                  'continuity_score':'0 severe persistent artifacts, 1 some transition/visual defects, 2 acceptable in frame inspection'},
        'examples':reviewed,
        'paired_evidence_vs_native_and_full':{'clear_wins':3,'partial_improvement':1,'shared_failure':1,'clear_losses':0},
        'interpretation_ko':'선택 증거의 부분적인 품질 이점과 계산 절감은 확인됐다. 로봇은 외관과 새 구도를 결합했다. 전체 연구의 압축 전역 메모리 직접 조건/자동 검색은 미검증이다.'})
    with (REPORT/'qualitative_scores.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary=json.loads((REPORT/'summary.json').read_text()); raw=summary['rows']; assert len(raw)==25
    cells=['local','native_full','full_reference','oracle_sparse','uniform_sparse']
    keys=[k for k in raw[0] if all(isinstance(r[k],(int,float)) and not isinstance(r[k],bool) for r in raw)]
    medians={c:{k:statistics.median(r[k] for r in raw if r['cell']==c) for k in keys} for c in cells}
    pairs=[]
    for name in mapping:
        rr={r['cell']:r for r in raw if r['example_id']==name}; o=rr['oracle_sparse']
        for b in ['native_full','full_reference']:
            pairs.append({'example_id':name,'baseline':b,
                'denoising_speedup':rr[b]['denoising_seconds']/o['denoising_seconds'],
                'execution_body_speedup':rr[b]['execution_body_seconds_including_audits']/o['execution_body_seconds_including_audits'],
                'component_sum_speedup':rr[b]['prepared_plus_execution_component_sum_seconds']/o['prepared_plus_execution_component_sum_seconds'],
                'allocated_reduction_fraction':1-o['peak_allocated_gib']/rr[b]['peak_allocated_gib'],
                'incremental_reduction_fraction':1-o['incremental_peak_gib']/rr[b]['incremental_peak_gib'],
                'device_peak_reduction_fraction':1-o['device_peak_gib']/rr[b]['device_peak_gib']})
    paired_medians={b:{k:statistics.median(p[k] for p in pairs if p['baseline']==b) for k in pairs[0] if k not in ['example_id','baseline']} for b in ['native_full','full_reference']}
    save('cost_analysis.json', {'condition_medians':medians,'paired_ratios':pairs,'paired_medians':paired_medians,'scope':summary['cost_scope']})
    print(json.dumps(paired_medians,indent=2))

if __name__=='__main__':main()
