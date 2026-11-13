import { exec } from 'node:child_process';
import { promisify } from 'node:util';
import { chromium } from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';

const run = promisify(exec);
const [destino, comando] = process.argv.slice(2);
if (!destino || !comando) throw new Error('Uso: terminal-capture.mjs <arquivo.png> <comando>');

let saida;
let codigo = 0;
try {
  const resultado = await run(comando, { timeout: 120000, maxBuffer: 4 * 1024 * 1024,
    env: { ...process.env, PYTHONIOENCODING: 'utf-8' } });
  saida = `${resultado.stdout}${resultado.stderr}`;
  codigo = 0;
} catch (erro) {
  saida = `${erro.stdout ?? ''}${erro.stderr ?? ''}`;
  codigo = erro.code ?? 1;
}

const mascarar = (texto) => texto
  .replace(/[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}/g, '[e-mail ocultado]')
  .replace(/\b(?:\d{1,3}\.){3}\d{1,3}\b/g, ip =>
    ip === '0.0.0.0' || ip === '127.0.0.1' || ip.startsWith('203.0.113.') ? ip : '[IP ocultado]')
  .replace(/Bearer\s+[A-Za-z0-9._-]+/g, 'Bearer [ocultado]')
  .replace(/\b(?=[A-Za-z0-9_-]{32,}\b)(?=[A-Za-z0-9_-]*\d)[A-Za-z0-9_-]+\b/g, '[valor ocultado]')
  .replace(/(password|token|secret|senha)\s*[:=]\s*\S+/gi, '$1=[ocultado]');

const comandoSeguro = mascarar(comando).replace(/(password|token|secret|senha)(=|\s+)[^\s]+/gi, '$1$2[ocultado]');
const html = `<!doctype html><meta charset="utf-8"><style>
body{margin:0;background:#0d1117;color:#c9d1d9;font:20px/1.45 ui-monospace,SFMono-Regular,Consolas,monospace}
main{padding:28px;white-space:pre-wrap;overflow-wrap:anywhere}.cabecalho{color:#8b949e;margin-bottom:14px}
</style><main><div class="cabecalho">$ ${escapar(comandoSeguro)}</div>${escapar(mascarar(saida))}${codigo ? `\n[comando terminou com código ${escapar(String(codigo))}]` : ''}</main>`;

function escapar(texto) {
  return String(texto).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;');
}

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1200, height: 100 }, deviceScaleFactor: 1 });
await page.setContent(html);
await page.locator('main').screenshot({ path: destino });
await browser.close();
if (codigo) process.exitCode = Number.isInteger(codigo) ? codigo : 1;
