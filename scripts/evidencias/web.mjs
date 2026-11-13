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
  if (ehGrafana) await entrarNoGrafana(page);
  await page.goto(paginaUrl, { waitUntil: 'networkidle', timeout: 60000 });
  await ocultarDadosPessoais(page);
  await page.screenshot({ path: arquivo, fullPage: paginaInteira });
  await browser.close();
}

async function entrarNoGrafana(page) {
  const senha = process.env.GRAFANA_ADMIN_PASSWORD;
  if (!senha) throw new Error('Defina GRAFANA_ADMIN_PASSWORD no ambiente.');
  for (let tentativa = 0; tentativa < 30; tentativa++) {
    try {
      const saude = await page.request.get('http://127.0.0.1:3000/api/health', { timeout: 2000 });
      if (saude.ok()) break;
    } catch {}
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
  const resposta = await page.request.post('http://127.0.0.1:3000/login', {
    data: { user: 'admin', password: senha },
  });
  if (!resposta.ok()) throw new Error(`Login Grafana falhou: HTTP ${resposta.status()}`);
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
  for (const no of nos) {
    const seguro = substituir(no.textContent);
    if (seguro !== no.textContent) no.textContent = seguro;
  }
  });
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  if (!alvo || !arquivo) throw new Error('Uso: node scripts/evidencias/web.mjs <url|grafana:caminho> <arquivo.png>');
  if (grafana) await capturarGrafana(alvo.slice('grafana:'.length), arquivo);
  else await capturar(url, arquivo);
}
