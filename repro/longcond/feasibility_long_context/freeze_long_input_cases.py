"""Freeze source-reviewed intervals and prompts before any new generation."""
from datetime import datetime,timezone
from long_input_common import *

def main():
    assert not PLAN.exists(),'Refuse to overwrite frozen design'
    old=json.loads((ROOT/'configs/five_case_examples.json').read_text())
    prompts={e['example_id']:e for e in json.loads((ROOT/'configs/five_case_prompt.json').read_text())['examples']}
    examples=[]
    for e in old['examples']:
        oldid=e['example_id'];num=oldid.split('_')[1];name='long_'+oldid[5:]
        T=e['target_start'];prompt=prompts[oldid]['P1_explicit_shot_action'];startidx={'001':17,'002':29,'003':42,'004':1,'005':24}[num]
        attrs=e['review']['evaluation_attributes_do_not_condition_on'];limits=list(e['review']['limitations'])
        title=e['title_ko'];reason='Original target retained; substitute evidence exists inside preceding 32 seconds.'
        if num=='001':
            T=109.84306666666667;title='보육원 직원 재등장 (새 구간)'
            prompt='A hard cut switches from the visiting assessor to a three-quarter side-angle medium close-up of the same nursery staff member who was seated at the laptop earlier. Her face and shoulders remain fully visible as she speaks and makes a small hand gesture. The camera stays fixed on the staff member in the childcare room.'
            attrs=['The same apparent face and tied-back dark ponytail of the nursery staff member','Red collared shirt with navy sleeveless nursery uniform']
            limits=['This is a different staff member and target from the earlier nursery-manager diagnostic.','Local shows the visiting assessor; it contains a different visible person, not an empty scene.','The same staff member also occurs at the laptop closer to T; Oracle gap is not the nearest possible evidence gap.']
            reason='The previous T=130.063 history contains a different staff member, not the manager. Move T to verified source cut at 109.8430667 and evaluate the staff member.'
        elif num=='002':
            T=260.0
            prompt="The close-up of the robot's lower body ends with a hard cut to a wider display shot. The same robot model stands upright on its own, with its entire head, both shoulders and upper torso comfortably inside the frame. The camera is fixed at the model's head height. Its helmet and face retain their appearance from the earlier view. The model maintains its display pose for the rest of the shot."
            limits=['The original T=367.634 preceding 32 seconds did not clearly expose the required head.','New Local shows torso, legs and then the back of the head; the frontal gold face and helmet front are not exposed.','The unprompted source continuation at T=260 does not show the requested display view. It is a temporal continuation reference, not a valid full-frame GT for this prompted view. Judge head appearance against Oracle and prompt; do not rank this case by GT DINO.','Some Oracle frames contain hands over the torso; background is retained.']
            reason='Move T to 260 so preceding 32 seconds contain the frontal helmet while Local does not. New-view prompting task; source continuation is not the requested-view GT.'
        elif num=='004':prompt=prompts[oldid]['P2_continuity']
        indices=list(range(startidx,startidx+9));uniform=list(range(41,50))
        hstart=T-32
        examples.append({'example_id':name,'previous_example_id':oldid,'candidate_id':e['candidate_id'],'title_ko':title,
          'history_start':hstart,'history_end':T,'local_start':T-2,'target_start':T,'target_end':T+3,'oracle_indices':indices,'uniform_indices':uniform,
          'oracle_nominal_source_interval':[hstart+(startidx-1)/3,hstart+(startidx+8)/3],
          'uniform_nominal_source_interval':[hstart+40/3,hstart+49/3],
          'prompt':prompt,'attributes':attrs,'selection_reason':reason,'limitations':limits,
          'source_review':'Assistant inspected timestamped RGB sheets before generation; not blind/user-validated selection',
          'gt_dino_valid_for_requested_view':num!='002','uniform_oracle_index_overlap':sorted(set(indices)&set(uniform))})
    p={'status':'frozen_for_execution','frozen_at_utc':datetime.now(timezone.utc).isoformat(),'previous_formal_generations':95,
       'user_execution_authorized':True,'seed':42,'width':512,'height':288,'fps':24,'history_seconds':32,'local_seconds':2,'target_seconds':3,
       'sampler_steps':8,'cells':list(CELLS),'new_generations':25,'evidence_latent_frames':9,
       'protocol_sha256':sha256(ROOT/'LONG_INPUT_VS_SPARSE_PROTOCOL.md'),'source_review_sha256':sha256(ROOT/'reports/long_input_selection/initial_review.json'),
       'dataset_revision':old['dataset_revision'],'uniform_rule':'One 9-latent-frame chunk at temporal center of eligible bank indices 1..90: indices 41..49; no evidence avoidance',
       'multi_evidence_status':'All five are single-chunk appearance diagnostics; natural complementary multi-evidence dependency was not established.',
       'success_criteria':{'minimum_sources_oracle_improves_local':2,'noninferior_cases_out_of_5':4,'median_denoising_speedup_goal':1.5,'incremental_memory_reduction_goal':0.2},'examples':examples}
    PLAN.parent.mkdir(parents=True,exist_ok=True);write_json(PLAN,p)
    print(PLAN,sha256(PLAN))

if __name__=='__main__':main()
