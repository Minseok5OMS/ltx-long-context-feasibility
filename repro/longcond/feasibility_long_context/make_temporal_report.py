"""Render the reviewed temporal-position experiment with inputs and synchronized playback."""

import html
import json
import os
from pathlib import Path

from run_generation import ROOT


def main():
    report = ROOT / "reports/temporal_position"
    summary = json.loads((report / "summary.json").read_text())
    audit = json.loads((report / "artifact_verification.json").read_text())
    review = json.loads((report / "review.json").read_text())
    if audit["status"] != "passed" or review["status"] != "assistant_sample_review_completed":
        raise ValueError("Audit and visual review must be complete")
    rel = lambda p: html.escape(os.path.relpath(p, report), quote=True)
    example = ROOT / "data" / summary["example_id"]
    preview = ROOT / "reports/reference/inputs" / summary["example_id"] / "oracle_middle.png"
    sections = []
    for seed in summary["seeds"]:
        score_rows = []
        for kind, label in [("image", "이미지 한 장 · 144 token"), ("video", "영상 3초 · 1,440 token")]:
            past = summary["aggregate_scores"][f"{kind}_past"]["values_by_seed"][str(seed)]
            target = summary["aggregate_scores"][f"{kind}_target"]["values_by_seed"][str(seed)]
            score_rows.append(f"<tr><th>{label}</th><td>{past:.4f}</td><td>{target:.4f}</td><td>{target-past:+.4f}</td></tr>")
        notes = ''.join(f'<li><b>{html.escape(k)}:</b> {html.escape(v)}</li>' for k, v in review["per_seed"][str(seed)].items())
        provenance = []
        for row in audit["provenance"]:
            if row["seed"] == seed:
                cfg = json.loads(Path(row["config_path"]).read_text())
                source = "기존 결과 재사용" if row["reused"] else "신규 생성"
                provenance.append(f'<tr><td>{row["cell"]}</td><td>{source}</td><td><a href="{rel(Path(cfg["outputs"]["target"]["path"]))}">개별 Target 영상</a></td>'
                                  f'<td><code>{html.escape(os.path.relpath(row["config_path"], ROOT))}</code></td></tr>')
        sections.append(f'<section id="seed-{seed}"><h2>Seed {seed}</h2>'
                        '<p>위 행: 이미지 한 장 · 아래 행: 영상 3초 / 왼쪽: 과거 위치 · 오른쪽: 생성 위치</p>'
                        f'<video id="video-{seed}" class="comparison" controls preload="metadata" src="seed{seed}_comparison.mp4"></video>'
                        f'<div class="buttons"><button onclick="playTarget({seed})">생성 구간부터 재생</button>'
                        f'<button onclick="setSpeed({seed},0.5)">0.5배속</button><button onclick="setSpeed({seed},1)">1배속</button></div>'
                        '<p>앞 2초는 동일한 원본 Local, 뒤 3초는 각 조건에서 생성한 Target이다. 한 영상 안에 합쳐 프레임을 동기화했다.</p>'
                        '<table><tr><th>참조 형식</th><th>과거 위치</th><th>생성 위치</th><th>위치 이동 차이</th></tr>'
                        + ''.join(score_rows) + '</table><ul>' + notes + '</ul>'
                        f'<details><summary>GT와 생성 결과의 6개 시점 프레임 보기</summary><a href="seed{seed}_frames.jpg">이미지 원본 크기로 열기</a>'
                        f'<img class="sheet" src="seed{seed}_frames.jpg" alt="GT와 네 조건의 생성 프레임"></details>'
                        '<details><summary>개별 영상과 실행 설정 위치</summary><div class="scroll"><table><tr><th>조건</th><th>실행</th><th>영상</th><th>설정 파일</th></tr>'
                        + ''.join(provenance) + '</table></div></details></section>')
    means = summary["aggregate_scores"]
    mean_rows = ''.join(f'<tr><th>{label}</th><td>{means[kind+"_past"]["mean"]:.4f}</td><td>{means[kind+"_target"]["mean"]:.4f}</td>'
                        f'<td>{summary["mean_effects"][kind+"_target_minus_past"]:+.4f}</td></tr>'
                        for kind, label in [("image", "이미지 한 장"), ("video", "영상 3초")])
    page = '''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>참조 시간 위치 2×2 비교</title><style>
*{box-sizing:border-box}body{margin:0;background:#101722;color:#e6ecf4;font:17px/1.65 system-ui,sans-serif}
main{max-width:1320px;margin:auto;padding:28px}a{color:#86c5ff}h1{font-size:32px}h2{margin-top:0}h3{font-size:20px}
section{margin:28px 0;padding:24px;border:1px solid #35455b;border-radius:12px;background:#172231}
nav{display:flex;gap:20px;flex-wrap:wrap}.inputs{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}
.inputs video,.inputs img{width:100%;aspect-ratio:16/9;object-fit:contain;background:#0b111b}.gt{width:512px;max-width:100%}
.comparison{width:1024px;max-width:100%;display:block;margin:auto}video{background:#0b111b}table{border-collapse:collapse;width:100%;margin:18px 0}
td,th{border:1px solid #475b75;padding:10px 14px;text-align:left}th{background:#223247}.callout{border-left:4px solid #7bc0fb;padding:16px 22px;background:#1e344a}
.buttons{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}button{font:inherit;background:#25486a;color:white;border:1px solid #7aa8d0;padding:7px 15px;border-radius:6px;cursor:pointer}
details{margin-top:18px}summary{cursor:pointer;color:#a8d7ff}.sheet{width:100%;margin-top:12px}.scroll{overflow:auto}code{font-size:13px;overflow-wrap:anywhere}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}.muted{color:#bdc9d8}@media(max-width:800px){main{padding:14px}section{padding:15px}.inputs{grid-template-columns:1fr}td,th{padding:6px}h1{font-size:26px}}
</style></head><body><main>'''
    page += ('<nav><a href="../../report.html">전체 실험</a><a href="../../TEMPORAL_POSITION_RESULT.html">결과 해석</a>'
             '<a href="../../TEMPORAL_POSITION_ABLATION.html">실험 설계</a>'
             + ''.join(f'<a href="#seed-{seed}">Seed {seed}</a>' for seed in summary["seeds"]) + '</nav>'
             '<h1>참조 형식 × 시간 위치: 2×2 비교</h1>'
             '<p>파일럿 001 · 동일한 과거 인터뷰 참조 · seed 42, 43, 44 · 기존 2회 재사용 + 신규 10회</p>'
             f'<p class="callout">{html.escape(review["conclusion"])}</p>'
             '<section><h2>실제로 넣은 입력</h2><div class="inputs">'
             f'<article><h3>공통 Local: 공사 차량 2초</h3><video controls preload="none" poster="{rel(preview.with_name("local_middle.png"))}" src="{rel(example / "local_context.mp4")}"></video>'
             '<p>원본 156.825333–158.825333초. VAE latent 앞 7칸을 고정하고 다음 3초를 생성한다.</p></article>'
             f'<article><h3>이미지 행의 참조</h3><img src="{rel(preview)}" alt="실제 사용한 과거 대표 이미지">'
             '<p>과거 인터뷰의 클립 frame 36 한 장. 원본 약 91.466378초, 독립 VAE 인코딩, 144 token.</p></article>'
             f'<article><h3>영상 행의 참조</h3><video controls preload="none" poster="{rel(preview)}" src="{rel(example / "oracle_context.mp4")}"></video>'
             '<p>원본 90–93초, 72프레임. 첫 프레임 복제 후 독립 VAE 인코딩, 1,440 token.</p></article></div>'
             '<p><b>각 행에서는 위와 같은 latent를 그대로 사용하고, 추가 참조 token의 시간 좌표만 0 → 6.083333초로 이동했다.</b> 공간 좌표·token 수·Local·Prompt·각 seed의 초기/step noise는 고정했다.</p>'
             '<p>참조는 token 배열 뒤에 추가되어 attention에 참여한다. Local·Reference는 생성 중 고정하며, 추가 Reference는 디코딩 전에 제거한다. 일반 distilled 모델을 사용했다.</p>'
             '<table><tr><th>참조</th><th>과거 위치</th><th>생성 위치</th></tr><tr><td>이미지 시간 구간</td><td>[0, 0.041667)초</td><td>[6.083333, 6.125)초</td></tr>'
             '<tr><td>영상 시간 구간</td><td>[0, 3.041667)초</td><td>[6.083333, 9.125)초</td></tr></table>'
             '<p>공통 Local: [4.041667, 6.083333)초 / Target: [6.083333, 9.083333)초. 영상 참조의 끝은 padding 때문에 Target보다 1/24초 길다. 원본의 실제 시간과 모델에 부여한 시간 좌표를 구분해야 한다.</p>'
             '<details><summary>모든 조건에 사용한 동일 Prompt</summary><p>' + html.escape(config_prompt(audit)) + '</p></details></section>'
             '<section><h2>GT와 보조 점수</h2>'
             f'<video class="gt" controls preload="none" poster="{rel(preview.with_name("target_middle.png"))}" src="{rel(example / "gt_target.mp4")}"></video>'
             '<p>GT는 평가에만 사용했다. 아래는 12개 시점의 DINOv2 전체 프레임 유사도를 세 seed에 걸쳐 평균한 값이다.</p>'
             '<table><tr><th>참조 형식</th><th>과거 위치</th><th>생성 위치</th><th>위치 이동 차이</th></tr>' + mean_rows + '</table>'
             '<p class="muted">하나의 원본 사례에서 seed만 반복했다. 신원 정확도·장거리 메모리 성능·통계적 일반화를 나타내는 점수가 아니다.</p></section>'
             + ''.join(sections)
             + '<section><h2>검증과 기록</h2><p>12개 조건의 입력·모델·공통 좌표·seed별 실제 초기 및 7회 step noise, 8개 step과 최종 고정 latent를 검사했다. 두 기존 결과의 원본 코드와 설정을 유지했다. 모든 참조 쌍에서 시간 평행 이동 외의 좌표 차이는 없었다.</p>'
             '<p>정성 기록은 assistant의 샘플 프레임 검토다. 사용자의 영상 검토와 blind 평가를 대신하지 않는다.</p>'
             '<p><a href="results.csv" download>조건별 CSV 다운로드</a> · <a href="paired_effects.csv" download>seed별 위치 효과 CSV 다운로드</a></p>'
             '<details><summary>검증 provenance 보기</summary><pre>' + html.escape(json.dumps(audit, ensure_ascii=False, indent=2)) + '</pre></details></section>'
             '<script>function playTarget(seed){const v=document.getElementById("video-"+seed);v.currentTime=2;v.play();}'
             'function setSpeed(seed,speed){document.getElementById("video-"+seed).playbackRate=speed;}</script></main></body></html>')
    (report / "index.html").write_text(page, encoding="utf-8")
    print(report / "index.html")


def config_prompt(audit):
    return json.loads(Path(audit["provenance"][0]["config_path"]).read_text())["prompt"]


if __name__ == "__main__":
    main()
