#!/usr/bin/env python3
"""Gate REF_INTEGRITY for docs/phase2/*.md. Deterministic, read-only.
 1. `Cnn·Name`  -> claim #nn (line nn of claims.jsonl) exists and its entity contains Name (case-insensitive).
 2. `Sxx:LINE~text` -> snapshots/Sxx-*.html line LINE contains text (exact substring).
 3. Gap-matrix rule: every VERIFIED row cites >=1 tier-A claim. Prints label counts.
Exit 1 on any failure. Does NOT judge semantic correctness."""
import re, sys, json, glob, pathlib
D = pathlib.Path('data/refinery/domains/smartcity-v2x-landscape')
claims = [json.loads(l) for l in open(D/'claims.jsonl', encoding='utf-8')]
DOCS = sys.argv[1] if len(sys.argv) > 1 else 'docs/phase2'
files = sorted(glob.glob(f'{DOCS}/*.md'))
bad, nclaim, nsnap = [], 0, 0
cache = {}
def snap_lines(sid):
    if sid not in cache:
        p = glob.glob(str(D/'snapshots'/f'{sid}-*.html'))
        cache[sid] = open(p[0], encoding='utf-8').read().split('\n') if len(p)==1 else None
    return cache[sid]
for f in files:
    txt = open(f, encoding='utf-8').read()
    for m in re.finditer(r'\bC(\d{1,3})·([^;|\n`()—,]+?)\s*(?=;|\||`|\)|\(|,|—|\.(?:\s|$)|$)', txt, re.M):
        n, name = int(m.group(1)), m.group(2).strip(); nclaim += 1
        if not (1 <= n <= len(claims)): bad.append(f'{f}: C{n} out of range'); continue
        if name.lower() not in claims[n-1]['entity'].lower(): bad.append(f'{f}: C{n}·{name} but entity={claims[n-1]["entity"]!r}')
    for m in re.finditer(r'\b(S\d{2}[a-z]?):(\d+)~([^;|\n`()—,]+?)\s*(?=;|\||`|\)|\(|,|—|\.(?:\s|$)|$)', txt, re.M):
        sid, ln, key = m.group(1), int(m.group(2)), m.group(3).strip(); nsnap += 1
        L = snap_lines(sid)
        if L is None: bad.append(f'{f}: snapshot {sid} not found/ambiguous'); continue
        if not (1 <= ln <= len(L)) or key not in L[ln-1]: bad.append(f'{f}: {sid}:{ln}~{key!r} not on that line')
# gap-matrix rules
gm = pathlib.Path(DOCS)/'01-evidence-gap-matrix.md'
counts = {}
if gm.exists():
    for row in gm.read_text(encoding='utf-8').splitlines():
        c = [x.strip() for x in row.strip().strip('|').split('|')]
        if len(c) >= 5 and re.fullmatch(r'[A-GV]\d\d', c[0]):
            lab = c[2].replace('*','').strip(); counts[lab] = counts.get(lab,0)+1
            if lab not in ('VERIFIED','SUPPORTED','HYPOTHESIS','UNKNOWN'): bad.append(f'{c[0]}: bad label {lab!r}')
            if lab == 'VERIFIED':
                tiers = [claims[int(n)-1]['tier'] for n in re.findall(r'\bC(\d{1,3})·', c[3]) if 1 <= int(n) <= len(claims)]
                if 'A' not in tiers: bad.append(f'{c[0]}: VERIFIED without tier-A claim')
# ---- ID_RESOLVE: every referenced ID must be defined (table first cell / heading / bold / bullet) ----
ID = r'(?:R-[A-Z]{3}-\d{2}|FM\d{2}|AC-M\d{2}|AC-VS-\d{2}|ADR-\d{3}|WP\d|DEC-\d|CAL-\d|ODD-\d{2}|N-\d{2}|I1[0-2]|I[1-9]|H[1-9]|PHY-\d{2}|VIS-\d{2}|COM-\d{2}|FUS-\d{2}|OD-\d|PX-\d|[A-GV]\d\d(?!·))'
defined, refs = {}, {}
for f in files:
    for ln, row in enumerate(open(f, encoding='utf-8').read().split('\n'), 1):
        m = re.match(r'^\|\s*[*`]*(' + ID + r')[*`]*\b', row) or re.match(r'^#+\s+(' + ID + r')\b', row) \
            or re.match(r'^\s*(?:[-*]|\d+\.)\s+\*{0,2}(' + ID + r')\b', row)
        if m: defined.setdefault(m.group(1), []).append(f'{pathlib.Path(f).name}:{ln}')
        for r in re.finditer(r'(?<![\w-])(' + ID + r')(?![\w-])', row): refs.setdefault(r.group(1), f'{pathlib.Path(f).name}:{ln}')
for k, w in sorted(refs.items()):
    if k not in defined: bad.append(f'ID_RESOLVE: {k} referenced at {w} but never defined')
for k, w in defined.items():
    if len(w) > 1 and not re.fullmatch(r'[A-GV]\d\d', k): bad.append(f'ID_DUP: {k} defined at {w}')
print(f'ids_defined={len(defined)} ids_referenced={len(refs)}')
print(f'files={len(files)} claim_refs={nclaim} snapshot_refs={nsnap} labels={counts}')
if bad: print('FAIL'); [print(' -', b) for b in bad]; sys.exit(1)
print('REF_INTEGRITY PASS (references resolve; this is NOT a semantic-correctness check)')
