/**
 * capturar_mapa.js — Produz as figuras da interface para o TCC.
 *
 * Abre o frontend no Chrome instalado na máquina (via puppeteer-core, sem
 * baixar navegador), aplica o fluxo de uso e grava as capturas em
 * docs/resultados/figuras/.
 *
 * Pré-requisitos: API em :3000 e frontend em :5173 no ar.
 *
 * Uso:
 *   node frontend/scripts/capturar_mapa.js [--url http://localhost:5173]
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

const FIGURAS = path.join(__dirname, '../../docs/resultados/figuras');

function parseArgs(argv) {
  const args = { url: 'http://localhost:5173', chrome: null };
  for (let i = 2; i < argv.length; i += 2) {
    const chave = argv[i].replace(/^--/, '');
    if (chave in args) args[chave] = argv[i + 1];
  }
  if (!args.chrome) args.chrome = CHROME_PADRAO.find(p => fs.existsSync(p));
  if (!args.chrome) throw new Error('Chrome não encontrado. Informe --chrome <caminho>.');
  return args;
}

const espera = ms => new Promise(r => setTimeout(r, ms));

async function main() {
  const { url, chrome } = parseArgs(process.argv);
  fs.mkdirSync(FIGURAS, { recursive: true });

  const navegador = await puppeteer.launch({
    executablePath: chrome,
    headless: 'new',
    args: ['--no-sandbox'],
  });

  try {
    const pagina = await navegador.newPage();
    await pagina.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 });
    await pagina.goto(url, { waitUntil: 'networkidle2', timeout: 60000 });
    await pagina.waitForSelector('.leaflet-overlay-pane path', { timeout: 60000 });

    // Estado inicial: malha carregada, ainda sem indicadores — os dados só são
    // buscados após o clique, decisão de projeto registrada em App.jsx
    await espera(2000);
    await pagina.screenshot({ path: path.join(FIGURAS, 'interface_estado_inicial.png') });

    // Estado com dados: mapa coroplético pela taxa por 100 mil habitantes
    await pagina.click('button.btn-primario');
    await espera(3000);
    await pagina.screenshot({ path: path.join(FIGURAS, 'mapa_coropletico_2023.png') });

    // Tooltip sobre o município de maior taxa, para ilustrar o RF-12
    const alvo = await pagina.evaluate(() => {
      const caminhos = [...document.querySelectorAll('.leaflet-overlay-pane path')];
      let melhor = null;
      let maiorArea = 0;
      for (const c of caminhos) {
        const r = c.getBoundingClientRect();
        const area = r.width * r.height;
        if (area > maiorArea) { maiorArea = area; melhor = r; }
      }
      return melhor ? { x: melhor.x + melhor.width / 2, y: melhor.y + melhor.height / 2 } : null;
    });
    if (alvo) {
      await pagina.mouse.move(alvo.x, alvo.y);
      await espera(1500);
      await pagina.screenshot({ path: path.join(FIGURAS, 'tooltip_municipio.png') });
    }

    console.log(`[figuras] gravadas em ${FIGURAS}`);
    for (const f of fs.readdirSync(FIGURAS)) {
      console.log(`  ${f} — ${(fs.statSync(path.join(FIGURAS, f)).size / 1024).toFixed(0)} KB`);
    }
  } finally {
    await navegador.close();
  }
}

main().catch(erro => {
  console.error('[figuras] falha:', erro.message);
  process.exit(1);
});
