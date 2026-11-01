#!/usr/bin/env python3
"""Build claims.jsonl from a hand-curated list. Every span is checked verbatim against its snapshot
(NFC + html.unescape, same as refinery.py) BEFORE writing; any miss aborts. fetched_at/url come from capture_manifest."""
import json, sys, html, unicodedata, pathlib
D = pathlib.Path('data/refinery/domains/smartcity-v2x-landscape')
N = lambda s: unicodedata.normalize('NFC', html.unescape(s))
man = {}
for l in (D/'capture_manifest.jsonl').read_text().splitlines():
    e = json.loads(l)
    if e['status']=='OK': man[e['id']] = e
out, bad = [], []
def C(ent, field, value, span, sid, tier, ext='verbatim', origin=None):
    m = man[sid]; snap = N((D/'snapshots'/f'{sid}.html').read_text(encoding='utf-8'))
    if N(span) not in snap: bad.append((sid, ent, field, span[:70])); return
    out.append({'entity':ent,'field':field,'value':value,'evidence_span':span,'extraction':ext,'tier':tier,
      'capture':{'url':m['url'],'fetched_at':m['fetched_at'],'snapshot':f'{sid}.html','source':sid,'origin_id':origin or sid}})
exec(open('scripts/claims_data.py',encoding='utf-8').read())
if bad:
    print('SPAN MISSES:'); [print(' ',b) for b in bad]; sys.exit(1)
(D/'claims.jsonl').write_text(''.join(json.dumps(c,ensure_ascii=False)+'\n' for c in out),encoding='utf-8')
print(len(out),'claims written')
