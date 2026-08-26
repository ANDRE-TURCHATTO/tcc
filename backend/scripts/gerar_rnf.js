'use strict';

/**
 * gerar_rnf.js — Monta a tabela de verificação dos requisitos não funcionais.
 *
 * Consolida em um único documento:
 *   - as medições de desempenho de `medir_rnf.js` (docs/resultados/rnf_desempenho.json)
 *   - as medições estáticas obtidas do repositório (tamanho da malha, camadas,
 *     interações da interface)
 *   - as medições produzidas fora deste script (cobertura de testes, tempo do
 *     pipeline, renderização do mapa), lidas de `rnf_manuais.json`
 *
 * O formato da tabela é o exigido pela seção de resultados do TCC:
 * requisito | métrica | meta | medido | atendido.
 *
 * Uso:
 *   node backend/scripts/gerar_rnf.js
 */

const fs   = require('fs');
const path = require('path');

const RAIZ      = path.join(__dirname, '../..');
const RESULTADOS = path.join(RAIZ, 'docs/resultados');

function lerJson(arquivo, padrao = null) {
  const caminho = path.join(RESULTADOS, arquivo);
  if (!fs.existsSync(caminho)) return padrao;
  return JSON.parse(fs.readFileSync(caminho, 'utf-8'));
}

const num = (v, casas = 1) =>
  v.toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas });

