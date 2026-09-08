"""Render reviewed repetition counts with actual inputs and synchronized results."""

import html
import json
import os
from pathlib import Path

from run_generation import ROOT


def main():
    report = ROOT / "reports/reference_repetition/seed42"
    summary = json.loads((report / "summary.json").read_text())
    audit = json.loads((report / "artifact_verification.json").read_text())
    review = json.loads((report / "review.json").read_text())
    if audit["status"] != "passed" or review["status"] != "assistant_sample_review_completed":
        raise ValueError("Complete artifact audit and sample-frame review first")
    example = ROOT / "data" / summary["example_id"]
    previews = ROOT / "reports/reference/inputs" / summary["example_id"]
    rel = lambda path: html.escape(os.path.relpath(path, report), quote=True)
    rows, individual = [], []
    for row in summary["rows"]:
        case = row["case"]
        record = next(r for r in audit["provenance"] if r["case"] == case)
        cfg = json.loads(Path(record["config_path"]).read_text())
        status = "기존 결과" if row["reused"] else "신규 생성"
        rows.append(f'<tr><th>{row["repeats"]}회 · {case}</th><td>{row["reference_tokens"]:,}</td>'
                    f'<td>{row["dino_gt_cosine"]:.4f}</td><td>{row["dino_gt_cosine_after_1s"]:.4f}</td>'
                    f'<td>{html.escape(review["outcomes"][case])}</td><td>{status}</td></tr>')
        individual.append(f'<article><h3>같은 이미지 latent ×{row["repeats"]}</h3>'
                          f'<video controls preload="none" poster="{case}_poster.jpg" src="{rel(Path(cfg["outputs"]["target"]["path"]))}"></video>'
                          f'<p>{html.escape(review["per_case"][case])}</p><details><summary>입력·실행 기록</summary><pre>'
                          + html.escape(json.dumps({"repeats": row["repeats"], "reference_tokens": row["reference_tokens"],
                                                    "reference_time_bounds": record["unique_temporal_bounds"],
                                                    "reference_tensor_sha256": record["reference_tensor_sha256"],
                                                    "config_path": record["config_path"], "config_sha256": record["config_sha256"],
                                                    "command": cfg["command"]}, ensure_ascii=False, indent=2))
                          + '</pre></details></article>')
    notes = ''.join(f'<li>{html.escape(note)}</li>' for note in review["interpretation"])
    prompt_cfg = json.loads(Path(audit["provenance"][0]["config_path"]).read_text())
    page = '''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>과거 이미지 반복수 1·2·4·10 비교</title><style>
*{box-sizing:border-box}body{margin:0;background:#101722;color:#e6edf6;font:17px/1.65 system-ui,sans-serif}
main{max-width:1640px;padding:28px;margin:auto}a{color:#91caff}nav{display:flex;gap:20px;flex-wrap:wrap}
h1{font-size:32px}h2{margin-top:0}h3{font-size:20px}section{padding:24px;margin:28px 0;border:1px solid #41536c;border-radius:12px;background:#172332}
.callout{padding:16px 22px;background:#213a50;border-left:4px solid #85c8fa}.inputs{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}
.individual{display:grid;grid-template-columns:repeat(2,1fr);gap:24px}video,img{max-width:100%}video{background:#090f18}
.inputs video,.inputs img,.individual video{width:100%;aspect-ratio:16/9;object-fit:contain}.comparison,.sheet{width:100%}
table{width:100%;border-collapse:collapse;margin:18px 0}td,th{padding:10px;border:1px solid #4c6079;text-align:left}th{background:#22364d}
.scroll{overflow:auto}details{margin:18px 0}summary{color:#b2dfff;cursor:pointer}code,pre{font-size:13px;overflow-wrap:anywhere}pre{white-space:pre-wrap}
button{background:#2b4d70;color:white;border:1px solid #80b4df;border-radius:6px;padding:8px 15px;margin:10px 8px 0 0;font:inherit;cursor:pointer}
.muted{color:#bac8d8}@media(max-width:850px){main{padding:14px}section{padding:15px}.inputs,.individual{grid-template-columns:1fr}h1{font-size:25px}}
</style></head><body><main>'''
    page += ('<nav><a href="../../../report.html">전체 실험</a><a href="../../../REFERENCE_REPETITION_RESULT.html">결과 해석</a>'
             '<a href="../../../REFERENCE_REPETITION_DIAGNOSIS.html">진단 설계</a><a href="../../../FEASIBILITY_STATUS.html">Stage 1 진행 상태</a>'
             '<a href="#comparison">동기화 비교</a><a href="#individual">개별 영상</a></nav>'
             '<h1>같은 과거 이미지의 반복수: 1·2·4·10회</h1>'
             '<p>파일럿 001 · seed 42 · 기존 1회·10회 재사용 + 신규 2회·4회 · 512×288 · 24 FPS · 8-step distilled</p>'
             f'<p class="callout">{html.escape(review["conclusion"])}</p>'
             '<section><h2>실제 입력과 주입 방식</h2><div class="inputs">'
             f'<article><h3>공통 Local · 공사 차량 2초</h3><video controls preload="none" poster="{rel(previews / "local_middle.png")}" src="{rel(example / "local_context.mp4")}"></video>'
             '<p>원본 156.825333–158.825333초. 이 다음 3초를 생성한다.</p></article>'
             f'<article><h3>모든 조건의 참조 · 동일한 이미지 한 장</h3><img src="{rel(previews / "oracle_middle.png")}" alt="실제로 입력한 과거 인터뷰 이미지">'
             '<p>원본 약 91.466378초. 독립 인코딩한 <b>같은 latent를 그대로 1·2·4·10회 복제</b>한다. 한 장은 144 token이다.</p></article>'
             f'<article><h3>GT Target · 평가용 3초</h3><video controls preload="none" poster="{rel(previews / "target_middle.png")}" src="{rel(example / "gt_target.mp4")}"></video>'
             '<p>원본 158.825333–161.825333초. 평가에서만 읽으며 생성 조건에는 포함하지 않는다.</p></article></div>'
             '<p>모든 복사본의 공간 좌표와 시간 구간은 같다. 참조 시간은 <b>[0, 1/24)초</b>에 겹치며, Local은 [97/24, 146/24)초, Target은 [146/24, 218/24)초다. 원본 시각은 같고 추가 참조의 반복수만 바꿨다.</p>'
             '<p>Local latent는 생성 배열 앞부분에서 고정한다. 참조 token은 배열 뒤에 추가되어 attention에 참여하고 clean 상태를 유지하며, 디코딩 전에 제거한다. 이미지 RGB를 반복해 VAE로 다시 인코딩한 것이 아니라 기존 latent를 복제했다.</p>'
             '<details><summary>공통 Prompt 보기</summary><p>' + html.escape(prompt_cfg["prompt"]) + '</p></details></section>'
             '<section><h2>반복수별 결과</h2><div class="scroll"><table><tr><th>반복수</th><th>참조 token</th><th>DINO 전체 3초</th>'
             '<th>DINO 1초 이후</th><th>샘플 프레임 관찰</th><th>실행</th></tr>' + ''.join(rows) + '</table></div><ul>' + notes + '</ul>'
             '<p class="muted">DINO는 전체 프레임 유사도이며 신원 정확도가 아니다. 1초 이후는 사전에 고정한 보조 구간이다. 한 사례·한 seed의 네 측정 지점으로 정확한 실패 임계점이나 단조성을 단정하지 않는다.</p></section>'
             '<section id="comparison"><h2>GT와 네 반복수의 동기화 비교</h2><p>왼쪽부터 GT / 1회 / 2회 / 4회 / 10회다.</p>'
             '<video id="comparison-video" class="comparison" controls preload="metadata" poster="comparison_poster.jpg" src="comparison.mp4"></video>'
             '<div><button onclick="const v=document.getElementById(\'comparison-video\');v.currentTime=2;v.play();">생성 구간부터 재생</button>'
             '<button onclick="document.getElementById(\'comparison-video\').playbackRate=0.5">0.5배속</button>'
             '<button onclick="document.getElementById(\'comparison-video\').playbackRate=1">1배속</button></div>'
             '<p>앞 2초는 동일한 원본 Local, 뒤 3초는 GT 또는 생성 Target이다. 한 파일에 합쳐 프레임을 동기화했다.</p>'
             '<details><summary>전체 구간의 여섯 시점 프레임</summary><a href="comparison_frames.jpg">원본 크기로 열기</a><img class="sheet" src="comparison_frames.jpg" alt="GT와 네 반복수의 여섯 시점"></details>'
             '<details><summary>초반 전환 프레임</summary><a href="transition_frames.jpg">원본 크기로 열기</a><img class="sheet" src="transition_frames.jpg" alt="GT와 네 반복수의 초반 여덟 시점"></details></section>'
             '<section id="individual"><h2>개별 Target 영상과 관찰</h2><div class="individual">' + ''.join(individual) + '</div></section>'
             '<section><h2>검증 기록</h2><p>공통 설정 38개, 실제 초기 및 7회 step noise, 참조 내용·좌표의 정확한 복제, 고정 latent를 확인했다. '
             '모든 8개 step 및 최종 고정 오차는 0이며 Target 288프레임의 전체 디코딩·24 FPS 시간표를 검사했다. 기존 1회·10회 결과와 점수의 일치도 확인했다.</p>'
             '<p>정성 기록은 assistant의 샘플 프레임 검토다. 사용자의 직접 영상 검토와 blind 평가는 별개다.</p>'
             '<p><a href="results.csv" download>조건별 CSV 다운로드</a> · <a href="../../reference_format/seed42/index.html">앞선 A–E 비교</a></p>'
             '<details><summary>실제 입력·원본 코드·결과 provenance</summary><pre>'
             + html.escape(json.dumps(audit, ensure_ascii=False, indent=2)) + '</pre></details></section></main></body></html>')
    (report / "index.html").write_text(page, encoding="utf-8")
    print(report / "index.html")


if __name__ == "__main__":
    main()
