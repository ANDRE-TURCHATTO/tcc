# Especificação da API — Longevus

> **Versão:** 1.0  
> **Framework:** Node.js + Fastify  
> **Base URL:** `http://localhost:3000` (desenvolvimento)

---

## Endpoints

---

### `GET /api/indicadores`

**Descrição:** Retorna dados agregados de internações por município, com filtros opcionais.

#### Parâmetros de Query

| Parâmetro | Tipo | Obrigatório | Valores Aceitos | Default |
|-----------|------|-------------|------------------|---------|
| `cid_capitulo` | string | Não | Numeral romano (I, II, IX, X...) | todos |
| `sexo` | string | Não | `M`, `F` | ambos |
| `faixa_etaria` | string | Não | `0-10`, `11-20`, `21-30`, `31-40`, `41-50`, `51-60`, `61+` | todas |

#### Resposta de Sucesso — `200 OK`

```json
{
  "dados": [
    {
      "codigo_ibge": "410840",
      "total_atendimentos": 9730,
      "valor_total": 14293187.45,
      "populacao": 96666,
      "taxa_por_100mil": 10065.6
    }
  ]
}
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `codigo_ibge` | string | Código IBGE do município, 6 dígitos |
| `total_atendimentos` | number | Internações no filtro corrente |
| `valor_total` | number | Soma dos valores das AIH, em reais |
| `populacao` | number \| null | População residente (Censo IBGE 2022) |
| `taxa_por_100mil` | number \| null | Internações por 100 mil habitantes; base da coloração do mapa (RF-11). Nulo quando a população não está cadastrada |

Todos os 42 municípios do recorte são retornados em qualquer combinação de
filtros. Municípios sem internações correspondentes vêm com
`total_atendimentos: 0`, e não omitidos.

#### Resposta de Erro — `400 Bad Request`

```json
{
  "error": "Parâmetro inválido",
  "detail": "O valor de 'sexo' deve ser 'M' ou 'F'"
}
```

#### Comportamento de Cache
- Chave de cache: `indicadores:{cid_capitulo}:{sexo}:{faixa_etaria}`
- TTL: 5 minutos
- Cache invalidado manualmente após nova carga de dados

---

### `GET /api/geometria`

**Descrição:** Retorna o GeoJSON com a malha territorial dos municípios do Sudoeste do Paraná.

#### Parâmetros

Nenhum.

#### Resposta de Sucesso — `200 OK`

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "codigo_ibge": "411850",
        "nome": "Francisco Beltrão"
      },
      "geometry": {
        "type": "Polygon",
        "coordinates": [[...]]
      }
    }
  ]
}
```

#### Comportamento
- O arquivo GeoJSON é servido estático (pré-gerado e simplificado)
- Tamanho máximo: **500KB**
- Cache: `Cache-Control: max-age=86400` (1 dia)

---

## Regras de Negócio da API

1. Parâmetros ausentes → sem filtro (retorna todos)
2. Parâmetros inválidos → `400 Bad Request` com mensagem descritiva
3. Resultado vazio → `200 OK` com `dados: []`
4. Todos os valores monetários em **BRL (R$)**
5. `codigo_ibge` sempre como **string de 6 dígitos**
