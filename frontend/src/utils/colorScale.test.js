/**
 * Testes da escala de cores do mapa coroplético.
 *
 * Validam o RF-11 — a coloração usa a taxa por 100 mil habitantes —, o RF-19
 * — os cortes são os quintis da distribuição observada — e os cenários
 * "Coloração normalizada pela população", "Cortes da escala por quintis da
 * distribuição", "Município sem população cadastrada" e "Nenhum resultado
 * para os filtros" de `spec/behaviors/mapa_coroplético.feature`.
 *
 * Os valores usados são os observados na competência de 2023, para que o
 * teste falhe caso a regra de normalização seja revertida.
 */

import { describe, expect, it } from 'vitest';

import { calcularCor, calcularCortes, obterIntervaloLegenda } from './colorScale';

const COR_SEM_DADOS = '#d9d9d9';
const ESCALA = ['#ffffb2', '#fecc5c', '#fd8d3c', '#f03b20', '#bd0026'];

// Extremos observados no recorte em 2023: Verê no topo, Itapejara no fim
const TAXA_MAXIMA = 13313.2;
const TAXA_MINIMA = 5476.3;

/** Amostra sintética uniforme, cujos quintis são conhecidos de antemão. */
const AMOSTRA_1_A_100 = Array.from({ length: 100 }, (_, i) => i + 1);

describe('calcularCortes', () => {
  it('devolve quatro cortes em ordem crescente', () => {
    const cortes = calcularCortes(AMOSTRA_1_A_100);

    expect(cortes).toHaveLength(4);
    expect([...cortes].sort((a, b) => a - b)).toEqual(cortes);
  });

  it('calcula os quintis da distribuição', () => {
    const cortes = calcularCortes(AMOSTRA_1_A_100);

    expect(cortes[0]).toBeCloseTo(20.8, 1);
    expect(cortes[3]).toBeCloseTo(80.2, 1);
  });

  it('discrimina quando a distribuição não parte de zero', () => {
    // É o caso real de 2023: a menor taxa é 41% da maior. Com cortes
    // proporcionais ao máximo, os dois níveis mais claros ficariam vazios.
    const taxas = [5476.3, 6520.3, 8596.8, 10065.6, 13313.2];
    const cortes = calcularCortes(taxas);

    // Todos os cortes ficam dentro do intervalo observado
    expect(cortes[0]).toBeGreaterThan(TAXA_MINIMA);
    expect(cortes[3]).toBeLessThan(TAXA_MAXIMA);

    // E o menor corte supera 20% do máximo, que é onde a escala antiga cortava
    expect(cortes[0]).toBeGreaterThan(TAXA_MAXIMA * 0.2);
  });

  it('ignora municípios sem taxa calculável', () => {
    const comBuracos = [null, 5476.3, undefined, 6520.3, 8596.8, 10065.6, 13313.2, NaN];

    expect(calcularCortes(comBuracos)).toEqual(
      calcularCortes([5476.3, 6520.3, 8596.8, 10065.6, 13313.2]),
    );
  });

  it('devolve lista vazia quando não há taxa alguma', () => {
    expect(calcularCortes([])).toEqual([]);
    expect(calcularCortes([null, undefined])).toEqual([]);
    expect(calcularCortes(null)).toEqual([]);
  });

  it('não depende da ordem de entrada', () => {
    const taxas = [13313.2, 5476.3, 10065.6, 6520.3, 8596.8];
    const embaralhada = [8596.8, 13313.2, 6520.3, 10065.6, 5476.3];

    expect(calcularCortes(embaralhada)).toEqual(calcularCortes(taxas));
  });
});

