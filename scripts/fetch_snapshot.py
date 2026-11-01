#!/usr/bin/env python3
"""Fetch URL -> raw bytes + extracted text snapshot + manifest entry (no LLM, no paraphrase).
usage: fetch_snapshot.py DOMAIN_DIR ID URL [ID URL ...]
Writes: <domain>/raw/<ID>.<ext>, <domain>/snapshots/<ID>.html (extracted plain text; ext .html only because bites.py globs *.html), appends <domain>/capture_manifest.jsonl
Failures are recorded with status, never faked."""
import sys, json, hashlib, subprocess, datetime, re, html, pathlib, unicodedata
from html.parser import HTMLParser

class T(HTMLParser):
    SKIP = {'script','style','noscript','svg','head','nav','footer','form'}
    BLOCK = {'p','div','br','li','tr','h1','h2','h3','h4','h5','h6','section','article','td','th','blockquote'}
    def __init__(s): super().__init__(); s.o=[]; s.d=0
    def handle_starttag(s,t,a):
        if t in s.SKIP: s.d+=1
        elif t in s.BLOCK: s.o.append('\n')
    def handle_endtag(s,t):
        if t in s.SKIP and s.d: s.d-=1
        elif t in s.BLOCK: s.o.append('\n')
    def handle_data(s,x):
        if not s.d: s.o.append(x)

def to_text(b, ctype):
    if b[:4] == b'%PDF':
        p = subprocess.run(['pdftotext','-layout','-','-'], input=b, capture_output=True)
        return p.stdout.decode('utf-8','replace') if p.returncode==0 else None
    s = b.decode('utf-8','replace')
    if '<html' in s[:2000].lower() or '<!doctype' in s[:200].lower() or '<body' in s.lower():
        t = T(); t.feed(s); s = html.unescape(''.join(t.o))
    s = unicodedata.normalize('NFC', s)
    s = re.sub(r'[ \t\xa0]+',' ',s); s = re.sub(r'\n\s*\n+','\n',s)
    return s.strip()+'\n'

def main():
    d = pathlib.Path(sys.argv[1]); a = sys.argv[2:]
    (d/'raw').mkdir(exist_ok=True); (d/'snapshots').mkdir(exist_ok=True)
    for i in range(0,len(a),2):
        sid,url = a[i],a[i+1]
        now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        r = subprocess.run(['curl','-sSL','--compressed','--max-time','90','-A','Mozilla/5.0 (research-bot; academic)','-o','-','-w','\n%{http_code}|%{content_type}|%{url_effective}',url],capture_output=True)
        body,_,meta = r.stdout.rpartition(b'\n')
        code,ctype,final = (meta.decode().split('|')+['','',''])[:3]
        e = {'id':sid,'url':url,'final_url':final,'fetched_at':now,'http':code,'content_type':ctype,'curl_rc':r.returncode,'bytes':len(body)}
        if r.returncode==0 and code.startswith('2') and body:
            ext = 'pdf' if body[:4]==b'%PDF' else 'html'
            (d/'raw'/f'{sid}.{ext}').write_bytes(body)
            txt = to_text(body, ctype)
            if txt:
                (d/'snapshots'/f'{sid}.html').write_text(txt, encoding='utf-8')
                e.update(status='OK', sha256=hashlib.sha256(body).hexdigest(), text_chars=len(txt))
            else: e['status']='TEXT_EXTRACT_FAILED'
        else:
            e['status']='BLOCKED_OR_FAILED'; e['err']=r.stderr.decode()[:200]
        with open(d/'capture_manifest.jsonl','a',encoding='utf-8') as f: f.write(json.dumps(e,ensure_ascii=False)+'\n')
        print(sid, e['status'], code, e.get('text_chars',''))
main()
