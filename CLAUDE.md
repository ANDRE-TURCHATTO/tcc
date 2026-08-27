# CLAUDE.md — Contexto do projeto Longevus (TCC)

## O que é este projeto

Plataforma web de visualização geoespacial de internações hospitalares do SIH/SUS
para os 42 municípios do Sudoeste do Paraná. TCC de Engenharia de Software (UNINTER),
autor André Luiz Costa da Silva.

Arquitetura em três camadas:

```
[DATASUS .dbc] → [pipeline/ Python: pysus + pandas] → [PostgreSQL/PostGIS @ Supabase]
                                                              ↓
                                              [backend/ Node.js 20 + Fastify]
                                                              ↓
                                    [frontend/ React 18 + Vite + Leaflet + TanStack Query]
```

Metodologia declarada no README: **Specification-Driven Development (SDD)** — spec formal
antes da implementação, implementação guiada pela spec, testes validados contra a spec.
Cenários BDD em Gherkin ficam em `spec/behaviors/`.

O texto do TCC está em `TCC.md` (e há uma versão .docx fora do repo, que é a entregue).

---

## Estado atual e diagnóstico

O TCC passou por uma revisão crítica. A parte de engenharia está sólida; os problemas são
de fechamento do ciclo. **O trabalho descreve o sistema mas nunca o executa e mede.**

### Bloqueadores (o TCC não se sustenta sem isso)

1. **A seção 6 "Resultados" não contém nenhum resultado.** Nenhum número, tabela ou achado.
   Só descrição de implementação — que é metodologia, não resultado. Mas o resumo afirma
   que "os resultados evidenciam a concentração territorial dos atendimentos". É uma
   afirmação empírica sem lastro no texto.

2. **O mapa coroplético usa valores absolutos.** `colorScale.js` colore por
   `total_atendimentos` bruto. Sem normalizar por população, o mapa mostra onde há mais
   gente, não padrão de utilização. Francisco Beltrão e Pato Branco ficarão vermelhos por
   serem maiores. **Correção obrigatória: internações por 100 mil habitantes.**

3. **Nenhum requisito não funcional foi medido.** O TCC afirma ter considerado desempenho,
   leveza do GeoJSON, usabilidade e manutenibilidade. Nenhum tem métrica, meta ou medição.

4. **Contradição PostGIS.** O objetivo específico diz "banco relacional com suporte
   geoespacial" e o README diz PostgreSQL+PostGIS, mas `GET /api/geometria` serve um
   GeoJSON estático e não há nenhuma consulta espacial no sistema. Ou usa PostGIS de fato,
   ou remove a alegação.

5. **Zero citações no corpo do texto do TCC.** Oito referências listadas, nenhuma citada.

6. **O TCC nunca menciona SDD nem BDD**, embora o README declare SDD e exista
   `spec/behaviors/`. A metodologia real é mais rigorosa do que o texto admite —
   e o TCC hoje não tem classificação metodológica nenhuma. Corrigir isso resolve
   dois problemas de uma vez.

### Inconsistências menores

- README tabela de tecnologias diz "Node-cache / Redis"; o TCC diz só `node-cache`.
  Decidir e padronizar (provavelmente Redis nunca foi usado — remover).
- O TCC afirma "testabilidade" mas não apresenta nenhum teste.
- Os 42 municípios precisam de critério declarado e citado. A mesorregião Sudoeste
  Paranaense do IBGE tem 37; 42 corresponde à AMSOP. Conferir
  `pipeline/data/municipios_sudoeste.csv` e declarar a fonte.

---

## Tarefas, em ordem

### 1. Rodar o pipeline e caracterizar a base

```bash
cd pipeline
python main.py --ano 2023 --mes 6      # confirmar competência a usar
```

Anotar: registros brutos baixados (PR), registros após filtro regional, descartados por
inconsistência (e por qual critério), registros carregados, valor total (`VAL_TOT`).
Se possível, carregar mais de uma competência — série de 12 meses fortalece muito o trabalho.

### 2. Normalizar por população

- Criar tabela `populacao_municipio (codigo_ibge, ano, populacao)`.
- Popular com estimativas do IBGE para os 42 municípios.
- Adicionar `taxa_por_100mil` na agregação do endpoint `/api/indicadores`.
- Alterar `colorScale.js` para colorir pela taxa, não pelo absoluto.
- Manter o absoluto no tooltip — os dois números juntos são informativos.

### 3. Extrair as tabelas de resultado

Queries de agregação a rodar contra o banco, para preencher as tabelas do TCC:

- Top 10 capítulos CID-10: contagem, %, valor total, valor médio.
- Distribuição por faixa etária × sexo.
- Ranking de municípios em absoluto **e** em taxa por 100 mil (as duas colunas lado a lado —
  se o ranking mudar, isso é um resultado em si).

### 4. Medir os RNF

```bash
# latência da API — cache frio e cache quente
autocannon -c 10 -d 20 http://localhost:3000/api/indicadores

# tamanho do GeoJSON antes/depois da simplificação
ls -lh frontend/public/*.geojson
mapshaper malha.geojson -simplify 5% -o malha-simplificada.geojson

# tempo do pipeline
time python main.py --ano 2023 --mes 6
```

Renderização: Lighthouse / aba Performance do DevTools. Tirar captura — vira figura no TCC.

Montar tabela: requisito | métrica | meta | medido | atendido.
**As metas precisam estar em `spec/requirements.md`.** Se não estiverem, adicionar lá primeiro —
é o que dá sentido à palavra "requisito".

### 5. Testes

Mínimo defensável: testes unitários de `pipeline/etl/transformer.py`, que é o módulo mais
crítico e mais fácil de testar.

- Decodificação da idade do SIH (o campo usa prefixo de unidade — casos de borda: dias,
  meses, anos; recém-nascido; idade > 100).
- Classificação em faixas etárias (bordas exatas: 10/11, 60/61).
- Mapeamento CID-10 → capítulo romano (um caso por capítulo I–XXII, mais código inválido).

Reportar cobertura. Se houver cenários Gherkin em `spec/behaviors/`, amarrar os testes a eles —
isso materializa o "testes validados contra a spec" que o README promete.

### 6. Corrigir o texto do TCC

Ver os dois documentos de revisão (fora do repo):
- `revisao_critica_tcc.md` — 40+ itens priorizados
- `tcc_secoes_reescritas.md` — título, resumo, abstract, introdução e esqueleto da seção 5/6 já reescritos

Pendente de reescrita: seções 2 e 3 com citações, seção de trabalhos relacionados
(comparação obrigatória com o TabNet do DATASUS), seção 4.3 Modelo de Dados
(hoje não descreve o modelo de dados — usar `spec/data-model.md`), e limitações.

---

## Convenções

- Documentação acadêmica em `docs/`; diagramas em PlantUML com render em `docs/diagrams/renders/`.
- Toda alteração de comportamento deve refletir na spec correspondente em `spec/` antes do código (SDD).
- Segredos em `.env`, nunca commitados.

## Perguntas prováveis da banca (manter respondíveis)

1. Qual a diferença entre o Longevus e o TabNet do DATASUS?
2. O mapa não está só mostrando onde há mais gente?
3. Qual período? Quantos registros?
4. Você diz que usou PostGIS — qual consulta espacial executou?
5. Algum profissional de saúde testou a interface?
6. Como mediu o desempenho e a usabilidade que declara como RNF?
7. Por que 42 municípios?
8. Tem testes automatizados?
9. O valor da AIH representa o custo real do atendimento? (Não — é repasse pela tabela SUS.)
