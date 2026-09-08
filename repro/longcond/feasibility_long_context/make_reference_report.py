"""Assemble reviewed reference diagnostics without rerunning generation or metrics."""

import html
import hashlib
import json
from pathlib import Path

from make_reference_inputs import build_input_previews
from render_reference_docs import render_documents


ROOT = Path(__file__).resolve().parent


def pilot_one_explanation(inputs):
    oracle = inputs["clips"]["oracle"]
    return (f'<section id="pilot-one-difference"><h2>파일럿 1: past와 target_guide는 무엇이 다른가?</h2>'
            '<p><b>둘 다 원본 90–93초의 같은 인터뷰를 참조한다.</b> 달라지는 것은 '
            '① 영상 전체인가 한 장인가, ② 모델에 어느 시점의 정보로 알려주는가다.</p>'
            '<p>공통 Local은 공사 차량 2초다. 이 뒤에 인터뷰 3초를 생성하라는 prompt와 noise도 동일하다.</p>'
            '<div class="method-grid"><article class="method past"><h3>past · 과거 영상 참조</h3>'
            f'<video controls preload="none" poster="{oracle["middle_png"]}" src="{oracle["file"]}"></video>'
            '<p><b>90–93초 영상 전체, 72프레임</b><br>VAE 인코딩 후 참조 1,440 token</p>'
            '<div class="flow"><span class="reference">참조 영상<br>과거 위치</span><span>→</span>'
            '<span>Local<br>공사 차량</span><span>→</span><span class="target">생성할<br>인터뷰</span></div>'
            '<p class="analogy">설명하면: “예전에 이런 인터뷰 장면이 있었다.”</p>'
            '<p>참조를 Local보다 앞선 시간에 두고, 생성기가 필요하면 그 외형을 이용하게 했다.</p>'
            '<p><b>관찰:</b> 이 사례의 Oracle 출력은 공사 장면을 계속 생성했다.</p></article>'
            '<article class="method guide"><h3>target_guide · 생성 시점의 이미지 guidance</h3>'
            f'<img src="{oracle["middle_png"]}" alt="target_guide에 실제 사용한 과거 인터뷰 이미지 한 장">'
            '<p><b>같은 영상의 프레임 36 한 장</b><br>VAE 인코딩 후 참조 144 token</p>'
            '<div class="flow"><span>Local<br>공사 차량</span><span>→</span>'
            '<span class="target">생성할 인터뷰<br><span class="inline-reference">↑ 과거 이미지에 이 시점 위치 부여</span></span></div>'
            '<p class="analogy">설명하면: “지금 생성할 장면은 이 외형을 참고해라.”</p>'
            '<p>과거 이미지에 생성 시작 시점의 위치를 부여했다. 참조 token을 별도로 추가한 것이며 '
            'target을 이 이미지로 직접 덮어쓰지는 않았다.</p>'
            '<p><b>관찰:</b> 이 사례의 Oracle 출력에서 보라색 셔츠와 인터뷰 배경이 재현됐다.</p></article></div>'
            '<p>위 따옴표 문장은 이해를 위한 설명이며 실제 prompt에 추가한 문장이 아니다. '
            '<b>target_guide도 과거 이미지이며, GT나 미래 프레임을 넣은 것이 아니다.</b></p>'
            '<details><summary>같은 부분과 다른 부분을 정확히 보기</summary>'
            '<div class="table-wrap"><table><tr><th>항목</th><th>past</th><th>target_guide</th></tr>'
            '<tr><td>참조 출처</td><td>원본 90–93초</td><td>같은 구간 중 원본 91.466378초의 한 장</td></tr>'
            '<tr><td>참조 시간 위치(모델 내부)</td><td>0–3.041667초: Local 이전</td>'
            '<td>6.083333–6.125초: 생성 시작 구간</td></tr>'
            '<tr><td>공통 Local / Target 위치</td><td colspan="2">Local 4.041667–6.083333초 / Target 6.083333–9.083333초</td></tr>'
            '<tr><td>참조 주입 경로</td><td colspan="2">독립 VAE → video token 배열 뒤에 추가 → 기존 self-attention</td></tr>'
            '<tr><td>생성 중 고정한 값</td><td colspan="2">Local·Reference latent 고정, Target latent denoise</td></tr>'
            '<tr><td>Local-only 출력</td><td colspan="2">두 실행 묶음에서 실제 latent와 영상까지 동일</td></tr></table></div></details>'
            '<p class="callout"><b>현재 말할 수 있는 것:</b> 생성 시점에 준 과거 이미지는 이 사례의 외형을 전달했다. '
            '위 두 결과만으로는 영상→이미지와 시간 위치가 함께 바뀌어 효과를 분리할 수 없었다. '
            '이후 완료한 <a href="reports/temporal_position/index.html">세 seed의 2×2 비교</a>에서는 '
            '영상의 시간 위치 효과가 크고, 이미지의 과거 위치에서도 외형이 전달됨을 확인했다.</p>'
            '<p>위 설명은 Oracle 기준이다. Random도 같은 주입 규칙을 사용하되 인터뷰 대신 산 풍경을 넣었다. '
            '<a href="REFERENCE_PROTOCOL.html">전체 입력·주입 설명 읽기</a></p></section>')


