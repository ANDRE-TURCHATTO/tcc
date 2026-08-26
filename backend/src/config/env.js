'use strict';

/**
 * Centraliza a leitura e validação das variáveis de ambiente.
 * Lança erro caso variáveis obrigatórias estejam ausentes.
 * O encerramento do processo fica a cargo do ponto de entrada (server.js).
 */
require('dotenv').config();

/**
 * A API acessa o banco por um de dois drivers:
 *
 *   - `postgres` — conexão direta via `pg` usando DATABASE_URL. É o modo do
 *     ambiente local (docker-compose.yml), o único em que as consultas
 *     espaciais do PostGIS e as medições de desempenho são reprodutíveis.
 *   - `supabase` — cliente REST do Supabase, usado na implantação em nuvem.
 *
 * DATABASE_URL tem precedência: se estiver definida, o driver direto é o
 * escolhido e as credenciais do Supabase tornam-se dispensáveis.
 *
 * @throws {Error} Se variáveis obrigatórias não estiverem definidas
 */
function carregarEnv() {
  const DATABASE_URL = process.env.DATABASE_URL;
  const driver = DATABASE_URL ? 'postgres' : 'supabase';

  const env = {
    PORT:               parseInt(process.env.PORT  || '3000', 10),
    HOST:               process.env.HOST            || '0.0.0.0',
    DB_DRIVER:          driver,
    DATABASE_URL,
    PG_POOL_MAX:        parseInt(process.env.PG_POOL_MAX || '10', 10),
    SUPABASE_URL:       process.env.SUPABASE_URL,
    SUPABASE_KEY:       process.env.SUPABASE_KEY,
    CACHE_TTL_SECONDS:  parseInt(process.env.CACHE_TTL_SECONDS || '300', 10),
    // Origens autorizadas a consumir a API. Lista separada por vírgula; o
    // padrão cobre o servidor de desenvolvimento do Vite.
    CORS_ORIGINS: (process.env.CORS_ORIGINS || 'http://localhost:5173,http://127.0.0.1:5173')
      .split(',')
      .map(o => o.trim())
      .filter(Boolean),
  };

  // Obrigatórias apenas no modo Supabase — no modo direto, DATABASE_URL basta
  const OBRIGATORIAS = driver === 'supabase' ? ['SUPABASE_URL', 'SUPABASE_KEY'] : [];

  for (const chave of OBRIGATORIAS) {
    if (!env[chave]) {
      throw new Error(
        `Variável de ambiente "${chave}" não definida. ` +
        'Defina DATABASE_URL para usar o Postgres local, ou copie ' +
        '.env.example para .env e preencha as credenciais do Supabase.'
      );
    }
  }

  return env;
}

module.exports = carregarEnv();
