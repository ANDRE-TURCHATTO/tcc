'use strict';

/**
 * medir_rnf.js — Mede os requisitos não funcionais de desempenho da API.
 *
 * Requisitos cobertos (ver spec/requirements.md, seção 2):
 *   RNF-01  latência p95 com cache aquecido, 10 conexões concorrentes / 20 s
 *   RNF-02  latência da primeira resposta, cache frio
 *   RNF-04  tamanho da malha GeoJSON servida
 *   RNF-05  tamanho e cardinalidade do payload de /api/indicadores
 *
 * A API precisa estar no ar antes da execução:
 *   docker compose up -d && npm start --prefix backend
 *
 * Uso:
 *   node backend/scripts/medir_rnf.js [--url http://localhost:3000] [--dur 20] [--conc 10]
 *
 * A saída é gravada em docs/resultados/rnf_desempenho.json, consumida por
 * `gerar_rnf.js` na montagem da tabela do TCC.
 */

const fs   = require('fs');
const path = require('path');

function parseArgs(argv) {
  const args = { url: 'http://localhost:3000', dur: 20, conc: 10 };
  for (let i = 2; i < argv.length; i += 2) {
    const chave = argv[i].replace(/^--/, '');
    if (chave in args) args[chave] = chave === 'url' ? argv[i + 1] : Number(argv[i + 1]);
  }
  return args;
}

/** Executa uma requisição e devolve latência em ms e tamanho do corpo em bytes. */
async function requisitar(url) {
  const inicio = process.hrtime.bigint();
  const resposta = await fetch(url);
  const corpo = await resposta.text();
  const fim = process.hrtime.bigint();
  return {
    ms: Number(fim - inicio) / 1e6,
    bytes: Buffer.byteLength(corpo),
    status: resposta.status,
    corpo,
  };
}

/** Percentil de uma amostra, por interpolação do índice inferior. */
function percentil(amostra, p) {
  const ordenada = [...amostra].sort((a, b) => a - b);
  const indice = Math.min(ordenada.length - 1, Math.ceil((p / 100) * ordenada.length) - 1);
  return ordenada[Math.max(0, indice)];
}

/**
 * Aplica carga sustentada: `conc` conexões em laço fechado por `dur` segundos.
 * Cada conexão dispara a requisição seguinte assim que a anterior retorna, o
 * que é o mesmo regime do autocannon.
 */
async function carga(url, conc, dur) {
  const fim = Date.now() + dur * 1000;
  const latencias = [];
  let erros = 0;

  async function conexao() {
    while (Date.now() < fim) {
      try {
        const r = await requisitar(url);
        if (r.status !== 200) erros++;
        latencias.push(r.ms);
      } catch {
        erros++;
      }
    }
  }

  await Promise.all(Array.from({ length: conc }, conexao));
  return { latencias, erros };
}

async function main() {
  const { url, dur, conc } = parseArgs(process.argv);
  const alvoIndicadores = `${url}/api/indicadores`;
  const alvoGeometria   = `${url}/api/geometria`;

  console.log(`[rnf] alvo: ${url} — ${conc} conexões por ${dur}s`);

  // RNF-02 — cache frio. A primeira requisição após o start da API não
  // encontra chave no node-cache e atravessa o banco.
  const frio = await requisitar(alvoIndicadores);
  console.log(`[rnf] cache frio: ${frio.ms.toFixed(1)} ms, ${frio.bytes} bytes`);

  // RNF-05 — cardinalidade do payload: uma linha por município, sem registro bruto
  const linhas = JSON.parse(frio.corpo);
  const dados = Array.isArray(linhas) ? linhas : (linhas.data || linhas.dados || []);

  // RNF-01 — cache quente
  const { latencias, erros } = await carga(alvoIndicadores, conc, dur);
  const total = latencias.length;

  // Malha servida pela API (RNF-04)
  const geo = await requisitar(alvoGeometria);

  const resultado = {
    alvo: url,
    concorrencia: conc,
    duracao_s: dur,
    indicadores: {
      cache_frio_ms: Number(frio.ms.toFixed(1)),
      requisicoes: total,
      erros,
      req_por_s: Number((total / dur).toFixed(1)),
      media_ms: Number((latencias.reduce((a, b) => a + b, 0) / total).toFixed(2)),
      p50_ms: Number(percentil(latencias, 50).toFixed(2)),
      p95_ms: Number(percentil(latencias, 95).toFixed(2)),
      p99_ms: Number(percentil(latencias, 99).toFixed(2)),
      max_ms: Number(Math.max(...latencias).toFixed(2)),
      payload_bytes: frio.bytes,
      linhas_payload: dados.length,
    },
    geometria: {
      bytes_servidos: geo.bytes,
      ms: Number(geo.ms.toFixed(1)),
    },
  };

  const destino = path.join(__dirname, '../../docs/resultados/rnf_desempenho.json');
  fs.mkdirSync(path.dirname(destino), { recursive: true });
  fs.writeFileSync(destino, JSON.stringify(resultado, null, 2) + '\n', 'utf-8');

  console.log(`[rnf] p95: ${resultado.indicadores.p95_ms} ms — ${resultado.indicadores.req_por_s} req/s`);
  console.log(`[rnf] gravado em ${destino}`);
}

main().catch(erro => {
  console.error('[rnf] falha:', erro.message);
  process.exit(1);
});
