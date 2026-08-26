/**
 * Testes da combinação entre geometria e indicadores.
 *
 * Validam que todos os municípios da malha permanecem no resultado, mesmo
 * sem indicador correspondente — condição do cenário "Município sem
 * população cadastrada" de `spec/behaviors/mapa_coroplético.feature` e do
 * contrato descrito em `spec/api-spec.md`, que exige os 42 municípios em
 * qualquer combinação de filtros.
 */

import { describe, expect, it } from 'vitest';

import {
  combinarDadosGeo,
  obterMaximoAtendimentos,
  obterMaximoTaxa,
  obterTaxas,
} from './mergeGeoData';

/** Malha reduzida, com três municípios reais do recorte. */
const GEOJSON = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      properties: { codigo_ibge: '410840', nome: 'Francisco Beltrão' },
      geometry: { type: 'Polygon', coordinates: [] },
    },
    {
      type: 'Feature',
      properties: { codigo_ibge: '412860', nome: 'Verê' },
      geometry: { type: 'Polygon', coordinates: [] },
    },
    {
      type: 'Feature',
      properties: { codigo_ibge: '411850', nome: 'Pato Branco' },
      geometry: { type: 'Polygon', coordinates: [] },
    },
  ],
};

const INDICADORES = [
  {
    codigo_ibge: '410840',
    total_atendimentos: 9730,
    valor_total: 14293187.45,
    populacao: 96666,
    taxa_por_100mil: 10065.6,
  },
  {
    codigo_ibge: '412860',
    total_atendimentos: 1056,
    valor_total: 1204418.2,
    populacao: 7932,
    taxa_por_100mil: 13313.2,
  },
];

describe('combinarDadosGeo', () => {
  it('devolve o geojson inalterado quando não há malha', () => {
    expect(combinarDadosGeo(null, INDICADORES)).toBeNull();
    expect(combinarDadosGeo({}, INDICADORES)).toEqual({});
  });

  it('injeta os indicadores nas propriedades da feição correspondente', () => {
    const resultado = combinarDadosGeo(GEOJSON, INDICADORES);
    const beltrao = resultado.features[0].properties;

    expect(beltrao.nome).toBe('Francisco Beltrão');
    expect(beltrao.total_atendimentos).toBe(9730);
    expect(beltrao.populacao).toBe(96666);
    expect(beltrao.taxa_por_100mil).toBe(10065.6);
  });

  it('preserva municípios sem indicador, com propriedades nulas', () => {
    const resultado = combinarDadosGeo(GEOJSON, INDICADORES);

    // Nenhuma feição pode desaparecer: a malha precisa renderizar completa
    expect(resultado.features).toHaveLength(3);

    const patoBranco = resultado.features[2].properties;
    expect(patoBranco.nome).toBe('Pato Branco');
    expect(patoBranco.total_atendimentos).toBeNull();
    expect(patoBranco.taxa_por_100mil).toBeNull();
  });

  it('não modifica o geojson original', () => {
    combinarDadosGeo(GEOJSON, INDICADORES);

    expect(GEOJSON.features[0].properties).toEqual({
      codigo_ibge: '410840',
      nome: 'Francisco Beltrão',
    });
  });

  it('tolera lista de indicadores ausente', () => {
    const resultado = combinarDadosGeo(GEOJSON, null);

    expect(resultado.features).toHaveLength(3);
    expect(resultado.features[0].properties.taxa_por_100mil).toBeNull();
  });
});

describe('obterMaximoTaxa', () => {
  it('devolve zero quando não há feições', () => {
    expect(obterMaximoTaxa(null)).toBe(0);
    expect(obterMaximoTaxa({ features: [] })).toBe(0);
  });

  it('devolve a maior taxa, ignorando municípios sem dado', () => {
    const resultado = combinarDadosGeo(GEOJSON, INDICADORES);

    // Verê tem a maior taxa, ainda que não o maior número absoluto
    expect(obterMaximoTaxa(resultado)).toBe(13313.2);
  });
});

describe('obterTaxas', () => {
  it('devolve lista vazia quando não há feições', () => {
    expect(obterTaxas(null)).toEqual([]);
    expect(obterTaxas({ features: [] })).toEqual([]);
  });

  it('extrai apenas as taxas calculáveis', () => {
    // A amostra que alimenta os quintis não pode incluir os municípios sem
    // taxa: eles recebem a cor neutra e deslocariam os cortes dos demais
    const taxas = obterTaxas(combinarDadosGeo(GEOJSON, INDICADORES));

    expect(taxas.every((t) => typeof t === 'number')).toBe(true);
    expect(taxas).toContain(13313.2);
  });
});

describe('obterMaximoAtendimentos', () => {
  it('devolve o maior valor absoluto', () => {
    const resultado = combinarDadosGeo(GEOJSON, INDICADORES);

    // O máximo absoluto é de outro município que não o de maior taxa —
    // é justamente essa divergência que torna a normalização necessária
    expect(obterMaximoAtendimentos(resultado)).toBe(9730);
  });
});
