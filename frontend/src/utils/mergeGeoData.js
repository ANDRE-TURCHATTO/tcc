/**
 * Combina os dados do GeoJSON (geometria) com os indicadores retornados pela API.
 *
 * Para cada feature do GeoJSON, busca o indicador correspondente pelo
 * campo `codigo_ibge` e injeta os dados na propriedade `properties`.
 *
 * @param {Object} geojson - FeatureCollection retornado por GET /api/geometria
 * @param {Array}  indicadores - array de
 *   { codigo_ibge, total_atendimentos, valor_total, populacao, taxa_por_100mil }
 * @returns {Object} novo GeoJSON com propriedades enriquecidas
 */
export function combinarDadosGeo(geojson, indicadores) {
  if (!geojson || !geojson.features) return geojson;

  // Cria um mapa rápido: codigo_ibge → indicador
  const mapaIndicadores = {};
  if (Array.isArray(indicadores)) {
    indicadores.forEach((item) => {
      mapaIndicadores[item.codigo_ibge] = item;
    });
  }

  const featuresEnriquecidas = geojson.features.map((feature) => {
    const codigoIbge = feature.properties?.codigo_ibge;
    const indicador = mapaIndicadores[codigoIbge] || null;

    return {
      ...feature,
      properties: {
        ...feature.properties,
        total_atendimentos: indicador?.total_atendimentos ?? null,
        valor_total: indicador?.valor_total ?? null,
        populacao: indicador?.populacao ?? null,
        taxa_por_100mil: indicador?.taxa_por_100mil ?? null,
      },
    };
  });

  return {
    ...geojson,
    features: featuresEnriquecidas,
  };
}

/**
 * Extrai as taxas por 100 mil habitantes presentes no GeoJSON enriquecido.
 *
 * É essa amostra que alimenta o cálculo dos quintis da escala (RF-19).
 * Municípios sem taxa calculável ficam de fora: recebem a cor neutra e não
 * devem deslocar os cortes dos demais.
 *
 * @param {Object} geojson - GeoJSON já combinado com indicadores
 * @returns {Array<number>} taxas encontradas, na ordem das features
 */
export function obterTaxas(geojson) {
  if (!geojson?.features?.length) return [];

  return geojson.features
    .map((feature) => feature.properties?.taxa_por_100mil)
    .filter((taxa) => typeof taxa === 'number' && Number.isFinite(taxa));
}

/**
 * Retorna a maior taxa por 100 mil habitantes no GeoJSON enriquecido.
 *
 * Não define mais os cortes da escala, que passaram a ser quantílicos;
 * permanece como estatística de apoio.
 *
 * @param {Object} geojson - GeoJSON já combinado com indicadores
 * @returns {number} maior taxa encontrada (0 se não houver dados)
 */
export function obterMaximoTaxa(geojson) {
  if (!geojson?.features?.length) return 0;

  return geojson.features.reduce((maximo, feature) => {
    const taxa = feature.properties?.taxa_por_100mil;
    if (typeof taxa === 'number' && taxa > maximo) return taxa;
    return maximo;
  }, 0);
}

/**
 * Retorna o maior número absoluto de atendimentos no GeoJSON enriquecido.
 *
 * Não é usado para colorir o mapa — serve a exibições complementares que
 * precisem do valor absoluto.
 *
 * @param {Object} geojson - GeoJSON já combinado com indicadores
 * @returns {number} valor máximo encontrado (0 se não houver dados)
 */
export function obterMaximoAtendimentos(geojson) {
  if (!geojson?.features?.length) return 0;

  return geojson.features.reduce((maximo, feature) => {
    const total = feature.properties?.total_atendimentos;
    if (typeof total === 'number' && total > maximo) return total;
    return maximo;
  }, 0);
}
