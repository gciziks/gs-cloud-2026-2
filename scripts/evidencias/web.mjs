import { chromium } from 'playwright';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const [alvo, arquivo] = process.argv.slice(2);
const grafana = alvo?.startsWith('grafana:') ?? false;
const url = grafana ? `http://127.0.0.1:3000${alvo.slice('grafana:'.length)}` : alvo;
const opcoes = {
  largura: Number(process.env.CAPTURA_LARGURA || 1366),
  altura: Number(process.env.CAPTURA_ALTURA || 900),
  paginaInteira: process.env.CAPTURA_PAGINA_INTEIRA !== 'false',
};

export async function capturar(paginaUrl, arquivo, configuracao = {}) {
  return capturarPagina(paginaUrl, arquivo, configuracao, false);
}

export async function capturarGrafana(caminho, arquivo, configuracao = {}) {
  return capturarPagina(`http://127.0.0.1:3000${caminho}`, arquivo, configuracao, true);
}

async function capturarPagina(paginaUrl, arquivo, configuracao, ehGrafana) {
  const viewport = {
    width: configuracao.largura ?? opcoes.largura,
    height: configuracao.altura ?? opcoes.altura,
  };
  const paginaInteira = configuracao.paginaInteira ?? opcoes.paginaInteira;
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport, deviceScaleFactor: 1, bypassCSP: true });
  await page.goto(paginaUrl, { waitUntil: 'networkidle', timeout: 60000 });
  if (ehGrafana) await entrarNoGrafana(page, paginaUrl);
  await ocultarDadosPessoais(page);
  await page.screenshot({ path: arquivo, fullPage: paginaInteira });
  await browser.close();
}

async function entrarNoGrafana(page, paginaUrl) {
  const senha = process.env.GRAFANA_ADMIN_PASSWORD;
  if (!senha) throw new Error('Defina GRAFANA_ADMIN_PASSWORD no ambiente.');
  if (await page.locator('input[name="user"]').count()) {
    await page.locator('input[name="user"]').fill('admin');
    await page.locator('input[name="password"]').fill(senha);
    await page.getByRole('button', { name: /log in|entrar/i }).click();
    await page.waitForLoadState('networkidle');
    await page.goto(paginaUrl, { waitUntil: 'networkidle' });
  }
}

async function ocultarDadosPessoais(page) {
  await page.addStyleTag({ content: 'input[type=password], [data-testid*=password] { filter: blur(12px) !important; }' });
  await page.evaluate(() => {
  const substituir = (texto) => texto
    .replace(/[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}/g, '[e-mail ocultado]')
    .replace(/\b(?:\d{1,3}\.){3}\d{1,3}\b/g, '[IP ocultado]')
    .replace(/Bearer\s+[A-Za-z0-9._-]+/g, 'Bearer [ocultado]')
    .replace(/\b(?=[A-Za-z0-9_-]{32,}\b)(?=[A-Za-z0-9_-]*\d)[A-Za-z0-9_-]+\b/g, '[valor ocultado]')
    .replace(/(password|token|secret|senha)\s*[:=]\s*\S+/gi, '$1=[ocultado]');
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const nos = [];
  while (walker.nextNode()) nos.push(walker.currentNode);
  for (const no of nos) no.textContent = substituir(no.textContent);
  });
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  if (!alvo || !arquivo) throw new Error('Uso: node scripts/evidencias/web.mjs <url|grafana:caminho> <arquivo.png>');
  if (grafana) await capturarGrafana(alvo.slice('grafana:'.length), arquivo);
  else await capturar(url, arquivo);
}
