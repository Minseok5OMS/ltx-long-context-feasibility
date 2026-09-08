"""Build a Korean five-case report with actual inputs, generation and review together."""

import html
import json
import os
from pathlib import Path
from PIL import Image

from render_reference_docs import render_documents
from run_generation import ROOT, read_rgb


def main():
    report = ROOT / "reports/five_cases/seed42"
    summary = json.loads((report / "summary.json").read_text())
    review = json.loads((report / "review.json").read_text())
    protocol = json.loads((ROOT / "configs/five_case_examples.json").read_text())
    audit = json.loads((report / "artifact_verification.json").read_text())
    render_documents()
    esc = html.escape

    def link(path):
        return esc(os.path.relpath(path, report))

    rows, cards = [], []
    for number, example in enumerate(protocol["examples"], 1):
        name = example["example_id"]
        data = ROOT / "data" / name
        cache = ROOT / "outputs" / name / "five_case_inputs_512x288"
        metadata = json.loads((data / "metadata.json").read_text())
        Image.fromarray(read_rgb(data / "local_context.mp4", 512, 288)[-1]).save(report / name / "input_local_poster.jpg", quality=94)
        results = {r["mode"]: r for r in summary["rows"] if r["example_id"] == name}
        observation = review["cases"][name]
        delta = summary["oracle_minus_local"][name]["dino_gt_cosine"]
        rows.append(f'<tr><td><a href="#{name}">{number}. {esc(example["title_ko"])}</a></td>'
                    f'<td>{results["local"]["dino_gt_cosine"]:.4f}</td><td>{results["oracle"]["dino_gt_cosine"]:.4f}</td>'
                    f'<td>{delta:+.4f}</td><td>{esc(observation["verdict_ko"])}</td></tr>')
        def bullets(items):
            return '<ul>' + ''.join(f'<li>{esc(item)}</li>' for item in items) + '</ul>'
        source_end_gap = metadata["target_start"] - metadata["oracle_end"]
        point_gap = metadata["target_start"] - metadata["oracle_image_source_seconds"]
        cards.append(f'''
<article id="{name}">
 <h2>{number}. {esc(example["title_ko"])}</h2>
 <p class="verdict">{esc(observation["verdict_ko"])} · {esc(observation["summary_ko"])}</p>
 <p>찾아볼 속성: {' · '.join(esc(a) for a in example["review"]["evaluation_attributes_do_not_condition_on"])}</p>
 <div class="inputs">
  <figure><figcaption>공통 Local · 실제 고정 조건<br><small>원본 {metadata["local_start"]:.6f}–{metadata["local_end"]:.6f}초</small></figcaption>
   <video controls preload="none" poster="{name}/input_local_poster.jpg" src="{link(cache / 'local_context.mp4')}"></video><p>48 RGB frames → 첫 장 복제 → 1,008 latent token</p></figure>
  <figure><figcaption>Oracle에만 넣은 실제 이미지 한 장<br><small>원본 {metadata["oracle_image_source_seconds"]:.6f}초</small></figcaption>
   <img src="{link(cache / 'oracle_image.png')}" alt="실제 독립 VAE 인코딩된 과거 이미지" loading="eager"><p>1 RGB frame → 144 latent token · past t=0</p></figure>
  <figure><figcaption>GT Target · 평가용<br><small>원본 {metadata["target_start"]:.6f}–{metadata["target_end"]:.6f}초</small></figcaption>
   <video controls preload="none" poster="{name}/gt_poster.jpg" src="{link(data / 'gt_target.mp4')}"></video><p>생성 입력에 포함하지 않음</p></figure>
 </div>
 <p><b>공통 prompt:</b> <span lang="en">{esc(example["prompt"])}</span></p>
 <p class="muted">원본 증거 구간 끝→Target 간격 {source_end_gap:.3f}초; 실제 선택 이미지→Target {point_gap:.3f}초. 모델의 RoPE 간격과 별개입니다.</p>
 <h3>동기화 비교 · 왼쪽 GT / 가운데 Local-only / 오른쪽 Local+Oracle</h3>
 <p>처음 2초는 세 열 모두 실제 Local, 이후 3초가 비교할 Target입니다. 참조 이미지는 위에 따로 표시했습니다.</p>
 <video class="comparison" controls playsinline preload="metadata" poster="{name}/comparison_poster.jpg" src="{name}/comparison.mp4"></video>
 <div class="observations"><div><h3>Local-only 관찰</h3>{bullets(observation["local_observations_ko"])}</div>
 <div><h3>Oracle 관찰</h3>{bullets(observation["oracle_observations_ko"])}</div></div>
 <p><b>동작·복사·연결:</b> {esc(observation["motion_copy_caveat_ko"])}</p>
 <p>DINO 전체: {results["local"]["dino_gt_cosine"]:.4f} → {results["oracle"]["dino_gt_cosine"]:.4f};
  1초 이후 공통 샘플: {results["local"]["dino_gt_cosine_after_1s"]:.4f} → {results["oracle"]["dino_gt_cosine_after_1s"]:.4f}. 인물/물체 정확도가 아닌 전체 프레임 보조값입니다.</p>
 <details><summary>시간별 프레임 확대</summary><p>Target 0 / 0.33 / 0.67 / 1 / 1.67 / 2.33 / 2.96초</p><a href="{name}/comparison_frames.jpg"><img src="{name}/comparison_frames.jpg" alt="GT, Local, Oracle 시간별 비교" loading="lazy"></a></details>
 <details><summary>사례 한계와 원본·실행 기록</summary>{bullets(example["review"]["limitations"])}
  <p>3초 Oracle 선택 구간은 검토용이며 그 전체 영상은 모델에 넣지 않았습니다.</p>
  <video controls preload="none" src="{link(cache / 'oracle_context.mp4')}"></video>
  <p><a download href="{link(data / 'metadata.json')}">원본 시간·속성·clip hash JSON 다운로드</a> ·
  <a download href="{link(cache / 'inputs.json')}">입력 cache 기록 다운로드</a> ·
  <a download href="{link(ROOT / 'outputs' / name / 'image_past_seed42/local/config.json')}">Local 설정 다운로드</a> ·
  <a download href="{link(ROOT / 'outputs' / name / 'image_past_seed42/oracle/config.json')}">Oracle 설정 다운로드</a></p></details>
 <p><a href="#top">요약 표로</a></p>
</article>''')
    body = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FineVideo 5개 원본 · Local / Oracle</title><style>
