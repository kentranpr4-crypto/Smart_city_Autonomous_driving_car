// WP0 toolchain smoke (NOT a VIS gate): serve the production build, open it in headless Chromium, record the WebGL renderer,
// measure frame timing over 120 frames, and save a screenshot.
const { spawn } = require('child_process'); const fs = require('fs'); const path = require('path');
const { chromium } = require('playwright');
// Default output is untracked (results/); set EVIDENCE=1 to deliberately refresh the committed evidence under docs/.
const OUT = process.env.EVIDENCE === '1' ? path.resolve(__dirname, '../docs/phase2/wp-reports/evidence/wp0') : path.resolve(__dirname, '../results/web_smoke'); fs.mkdirSync(OUT, { recursive: true });
const PORT = 4173;
(async () => {
  const srv = spawn('npx', ['vite', 'preview', '--host', '127.0.0.1', '--port', String(PORT), '--strictPort'], { cwd: path.resolve(__dirname, '../web'), stdio: 'ignore' });
  const wait = async () => { for (let i = 0; i < 60; i++) { try { const r = await fetch(`http://127.0.0.1:${PORT}/`); if (r.ok) return; } catch {} await new Promise(r => setTimeout(r, 250)); } throw new Error('preview server did not start'); };
  let result = { status: 'FAIL' };
  try {
    await wait();
    const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
    const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
    const errors = []; page.on('pageerror', e => errors.push(String(e))); page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
    await page.goto(`http://127.0.0.1:${PORT}/`);
    await page.waitForFunction(() => window.__smoke, null, { timeout: 15000 });
    const smoke = await page.evaluate(() => window.__smoke);
    const frames = await page.evaluate(() => new Promise(res => { const t = []; let last = performance.now(); let n = 0;
      const f = now => { t.push(now - last); last = now; if (++n < 120) requestAnimationFrame(f); else res(t.slice(5)); }; requestAnimationFrame(f); }));
    frames.sort((a, b) => a - b); const q = p => frames[Math.min(frames.length - 1, Math.floor(p * frames.length))];
    await page.screenshot({ path: path.join(OUT, 'toolchain-smoke.png') });
    result = { status: errors.length ? 'FAIL' : 'PASS', note: 'toolchain smoke only; NOT VIS evidence; software renderer is not representative of product performance',
               webgl: smoke, frame_ms: { n: frames.length, p50: q(0.5), p95: q(0.95), p99: q(0.99), max: frames[frames.length - 1] }, console_errors: errors,
               viewport: '1280x720', chromium: browser.version(), when: new Date().toISOString() };
    await browser.close();
  } catch (e) { result = { status: 'FAIL', error: String(e) }; }
  finally { srv.kill('SIGTERM'); }
  fs.writeFileSync(path.join(OUT, 'toolchain-smoke.json'), JSON.stringify(result, null, 2) + '\n'); console.log(JSON.stringify(result, null, 2));
  process.exit(result.status === 'PASS' ? 0 : 1);
})();
