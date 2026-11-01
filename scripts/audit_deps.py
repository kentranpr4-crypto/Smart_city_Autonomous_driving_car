#!/usr/bin/env python3
"""Pre-install dependency audit (read-only, network): latest version published >= MIN_AGE_DAYS before TODAY,
its license, size, and peer deps. Writes JSON to stdout. Does not install anything."""
import json, subprocess, sys, urllib.request, datetime as dt
TODAY = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else dt.date.today()
MIN_AGE = 14
cut = TODAY - dt.timedelta(days=MIN_AGE)
def vkey(v):
    core = v.split('-')[0].split('+')[0]
    try: return tuple(int(x) for x in core.split('.'))
    except ValueError: return (0,)
def npm(pkg):
    r = subprocess.run(['npm','view',pkg,'--json','time','versions'], capture_output=True, text=True, timeout=90)
    d = json.loads(r.stdout); times = d['time']; vers = [v for v in d['versions'] if '-' not in v]
    ok = [v for v in vers if dt.date.fromisoformat(times[v][:10]) <= cut]
    ok.sort(key=vkey); v = ok[-1]
    m = json.loads(subprocess.run(['npm','view',f'{pkg}@{v}','--json','license','dist.unpackedSize','peerDependencies','dependencies'],capture_output=True,text=True,timeout=90).stdout)
    return dict(pkg=pkg, version=v, published=times[v][:10], license=m.get('license'), unpacked_kb=round(m.get('dist.unpackedSize',0)/1024), peers=m.get('peerDependencies'), deps=m.get('dependencies'), newest_overall=sorted(vers,key=vkey)[-1])
def pypi(pkg):
    d = json.load(urllib.request.urlopen(f'https://pypi.org/pypi/{pkg}/json', timeout=60))
    best = None
    for v, files in d['releases'].items():
        if not files or any(c in v for c in ('a','b','rc','dev')): continue
        up = min(dt.date.fromisoformat(f['upload_time'][:10]) for f in files)
        if up <= cut and (best is None or vkey(v) > vkey(best[0])): best = (v, up, files)
    v, up, files = best; info = d['info']
    sdist = [f for f in files if f['packagetype']=='sdist']; wheel = [f for f in files if f['packagetype']=='bdist_wheel']
    size = (wheel or sdist)[0]['size']
    lic = info.get('license_expression') or (info.get('license') or '')[:60] or [c for c in info.get('classifiers',[]) if 'License' in c]
    return dict(pkg=pkg, version=v, published=str(up), license=lic, size_kb=round(size/1024), requires=info.get('requires_dist'), requires_python=info.get('requires_python'))
out = {'today': str(TODAY), 'cutoff': str(cut), 'npm': [], 'pypi': []}
for p in ['react','react-dom','three','@react-three/fiber','@react-three/drei','zustand','vite','@vitejs/plugin-react','typescript','@types/react','@types/three']:
    try: out['npm'].append(npm(p))
    except Exception as e: out['npm'].append({'pkg':p,'error':str(e)[:150]})
for p in ['pytest','hypothesis','fastapi','websockets','starlette','pydantic','pyyaml','jsonschema','numpy','uvicorn']:
    try: out['pypi'].append(pypi(p))
    except Exception as e: out['pypi'].append({'pkg':p,'error':str(e)[:150]})
print(json.dumps(out, indent=1, ensure_ascii=False))
