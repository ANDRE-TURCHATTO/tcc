# Requisitos do Sistema Longevus

> **Versão:** 1.0  
> **Status:** Em especificação  
> **Autor:** André Luiz Costa da Silva

---

## 1. Requisitos Funcionais

### 1.1 Pipeline de Dados (ETL — Python)

| ID | Requisito | Prioridade |
|----|-----------|------------|
| RF-01 | O sistema deve extrair arquivos `.dbc` do SIH/SUS referentes ao estado do Paraná | Alta |
| RF-02 | O sistema deve filtrar os registros, mantendo apenas municípios do Sudoeste do Paraná | Alta |
| RF-03 | O sistema deve criar faixas etárias agrupadas (0-10, 11-20, 21-30, 31-40, 41-50, 51-60, 61+) | Alta |
| RF-04 | O sistema deve agrupar os códigos CID-10 por capítulos | Alta |
| RF-05 | O sistema deve carregar os dados transformados no banco PostgreSQL/PostGIS (Supabase) | Alta |
| RF-16 | O sistema deve descartar registros inconsistentes e contabilizar os descartes por motivo (`idade_indecifravel`, `sexo_invalido`, `cid_desconhecido`, `valor_invalido`), registrando o funil completo: brutos → fora da região → descartados → carregados | Alta |

| RF-17 | O sistema deve manter a população residente de cada município do recorte, obtida do IBGE, como denominador das taxas de internação | Alta |
| RF-18 | O recorte territorial deve ser derivado das microrregiões do IBGE que compõem a AMSOP — Capanema, Francisco Beltrão, Pato Branco e Palmas — totalizando 42 municípios, e deve ser verificável contra a base de localidades do IBGE | Alta |

#### Regras de decodificação dos campos de origem (RF-03, RF-16)

O SIH/SUS não armazena idade e sexo no formato adotado pelo modelo de dados do
Longevus, exigindo conversão explícita no transformador:

| Campo de origem | Codificação no SIH/SUS | Regra aplicada |
|-----------------|------------------------|----------------|
| `IDADE` + `COD_IDADE` | `COD_IDADE` indica a unidade: 0 = ignorada, 1 = horas, 2 = dias, 3 = meses, 4 = anos (0–99), 5 = anos a partir de 100 (`idade = 100 + IDADE`) | Unidades subanuais (0–3) são convertidas para 0 anos completos; unidade fora do domínio descarta o registro. Na ausência da coluna `COD_IDADE`, `IDADE` é interpretada como anos completos |
| `SEXO` | 1 = masculino, 3 = feminino, 2 = feminino em layouts anteriores a 2008, 0/9 = ignorado | Convertido para o domínio `'M'` / `'F'`; valor ignorado descarta o registro |
| `DIAG_PRINC` | Código CID-10 | Mapeado para o capítulo em numeral romano (RF-04); código sem capítulo correspondente descarta o registro |
| `VAL_TOT` | Valor da AIH em reais | Valor ausente ou negativo descarta o registro |

### 1.2 Backend (API Node.js/Fastify)

| ID | Requisito | Prioridade |
|----|-----------|------------|
| RF-06 | A API deve expor o endpoint `GET /api/indicadores` com parâmetros: `cid_capitulo`, `sexo`, `faixa_etaria` | Alta |
| RF-07 | O endpoint `/api/indicadores` deve retornar dados agregados por município no formato `{ dados: [{ codigo_ibge, total_atendimentos, valor_total, populacao, taxa_por_100mil }] }` | Alta |
| RF-08 | A API deve expor o endpoint `GET /api/geometria` retornando o GeoJSON da malha territorial do Sudoeste do Paraná | Alta |
| RF-09 | A API deve implementar cache dos resultados de queries para reduzir sobrecarga no banco | Média |

### 1.3 Frontend (React + Vite)

| ID | Requisito | Prioridade |
|----|-----------|------------|
| RF-10 | O frontend deve renderizar um mapa interativo com a malha municipal do Sudoeste do Paraná | Alta |
| RF-11 | O mapa deve aplicar coloração coroplética nos municípios conforme a **taxa de internações por 100 mil habitantes** (escala amarelo → vermelho). O valor absoluto não pode ser usado como base da coloração, sob pena de o mapa refletir a distribuição populacional em vez do padrão de utilização dos serviços | Alta |
| RF-19 | Os cortes da escala devem ser os **quintis da distribuição observada** no conjunto filtrado, e não frações do valor máximo. Cortes proporcionais ao máximo deixam níveis inteiros da escala sem uso quando a menor taxa da região já está próxima da maior — foi o que ocorreu em 2023, com a menor taxa em 41% da maior. A legenda deve exibir os intervalos calculados, e o texto do trabalho deve declarar que cores de mapas com filtros diferentes não são comparáveis entre si | Alta |
| RF-12 | O tooltip do mapa deve exibir: nome do município, taxa por 100 mil habitantes, total de atendimentos, população residente e valor total (R$) ao passar o mouse | Alta |
| RF-13 | A sidebar deve conter filtros por CID-10 (capítulo), Sexo e Faixa Etária | Alta |
| RF-14 | O botão "Atualizar Mapa" deve disparar nova requisição à API com os filtros selecionados | Alta |
| RF-15 | O frontend deve usar TanStack Query para gerenciamento de estado e requisições | Média |

