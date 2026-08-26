/**
 * Serviço de comunicação com a API backend do Longevus.
 *
 * A URL base é configurada via variável de ambiente VITE_API_BASE_URL.
 * Exemplo: http://localhost:3000
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3000';

/**
 * Busca o GeoJSON com a malha territorial dos municípios.
 * Endpoint: GET /api/geometria
 *
 * @returns {Promise<Object>} FeatureCollection do GeoJSON
 */
export async function buscarGeometria() {
  const resposta = await fetch(`${BASE_URL}/api/geometria`);

  if (!resposta.ok) {
    throw new Error(`Erro ao buscar geometria: ${resposta.status} ${resposta.statusText}`);
  }

  return resposta.json();
}

/**
 * Busca os indicadores agregados por município com filtros opcionais.
 * Endpoint: GET /api/indicadores
 *
 * @param {Object} filtros - { cid_capitulo, sexo, faixa_etaria }
 * @returns {Promise<Object>} { dados: [{ codigo_ibge, total_atendimentos, valor_total, populacao, taxa_por_100mil }] }
 */
export async function buscarIndicadores(filtros = {}) {
  // Monta os query params removendo valores vazios
  const params = new URLSearchParams();
  Object.entries(filtros).forEach(([chave, valor]) => {
    if (valor !== '' && valor !== null && valor !== undefined) {
      params.append(chave, valor);
    }
  });

  const query = params.toString() ? `?${params.toString()}` : '';
  const resposta = await fetch(`${BASE_URL}/api/indicadores${query}`);

  if (!resposta.ok) {
    throw new Error(`Erro ao buscar indicadores: ${resposta.status} ${resposta.statusText}`);
  }

  return resposta.json();
}
