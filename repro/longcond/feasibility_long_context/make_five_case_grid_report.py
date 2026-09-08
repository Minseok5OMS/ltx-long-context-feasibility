"""Render five image/video x past/target comparisons with actual source inputs."""

import html
import json
import os
from PIL import Image

from render_reference_docs import render_documents
from run_generation import ROOT, read_rgb


def main():
    report = ROOT / "reports/five_case_grid/seed42"
    summary = json.loads((report / "summary.json").read_text())
    review = json.loads((report / "review.json").read_text())
    cohort = json.loads((ROOT / "configs/five_case_examples.json").read_text())
    audit = json.loads((report / "artifact_verification.json").read_text())
    render_documents()
    esc = html.escape
    cells = ["image_past", "image_target", "video_past", "video_target"]
    labels = {"image_past": "Image / Past", "image_target": "Image / Target", "video_past": "Video / Past", "video_target": "Video / Target"}
    rows, articles = [], []
    def link(path):
        return esc(os.path.relpath(path, report))
    for index, example in enumerate(cohort["examples"], 1):
        name = example["example_id"]
        data = ROOT / "data" / name
        cache = ROOT / "outputs" / name / "five_case_inputs_512x288"
        video_cache = ROOT / "outputs" / name / "five_case_video_inputs_512x288"
        meta = json.loads((data / "metadata.json").read_text())
        Image.fromarray(read_rgb(data / "oracle_context.mp4", 512, 288)[0]).save(report / name / "video_input_poster.jpg", quality=94)
        by_cell = {r["mode"]: r for r in summary["rows"] if r["example_id"] == name}
        note = review["cases"][name]
        rows.append(f'<tr><td><a href="#{name}">{index}. {esc(example["title_ko"])}</a></td>'
                    + ''.join(f'<td>{by_cell[cell]["dino_gt_cosine"]:.4f}</td>' for cell in cells)
                    + f'<td>{esc(note["verdict_ko"])}</td></tr>')
        cards = []
        for cell in cells:
            c = note["cells"][cell]
            tags = '기존 재사용' if cell == "image_past" else '신규 생성'
            cards.append(f'<section><h3>{labels[cell]} <small>· {tags}</small></h3>'
                         f'<img src="{name}/{cell}_poster.jpg" loading="lazy" alt="{labels[cell]} Target 1.33초">'
                         f'<p>{esc(c["observation_ko"])}</p><p class="muted">{esc(c["motion_copy_ko"])}</p></section>')
        metric_rows = ''.join('<tr><td>'+labels[cell]+'</td>'
                              + f'<td>{by_cell[cell]["dino_gt_cosine"]:.4f}</td><td>{by_cell[cell]["dino_gt_cosine_after_1s"]:.4f}</td>'
                              + f'<td>{by_cell[cell]["dino_gt_cosine"]-by_cell["local"]["dino_gt_cosine"]:+.4f}</td></tr>' for cell in cells)
        effect = summary["contrasts"][name]["dino_gt_cosine"]
        articles.append(f'''
<article id="{name}"><h2>{index}. {esc(example["title_ko"])}</h2>
<p class="callout">{esc(note["summary_ko"])}</p>
<p>평가할 속성: {' · '.join(esc(a) for a in example["review"]["evaluation_attributes_do_not_condition_on"])}</p>
<div class="inputs">
 <figure><figcaption>공통 Local · 2초</figcaption><video controls preload="none" poster="../../five_cases/seed42/{name}/input_local_poster.jpg" src="{link(cache/'local_context.mp4')}"></video><p class="muted">원본 {meta["local_start"]:.6f}–{meta["local_end"]:.6f}초</p></figure>
 <figure><figcaption>Image 두 조건의 실제 참조</figcaption><img loading="eager" src="{link(cache/'oracle_image.png')}" alt="같은 과거 이미지 한 장"><p class="muted">원본 {meta["oracle_image_source_seconds"]:.6f}초 · 144 token</p></figure>
 <figure><figcaption>Video 두 조건의 실제 참조</figcaption><video controls preload="none" poster="{name}/video_input_poster.jpg" src="{link(video_cache/'oracle_padded_input.mp4')}"></video><p class="muted">원본 {meta["oracle_start"]:.3f}–{meta["oracle_end"]:.3f}초 · 1,440 token<br>첫 장 복제를 포함한 실제 전처리 영상</p></figure>
</div>
<p><b>네 조건의 공통 prompt:</b> <span lang="en">{esc(example["prompt"])}</span></p>
<h3>동기화 비교 · 첫 2초 Local, 이후 3초 Target</h3>
<p>맨 위: GT / Local-only. 아래 2×2: 행은 Image / Video, 열은 Past / Target 위치입니다. 모든 참조의 RGB는 실제 과거에서 가져왔습니다.</p>
<video class="comparison" controls playsinline preload="metadata" poster="{name}/comparison_poster.jpg" src="{name}/comparison.mp4"></video>
<p><b>기존 Local 기준:</b> {esc(note["local_observation_ko"])} · DINO {by_cell["local"]["dino_gt_cosine"]:.4f}</p>
<div class="grid">{''.join(cards)}</div>
<details><summary>수치와 시간 위치의 상호작용</summary><div class="scroll"><table><tr><th>조건</th><th>전체 DINO</th><th>1초 이후 DINO</th><th>Local 대비</th></tr>{metric_rows}</table></div>
<p>Target−Past: Image {effect["image_target_minus_past"]:+.4f}, Video {effect["video_target_minus_past"]:+.4f}. 두 위치 효과 차이 {effect["interaction_video_effect_minus_image_effect"]:+.4f}. 한 seed의 보조 유사도 차이이며 통계적 유의성이 아닙니다.</p></details>
<details><summary>시간별 전체 6조건 프레임 확대</summary><a href="{name}/comparison_frames.jpg"><img loading="lazy" src="{name}/comparison_frames.jpg" alt="GT, Local, Image Past/Target, Video Past/Target"></a></details>
<details><summary>원본과 검증 기록</summary><p>GT 원본 {meta["target_start"]:.6f}–{meta["target_end"]:.6f}초는 평가용이며 생성에 넣지 않았습니다.</p>
<p><a href="{link(data/'gt_target.mp4')}">평가용 GT 영상</a> · <a download href="{link(data/'metadata.json')}">원본 시간·속성 기록 다운로드</a> · <a download href="{link(video_cache/'inputs.json')}">영상 인코딩 기록 다운로드</a></p>
<p>{esc(note["limitation_ko"])}</p></details><a href="#top">요약 표로</a></article>''')
    body = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>FineVideo 5개 · 참조 2×2 비교</title><style>
