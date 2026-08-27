'use strict';

const { Pool } = require('pg');
const env = require('../config/env');

/**
 * Pool de conexões com o PostgreSQL/PostGIS.
 *
 * Instanciado apenas quando DATABASE_URL está definida (modo `postgres`).
 * O pool é a razão de a latência da API não pagar o custo de handshake a
 * cada requisição — condição para a medição do RNF-01.
 */
let _pool = null;

function obterPool() {
  if (env.DB_DRIVER !== 'postgres') {
    throw new Error('Pool Postgres solicitado, mas DATABASE_URL não está definida.');
  }
  if (!_pool) {
    _pool = new Pool({
      connectionString: env.DATABASE_URL,
      max: env.PG_POOL_MAX,
    });
  }
  return _pool;
}

/**
 * Executa uma consulta parametrizada e devolve as linhas.
 *
 * @param {string} sql
 * @param {Array<any>} params
 * @returns {Promise<Array<object>>}
 */
async function consultar(sql, params = []) {
  const { rows } = await obterPool().query(sql, params);
  return rows;
}

/** Encerra o pool. Usado no desligamento gracioso do servidor. */
async function encerrar() {
  if (_pool) {
    await _pool.end();
    _pool = null;
  }
}

module.exports = { obterPool, consultar, encerrar };