:root{{color-scheme:dark}}*{{box-sizing:border-box}}body{{background:#10151e;color:#e6ecf4;font:16px/1.65 system-ui,sans-serif;max-width:1220px;margin:0 auto;padding:28px 24px 80px}}a{{color:#8bc4ff}}h1{{font-size:30px}}h2{{font-size:25px}}h3{{font-size:18px}}.lead,.verdict{{background:#1e2d42;padding:16px;border-radius:10px}}.muted,small{{color:#abb9cc}}article{{border-top:1px solid #405065;margin-top:40px;padding-top:20px;scroll-margin-top:15px}}table{{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}}th,td{{padding:10px;border-bottom:1px solid #3a4658;text-align:left}}.tablewrap{{overflow-x:auto}}figure{{margin:0}}figcaption{{font-weight:650;min-height:62px}}figure p{{font-size:13px;color:#b4c3d6}}video,img{{width:100%;height:auto;background:#080c12;border-radius:6px}}.inputs{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:15px}}.inputs video,.inputs img{{aspect-ratio:16/9;object-fit:contain}}.comparison{{max-height:360px}}.observations{{display:grid;grid-template-columns:1fr 1fr;gap:25px}}details{{background:#18212e;padding:12px 16px;border-radius:8px;margin:15px 0}}summary{{cursor:pointer;color:#aacff7}}details video{{max-width:512px}}nav{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:25px}}li{{margin:5px 0}}@media(max-width:760px){{body{{padding:18px 12px}}.inputs,.observations{{grid-template-columns:1fr}}figcaption{{min-height:0}}h1{{font-size:25px}}}}
</style></head><body id="top">
<nav><a href="../../../report.html">전체 실험</a><a href="../../../FIVE_CASE_RESULT.html">결과·해석 문서</a><a href="../../../FIVE_CASE_PROTOCOL.html">사전 고정 설계</a><a href="../../../FEASIBILITY_STATUS.html">Stage 진행 현황</a></nav>
<h1>FineVideo 5개 원본 · Local / Oracle</h1>
<p class="lead">{esc(review["overall_summary_ko"])}</p>
<p>서로 다른 원본 5개 · seed 42 · 과거 이미지 한 장 · 신규 10회. 장면/시점 전환은 공통 prompt로 지시했습니다. 외관 활용 진단이며 상태·사건·학습된 전역 메모리의 검증은 아닙니다.</p>
<div class="tablewrap"><table><thead><tr><th>사례</th><th>Local DINO</th><th>Oracle DINO</th><th>차이</th><th>정성 판정</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<p class="muted">DINO는 배경·구도·전환까지 반영하는 보조 유사도입니다. 정성 판정은 assistant의 지정 프레임 검토이며 사람의 검수 완료가 아닙니다. 수치 상승을 곧바로 성공으로 집계하지 않았습니다.</p>
<details><summary>어떻게 주입했나 · 다섯 사례의 공통 방식</summary>
<p>Local은 생성 latent 앞 1,008 token을 denoising 내내 고정합니다. Oracle은 별도의 과거 이미지 VAE latent 144 token을 append하여 같은 self-attention에 참여합니다. 참조는 decoder 전에 제거합니다. Local도 실제 생성 조건이며, 단순히 영상 앞에 붙여 디코딩하는 방식이 아닙니다.</p>
<p>모델 시간: Oracle [0,1/24)초 → Local [97/24,146/24)초 → Target [146/24,218/24)초. Local-only에도 같은 base 시간 이동을 적용합니다. 512×288, 24 FPS, 3초, 기존 distilled 8 step, BF16, IC-LoRA·CFG·새 학습 없음.</p>
<p>초기 및 7회 ancestral target noise, 공통 base AV 좌표, prompt, local을 쌍에서 고정했습니다. {len(audit["paired_equal_fields"])}개 공통 설정·실제 참조·좌표·noise 감사를 통과했고 고정 latent 오차는 모든 step과 최종에 0입니다. Target 720프레임, 전체 출력 3,130프레임을 디코딩·PTS 검사했습니다.</p>
<p>초기 실행의 Oracle 디코더 CUDA 오류를 별도 디코더 프로세스로 복구했습니다. 같은 Local의 재디코딩 MP4 hash가 원래 출력과 일치했습니다. 모든 정식 조건을 동일 방식으로 재실행했고 중단 시도는 보존했습니다.</p></details>
{''.join(cards)}
<footer><p><a download href="results.csv">수치 CSV</a> · <a download href="summary.json">평가 JSON</a> · <a download href="review.json">정성 기록 JSON</a> · <a download href="artifact_verification.json">입력·출력 감사 JSON</a> · <a download href="../../five_case_selection/execution_recovery.json">실행 오류 복구 기록</a></p></footer>
</body></html>'''
    (report / "index.html").write_text(body, encoding="utf-8")
    print(report / "index.html")


if __name__ == "__main__":
    main()
