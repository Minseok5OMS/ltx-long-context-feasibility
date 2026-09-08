"""Check generated report links, UTF-8 pages and optional live HTTP delivery."""

import argparse
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen

from run_generation import ROOT, sha256, write_json


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.ids = [], set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        for key in ("href", "src", "poster"):
            if key in attrs:
                self.links.append((attrs[key], "download" in attrs))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--http", action="store_true")
    args = parser.parse_args()
    report = ROOT / "reports/five_cases/seed42"
    pages = sorted(set(ROOT.glob("*.html")) | {report / "index.html"})
    local_targets, count, raw_md = set(), 0, []
    for page in pages:
        source = page.read_text(encoding="utf-8")
        assert '<meta charset="utf-8"' in source.lower(), page
        links = Links()
        links.feed(source)
        for href, download in links.links:
            parts = urlsplit(href)
            if parts.scheme or parts.netloc:
                continue
            target = (page.parent / unquote(parts.path)).resolve() if parts.path else page
            assert target.exists(), (page.name, href)
            if target.suffix == ".md" and not download:
                raw_md.append((page.name, href))
            if parts.fragment and target.suffix == ".html":
                other = Links()
                other.feed(target.read_text(encoding="utf-8"))
                assert unquote(parts.fragment) in other.ids, (page.name, href, "missing anchor")
            local_targets.add(target)
            count += 1
    assert not raw_md, raw_md
    summary = json.loads((report / "summary.json").read_text())
    audit = json.loads((report / "artifact_verification.json").read_text())
    assert len(summary["rows"]) == 10 and audit["status"] == "passed"
    assert summary["evaluation_script_sha256"] == sha256(ROOT / "evaluate_five_cases.py")
    assert summary["audit_script_sha256"] == sha256(ROOT / "five_case_artifacts.py")
    http = []
    if args.http:
        for target in sorted(local_targets | set(pages)):
            if target.is_dir() or not target.is_relative_to(ROOT):
                continue
            path = target.relative_to(ROOT).as_posix()
            # Check all directly linked report assets without downloading large videos.
            with urlopen(Request(f"http://127.0.0.1:8765/{path}", method="HEAD"), timeout=15) as response:
                assert response.status == 200
                http.append({"path": path, "status": response.status, "content_type": response.headers.get_content_type()})
        for path in ("reports/five_cases/seed42/index.html", "FIVE_CASE_RESULT.html", "FIVE_CASE_PROTOCOL.html", "report.html"):
            with urlopen(f"http://127.0.0.1:8765/{path}", timeout=15) as response:
                decoded = response.read().decode("utf-8")
                assert "Oracle" in decoded
    record = {"status": "passed", "verified_at_utc": datetime.now(timezone.utc).isoformat(),
              "html_pages": len(pages), "local_links_checked": count, "raw_md_navigation_links": len(raw_md),
              "http_checked": args.http, "http_assets": http,
              "report_sha256": sha256(report / "index.html"), "summary_sha256": sha256(report / "summary.json"),
              "review_sha256": sha256(report / "review.json"), "artifact_audit_sha256": sha256(report / "artifact_verification.json"),
              "report_script_sha256": sha256(ROOT / "make_five_case_report.py")}
    write_json(report / ("delivery_verification.json" if args.http else "document_verification.json"), record)
    print(json.dumps({k: v for k, v in record.items() if k != "http_assets"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
