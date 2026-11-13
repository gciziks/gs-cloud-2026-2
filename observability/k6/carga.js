import http from 'k6/http';
import { sleep } from 'k6';

export const options = { vus: 20, duration: '5m' };

const capitais = [
  3550308, 3304557, 3106200, 4106902, 4314902, 2927408, 5208707,
  1302603, 5300108, 2304400, 2611606, 2704302, 2507507, 2408102,
  5002704, 5103403, 4205407, 3205309, 2800308, 2211001, 1721000,
];

export default function () {
  const base = __ENV.MVP_URL;
  if (!base) throw new Error('Defina MVP_URL');
  const codigo = capitais[Math.floor(Math.random() * capitais.length)];
  const caminhos = [
    '/', '/buscar?q=sao', `/municipio/${codigo}`,
    `/api/municipios/${codigo}/previsao`,
  ];
  http.get(`${base}${caminhos[Math.floor(Math.random() * caminhos.length)]}`);
  if (Math.random() < 0.02) http.get(`${base}/municipio/0`);
  sleep(1);
}
