-- Migration: criação da função RPC de agregação de internações
-- Execute este script no SQL Editor do Supabase (ou via psql)
-- antes de iniciar a API backend.

-- Função utilizada pelo endpoint GET /api/indicadores.
-- Recebe filtros opcionais e retorna dados agregados por município,
-- acompanhados da população residente e da taxa por 100 mil habitantes.
--
-- A agregação parte de `municipios_sudoeste` com LEFT JOIN sobre as
-- internações, de modo que municípios sem registros no filtro corrente
-- retornem com contagem zero em vez de sumirem do resultado — condição para
-- que o mapa renderize os 42 municípios em qualquer combinação de filtros.
--
-- A taxa por 100 mil habitantes (RF-11) é o indicador que colore o mapa: o
-- valor absoluto reflete o tamanho da população, não o padrão de utilização
-- dos serviços de saúde.
CREATE OR REPLACE FUNCTION agregar_internacoes(
  p_cid_capitulo   TEXT DEFAULT NULL,
  p_sexo           TEXT DEFAULT NULL,
  p_faixa_etaria   TEXT DEFAULT NULL,
  p_ano_populacao  INTEGER DEFAULT 2022
)
RETURNS TABLE (
  codigo_ibge        TEXT,
  total_atendimentos BIGINT,
  valor_total        NUMERIC,
  populacao          INTEGER,
  taxa_por_100mil    NUMERIC
)
LANGUAGE sql
STABLE
AS $$
  SELECT
    m.codigo_ibge::TEXT                                  AS codigo_ibge,
    COUNT(i.id)                                          AS total_atendimentos,
    COALESCE(SUM(i.valor_total), 0)                      AS valor_total,
    p.populacao                                          AS populacao,
    ROUND(COUNT(i.id)::NUMERIC * 100000
          / NULLIF(p.populacao, 0), 1)                   AS taxa_por_100mil
  FROM municipios_sudoeste m
  LEFT JOIN populacao_municipio p
         ON p.codigo_ibge = m.codigo_ibge
        AND p.ano = p_ano_populacao
  LEFT JOIN internacoes i
         ON i.municipio_codigo = m.codigo_ibge
        AND (i.cid_capitulo  = p_cid_capitulo  OR p_cid_capitulo  IS NULL)
        AND (i.sexo          = p_sexo          OR p_sexo          IS NULL)
        AND (i.faixa_etaria  = p_faixa_etaria  OR p_faixa_etaria  IS NULL)
  GROUP BY m.codigo_ibge, p.populacao;
$$;
