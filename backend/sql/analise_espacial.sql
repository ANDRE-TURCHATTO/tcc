-- ============================================================
-- Consultas espaciais do Longevus (PostGIS)
--
-- Estas consultas justificam o uso do PostGIS: operam sobre a topologia do
-- território, não apenas sobre atributos. A pergunta que respondem é se as
-- taxas altas de internação se distribuem aleatoriamente pelo recorte ou se
-- formam blocos contíguos de municípios vizinhos.
--
-- Pré-requisitos:
--   - extensão postgis habilitada
--   - `municipios_sudoeste.geometria` preenchida (etl.loader.carregar_geometrias)
-- ============================================================

-- ------------------------------------------------------------
-- 1. Matriz de vizinhança por contiguidade
--
-- ST_Touches é verdadeiro quando dois polígonos compartilham fronteira sem
-- sobreposição de interiores — exatamente a definição de municípios
-- limítrofes. O índice GIST sobre a coluna geométrica sustenta o predicado.
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW vizinhos_municipios AS
SELECT
    a.codigo_ibge  AS codigo_ibge,
    a.nome         AS nome,
    b.codigo_ibge  AS codigo_vizinho,
    b.nome         AS nome_vizinho
FROM municipios_sudoeste a
JOIN municipios_sudoeste b
  ON a.codigo_ibge <> b.codigo_ibge
 AND ST_Touches(a.geometria, b.geometria);

-- ------------------------------------------------------------
-- 2. Taxa de internação por município
--
-- Isolada em view para que a análise espacial não repita a agregação.
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW taxa_por_municipio AS
SELECT
    m.codigo_ibge,
    m.nome,
    m.microrregiao,
    COUNT(i.id)                                             AS internacoes,
    p.populacao,
    ROUND(COUNT(i.id)::NUMERIC * 100000
          / NULLIF(p.populacao, 0), 1)                      AS taxa_por_100mil
FROM municipios_sudoeste m
LEFT JOIN populacao_municipio p
       ON p.codigo_ibge = m.codigo_ibge
LEFT JOIN internacoes i
       ON i.municipio_codigo = m.codigo_ibge
GROUP BY m.codigo_ibge, m.nome, m.microrregiao, p.populacao;

-- ------------------------------------------------------------
-- 3. Autocorrelação espacial local
--
-- Para cada município, compara a própria taxa com a média das taxas dos
-- municípios limítrofes. A classificação segue a lógica dos indicadores
-- locais de associação espacial (LISA):
--
--   alta-alta   — taxa alta cercada de taxas altas (aglomerado de risco)
--   baixa-baixa — taxa baixa cercada de taxas baixas
--   alta-baixa  — taxa alta isolada entre vizinhos de taxa baixa (outlier)
--   baixa-alta  — taxa baixa cercada de taxas altas (outlier)
--
-- A referência de corte é a mediana regional das taxas.
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW autocorrelacao_espacial AS
WITH referencia AS (
    SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY taxa_por_100mil) AS mediana
    FROM taxa_por_municipio
    WHERE taxa_por_100mil IS NOT NULL
),
vizinhanca AS (
    SELECT
        t.codigo_ibge,
        t.nome,
        t.taxa_por_100mil,
        COUNT(v.codigo_vizinho)              AS qtd_vizinhos,
        ROUND(AVG(tv.taxa_por_100mil), 1)    AS taxa_media_vizinhos
    FROM taxa_por_municipio t
    LEFT JOIN vizinhos_municipios v ON v.codigo_ibge = t.codigo_ibge
    LEFT JOIN taxa_por_municipio tv ON tv.codigo_ibge = v.codigo_vizinho
    GROUP BY t.codigo_ibge, t.nome, t.taxa_por_100mil
)
SELECT
    z.codigo_ibge,
    z.nome,
    z.taxa_por_100mil,
    z.qtd_vizinhos,
    z.taxa_media_vizinhos,
    ROUND(z.taxa_por_100mil - z.taxa_media_vizinhos, 1) AS diferenca,
    CASE
        WHEN z.taxa_por_100mil    >= r.mediana
         AND z.taxa_media_vizinhos >= r.mediana THEN 'alta-alta'
        WHEN z.taxa_por_100mil    <  r.mediana
         AND z.taxa_media_vizinhos <  r.mediana THEN 'baixa-baixa'
        WHEN z.taxa_por_100mil    >= r.mediana
         AND z.taxa_media_vizinhos <  r.mediana THEN 'alta-baixa'
        ELSE 'baixa-alta'
    END AS classificacao
FROM vizinhanca z
CROSS JOIN referencia r
WHERE z.taxa_por_100mil IS NOT NULL;

-- ------------------------------------------------------------
-- 4. Métricas territoriais do recorte
--
-- ST_Area sobre geografia devolve metros quadrados; a divisão converte para
-- quilômetros quadrados. ST_Union dissolve as fronteiras internas para medir
-- o recorte como um único polígono.
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW metricas_territoriais AS
SELECT
    COUNT(*)                                                       AS municipios,
    ROUND((ST_Area(ST_Union(geometria)::geography) / 1e6)::NUMERIC, 1)
                                                                   AS area_km2,
    ROUND((ST_Perimeter(ST_Union(geometria)::geography) / 1000)::NUMERIC, 1)
                                                                   AS perimetro_km
FROM municipios_sudoeste
WHERE geometria IS NOT NULL;
