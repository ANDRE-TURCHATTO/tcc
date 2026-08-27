# Análise espacial — Sudoeste do Paraná, 2023

> Gerado por `pipeline/analise_espacial.py`. Não editar manualmente.

Consultas executadas em PostgreSQL com extensão PostGIS, sobre a malha municipal do IBGE armazenada em SRID 4674 (SIRGAS 2000). As definições estão em `backend/sql/analise_espacial.sql`.

## 1. Métricas territoriais do recorte

| Indicador | Valor | Consulta espacial |
|-----------|-------|-------------------|
| Municípios com geometria | 42 | — |
| Área total | 17.029,9 km² | `ST_Area(ST_Union(geometria)::geography)` |
| Perímetro do recorte | 916,7 km | `ST_Perimeter(ST_Union(geometria)::geography)` |
| Pares de municípios limítrofes | 196 | `ST_Touches` |

## 2. Vizinhança por contiguidade

Municípios com maior número de limítrofes, obtidos por `ST_Touches` sobre os polígonos municipais:

| Município | Municípios limítrofes |
|-----------|-----------------------|
| Ampére | 11 |
| Francisco Beltrão | 10 |
| Pato Branco | 7 |
| Clevelândia | 6 |
| Coronel Vivida | 6 |
| Dois Vizinhos | 6 |
| Flor da Serra do Sul | 6 |
| Itapejara d'Oeste | 6 |
| Salto do Lontra | 6 |
| São João | 6 |

Média de 4,7 municípios limítrofes por município.

## 3. Autocorrelação espacial das taxas

Cada município tem sua taxa comparada à média das taxas dos municípios limítrofes, tomando a mediana regional como referência de corte. A classificação segue a lógica dos indicadores locais de associação espacial (LISA).

| Classificação | Municípios | % | Interpretação |
|---------------|------------|---|---------------|
| `alta-alta` | 17 | 40,5% | Taxa alta cercada de taxas altas (aglomerado) |
| `baixa-baixa` | 15 | 35,7% | Taxa baixa cercada de taxas baixas (aglomerado) |
| `alta-baixa` | 4 | 9,5% | Taxa alta isolada entre vizinhos de taxa baixa (outlier) |
| `baixa-alta` | 6 | 14,3% | Taxa baixa cercada de taxas altas (outlier) |

**32 dos 42 municípios (76,2%) estão em aglomerados** — isto é, têm taxa do mesmo lado da mediana que a média de seus vizinhos. Sob distribuição aleatória, esperar-se-ia algo próximo de 50%.

### 3.1 Municípios por taxa, com o contexto de vizinhança

