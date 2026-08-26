'use strict';

const env = require('../config/env');

/**
 * Ano de referência do denominador populacional.
 *
 * O Censo Demográfico 2022 do IBGE é a fonte adotada: a série de estimativas
 * populacionais do IBGE não cobre 2023, ano das competências analisadas.
 */
const ANO_POPULACAO = 2022;

/**
 * Consulta a função de agregação pelo driver direto do PostgreSQL.
 *
 * A mesma função `agregar_internacoes` (backend/sql/agregar_internacoes.sql)
 * atende os dois drivers: no Supabase ela é exposta como RPC; aqui é
 * invocada como função de tabela.
 */
async function _viaPostgres({ cid_capitulo, sexo, faixa_etaria }) {
  const { consultar } = require('../lib/db');

  return consultar(
    `SELECT codigo_ibge, total_atendimentos, valor_total, populacao, taxa_por_100mil
       FROM agregar_internacoes($1, $2, $3, $4)`,
    [cid_capitulo || null, sexo || null, faixa_etaria || null, ANO_POPULACAO],
  );
}

/** Consulta a mesma função pela RPC do Supabase. */
async function _viaSupabase({ cid_capitulo, sexo, faixa_etaria }) {
  const supabase = require('../lib/supabase');

  const { data, error } = await supabase.rpc('agregar_internacoes', {
    p_cid_capitulo:  cid_capitulo  || null,
    p_sexo:          sexo          || null,
    p_faixa_etaria:  faixa_etaria  || null,
    p_ano_populacao: ANO_POPULACAO,
  });

  if (error) {
    throw new Error(`Erro ao consultar o banco de dados: ${error.message}`);
  }

  return data || [];
}

/**
 * Executa a query de agregação de internações por município.
 *
 * A agregação parte de `municipios_sudoeste` com LEFT JOIN sobre as
 * internações, de modo que municípios sem registros no filtro corrente
 * retornem com contagem zero em vez de sumirem do resultado — condição para
 * que o mapa renderize os 42 municípios em qualquer combinação de filtros.
 *
 * Cada linha traz também a população residente e a taxa por 100 mil
 * habitantes, que é o indicador usado para colorir o mapa (RF-11).
 *
 * @param {{ cid_capitulo?: string, sexo?: string, faixa_etaria?: string }} filtros
 * @returns {Promise<Array<{
 *   codigo_ibge: string,
 *   total_atendimentos: number,
 *   valor_total: number,
 *   populacao: number|null,
 *   taxa_por_100mil: number|null
 * }>>}
 */
async function buscarAgregadoPorMunicipio(filtros = {}) {
  const linhas = env.DB_DRIVER === 'postgres'
    ? await _viaPostgres(filtros)
    : await _viaSupabase(filtros);

  // Garante os tipos do contrato: numéricos como number, e null preservado
  // onde a população do município não está cadastrada. O driver `pg` devolve
  // BIGINT e NUMERIC como string, o que torna a conversão obrigatória.
  return linhas.map(row => ({
    codigo_ibge:        String(row.codigo_ibge),
    total_atendimentos: Number(row.total_atendimentos),
    valor_total:        Number(row.valor_total),
    populacao:          row.populacao === null ? null : Number(row.populacao),
    taxa_por_100mil:    row.taxa_por_100mil === null ? null : Number(row.taxa_por_100mil),
  }));
}

module.exports = { buscarAgregadoPorMunicipio, ANO_POPULACAO };