:root{{color-scheme:dark}}*{{box-sizing:border-box}}body{{max-width:1220px;margin:auto;padding:28px 24px 70px;background:#10151e;color:#e6ecf4;font:16px/1.7 system-ui,sans-serif}}a{{color:#8bc4ff}}h1{{font-size:29px}}h2{{font-size:25px}}h3{{font-size:18px}}nav{{display:flex;flex-wrap:wrap;gap:16px}}.callout{{background:#1e2d42;border-left:4px solid #85bafd;padding:16px;border-radius:6px}}table{{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}}th,td{{padding:10px;border-bottom:1px solid #3a4658;text-align:left}}.scroll{{overflow-x:auto}}article{{border-top:1px solid #405065;margin-top:38px;padding-top:20px;scroll-margin-top:16px}}.inputs{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}}figure{{margin:0}}figcaption{{font-weight:650}}img,video{{width:100%;height:auto;background:#080c12;border-radius:6px}}.inputs img,.inputs video{{aspect-ratio:16/9;object-fit:contain}}.comparison{{display:block;max-width:860px;margin:auto}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:22px}}.grid section{{background:#18212e;padding:14px;border-radius:8px}}.grid img{{max-width:420px}}.muted,small{{color:#aebdd1}}details{{background:#18212e;margin:16px 0;padding:13px 16px;border-radius:8px}}summary{{cursor:pointer;color:#aacff7}}@media(max-width:760px){{body{{padding:18px 12px}}.inputs{{grid-template-columns:1fr}}.grid{{gap:10px}}h1{{font-size:24px}}}}
</style></head><body id="top"><nav><a href="../../../report.html">전체 실험</a><a href="../../../FIVE_CASE_GRID_RESULT.html">결과·해석</a><a href="../../../FIVE_CASE_GRID_PROTOCOL.html">사전 설계</a><a href="../../five_cases/seed42/index.html">이전 5개 Local/Oracle</a></nav>
<h1>5개 사례 · 이미지/영상 × 과거/생성 위치</h1><p class="callout">{esc(review["overall_summary_ko"])}</p>
<p>seed 42 · Oracle 20조건 = 기존 5 + 신규 15. Local 기준 5개도 재사용했습니다. 사례·prompt·Local·noise·모델 설정을 유지했습니다. Attention 측정과 prompt 변경은 이 비교 이후 검토할 항목입니다.</p>
<div class="scroll"><table><thead><tr><th>사례</th><th>Image / Past</th><th>Image / Target</th><th>Video / Past</th><th>Video / Target</th><th>정성 관찰</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<p class="muted">전체 Target DINO 보조 유사도입니다. 외관 정확도나 일반화 성공률이 아닙니다. 정성 평가는 assistant의 샘플 프레임 검토이며 사람의 검수 완료가 아닙니다.</p>
<details><summary>2×2에서 바꾼 것과 실제 주입 방식</summary><p>Image 144 token / Video 1,440 token. 같은 형식의 두 위치에서는 content·token 수·공간 좌표를 고정하고 추가 참조의 시간 좌표만 +146/24초 이동했습니다. Base AV 좌표와 실제 초기 및 7회 step noise는 모두 같습니다. Local은 denoising 중 1,008 token의 고정 조건입니다. 참조는 self-attention에 참여하고 decoder 전에 제거됩니다.</p>
<p>Image/Past [0,1/24), Image/Target [146/24,147/24), Video/Past [0,73/24), Video/Target [146/24,219/24). Local [97/24,146/24), Target [146/24,218/24). Target 좌표에 둬도 GT를 넣는 것은 아닙니다.</p>
<p>재사용한 10개 출력의 감사와 DINO 재평가가 일치했고, 신규 15개는 실제 내용·좌표·noise·고정 latent·코드·decoder를 검증했습니다. 공통 설정 {len(audit["common_fields_checked_against_reused_image_past"])}개, 고정 오차 0, Target 1,800프레임/전체 출력 7,825프레임을 디코딩·PTS 검사했습니다.</p></details>
{''.join(articles)}<footer><p><a download href="results.csv">25조건 수치 CSV</a> · <a download href="summary.json">평가·상호작용 JSON</a> · <a download href="review.json">정성 기록</a> · <a download href="artifact_verification.json">실제 입력·출력 감사</a></p></footer></body></html>'''
    (report / "index.html").write_text(body, encoding="utf-8")
    print(report / "index.html")


if __name__ == "__main__":
    main()