| Município | Taxa/100 mil | Vizinhos | Média dos vizinhos | Diferença | Classificação |
|-----------|--------------|----------|--------------------|-----------|---------------|
| Verê | 13.313,2 | 6 | 8.796,7 | 4.516,5 | `alta-baixa` |
| Planalto | 13.030,5 | 4 | 11.000,5 | 2.030,0 | `alta-alta` |
| Coronel Domingos Soares | 12.922,6 | 3 | 9.469,3 | 3.453,3 | `alta-alta` |
| Ampére | 12.553,5 | 11 | 10.167,2 | 2.386,3 | `alta-alta` |
| Boa Esperança do Iguaçu | 12.423,6 | 4 | 9.294,4 | 3.129,2 | `alta-baixa` |
| Cruzeiro do Iguaçu | 11.976,8 | 3 | 11.241,1 | 735,7 | `alta-alta` |
| Capanema | 11.727,9 | 2 | 11.103,0 | 624,9 | `alta-alta` |
| Mangueirinha | 11.672,6 | 5 | 9.398,4 | 2.274,2 | `alta-alta` |
| Nova Esperança do Sudoeste | 11.434,7 | 5 | 10.008,0 | 1.426,7 | `alta-alta` |
| Dois Vizinhos | 11.052,2 | 6 | 10.879,2 | 173,0 | `alta-alta` |
| Pérola d'Oeste | 10.544,9 | 4 | 11.246,7 | -701,8 | `alta-alta` |
| São Jorge d'Oeste | 10.247,4 | 4 | 10.715,6 | -468,2 | `alta-alta` |
| Santa Izabel do Oeste | 10.106,6 | 5 | 9.462,4 | 644,2 | `alta-alta` |
| Francisco Beltrão | 10.065,6 | 10 | 9.461,0 | 604,6 | `alta-alta` |
| Pinhal de São Bento | 9.996,4 | 4 | 9.763,3 | 233,1 | `alta-alta` |
| Bela Vista da Caroba | 9.972,7 | 3 | 10.842,8 | -870,1 | `alta-alta` |
| Clevelândia | 9.787,7 | 6 | 8.787,9 | 999,8 | `alta-baixa` |
| Santo Antônio do Sudoeste | 9.779,1 | 5 | 9.345,8 | 433,3 | `alta-alta` |
| Marmeleiro | 9.452,2 | 3 | 9.065,9 | 386,3 | `alta-baixa` |
| Pranchita | 9.430,0 | 4 | 10.712,6 | -1.282,6 | `alta-alta` |
| Enéas Marques | 9.418,2 | 5 | 10.752,3 | -1.334,1 | `alta-alta` |
| Realeza | 9.175,5 | 5 | 10.734,2 | -1.558,7 | `baixa-alta` |
| Renascença | 9.043,1 | 4 | 8.275,6 | 767,5 | `baixa-baixa` |
| Saudade do Iguaçu | 8.726,3 | 2 | 8.119,0 | 607,3 | `baixa-baixa` |
| Coronel Vivida | 8.709,4 | 6 | 7.973,1 | 736,3 | `baixa-baixa` |
| Chopinzinho | 8.650,7 | 5 | 8.643,2 | 7,5 | `baixa-baixa` |
| Pato Branco | 8.596,8 | 7 | 7.163,7 | 1.433,1 | `baixa-baixa` |
| Salgado Filho | 8.417,2 | 5 | 8.499,9 | -82,7 | `baixa-baixa` |
| Manfrinópolis | 8.303,2 | 5 | 9.824,3 | -1.521,1 | `baixa-alta` |
| Flor da Serra do Sul | 8.088,9 | 6 | 8.235,8 | -146,9 | `baixa-baixa` |
| Salto do Lontra | 7.895,9 | 6 | 10.114,6 | -2.218,7 | `baixa-alta` |
| Sulina | 7.587,2 | 3 | 7.965,8 | -378,6 | `baixa-baixa` |
| Bom Sucesso do Sul | 7.526,5 | 5 | 7.848,0 | -321,5 | `baixa-baixa` |
| Palmas | 6.947,6 | 2 | 11.355,2 | -4.407,6 | `baixa-alta` |
| Honório Serpa | 6.921,7 | 4 | 9.691,6 | -2.769,9 | `baixa-alta` |
| Barracão | 6.845,0 | 2 | 7.210,3 | -365,3 | `baixa-baixa` |
| São João | 6.520,3 | 6 | 8.997,4 | -2.477,1 | `baixa-baixa` |
| Bom Jesus do Sul | 6.331,7 | 4 | 8.282,6 | -1.950,9 | `baixa-baixa` |
| Nova Prata do Iguaçu | 6.252,5 | 4 | 9.900,4 | -3.647,9 | `baixa-alta` |
| Vitorino | 6.058,1 | 4 | 7.708,2 | -1.650,1 | `baixa-baixa` |
| Mariópolis | 5.666,3 | 3 | 8.147,5 | -2.481,2 | `baixa-baixa` |
| Itapejara d'Oeste | 5.476,3 | 6 | 9.122,0 | -3.645,7 | `baixa-baixa` |
