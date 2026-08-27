/**
 * Escala de cores do mapa coroplético.
 *
 * A coloração usa a **taxa de internações por 100 mil habitantes**, não o
 * número absoluto de atendimentos (RF-11). Colorir pelo absoluto faria o mapa
 * reproduzir a distribuição populacional da região: os municípios mais
 * populosos apareceriam sempre no extremo da escala, independentemente do
 * padrão de utilização dos serviços de saúde.
 *
 * Os cortes são os **quintis da distribuição observada** no conjunto filtrado
 * (RF-19). Cortes proporcionais ao máximo — 20%, 40%, 60%, 80% dele — só
 * discriminam quando a distribuição parte de perto de zero, e não é o caso
 * aqui: em 2023 a menor taxa municipal já era 41% da maior, de modo que os
 * dois níveis mais claros da escala nunca eram usados e quase toda a região
 * aparecia em vermelho.
 *
 * A contrapartida é declarada: como os cortes dependem do conjunto filtrado,
 * as cores de dois mapas com filtros diferentes não são comparáveis entre si.
 * O valor numérico no tooltip é que permanece comparável.
 */

/** Escala sequencial amarelo → vermelho, cinco níveis. */
const ESCALA = ['#ffffb2', '#fecc5c', '#fd8d3c', '#f03b20', '#bd0026'];

/** Cor aplicada a municípios sem dado disponível. */
const COR_SEM_DADOS = '#d9d9d9';

/** Quantis que separam os cinco níveis da escala. */
const QUANTIS = [0.2, 0.4, 0.6, 0.8];

/**
 * Quantil de uma amostra já ordenada, por interpolação linear entre os dois
 * valores vizinhos da posição — o mesmo método do `numpy.percentile` padrão.
 *
 * @param {Array<number>} ordenada - amostra em ordem crescente
 * @param {number} q - quantil desejado, entre 0 e 1
 * @returns {number}
 */
function quantil(ordenada, q) {
  if (ordenada.length === 1) return ordenada[0];

  const posicao = (ordenada.length - 1) * q;
  const inferior = Math.floor(posicao);
  const superior = Math.ceil(posicao);

  if (inferior === superior) return ordenada[inferior];
  return ordenada[inferior] + (ordenada[superior] - ordenada[inferior]) * (posicao - inferior);
}

/**
 * Calcula os quatro cortes que separam os cinco níveis da escala.
 *
 * Municípios sem taxa calculável ficam fora do cálculo: eles recebem a cor
 * neutra e não devem deslocar os cortes dos demais.
 *
 * @param {Array<number|null>} taxas - taxas por 100 mil habitantes
 * @returns {Array<number>} quatro cortes em ordem crescente, ou [] se não houver dado
 */
export function calcularCortes(taxas) {
  const validas = (taxas || [])
    .filter((t) => typeof t === 'number' && Number.isFinite(t))
    .sort((a, b) => a - b);

  if (validas.length === 0) return [];

  return QUANTIS.map((q) => quantil(validas, q));
}

/**
 * Calcula a cor coroplética de um município a partir da sua taxa de
 * internações por 100 mil habitantes.
 *
 * Cada corte pertence ao nível que ele fecha: uma taxa exatamente igual ao
 * primeiro corte recebe o tom mais claro.
 *
 * @param {number|null} taxa - taxa_por_100mil do município
 * @param {Array<number>} cortes - cortes devolvidos por `calcularCortes`
 * @returns {string} cor em hexadecimal
 */
export function calcularCor(taxa, cortes) {
  if (taxa === null || taxa === undefined || !Number.isFinite(taxa)) {
    return COR_SEM_DADOS;
  }
  if (!Array.isArray(cortes) || cortes.length === 0) {
    return COR_SEM_DADOS;
  }

  const nivel = cortes.findIndex((corte) => taxa <= corte);
  return nivel === -1 ? ESCALA[ESCALA.length - 1] : ESCALA[nivel];
}

/**
 * Formata uma taxa para exibição no padrão brasileiro.
 *
 * @param {number} taxa
 * @returns {string}
 */
function formatarTaxa(taxa) {
  return new Intl.NumberFormat('pt-BR', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(Math.round(taxa));
}

/**
 * Retorna os intervalos da legenda a partir dos cortes em vigor.
 *
 * Os rótulos são expressos na unidade do indicador — internações por 100 mil
 * habitantes —, de modo que a legenda comunique o que está sendo colorido.
 *
 * @param {Array<number>} cortes - cortes devolvidos por `calcularCortes`
 * @returns {Array<{cor: string, rotulo: string}>}
 */
export function obterIntervaloLegenda(cortes) {
  if (!Array.isArray(cortes) || cortes.length === 0) {
    return [{ cor: COR_SEM_DADOS, rotulo: 'Sem dados' }];
  }

  const intervalos = cortes.map((corte, indice) => ({
    cor: ESCALA[indice],
    rotulo: `Até ${formatarTaxa(corte)}`,
  }));

  return [
    ...intervalos,
    {
      cor: ESCALA[ESCALA.length - 1],
      rotulo: `Acima de ${formatarTaxa(cortes[cortes.length - 1])}`,
    },
    { cor: COR_SEM_DADOS, rotulo: 'Sem dados' },
  ];
}
