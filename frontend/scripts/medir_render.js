/**
 * medir_render.js — Mede o RNF-03: intervalo entre o clique em "Atualizar
 * Mapa" e o fim da repintura da camada coroplética.
 *
 * A medição é feita no próprio navegador (Chrome instalado na máquina,
 * dirigido por puppeteer-core — nenhum binário é baixado). O relógio começa
 * no clique e para no primeiro quadro renderizado após a última mutação do
 * DOM do painel de sobreposição do Leaflet, que é onde os polígonos vivem.
 * O intervalo, portanto, inclui a requisição à API, a recombinação dos dados
 * com a geometria e a repintura dos 42 polígonos.
 *
 * Pré-requisitos: API em :3000 e frontend em :5173 no ar.
 *
 * Uso:
 *   node frontend/scripts/medir_render.js [--url http://localhost:5173] [--n 7]
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import puppeteer from 'puppeteer-core';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const CHROME_PADRAO = [
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
];

function parseArgs(argv) {
  const args = { url: 'http://localhost:5173', n: 7, chrome: null };
  for (let i = 2; i < argv.length; i += 2) {
    const chave = argv[i].replace(/^--/, '');
    if (chave in args) args[chave] = chave === 'n' ? Number(argv[i + 1]) : argv[i + 1];
  }
  if (!args.chrome) args.chrome = CHROME_PADRAO.find(p => fs.existsSync(p));
  if (!args.chrome) throw new Error('Chrome não encontrado. Informe --chrome <caminho>.');
  return args;
}

/**
 * Instala na página um cronômetro ligado às mutações do painel de sobreposição
 * do Leaflet. `iniciar()` zera o relógio; `esperarFim()` resolve com o tempo
 * decorrido até o quadro seguinte à última mutação.
 */
const CRONOMETRO = () => {
  window.__cron = {
    t0: null,
    ultimaMutacao: null,
    observador: null,
    iniciar() {
      this.t0 = performance.now();
      this.ultimaMutacao = null;
      const alvo = document.querySelector('.leaflet-overlay-pane');
      this.observador?.disconnect();
      this.observador = new MutationObserver(() => {
        this.ultimaMutacao = performance.now();
      });
      this.observador.observe(alvo, { childList: true, subtree: true, attributes: true });
    },
    async esperarFim(quietudeMs = 300, limiteMs = 15000) {
      const inicio = performance.now();
      while (performance.now() - inicio < limiteMs) {
        await new Promise(r => setTimeout(r, 50));
        if (this.ultimaMutacao && performance.now() - this.ultimaMutacao > quietudeMs) break;
      }
      // Espera o quadro seguinte: só então a repintura está de fato na tela
      const fim = await new Promise(r => requestAnimationFrame(() => r(performance.now())));
      this.observador.disconnect();
      if (!this.ultimaMutacao) return null;
      // Desconta a janela de quietude, que é instrumento e não tempo de resposta
      return this.ultimaMutacao - this.t0 + (fim - performance.now());
    },
  };
  return true;
};

const mediana = a => {
  const o = [...a].sort((x, y) => x - y);
  const m = Math.floor(o.length / 2);
  return o.length % 2 ? o[m] : (o[m - 1] + o[m]) / 2;
};

async function main() {
  const { url, n, chrome } = parseArgs(process.argv);

  const navegador = await puppeteer.launch({
    executablePath: chrome,
    headless: 'new',
    args: ['--no-sandbox', '--window-size=1440,900'],
  });

  try {
    const pagina = await navegador.newPage();
    await pagina.setViewport({ width: 1440, height: 900 });
    await pagina.goto(url, { waitUntil: 'networkidle2', timeout: 60000 });

    // Espera o mapa existir com os 42 polígonos pintados
    await pagina.waitForSelector('.leaflet-overlay-pane path', { timeout: 60000 });
    const poligonos = await pagina.$$eval('.leaflet-overlay-pane path', ps => ps.length);
    console.log(`[render] mapa inicial com ${poligonos} polígonos`);

    // Localiza os controles pelo texto, sem depender de seletores de estilo
    const seletorBotao = 'button.btn-primario';
    const seletorCid   = '#filtro-cid';

    const opcoes = await pagina.$$eval(`${seletorCid} option`, os =>
      os.map(o => o.value).filter(v => v !== ''));
    if (opcoes.length === 0) throw new Error('Nenhuma opção de CID-10 disponível no filtro.');

    const amostras = [];
    for (let i = 0; i < n; i++) {
      // Alterna entre um capítulo e "todos" para garantir payload diferente a
      // cada iteração — repintura com dados idênticos não é repintura
      const valor = i % 2 === 0 ? opcoes[i % opcoes.length] : '';
      await pagina.select(seletorCid, valor);

      await pagina.evaluate(CRONOMETRO);
      await pagina.evaluate(() => window.__cron.iniciar());
      await pagina.click(seletorBotao);
      const ms = await pagina.evaluate(() => window.__cron.esperarFim());

      if (ms === null) {
        console.log(`[render] iteração ${i + 1}: sem repintura detectada (payload idêntico)`);
        continue;
      }
      amostras.push(ms);
      console.log(`[render] iteração ${i + 1}: ${ms.toFixed(1)} ms (filtro CID = ${valor || 'todos'})`);
    }

    if (amostras.length === 0) throw new Error('Nenhuma repintura medida.');

    const resultado = {
      alvo: url,
      iteracoes: amostras.length,
      amostras_ms: amostras.map(v => Number(v.toFixed(1))),
      mediana_ms: Number(mediana(amostras).toFixed(1)),
      media_ms: Number((amostras.reduce((a, b) => a + b, 0) / amostras.length).toFixed(1)),
      max_ms: Number(Math.max(...amostras).toFixed(1)),
      poligonos,
    };

    const destino = path.join(__dirname, '../../docs/resultados/rnf_render.json');
    fs.mkdirSync(path.dirname(destino), { recursive: true });
    fs.writeFileSync(destino, JSON.stringify(resultado, null, 2) + '\n', 'utf-8');

    console.log(`[render] mediana: ${resultado.mediana_ms} ms — máxima: ${resultado.max_ms} ms`);
    console.log(`[render] gravado em ${destino}`);
  } finally {
    await navegador.close();
  }
}

main().catch(erro => {
  console.error('[render] falha:', erro.message);
  process.exit(1);
});