function main() {
  const desempenho = lerJson('rnf_desempenho.json');
  if (!desempenho) {
    throw new Error('rnf_desempenho.json ausente. Execute node backend/scripts/medir_rnf.js primeiro.');
  }
  const manuais = lerJson('rnf_manuais.json', {});

  // A renderização vem de frontend/scripts/medir_render.js quando disponível;
  // o arquivo de medições manuais é o recurso de fallback.
  const render = lerJson('rnf_render.json');
  const renderMs = render ? render.mediana_ms : manuais.render_ms;

  const geojsonKb = desempenho.geometria.bytes_servidos / 1024;
  const payloadKb = desempenho.indicadores.payload_bytes / 1024;
  const ind = desempenho.indicadores;

  // Cada linha: [id, requisito, métrica, meta, medido, atendido]
  const linhas = [
    ['RNF-01', 'Desempenho da API',
     'Latência p95, 10 conexões / 20 s, cache quente', '≤ 500 ms',
     `${num(ind.p95_ms, 2)} ms`, ind.p95_ms <= 500],

    ['RNF-02', 'Desempenho a frio',
     'Latência da primeira resposta após reinício da API', '≤ 2.000 ms',
     `${num(ind.cache_frio_ms)} ms`, ind.cache_frio_ms <= 2000],

    ['RNF-03', 'Renderização do mapa',
     'Intervalo entre o clique em "Atualizar Mapa" e o fim da repintura', '≤ 2.000 ms',
     renderMs != null
       ? `${num(renderMs)} ms (mediana de ${render ? render.iteracoes : '?'} repinturas)`
       : '— não medido —',
     renderMs != null ? renderMs <= 2000 : null],

    ['RNF-04', 'Leveza da malha',
     'Tamanho do GeoJSON servido por GET /api/geometria', '≤ 500 KB',
     `${num(geojsonKb)} KB`, geojsonKb <= 500],

    ['RNF-05', 'Leveza do payload',
     'Tamanho e cardinalidade da resposta de GET /api/indicadores', '≤ 50 KB e 42 linhas',
     `${num(payloadKb)} KB, ${ind.linhas_payload} linhas`,
     payloadKb <= 50 && ind.linhas_payload === 42],

    ['RNF-06', 'Corretude do pipeline',
     'Cobertura de linhas de pipeline/etl/transformer.py', '≥ 90%',
     manuais.cobertura_pct != null
       ? `${num(manuais.cobertura_pct, 0)}% (${manuais.testes} testes)` : '— não medido —',
     manuais.cobertura_pct != null ? manuais.cobertura_pct >= 90 : null],

    ['RNF-07', 'Reprodutibilidade',
     'Tempo de execução do pipeline para as 12 competências de 2023', '≤ 30 min, sem passo manual',
     manuais.pipeline_s != null
       ? `${num(manuais.pipeline_s)} s (${num(manuais.pipeline_s / 60)} min)` : '— não medido —',
     manuais.pipeline_s != null ? manuais.pipeline_s <= 1800 : null],

    ['RNF-08', 'Manutenibilidade',
     'Importações que invertem a ordem rota → serviço → repositório → driver', 'Zero violações',
     manuais.violacoes_camadas != null ? `${manuais.violacoes_camadas} violações` : '— não medido —',
     manuais.violacoes_camadas != null ? manuais.violacoes_camadas === 0 : null],

    ['RNF-09', 'Disponibilidade',
     'Requisições com erro durante a carga sustentada', 'Zero erros',
     `${ind.erros} erros em ${ind.requisicoes.toLocaleString('pt-BR')} requisições`,
     ind.erros === 0],

    ['RNF-10', 'Usabilidade',
     'Interações necessárias para produzir um mapa filtrado', '≤ 4 interações',
     manuais.interacoes != null ? `${manuais.interacoes} interações` : '— não medido —',
     manuais.interacoes != null ? manuais.interacoes <= 4 : null],
  ];

  const marca = ok => (ok === null ? 'não medido' : ok ? 'sim' : '**não**');

  const doc = `# Verificação dos requisitos não funcionais — 2023

> Gerado por \`backend/scripts/gerar_rnf.js\`. Não editar manualmente.

As metas estão declaradas em \`spec/requirements.md\`, seção 2. As medições de
desempenho foram tomadas contra o ambiente local (PostgreSQL 16 com PostGIS 3.4
em container, API Fastify em Node.js 20), com a base de 2023 carregada:
61.814 internações em 42 municípios.

## 1. Tabela de verificação

| ID | Requisito | Métrica | Meta | Medido | Atendido |
|----|-----------|---------|------|--------|----------|
${linhas.map(([id, req, met, meta, medido, ok]) =>
  `| ${id} | ${req} | ${met} | ${meta} | ${medido} | ${marca(ok)} |`).join('\n')}

## 2. Distribuição da latência sob carga (RNF-01)

Carga de ${desempenho.concorrencia} conexões concorrentes em laço fechado por
${desempenho.duracao_s} segundos contra \`GET /api/indicadores\`, com o cache
aquecido.

| Estatística | Valor |
|-------------|-------|
| Requisições completadas | ${ind.requisicoes.toLocaleString('pt-BR')} |
| Vazão | ${num(ind.req_por_s)} req/s |
| Latência média | ${num(ind.media_ms, 2)} ms |
| p50 | ${num(ind.p50_ms, 2)} ms |
| p95 | ${num(ind.p95_ms, 2)} ms |
| p99 | ${num(ind.p99_ms, 2)} ms |
| Máxima | ${num(ind.max_ms, 2)} ms |
| Erros | ${ind.erros} |

A diferença entre a primeira resposta (${num(ind.cache_frio_ms)} ms, que
atravessa o banco) e a mediana sob carga (${num(ind.p50_ms, 2)} ms, servida do
cache in-memory) é o efeito isolado do cache: uma redução de
${num(ind.cache_frio_ms / ind.p50_ms, 0)}× no tempo de resposta.

## 3. Repintura do mapa (RNF-03)

${render ? `Sete repinturas sucessivas da camada coroplética, alternando o filtro de
capítulo CID-10 para garantir payload distinto a cada iteração. O relógio parte
do clique em "Atualizar Mapa" e para no primeiro quadro após a última mutação
do painel de sobreposição do Leaflet — o intervalo cobre a requisição à API, a
recombinação com a geometria e a repintura dos ${render.poligonos} polígonos.

| Estatística | Valor |
|-------------|-------|
| Repinturas medidas | ${render.iteracoes} |
| Mediana | ${num(render.mediana_ms)} ms |
| Média | ${num(render.media_ms)} ms |
| Máxima | ${num(render.max_ms)} ms |
| Amostras | ${render.amostras_ms.map(v => num(v)).join(' · ')} ms |
` : 'Medição pendente — executar `node frontend/scripts/medir_render.js`.'}

## 4. Como reproduzir

\`\`\`bash
docker compose up -d
docker exec -i longevus-db psql -U longevus -d longevus < pipeline/sql/create_tables.sql
python pipeline/carregar_banco.py --ano 2023
docker exec -i longevus-db psql -U longevus -d longevus < backend/sql/agregar_internacoes.sql
npm start --prefix backend            # em outro terminal
node backend/scripts/medir_rnf.js
npm run dev --prefix frontend          # em outro terminal
node frontend/scripts/medir_render.js
node backend/scripts/gerar_rnf.js
\`\`\`
`;

  const destino = path.join(RESULTADOS, 'rnf_2023.md');
  fs.writeFileSync(destino, doc, 'utf-8');
  console.log(`[rnf] documento gravado em ${destino}`);
}

main();
