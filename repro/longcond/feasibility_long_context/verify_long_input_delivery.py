"""Check generated report links and optional HTTP delivery without changing artifacts."""
import argparse,json,urllib.request
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote,quote
from long_input_common import *

class Parser(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.videos=0
    def handle_starttag(self,tag,attrs):
        if tag=='video':self.videos+=1
        for k,v in attrs:
            if k in ['href','src','poster'] and v:self.links.append(v)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--http',action='store_true');a=ap.parse_args()
    files=[REPORT/'index.html',ROOT/'LONG_INPUT_RESULT.html',ROOT/'LONG_INPUT_VS_SPARSE_PROTOCOL.html',ROOT/'NEXT_STAGE.html']
    checked=set();http=[];documents=[]
    for p in files:
        text=p.read_text(encoding='utf-8');parser=Parser();parser.feed(text);assert '<meta charset="utf-8">' in text
        for href in parser.links:
            u=urlsplit(href)
            if u.scheme or u.netloc or not u.path:continue
            target=(p.parent/unquote(u.path)).resolve();assert target.exists(),(p,href)
            checked.add(target)
        documents.append({'path':str(p),'sha256':sha256(p),'videos':parser.videos})
    assert documents[0]['videos']==50 # 5 inputs + 5 generated results, for each of 5 cases
    if a.http:
        for p in sorted(checked|set(files)):
            if not p.is_file():continue
            rel=p.resolve().relative_to(ROOT.resolve()).as_posix()
            url='http://127.0.0.1:8765/'+quote(rel)
            req=urllib.request.Request(url,method='HEAD')
            with urllib.request.urlopen(req,timeout=15) as r:assert r.status==200;http.append({'path':rel,'status':r.status,'bytes':r.headers.get('Content-Length')})
        for p in files:
            rel=p.resolve().relative_to(ROOT.resolve()).as_posix()
            with urllib.request.urlopen('http://127.0.0.1:8765/'+quote(rel),timeout=15) as r:assert r.read()==p.read_bytes()
    write_json(REPORT/('delivery_verification.json' if a.http else 'document_verification.json'),{'status':'passed','documents':documents,'local_links':len(checked),'http_assets':http,'http_count':len(http),'video_count':documents[0]['videos'],'scope':'HTML/UTF-8/local assets and HTTP response; browser playback interaction is separate'})
    print('PASS',len(files),'documents',len(checked),'local assets',len(http),'HTTP assets')

if __name__=='__main__':main()