---

## 2. Requisitos Não-Funcionais

Cada requisito não funcional declara **métrica**, **meta** e **instrumento de
medição**. Um requisito sem métrica não é verificável e, portanto, não é
requisito: é intenção. As medições realizadas estão em
`docs/resultados/rnf_2023.md`.

| ID | Categoria | Requisito | Métrica | Meta | Instrumento |
|----|-----------|-----------|---------|------|-------------|
| RNF-01 | **Desempenho da API** | O endpoint `GET /api/indicadores` deve responder rapidamente com o cache aquecido | Latência p95 sob carga de 10 conexões concorrentes por 20 s | ≤ 500 ms | `autocannon -c 10 -d 20` |
| RNF-02 | **Desempenho a frio** | A primeira requisição, que atravessa o banco sem cache, deve permanecer utilizável | Latência da primeira resposta após limpeza do cache | ≤ 2.000 ms | `curl -w %{time_total}` |
| RNF-03 | **Renderização do mapa** | O mapa deve completar a repintura após a aplicação de filtros dentro do tempo de tolerância do usuário | Intervalo entre o clique em "Atualizar Mapa" e o fim da repintura da camada GeoJSON, medido na aba Performance do DevTools | ≤ 2.000 ms | Chrome DevTools / Lighthouse |
| RNF-04 | **Leveza da malha** | A malha territorial deve ser simplificada o bastante para trafegar em conexão modesta | Tamanho do arquivo `sudoeste-pr.geojson` | ≤ 500 KB | `ls -l` sobre o arquivo servido |
| RNF-05 | **Leveza do payload** | O frontend deve receber apenas agregados, nunca registros individuais de internação | Tamanho da resposta de `GET /api/indicadores` e número de linhas retornadas | ≤ 50 KB e exatamente 42 linhas (uma por município) | `curl -s | wc -c` e inspeção do JSON |
| RNF-06 | **Corretude do pipeline** | As regras de transformação mais críticas — decodificação de idade, faixa etária e capítulo CID-10 — devem ser cobertas por testes automatizados | Cobertura de linhas de `pipeline/etl/transformer.py` | ≥ 90% | `pytest --cov=etl.transformer` |
| RNF-07 | **Reprodutibilidade** | O ciclo do `.dbc` ao banco deve executar sem intervenção manual e em tempo previsível | Tempo total de execução do pipeline para as 12 competências de 2023 | ≤ 30 min, sem passo manual | Cronometragem em `caracterizar_base.py` |
| RNF-08 | **Manutenibilidade** | O código deve seguir arquitetura em camadas, sem dependências invertidas entre elas | Ausência de importação de camada externa por camada interna (rota → serviço → repositório → driver) | Zero violações | Inspeção do grafo de `require`/`import` |
| RNF-09 | **Disponibilidade** | O banco deve estar acessível nos dois ambientes previstos | Sucesso do healthcheck do container local e da conexão com o Supabase | Ambos acessíveis | `pg_isready` (docker-compose) e requisição à API |
| RNF-10 | **Usabilidade** | A interface deve ser operável por profissional de saúde sem afinidade técnica com dados | Número de interações necessárias para produzir um mapa filtrado a partir da tela inicial | ≤ 4 interações | Contagem sobre o fluxo implementado |

> **Limitação declarada:** o RNF-10 é medido por contagem de interações, não
> por teste com usuários reais. Nenhum profissional de saúde avaliou a
> interface no escopo deste trabalho — ver seção de limitações do TCC.

---

## 3. Restrições

- Os dados são limitados ao recorte geográfico do **Sudoeste do Paraná**
- A fonte primária de dados é exclusivamente o **SIH/SUS (DATASUS)**
- A base cartográfica será obtida do **IBGE**
- O banco de dados é **PostgreSQL com a extensão PostGIS**, em dois ambientes equivalentes: container local (`docker-compose.yml`), usado nas medições e nas consultas espaciais, e **Supabase** na implantação em nuvem

---

## 4. Critérios de Aceitação Globais

- [ ] Pipeline executa do `.dbc` ao banco sem intervenção manual (RNF-07)
- [ ] API responde com latência p95 ≤ 500 ms com cache ativo (RNF-01)
- [ ] GeoJSON servido abaixo de 500 KB (RNF-04)
- [ ] Mapa colore pela taxa por 100 mil habitantes, não pelo valor absoluto (RF-11)
- [ ] Tooltip exibe taxa, absoluto, população e valor total (RF-12)
- [ ] Transformações críticas do pipeline cobertas por testes ≥ 90% (RNF-06)
- [ ] Ao menos uma consulta espacial do PostGIS executada sobre a malha carregada
