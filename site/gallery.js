'use strict';
const data = window.ARCHIVE;
const groupSelect = document.querySelector('#group');
const caseSelect = document.querySelector('#case');
const variantSelect = document.querySelector('#variant');
const esc = value => String(value == null ? '' : value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const range = value => Array.isArray(value) ? `[${value.map(x => Number(x).toFixed(4)).join(', ')}) s` : '원본 config 참조';
const video = (asset, output=false) => `<video ${output?'data-output="true"':''} controls playsinline preload="none" poster="${esc(asset.poster)}" src="${esc(asset.path)}"></video>`;
const inputNames = {local_context:'Local · 고정 prefix',oracle_context:'Oracle · 과거 증거 구간',random_context:'Random · 무관한 과거 구간',history_32s:'History · 연속 과거 32초',uniform_context:'Uniform · 중앙 고정 구간',gt_target:'원본 후속 · 입력 제외'};
function setChoices(select, choices, previous='') { select.innerHTML=choices.map(([v,t])=>`<option value="${esc(v)}">${esc(t)}</option>`).join(''); if(choices.some(x=>x[0]===previous))select.value=previous; }
setChoices(groupSelect,data.groups.map(g=>[g.id,`${g.id}. ${g.title} · 신규 ${g.new_count}회 / 비교 ${g.entries.length}개`]));
groupSelect.value='9';
function filters(reset=false){
 const group=data.groups.find(g=>g.id===groupSelect.value);
 const ids=[...new Set(group.entries.map(e=>data.runs[e.run].case_id))];
 setChoices(caseSelect,[['','전체 사례'],...ids.map(id=>[id,data.cases[id].title])],reset?'':caseSelect.value);
 const variants=[...new Set(group.entries.map(e=>e.variant).filter(Boolean))].sort();
 setChoices(variantSelect,[['','전체'],...variants.map(v=>[v,v])],reset?'':variantSelect.value);
 variantSelect.parentElement.hidden=variants.length===0;
 render();
}
function render(){
 document.querySelectorAll('video').forEach(v=>v.pause());
 const group=data.groups.find(g=>g.id===groupSelect.value);
 document.querySelector('#description').textContent=group.summary;
 const entries=group.entries.filter(e=>(!caseSelect.value||data.runs[e.run].case_id===caseSelect.value)&&(!variantSelect.value||e.variant===variantSelect.value));
 const ids=[...new Set(entries.map(e=>data.runs[e.run].case_id))];
 document.querySelector('#results').innerHTML=ids.map(id=>{
  const c=data.cases[id];
  const inputs=Object.entries(c.inputs).map(([kind,asset])=>`<article class="card"><h3>${esc(inputNames[kind]||kind)}</h3>${video(asset)}<p class="detail">${esc(asset.note||'RGB 표시 영상')}</p></article>`).join('');
  const stills=Object.entries(c.stills).map(([kind,a])=>`<article class="card"><h3>${esc(kind==='oracle'?'Oracle 이미지':'Random 이미지')} · frame ${a.frame_index}</h3><img src="${esc(a.path)}" alt="${esc(kind)} 실제 이미지 참조"><p class="detail">이 이미지 한 장을 인코딩한 조건에만 해당합니다. 영상 조건과 구분합니다.</p></article>`).join('');
  const cards=entries.filter(e=>data.runs[e.run].case_id===id).map(e=>{
   const r=data.runs[e.run];
   const ref=r.reference_asset?`<a href="${esc(r.reference_asset)}">${esc(r.reference_label)}</a>`:esc(r.reference_label);
   return `<article class="card"><h3>${esc(e.label||r.label)}</h3><span class="tag">seed ${r.seed}</span>${e.variant?`<span class="tag">${esc(e.variant)}</span>`:''}${e.reused?'<span class="tag reuse">재사용</span>':'<span class="tag">신규 실행</span>'}${video(r.target,true)}<p class="detail"><strong>참조:</strong> ${ref}</p><p class="detail">${esc(r.condition_note)}</p>${r.cost?`<p class="detail">Denoising ${r.cost.denoising_seconds.toFixed(3)} s · peak allocated ${r.cost.peak_allocated_gib.toFixed(3)} GiB</p>`:''}<div class="result-links"><a href="${esc(r.continuation.path)}">Local + Target 5초</a><a href="${esc(r.config)}" download>원본 config 다운로드</a></div><details><summary>Prompt · 좌표 · 실행 정보</summary><pre>${esc(r.prompt)}</pre><p class="detail">참조 모델 좌표: ${esc(range(r.reference_time))}<br>Target 모델 좌표: ${esc(range(r.target_time))}<br>참조 token: ${r.reference_tokens}<br>원본 참조 구간: ${esc(range(r.source_interval))}<br>실행 ID: ${esc(r.id)}<br>실제 실행 경로: <code>${esc(r.source_config)}</code></p>${r.indices?`<p class="detail">H latent indices: ${esc(r.indices.join(', '))}</p>`:''}</details></article>`;
  }).join('');
  return `<section class="case"><h2 class="case-title">${esc(c.title)} <small>${esc(id)}</small></h2><p>${esc(c.observation||'진단 결과 해석은 실험 흐름 문서를 함께 확인하세요.')}</p><details class="input-panel" open><summary>실제 입력과 평가용 후속 구간</summary><p class="detail">${esc(c.note)}</p><div class="inputs">${inputs}${stills}</div><p class="detail">원본: ${esc(c.source_title)} · <a href="${esc(c.metadata)}" download>구간·출처 metadata 다운로드</a></p></details><div class="controls"><button class="play-all">이 사례 결과 처음부터 재생</button><button class="pause-all">일시정지</button></div><div class="grid">${cards}</div></section>`;
 }).join('')||'<p class="empty">해당 조건에 결과가 없습니다.</p>';
 document.querySelectorAll('.play-all').forEach(b=>b.addEventListener('click',()=>{const videos=b.closest('.case').querySelectorAll('video[data-output]');videos.forEach(v=>{v.currentTime=0;v.play().catch(()=>{});});}));
 document.querySelectorAll('.pause-all').forEach(b=>b.addEventListener('click',()=>b.closest('.case').querySelectorAll('video').forEach(v=>v.pause())));
}
groupSelect.addEventListener('change',()=>filters(true));caseSelect.addEventListener('change',render);variantSelect.addEventListener('change',render);filters();
