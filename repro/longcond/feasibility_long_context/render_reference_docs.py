"""Render the local Markdown documentation as readable, offline UTF-8 HTML pages."""

import html
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from markdown_it import MarkdownIt


ROOT = Path(__file__).resolve().parent


def render_documents():
    documents = {p.name: p for p in ROOT.glob("*.md")}
    renderer = MarkdownIt("commonmark", {"html": False}).enable("table")
    pages = []
    for name, source in sorted(documents.items()):
        tokens = renderer.parse(source.read_text(encoding="utf-8"))
        title, toc = source.stem, []
        heading_index = 0
        for i, token in enumerate(tokens):
            if token.type == "heading_open":
                heading_index += 1
                anchor = f"section-{heading_index}"
                token.attrSet("id", anchor)
                label = tokens[i + 1].content
                if token.tag == "h1":
                    title = label
                elif token.tag == "h2":
                    toc.append(f'<li><a href="#{anchor}">{html.escape(label)}</a></li>')
            for child in token.children or []:
                if child.type != "link_open":
                    continue
                href = child.attrGet("href") or ""
                parts = urlsplit(href)
                if not parts.scheme and not parts.netloc and parts.path in documents:
                    child.attrSet("href", urlunsplit(parts._replace(path=str(Path(parts.path).with_suffix(".html")))))
        body = renderer.renderer.render(tokens, renderer.options, {})
        if name == 'LONG_INPUT_VS_SPARSE_PROTOCOL.md':
            body = '<blockquote>아래는 생성 전 동결한 사전 설계 원본입니다. 이후 25조건을 완료했고 정식 누적은 120회입니다. <a href="LONG_INPUT_RESULT.html">최종 결과와 실제 구현 차이 보기</a></blockquote>' + body
        # Tables and code keep their own horizontal scroll on narrow screens.
        body = body.replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")
        page = ('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width, initial-scale=1">'
                f'<title>{html.escape(title)}</title><style>'
                ':root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#141923;color:#e8edf5;'
                'font:17px/1.8 system-ui,"Noto Sans CJK KR",sans-serif}main{max-width:1180px;margin:auto;padding:24px}'
                'a{color:#91d5ff;text-underline-offset:3px}nav{display:flex;gap:22px;flex-wrap:wrap;padding:12px 0 20px;'
                'border-bottom:1px solid #455068}h1{font-size:30px;line-height:1.4}h2{font-size:24px;margin-top:42px;'
                'padding-top:14px;border-top:1px solid #455068}h3{font-size:20px}p{margin:18px 0}'
                'img,video{max-width:100%;height:auto}pre{overflow:auto;background:#0b101a;padding:20px;border-radius:8px;'
                'font-size:14px;line-height:1.6}code{font-family:ui-monospace,monospace;background:#222d40;padding:2px 5px;'
                'border-radius:3px}pre code{padding:0;background:none}.table-wrap{overflow-x:auto;margin:20px 0}'
                'table{border-collapse:collapse;width:100%}td,th{border:1px solid #526078;padding:12px;text-align:left;'
                'vertical-align:top}th{background:#222d40}td img{min-width:200px;max-width:440px;width:100%}'
                'blockquote{margin:20px 0;padding:4px 20px;border-left:4px solid #91d5ff;background:#1b2536}'
                'details{padding:12px 18px;background:#1b2536;margin:22px 0;border-radius:8px}summary{cursor:pointer}'
                'li{margin:8px 0}@media(max-width:650px){main{padding:16px}h1{font-size:25px}body{font-size:16px}}'
                '</style></head><body><main><nav><a href="report.html">← 입력·생성 결과</a>'
                '<a href="reports/long_input/index.html">최신 긴 입력·Sparse 비교</a>'
                '<a href="reports/five_case_prompt/seed42/index.html">이전 P0–P3 비교</a>'
                '<a href="reports/five_case_grid/seed42/index.html">이전 5개 2×2</a>'
                '<a href="REFERENCE_PROTOCOL.html">참조 주입 설명</a><a href="REFERENCE_RESULT.html">결과 해석</a>'
                f'<a href="{html.escape(name)}" download>MD 원본 저장</a></nav>'
                '<details><summary>문서 목차</summary><ul>' + ''.join(toc) + '</ul></details>'
                + body + '</main></body></html>')
        output = source.with_suffix(".html")
        output.write_text(page, encoding="utf-8")
        pages.append(output)
    return pages


if __name__ == "__main__":
    for path in render_documents():
        print(path)
