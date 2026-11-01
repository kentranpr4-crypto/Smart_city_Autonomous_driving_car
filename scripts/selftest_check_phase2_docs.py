#!/usr/bin/env python3
"""Bite test for check_phase2_docs.py: inject faults into a temp copy; the checker MUST fail each time."""
import shutil, subprocess, sys, tempfile, pathlib
SRC = pathlib.Path('docs/phase2'); script = 'scripts/check_phase2_docs.py'
def run(d): return subprocess.run([sys.executable, script, str(d)], capture_output=True, text=True)
base = tempfile.mkdtemp(); ok_all = True
b = pathlib.Path(base)/'clean'; shutil.copytree(SRC, b)
r = run(b); print('clean copy       :', 'PASS (expected)' if r.returncode == 0 else 'FAIL!!'); ok_all &= r.returncode == 0
faults = {
 'claim_out_of_range':  ('01-evidence-gap-matrix.md', 'C25·CoAlign', 'C999·CoAlign'),
 'claim_wrong_entity':  ('01-evidence-gap-matrix.md', 'C25·CoAlign', 'C25·V2VNet'),
 'snapshot_wrong_line': ('01-evidence-gap-matrix.md', 'S01b:975~referenceTime', 'S01b:976~referenceTime'),
 'verified_without_A':  ('01-evidence-gap-matrix.md', '| F01 | Chia sẻ góc nhìn giúp "nhìn xuyên" vật che | **VERIFIED** | C18·V2VNet ; C28·Collaborative perception survey |', '| F01 | Chia sẻ góc nhìn giúp "nhìn xuyên" vật che | **VERIFIED** | C62·VinFast |'),
 'undefined_id':        ('02-mvp-prd.md', 'xem FM17', 'xem FM99'),
 'bad_label':           ('01-evidence-gap-matrix.md', '| A01 | Sai số pose của tác tử làm lệch thông điệp không gian và giảm hiệu năng cộng tác | **VERIFIED**', '| A01 | Sai số pose của tác tử làm lệch thông điệp không gian và giảm hiệu năng cộng tác | CERTAIN'),
}
for name, (fn, old, new) in faults.items():
    d = pathlib.Path(base)/name; shutil.copytree(SRC, d); f = d/fn; s = f.read_text(encoding='utf-8')
    if old not in s: print(f'{name:17}: SELFTEST BROKEN (pattern missing)'); ok_all = False; continue
    f.write_text(s.replace(old, new, 1), encoding='utf-8'); r = run(d)
    bit = r.returncode != 0; ok_all &= bit; print(f'{name:17}:', 'BITES (caught)' if bit else 'MISSED!!')
print('SELFTEST', 'PASS' if ok_all else 'FAIL'); sys.exit(0 if ok_all else 1)
