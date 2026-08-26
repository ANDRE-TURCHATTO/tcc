# Modelo de Dados — Longevus

> **Versão:** 1.0  
> **Banco:** PostgreSQL + PostGIS (Supabase)

---

## 1. Tabelas

### 1.1 `internacoes`

Dados brutos filtrados e transformados provenientes do SIH/SUS.

```sql
CREATE TABLE internacoes (
  id               SERIAL PRIMARY KEY,
  municipio_codigo VARCHAR(7)     NOT NULL,  -- Código IBGE do município de residência
  idade            INTEGER        NOT NULL,
  sexo             CHAR(1)        NOT NULL,  -- 'M' = Masculino, 'F' = Feminino
  faixa_etaria     VARCHAR(10)    NOT NULL,  -- Ex: '0-10', '11-20', ..., '61+'
  cid_principal    VARCHAR(4)     NOT NULL,  -- Código CID-10 (ex: 'J18')
  cid_capitulo     VARCHAR(5)     NOT NULL,  -- Capítulo CID-10 (ex: 'X', 'XI')
  valor_total      NUMERIC(12, 2) NOT NULL,  -- Valor pago pela internação (R$)
  ano_competencia  INTEGER        NOT NULL,  -- Ano de referência
  mes_competencia  INTEGER        NOT NULL   -- Mês de referência
);
```

### 1.2 `municipios_sudoeste`

Tabela de referência dos municípios do Sudoeste do Paraná.

O recorte corresponde às microrregiões do IBGE que compõem a AMSOP —
Capanema (8), Francisco Beltrão (19), Pato Branco (10) e Palmas (5) —,
totalizando 42 municípios (RF-18).

```sql
CREATE TABLE municipios_sudoeste (
  codigo_ibge  VARCHAR(7)   PRIMARY KEY,
  nome         VARCHAR(100) NOT NULL,
  microrregiao VARCHAR(100)
);
```

### 1.3 `populacao_municipio`

Denominador populacional das taxas de internação (RF-17). Sem ele, o mapa
coroplético refletiria o tamanho da população de cada município em vez do
padrão de utilização dos serviços de saúde.

```sql
CREATE TABLE populacao_municipio (
  codigo_ibge  VARCHAR(7)   NOT NULL,
  ano          INTEGER      NOT NULL,  -- Ano de referência da contagem
  populacao    INTEGER      NOT NULL,  -- População residente
  fonte        VARCHAR(120) NOT NULL,  -- Ex: 'IBGE — Censo Demográfico 2022'
  PRIMARY KEY (codigo_ibge, ano),
  CONSTRAINT fk_populacao_municipio
      FOREIGN KEY (codigo_ibge)
      REFERENCES municipios_sudoeste (codigo_ibge)
);
```

**Fonte adotada:** Censo Demográfico 2022 do IBGE (população residente
recenseada). A série de estimativas populacionais do IBGE não cobre o ano de
2023 — o Censo 2022 a substituiu naquele intervalo —, de modo que o ano
imediatamente anterior à competência analisada é o denominador disponível
mais próximo.

---

## 2. Índices Recomendados

```sql
-- Otimiza as queries de filtro da API
CREATE INDEX idx_internacoes_cid_capitulo  ON internacoes (cid_capitulo);
CREATE INDEX idx_internacoes_sexo          ON internacoes (sexo);
CREATE INDEX idx_internacoes_faixa_etaria  ON internacoes (faixa_etaria);
CREATE INDEX idx_internacoes_municipio     ON internacoes (municipio_codigo);
```

---

## 3. Query Principal (Agregação)

Query executada pelo endpoint `GET /api/indicadores`. A agregação parte de
`municipios_sudoeste` com `LEFT JOIN` sobre as internações, de modo que
municípios sem nenhum registro no filtro corrente apareçam com contagem zero
em vez de desaparecerem do resultado — condição para que o mapa renderize os
42 municípios em qualquer combinação de filtros.

```sql
SELECT
  m.codigo_ibge,
  COUNT(i.id)                        AS total_atendimentos,
  COALESCE(SUM(i.valor_total), 0)    AS valor_total,
  p.populacao,
  ROUND(COUNT(i.id)::NUMERIC * 100000 / NULLIF(p.populacao, 0), 1)
                                     AS taxa_por_100mil
FROM municipios_sudoeste m
LEFT JOIN populacao_municipio p
       ON p.codigo_ibge = m.codigo_ibge
      AND p.ano = :ano_populacao
LEFT JOIN internacoes i
       ON i.municipio_codigo = m.codigo_ibge
      AND (i.cid_capitulo = :cid_capitulo OR :cid_capitulo IS NULL)
      AND (i.sexo         = :sexo         OR :sexo         IS NULL)
      AND (i.faixa_etaria = :faixa_etaria OR :faixa_etaria IS NULL)
GROUP BY m.codigo_ibge, p.populacao;
```

`taxa_por_100mil` é nula quando a população do município não está cadastrada,
situação em que o mapa aplica a cor neutra de "sem dados".

---

## 4. Contrato de Resposta da API

### `GET /api/indicadores`

**Query Params:**
| Parâmetro | Tipo | Obrigatório | Exemplo |
|-----------|------|-------------|--------|
| `cid_capitulo` | string | Não | `"X"` |
| `sexo` | string | Não | `"M"`, `"F"` |
| `faixa_etaria` | string | Não | `"0-10"` |

**Resposta (200 OK):**
```json
{
  "dados": [
    {
      "codigo_ibge": "410840",
      "total_atendimentos": 9730,
      "valor_total": 14293187.45,
      "populacao": 96666,
      "taxa_por_100mil": 10065.6
    },
    {
      "codigo_ibge": "411850",
      "total_atendimentos": 7895,
      "valor_total": 11804922.10,
      "populacao": 91836,
      "taxa_por_100mil": 8596.8
    }
  ]
}
```

### `GET /api/geometria`

**Resposta (200 OK):** GeoJSON FeatureCollection  
**Tamanho máximo:** 500KB  
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
      "geometry": { ... }
    }
  ]
}
```

---

## 5. Faixas Etárias Padronizadas

| Faixa | Range de Idade |
|-------|----------------|
| `0-10` | 0 a 10 anos |
| `11-20` | 11 a 20 anos |
| `21-30` | 21 a 30 anos |
| `31-40` | 31 a 40 anos |
| `41-50` | 41 a 50 anos |
| `51-60` | 51 a 60 anos |
| `61+` | 61 anos ou mais |

---

## 6. Capítulos CID-10 Principais

| Código | Descrição |
|--------|-----------|
| I | Algumas doenças infecciosas e parasitárias |
| II | Neoplasias |
| IX | Doenças do aparelho circulatório |
| X | Doenças do aparelho respiratório |
| XI | Doenças do aparelho digestivo |
| XIII | Doenças do sistema osteomuscular |
| XIV | Doenças do aparelho geniturinário |
| XV | Gravidez, parto e puerpério |
| XIX | Lesões, envenenamentos |
