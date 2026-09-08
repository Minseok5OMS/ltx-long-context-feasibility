"""Check readable UTF-8 documents, experiment report links, and optional live HTTP."""
import argparse
import json
from pathlib import Path
from urllib.parse import unquote,urlsplit
from urllib.request import Request,urlopen

from five_case_prompt_common import ROOT,REPORT,now
from run_generation import sha256,write_json
from verify_five_case_grid_delivery import Links


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--http',action='store_true')
    args=p.parse_args()
    pages=sorted(set(ROOT.glob('*.html'))|{REPORT/'index.html',ROOT/'reports/five_case_grid/seed42/index.html'})
    targets=set(); count=0; raw=[]
    for page in pages:
        source=page.read_text(encoding='utf-8')
        assert '<meta charset="utf-8"' in source.lower()
        parser=Links();parser.feed(source)
        for uri,download in parser.links:
            parts=urlsplit(uri)
            if parts.scheme or parts.netloc:
                continue
            target=(page.parent/unquote(parts.path)).resolve() if parts.path else page
            assert target.exists(),(page,uri)
            if target.suffix=='.md' and not download:
                raw.append((str(page),uri))
            if parts.fragment and target.suffix=='.html':
                other=Links();other.feed(target.read_text(encoding='utf-8'))
                assert unquote(parts.fragment) in other.ids,(page,uri,'missing anchor')
            targets.add(target);count+=1
    assert not raw,raw
    summary=json.loads((REPORT/'summary.json').read_text())
    audit=json.loads((REPORT/'artifact_verification.json').read_text())
    manifest=json.loads((REPORT/'report_manifest.json').read_text())
    assert len(summary['rows'])==60 and audit['status']=='passed' and not audit['partial']
    assert audit['new_generations']==45 and audit['reused_generations']==15
    assert summary['evaluation_script_sha256']==sha256(ROOT/'evaluate_five_case_prompts.py')
    assert summary['audit_script_sha256']==sha256(ROOT/'five_case_prompt_artifacts.py')
    assert manifest['report_sha256']==sha256(REPORT/'index.html')
    assert manifest['script_sha256']==sha256(ROOT/'make_five_case_prompt_report.py')
    page_source=(REPORT/'index.html').read_text()
    assert page_source.count('data-generated="1"')==60
    assert page_source.count('preload="none"')==75
    http=[]
    if args.http:
        for target in sorted(targets|set(pages)):
            if target.is_dir() or not target.is_relative_to(ROOT):
                continue
            path=target.relative_to(ROOT).as_posix()
            with urlopen(Request(f'http://127.0.0.1:8765/{path}',method='HEAD'),timeout=15) as response:
                assert response.status==200
                http.append({'path':path,'status':response.status,'content_type':response.headers.get_content_type()})
        for path in ('reports/five_case_prompt/seed42/index.html','PROMPT_CONTROL_RESULT.html','PROMPT_CONTROL_PROPOSAL.html','NEXT_STAGE.html'):
            with urlopen(f'http://127.0.0.1:8765/{path}',timeout=15) as response:
                assert response.status==200
                assert response.read().decode('utf-8')==(ROOT/path).read_text(encoding='utf-8')
    record={'status':'passed','verified_at_utc':now(),'html_pages':len(pages),'local_links_checked':count,
        'raw_md_navigation_links':len(raw),'generated_video_players':60,'preload_none_video_players':75,
        'http_checked':args.http,'http_assets':http,'report_sha256':sha256(REPORT/'index.html'),
        'summary_sha256':sha256(REPORT/'summary.json'),'artifact_audit_sha256':sha256(REPORT/'artifact_verification.json'),
        'limitations':['HTTP and local link checks do not verify playback on the user PC.']}
    write_json(REPORT/('delivery_verification.json' if args.http else 'document_verification.json'),record)
    print(json.dumps({k:v for k,v in record.items() if k!='http_assets'},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
