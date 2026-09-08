"""Render reviewed A–E inputs, controls, metrics and synchronized video in Korean."""

import html
import json
import os
from pathlib import Path

from run_generation import ROOT


def main():
    report = ROOT / "reports/reference_format/seed42"
    summary = json.loads((report / "summary.json").read_text())
    audit = json.loads((report / "artifact_verification.json").read_text())
    review = json.loads((report / "review.json").read_text())
    if audit["status"] != "passed" or review["status"] != "assistant_sample_review_completed":
        raise ValueError("Audit and visual review must be complete")
    example = ROOT / "data" / summary["example_id"]
    previews = ROOT / "reports/reference/inputs" / summary["example_id"]
    rel = lambda path: html.escape(os.path.relpath(path, report), quote=True)
    labels = {"A": "이미지 1장 / 한 시점", "B": "이미지 latent ×10 / 한 시점", "C": "이미지 latent ×10 / 여러 시점",
              "D": "영상 latent / 한 시점", "E": "영상 latent / 여러 시점"}
    rows = []
    individual = []
    for row in summary["rows"]:
        case = row["case"]
        record = next(r for r in audit["provenance"] if r["case"] == case)
        cfg = json.loads(Path(record["config_path"]).read_text())
        time_range = "[0, 1/24)초에 모두 겹침" if case in ("A", "B", "D") else "[0, 73/24)초의 10칸에 분산"
        status = "기존 결과" if row["reused"] else "신규 생성"
        rows.append(f'<tr><th>{case} · {labels[case]}</th><td>{row["reference_tokens"]:,}</td><td>{time_range}</td>'
                    f'<td>{row["dino_gt_cosine"]:.4f}</td><td>{row["dino_gt_cosine_after_1s"]:.4f}</td><td>{status}</td></tr>')
        individual.append(f'<article><h3>{case} · {labels[case]}</h3><video controls preload="metadata" src="{rel(Path(cfg["outputs"]["target"]["path"]))}"></video>'
                          f'<p>{html.escape(review["per_case"][case])}</p><details><summary>입력·설정 기록</summary>'
                          f'<p>설정 파일: <code>{html.escape(os.path.relpath(record["config_path"], ROOT))}</code></p>'
                          '<pre>' + html.escape(json.dumps({"input": cfg.get("reference_spec", labels[case]),
                                                            "reference_time_bounds": record["unique_temporal_bounds"],
                                                            "reference_tensor_sha256": record["reference_tensor_sha256"],
                                                            "config_sha256": record["config_sha256"]}, ensure_ascii=False, indent=2))
                          + '</pre></details></article>')
    notes = ''.join(f'<li>{html.escape(note)}</li>' for note in review["interpretation"])
    prompt_cfg = json.loads(Path(audit["provenance"][0]["config_path"]).read_text())
    page = '''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>영상 past 실패 원인 진단 · A–E</title><style>
*{box-sizing:border-box}body{margin:0;background:#101722;color:#e6edf6;font:17px/1.65 system-ui,sans-serif}
main{max-width:1640px;padding:28px;margin:auto}a{color:#91caff}nav{display:flex;gap:20px;flex-wrap:wrap}
h1{font-size:32px}h2{margin-top:0}h3{font-size:20px}section{padding:24px;margin:28px 0;border:1px solid #41536c;border-radius:12px;background:#172332}
.callout{padding:16px 22px;background:#213a50;border-left:4px solid #85c8fa}.inputs,.individual{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}
video,img{max-width:100%}video{background:#090f18}.inputs video,.inputs img,.individual video{width:100%;aspect-ratio:16/9;object-fit:contain}
.comparison,.sheet{width:100%}table{width:100%;border-collapse:collapse;margin:18px 0}td,th{padding:10px;border:1px solid #4c6079;text-align:left}th{background:#22364d}
.scroll{overflow:auto}details{margin:18px 0}summary{color:#b2dfff;cursor:pointer}code,pre{font-size:13px;overflow-wrap:anywhere}pre{white-space:pre-wrap}
button{background:#2b4d70;color:white;border:1px solid #80b4df;border-radius:6px;padding:8px 15px;margin:10px 8px 0 0;font:inherit;cursor:pointer}
.muted{color:#bac8d8}@media(max-width:850px){main{padding:14px}section{padding:15px}.inputs,.individual{grid-template-columns:1fr}h1{font-size:25px}}
</style></head><body><main>'''
    page += ('<nav><a href="../../../report.html">전체 실험</a><a href="../../../REFERENCE_FORMAT_RESULT.html">결과 해석</a>'
             '<a href="../../../REFERENCE_FORMAT_DIAGNOSIS.html">진단 설계</a><a href="#comparison">동기화 비교</a><a href="#individual">개별 영상</a></nav>'
             '<h1>영상 past 실패 원인 진단: token 반복 × 시간 배치</h1>'
             '<p>파일럿 001 · seed 42 하나 · 기존 A·E 재사용 + 신규 B·C·D 3회 · 512×288 · 24 FPS · 8-step distilled</p>'
             f'<p class="callout">{html.escape(review["conclusion"])}</p>'
             '<section><h2>실제 입력과 조작</h2><div class="inputs">'
             f'<article><h3>공통 Local · 공사 차량 2초</h3><video controls preload="none" poster="{rel(previews / "local_middle.png")}" src="{rel(example / "local_context.mp4")}"></video>'
             '<p>원본 156.825333–158.825333초. 다음 3초의 인터뷰를 생성한다.</p></article>'
             f'<article><h3>A·B·C · 동일한 과거 이미지</h3><img src="{rel(previews / "oracle_middle.png")}" alt="실제 사용한 과거 인터뷰 이미지">'
             '<p>원본 약 91.466378초의 한 장. A는 독립 인코딩한 latent 1개, B·C는 <b>그 latent를 그대로 10회 복제</b>했다.</p></article>'
             f'<article><h3>D·E · 동일한 과거 영상</h3><video controls preload="none" poster="{rel(previews / "oracle_middle.png")}" src="{rel(example / "oracle_context.mp4")}"></video>'
             '<p>원본 90–93초 영상. 기존 VAE latent의 내용과 순서를 그대로 쓴다. D에서 시간 좌표만 한곳에 모았다.</p></article></div>'
             '<p><b>B·C·D·E의 참조량은 모두 1,440 token이다.</b> B↔C, D↔E는 각자 같은 latent에서 시간 배치만 달라진다. B↔D와 C↔E는 각자 같은 token 수·시간 좌표에서 latent 내용/표현이 달라진다.</p>'
             '<p>한 시점 조건은 참조 시간의 시작·끝을 모두 [0, 1/24)초로 맞춘다. 여러 시점 조건은 기존 영상 past의 [0, 73/24)초 grid를 그대로 쓴다. '
             '공통 Local은 [97/24, 146/24)초, Target은 [146/24, 218/24)초다. 모든 참조는 모델상 과거에 있다.</p>'
             '<p>참조 token은 뒤에 추가되어 기존 attention에 참여하며 생성 중 clean 상태로 고정한다. 추가 참조는 디코딩 전에 제거한다. 같은 시점의 중복 token은 원인 분리용 인위적 입력이다.</p>'
             '<details><summary>동일 Prompt 보기</summary><p>' + html.escape(prompt_cfg["prompt"]) + '</p></details></section>'
             '<section><h2>보조 점수와 관찰</h2><div class="scroll"><table><tr><th>조건</th><th>Token</th><th>참조 시간 배치</th>'
             '<th>DINO 전체 3초</th><th>DINO 1초 이후</th><th>실행</th></tr>' + ''.join(rows) + '</table></div><ul>' + notes + '</ul>'
             '<p class="muted">DINO는 전체 프레임 유사도이며 신원 정확도 점수가 아니다. 1초 이후는 전환 지연의 영향을 보기 위한 고정 보조 구간이며 자동으로 전환 시점을 검출한 값이 아니다. 한 사례·한 seed의 진단이다.</p></section>'
             '<section id="comparison"><h2>GT와 A–E 동기화 비교</h2><p>왼쪽 열: 위 GT / 아래 A. 오른쪽 2×2: 위 B·C / 아래 D·E. 오른쪽의 왼쪽 열은 한 시점, 오른쪽 열은 여러 시점이다.</p>'
             '<video id="comparison-video" class="comparison" controls preload="metadata" poster="comparison_poster.jpg" src="comparison.mp4"></video>'
             '<div><button onclick="const v=document.getElementById(\'comparison-video\');v.currentTime=2;v.play();">생성 구간부터 재생</button>'
             '<button onclick="document.getElementById(\'comparison-video\').playbackRate=0.5">0.5배속</button>'
             '<button onclick="document.getElementById(\'comparison-video\').playbackRate=1">1배속</button></div>'
             '<p>앞 2초는 동일한 원본 Local, 뒤 3초는 GT 또는 생성 Target이다. 한 파일에 합쳐 프레임을 동기화했다.</p>'
             '<details><summary>전체 구간의 여섯 시점 프레임 보기</summary><a href="comparison_frames.jpg">원본 크기로 열기</a><img class="sheet" src="comparison_frames.jpg" alt="GT와 A–E의 여섯 시점"></details>'
             '<details><summary>초반 전환을 더 촘촘하게 보기</summary><a href="transition_frames.jpg">원본 크기로 열기</a><img class="sheet" src="transition_frames.jpg" alt="GT와 A–E의 초기 전환"></details></section>'
             '<section id="individual"><h2>개별 Target 영상과 정성 기록</h2><div class="individual">' + ''.join(individual) + '</div></section>'
             '<section><h2>검증과 기록</h2><p>모든 조건에서 공통 모델·Prompt·Local·base AV 좌표·실제 초기 및 7회 step noise가 일치한다. '
             '각 8개 step과 최종 상태에서 Local·Reference 고정 오차는 0이다. 실제 참조 복제·시간 좌표·최종 latent, Target 360프레임과 24 FPS 시간표를 검사했다.</p>'
             '<p>정성 기록은 assistant의 샘플 프레임 검토다. 사용자의 직접 영상 검토와 blind 평가를 대신하지 않는다.</p>'
             '<p><a href="results.csv" download>조건별 CSV 다운로드</a></p><details><summary>실제 입력·원본 코드·결과 provenance</summary><pre>'
             + html.escape(json.dumps(audit, ensure_ascii=False, indent=2)) + '</pre></details></section></main></body></html>')
    (report / "index.html").write_text(page, encoding="utf-8")
    print(report / "index.html")


if __name__ == "__main__":
    main()
