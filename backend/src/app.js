'use strict';

const Fastify = require('fastify');
const cors    = require('@fastify/cors');

const env = require('./config/env');
const indicadoresRoutes = require('./routes/indicadores');
const geometriaRoutes   = require('./routes/geometria');

/**
 * Cria e configura a instância Fastify com todas as rotas registradas.
 * Separado do server.js para facilitar testes unitários.
 *
 * @returns {import('fastify').FastifyInstance}
 */
function buildApp() {
  const app = Fastify({ logger: true });

  // O frontend é servido de outra origem (Vite em :5173 no desenvolvimento),
  // de modo que o navegador exige cabeçalho CORS para liberar as respostas.
  // Sem isso o mapa não recebe nem a geometria nem os indicadores.
  app.register(cors, {
    origin: env.CORS_ORIGINS,
    methods: ['GET'],
  });

  // Registra as rotas da API
  app.register(indicadoresRoutes);
  app.register(geometriaRoutes);

  // Rota de health check
  app.get('/health', async () => ({ status: 'ok' }));

  return app;
}

module.exports = buildApp;