def main():
    inputs_by_example = build_input_previews()
    sections, rows = [], []
    for path in sorted((ROOT / "reports/reference").glob("*/*/summary.json")):
        summary = json.loads(path.read_text())
        review_path = path.with_name("review.json")
        if not review_path.exists():
            raise ValueError(f"Missing visual review: {review_path}")
        review = json.loads(review_path.read_text())
        if review["status"] != "reviewed" or summary["paired_controls"]["status"] != "passed":
            raise ValueError(f"Incomplete group: {path.parent}")
        old_status = summary["review_status"]
        summary["review_status"] = "Assistant sample-frame review recorded in review.json; not human or blind review"
        summary["review_sha256"] = hashlib.sha256(review_path.read_bytes()).hexdigest()
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
        detail_page = path.with_name("index.html")
        detail_page.write_text(detail_page.read_text().replace(html.escape(old_status), html.escape(summary["review_status"])))
        name = f'{summary["example_id"]} / {summary["layout"]} / seed {summary["seed"]}'
        report = path.parent.relative_to(ROOT)
        group = Path(summary["group_directory"]).relative_to(ROOT)
        scores = summary["scores"]
        cells = ''.join(f'<td>{scores[m]:.4f}</td>' for m in ["local", "random", "oracle"])
        rows.append(f'<tr><td><a href="{report}/index.html">{name}</a></td>{cells}'
                    f'<td>{summary["oracle_minus_local"]:+.4f}</td><td>{summary["oracle_minus_random"]:+.4f}</td></tr>')
        comments = ''.join(f'<li><b>{m.capitalize()}:</b> {html.escape(review[m])}</li>' for m in ["local", "random", "oracle"])
        inputs = inputs_by_example[summary["example_id"]]
        cards = []
        for kind in ["local", "random", "oracle"]:
            clip = inputs["clips"][kind]
            start, end = clip["requested_source_range"]
            if kind != "local" and summary["layout"] == "target_guide":
                media = f'<img src="{clip["middle_png"]}" alt="실제 주입한 {kind} 대표 이미지">'
                note = (f'실제 입력: 프레임 {clip["middle_frame_index"]} 한 장 · '
                        f'원본 {clip["middle_source_pts_seconds"]:.6f}초 · 144 token · 생성 위치 6.0833초')
            else:
                media = f'<video controls preload="none" poster="{clip["middle_png"]}" src="{clip["file"]}"></video>'
                note = ('모든 조건에 공통: 전체 48프레임 · 1,008 token 고정' if kind == "local" else
                        '해당 조건에만 입력: 전체 72프레임 · 1,440 token · 과거 위치 0초')
            cards.append(f'<div><h3>{kind.capitalize()} · 원본 {start:.3f}–{end:.3f}초</h3>{media}<p>{note}</p>'
                         f'<a href="{clip["file"]}">원본 입력 클립</a></div>')
        mechanism = ('과거 영상 전체를 독립 VAE 인코딩 → 생성 token 뒤에 추가 → 과거 시간 위치 부여'
                     if summary["layout"] == "past" else
                     '과거 대표 이미지 한 장을 독립 VAE 인코딩 → 생성 token 뒤에 추가 → 생성 시작 시간 위치 부여')
        sections.append(f'<section><h2>{name}</h2><p>{html.escape(review["conclusion"])}</p>'
                        f'<h3>무엇을 입력했나</h3><p>Local-only에는 Local만, Random에는 Local+Random, Oracle에는 Local+Oracle을 넣었다.</p>'
                        f'<div class="inputs">{"".join(cards)}</div><p><b>주입 방식:</b> {mechanism}. '
                        '참조는 clean latent로 고정하고 기존 video self-attention에서 읽게 했다. '
                        'GT를 넣거나 target token을 참조로 덮어쓰지 않았다.</p>'
                        f'<p><b>공통 prompt:</b> {html.escape(inputs["prompt"])}</p>'
                        '<p><a href="REFERENCE_PROTOCOL.html">원본 구간·입력 이미지·주입 구조 설명 읽기</a></p>'
                        '<h3>생성 결과</h3>'
                        f'<video controls preload="none" src="{group}/comparison.mp4"></video>'
                        f'<p>왼쪽부터 GT / Local / Random / Oracle. 처음 2초는 공통 local, 이후 3초는 target.</p>'
                        f'<img loading="lazy" src="{report}/comparison.jpg" alt="GT와 생성 프레임 비교">'
                        f'<ul>{comments}</ul><p>{html.escape(review["quality"])}</p>'
                        f'<p><a href="{report}/index.html">입력 참조·상세 지표</a> · '
                        f'<a href="{report}/summary.json">수치와 통제 검사</a> · '
                        f'<a href="{report}/review.json">외형 검토 기록</a></p></section>')
    if not rows:
        raise ValueError("No evaluated groups")
    page = ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>LTX reference feasibility diagnostics</title>'
            '<style>body{max-width:1400px;margin:32px auto;padding:0 20px;font:17px/1.65 sans-serif;background:#141923;color:#eee}'
            'a{color:#8fd4ff}video,img{max-width:100%;display:block}video{width:100%}table{border-collapse:collapse}'
            'td,th{border:1px solid #727987;padding:9px}section{border-top:1px solid #727987;margin-top:36px;padding-top:12px}'
            '.inputs,.method-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px}.inputs h3{font-size:16px}'
            '.method{padding:20px;background:#1b2536;border-radius:10px;border-top:4px solid #91d5ff}.guide{border-color:#b2df96}'
            '.method h3{margin-top:0}.flow{display:flex;align-items:center;gap:8px;font-size:15px;margin:24px 0}'
            '.flow>span:not(:nth-child(even)){padding:10px;border:1px solid #526078;border-radius:6px;text-align:center;flex:1}'
            '.reference{background:#214463}.target{background:#314a31}.inline-reference{font-size:13px;color:#d0efb6}'
            '.analogy{font-size:20px;color:#b9ddfa}.callout{padding:20px;background:#26354a;border-left:4px solid #91d5ff}'
            '.table-wrap{overflow:auto}details{margin:20px 0;padding:14px;background:#1b2536}summary{cursor:pointer}'
            '#pilot-one-difference{margin-bottom:40px}:root{color-scheme:dark}</style>'
            '<h1>LTX 참조 활용 진단</h1>'
            '<p class="callout"><b>최신 결과 · 원본 5개 / 참조 2×2:</b> <a href="reports/five_case_grid/seed42/index.html">이미지/영상 × Past/Target 전체 비교</a><br>'
            '기존 기준 10개 재사용 + 신규 15회. Target에서 로봇·학생·차량의 외관이 드러났고 관리자·보존 작업자는 Video/Past도 작동했다. '
            '과거 구도·동작·컷/자막 재현과 새 장면 제어는 구분해야 한다. <a href="FIVE_CASE_GRID_RESULT.html">결과·검증·해석</a></p>'
            '<p class="callout"><b>앞선 결과 · 원본 5개 / 신규 10회:</b> <a href="reports/five_cases/seed42/index.html">FineVideo Local / Oracle 비교</a><br>'
            '두 인물 사례는 과거 외관을 전달했지만 참조 구도 영향이 컸고, 로봇·학생·차량은 필요한 시점으로 전환하지 못했다. '
            '<a href="FIVE_CASE_RESULT.html">결과·검증·해석</a> · <a href="FIVE_CASE_PROTOCOL.html">사전 고정 설계</a></p>'
            '<p class="callout"><b>앞선 결과 · seed 42:</b> <a href="reports/reference_repetition/seed42/index.html">과거 이미지 반복수 1·2·4·10 비교</a><br>'
            '2·4회도 인터뷰 외형을 전달했다. 4회는 초반 전환이 더 오래 겹치지만 1초 이후 점수는 1·2회와 비슷하며, 10회는 공사 장면을 지속한다. '
            '<a href="REFERENCE_REPETITION_RESULT.html">실제 입력·검증·해석 읽기</a> · <a href="FEASIBILITY_STATUS.html">Stage 1 진행 상태</a></p>'
            '<p class="callout"><b>앞선 결과 · seed 42:</b> <a href="reports/reference_format/seed42/index.html">영상 past 실패 원인 진단 A–E</a><br>'
            '같은 이미지 latent를 같은 과거 시점에 10회 복제한 B부터 외형 전달이 실패했다. C·D도 공사 장면을 지속했다. '
            '<a href="REFERENCE_FORMAT_RESULT.html">실제 입력·검증·해석 읽기</a></p>'
            '<p class="callout"><b>앞선 결과:</b> <a href="reports/temporal_position/index.html">참조 형식 × 시간 위치 2×2 비교 · seed 42, 43, 44</a><br>'
            '영상 참조를 생성 위치로 옮기면 세 seed 모두 인터뷰 외형이 재현됐다. 이미지 한 장은 과거 위치에서도 작동하며 전환이 더 느렸다. '
            '<a href="TEMPORAL_POSITION_RESULT.html">결과 해석 읽기</a></p>'
            '<p>아래는 초기 Local/Random/Oracle 9회 결과다. 2026-09-06 · 512×288 · 24 FPS · 8-step distilled · seed 42</p>'
            '<p>기본 past 입력에서는 첫 사례의 외형 복원이 실패했고, 두 번째는 의상 무늬만 일부 반영됐다. '
            '생성 시점에 배치한 과거 대표 이미지는 첫 사례의 인터뷰 외형을 재현했다. '
            '안정적인 과거 시간 위치 참조 활용은 아직 확인되지 않았다.</p>'
            '<p>같은 원본의 두 편집된 인터뷰 사례이며 장면 전환을 prompt로 지시했다. '
            'target_guide는 과거 대표 이미지를 생성 시작 시점에 배치하는 별도 진단이다. '
            '과거 영상과 비교하면 시간 위치와 참조량이 함께 달라진다.</p>'
            '<p>모든 비교에서 prompt·local latent·target 초기 및 7회 step noise·공통 위치·생성 설정 일치를 검사했다. '
            'GT 영상은 평가 단계에서만 읽었다. 아래 DINOv2 값은 전체 프레임 유사도이며 인물 정확도가 아니다. '
            '외형 검토는 assistant가 표본 프레임으로 수행했다.</p>'
            '<p><a href="#pilot-one-difference">파일럿 1의 두 방식 비교</a> · '
            '<a href="REFERENCE_RESULT.html">해석과 다음 단계</a> · <a href="REFERENCE_PROTOCOL.html">실험 설계</a> · '
            '<a href="results.csv">결과 CSV</a></p>'
            + pilot_one_explanation(inputs_by_example["pilot_001_interview_return"])
            + '<h2>실험별 수치와 생성 결과</h2>'
            '<table><tr><th>사례 / 입력 형식</th><th>Local</th><th>Random</th><th>Oracle</th>'
            '<th>Oracle − Local</th><th>Oracle − Random</th></tr>' + ''.join(rows) + '</table>'
            + ''.join(sections) + '</html>')
    (ROOT / "report.html").write_text(page, encoding="utf-8")
    render_documents()
    print(ROOT / "report.html")


if __name__ == "__main__":
    main()