describe('calcularCor', () => {
  const CORTES = calcularCortes(AMOSTRA_1_A_100);

  it('devolve a cor neutra quando a taxa é nula', () => {
    // Cenário: município sem população cadastrada
    expect(calcularCor(null, CORTES)).toBe(COR_SEM_DADOS);
    expect(calcularCor(undefined, CORTES)).toBe(COR_SEM_DADOS);
  });

  it('devolve a cor neutra quando não há cortes definidos', () => {
    // Cenário "Nenhum resultado para os filtros"
    expect(calcularCor(1000, [])).toBe(COR_SEM_DADOS);
    expect(calcularCor(1000, null)).toBe(COR_SEM_DADOS);
  });

  it('colore no nível mais alto o município de maior taxa', () => {
    const cortes = calcularCortes([TAXA_MINIMA, TAXA_MAXIMA]);

    expect(calcularCor(TAXA_MAXIMA, cortes)).toBe(ESCALA[4]);
  });

  it('respeita as bordas exatas de cada nível', () => {
    const cortes = [200, 400, 600, 800];

    // Cada corte pertence ao nível que ele fecha
    expect(calcularCor(200, cortes)).toBe(ESCALA[0]);
    expect(calcularCor(200.01, cortes)).toBe(ESCALA[1]);
    expect(calcularCor(400, cortes)).toBe(ESCALA[1]);
    expect(calcularCor(400.01, cortes)).toBe(ESCALA[2]);
    expect(calcularCor(600, cortes)).toBe(ESCALA[2]);
    expect(calcularCor(600.01, cortes)).toBe(ESCALA[3]);
    expect(calcularCor(800, cortes)).toBe(ESCALA[3]);
    expect(calcularCor(800.01, cortes)).toBe(ESCALA[4]);
  });

  it('distingue taxa zero de ausência de dado', () => {
    // Zero é informação: o município existe na base e não teve internações no
    // filtro corrente, e por isso recebe o tom mais claro da escala. A cor
    // neutra fica reservada a quem não tem taxa calculável — município sem
    // população cadastrada.
    expect(calcularCor(0, CORTES)).toBe(ESCALA[0]);
    expect(calcularCor(null, CORTES)).toBe(COR_SEM_DADOS);
  });

  /**
   * Cenário "Cortes da escala por quintis da distribuição": com 42 municípios
   * e cinco níveis, cada cor recebe entre 7 e 10 deles, e nenhum nível fica
   * sem uso. É esta propriedade que a escala proporcional ao máximo não tinha.
   */
  it('distribui os 42 municípios entre os cinco níveis', () => {
    const taxas = Array.from({ length: 42 }, (_, i) =>
      TAXA_MINIMA + ((TAXA_MAXIMA - TAXA_MINIMA) * i) / 41);
    const cortes = calcularCortes(taxas);

    const contagem = ESCALA.map(
      (cor) => taxas.filter((t) => calcularCor(t, cortes) === cor).length);

    expect(contagem.every((n) => n >= 7 && n <= 10)).toBe(true);
    expect(contagem.reduce((a, b) => a + b, 0)).toBe(42);
  });

  /**
   * Cenário "Coloração normalizada pela população", com os números reais de
   * 2023. Verê tem menos internações em termos absolutos que Pato Branco,
   * mas taxa muito maior. Se o mapa voltasse a colorir pelo absoluto, este
   * teste falharia.
   */
  it('colore Verê mais intensamente que Pato Branco', () => {
    const vere = { internacoes: 1056, populacao: 7932 };
    const patoBranco = { internacoes: 7895, populacao: 91836 };

    const taxaVere = (vere.internacoes / vere.populacao) * 100000;
    const taxaPatoBranco = (patoBranco.internacoes / patoBranco.populacao) * 100000;

    // Pato Branco tem 7,5 vezes mais internações em números absolutos
    expect(patoBranco.internacoes).toBeGreaterThan(vere.internacoes);
    // ...e ainda assim uma taxa menor
    expect(taxaVere).toBeGreaterThan(taxaPatoBranco);

    const cortes = calcularCortes([taxaPatoBranco, taxaVere, 9000, 10000, 11000]);

    expect(ESCALA.indexOf(calcularCor(taxaVere, cortes)))
      .toBeGreaterThan(ESCALA.indexOf(calcularCor(taxaPatoBranco, cortes)));
  });
});

describe('obterIntervaloLegenda', () => {
  it('devolve apenas "Sem dados" quando não há cortes', () => {
    expect(obterIntervaloLegenda([])).toEqual([
      { cor: COR_SEM_DADOS, rotulo: 'Sem dados' },
    ]);
    expect(obterIntervaloLegenda(null)).toEqual([
      { cor: COR_SEM_DADOS, rotulo: 'Sem dados' },
    ]);
  });

  it('devolve os cinco níveis da escala mais a cor neutra', () => {
    const intervalos = obterIntervaloLegenda(calcularCortes(AMOSTRA_1_A_100));

    expect(intervalos).toHaveLength(6);
    expect(intervalos.map((item) => item.cor)).toEqual([...ESCALA, COR_SEM_DADOS]);
  });

  it('rotula com os cortes calculados, no padrão brasileiro', () => {
    const intervalos = obterIntervaloLegenda([2000, 4000, 6000, 8000]);

    expect(intervalos[0].rotulo).toBe('Até 2.000');
    expect(intervalos[3].rotulo).toBe('Até 8.000');
    expect(intervalos[4].rotulo).toBe('Acima de 8.000');
  });
});
