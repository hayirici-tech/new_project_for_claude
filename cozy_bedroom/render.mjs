#!/usr/bin/env node
// Renders scene.html in headless Chromium into two layers (background / desk foreground).
//   node render.mjs [--scale 2] [--out output]
// Needs `npm install` in this folder (three) and a Playwright install with Chromium.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
let chromium;
try { ({ chromium } = require('playwright')); }
catch { ({ chromium } = require('/opt/node-tools/node_modules/playwright')); }

const here = path.dirname(fileURLToPath(import.meta.url));
const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const scale = arg('--scale', '2'), out = path.resolve(here, arg('--out', 'output'));
const threeDir = process.env.THREE_DIR || path.join(here, 'node_modules', 'three');
const types = { '.html': 'text/html', '.js': 'text/javascript' };

const server = http.createServer((req, res) => {
  const url = req.url.split('?')[0];
  const file = url.startsWith('/three/') ? path.join(threeDir, url.slice(7)) : path.join(here, url === '/' ? 'scene.html' : url);
  fs.readFile(file, (err, data) => {
    if (err) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { 'content-type': types[path.extname(file)] || 'application/octet-stream' }); res.end(data);
  });
});
await new Promise(r => server.listen(0, '127.0.0.1', r));

const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
page.on('console', m => console.log('[page]', m.text()));
page.on('pageerror', e => { console.error('[page error]', e.message); process.exitCode = 1; });
await page.goto(`http://127.0.0.1:${server.address().port}/?scale=${scale}`);
await page.waitForFunction('window.ready === true', null, { timeout: 180000 });
fs.mkdirSync(out, { recursive: true });
for (const pass of ['bg', 'fg', 'all']) {
  const url = await page.evaluate(p => window.renderPass(p), pass);
  fs.writeFileSync(path.join(out, `_layer_${pass}.png`), Buffer.from(url.split(',')[1], 'base64'));
  console.log('rendered', pass);
}
await browser.close();
server.close();
