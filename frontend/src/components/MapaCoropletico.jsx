/**
 * MapaCoropletico
 *
 * Componente principal do mapa interativo.
 * Renderiza o GeoJSON dos municípios do Sudoeste do Paraná usando Leaflet,
 * aplica coloração coroplética conforme a taxa de internações por 100 mil
 * habitantes (RF-11) e exibe tooltip com os demais indicadores.
 */

import { useRef } from 'react';
import { MapContainer, TileLayer, GeoJSON } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

import { calcularCor, calcularCortes } from '../utils/colorScale';
import { combinarDadosGeo, obterTaxas } from '../utils/mergeGeoData';
import LegendaMapa from './LegendaMapa';
import EstadoCarregamento from './EstadoCarregamento';

// Coordenadas centrais aproximadas do Sudoeste do Paraná
const CENTRO_SUDOESTE_PR = [-25.8, -52.9];
const ZOOM_INICIAL = 9;

/**
 * @param {{
 *   geojson: Object|null,
 *   indicadores: Array|null,
 *   carregandoGeo: boolean,
 *   carregandoIndicadores: boolean,
 *   erroGeo: Error|null,
 *   erroIndicadores: Error|null,
 *   semDados: boolean,
 * }} props
 */
export default function MapaCoropletico({
  geojson,
  indicadores,
  carregandoGeo,
  carregandoIndicadores,
  erroGeo,
  erroIndicadores,
  semDados,
}) {
  // Chave de remontagem da camada GeoJSON.
  //
  // O componente <GeoJSON> do react-leaflet cria a camada Leaflet uma única
  // vez: mudanças posteriores em `data` e `style` não repintam os polígonos.
  // A remontagem por `key` é o que força a repintura quando novos indicadores
  // chegam.
  //
  // O incremento acontece durante o render, e não em um efeito: um efeito só
  // roda depois da renderização, de modo que a chave nova chegaria um render
  // atrasada — justamente o render em que os indicadores aparecem. O resultado
  // seria o mapa permanecer cinza com a legenda já preenchida.
  const indicadoresAnteriores = useRef(null);
  const geojsonKey = useRef(0);
  if (indicadoresAnteriores.current !== indicadores) {
    indicadoresAnteriores.current = indicadores;
    geojsonKey.current += 1;
  }

  // Combina geometria com indicadores. A escala de cores é ancorada na maior
  // taxa observada, não no maior valor absoluto.
  const geoDados = combinarDadosGeo(geojson, indicadores || []);

  // Cortes quantílicos da distribuição corrente (RF-19). São recalculados a
  // cada conjunto de indicadores, de modo que os cinco níveis da escala
  // permaneçam em uso qualquer que seja o filtro aplicado.
  const cortes = calcularCortes(obterTaxas(geoDados));

  // Função de estilo aplicada a cada feature do GeoJSON
  function estilizarFeature(feature) {
    const taxa = feature.properties?.taxa_por_100mil;
    return {
      fillColor: calcularCor(taxa, cortes),
      weight: 1,
      opacity: 1,
      color: '#555',
      fillOpacity: 0.75,
    };
  }

  // Eventos de interação em cada município
  function aoPassarMouse(event) {
    event.layer.setStyle({
      weight: 2,
      color: '#333',
      fillOpacity: 0.9,
    });
    event.layer.bringToFront();
  }

  function onEachFeature(feature, layer) {
    const {
      nome,
      total_atendimentos,
      valor_total,
      populacao,
      taxa_por_100mil,
    } = feature.properties || {};

    // Formata os valores para o tooltip. A taxa vem primeiro por ser o
    // indicador que colore o mapa; o absoluto permanece à vista porque os
    // dois números juntos são o que torna a leitura interpretável.
    const inteiro = (valor) =>
      valor !== null && valor !== undefined
        ? new Intl.NumberFormat('pt-BR').format(valor)
        : 'Sem dados';

    const taxaFormatada =
      taxa_por_100mil !== null && taxa_por_100mil !== undefined
        ? `${new Intl.NumberFormat('pt-BR', {
            minimumFractionDigits: 1,
            maximumFractionDigits: 1,
          }).format(taxa_por_100mil)} / 100 mil hab.`
        : 'Sem dados';

    const valorFormatado =
      valor_total !== null && valor_total !== undefined
        ? new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(valor_total)
        : '—';

    layer.bindTooltip(
      `<div class="tooltip-info">
        <strong class="tooltip-municipio">${nome || 'Município'}</strong>
        <table class="tooltip-tabela">
          <tbody>
            <tr><td>Taxa de internação:</td><td><strong>${taxaFormatada}</strong></td></tr>
            <tr><td>Atendimentos:</td><td><strong>${inteiro(total_atendimentos)}</strong></td></tr>
            <tr><td>População:</td><td><strong>${inteiro(populacao)}</strong></td></tr>
            <tr><td>Valor total:</td><td><strong>${valorFormatado}</strong></td></tr>
          </tbody>
        </table>
      </div>`,
      { sticky: true }
    );

    layer.on({
      mouseover: aoPassarMouse,
      mouseout: (e) => {
        // Resetar estilo exige referência ao GeoJSON layer — usamos o evento
        const alvo = e.target;
        alvo.setStyle(estilizarFeature(feature));
      },
    });
  }

  // Estados de loading e erro
  if (carregandoGeo) {
    return <EstadoCarregamento tipo="carregando" mensagem="Carregando o mapa..." />;
  }

  if (erroGeo) {
    return (
      <EstadoCarregamento
        tipo="erro"
        mensagem="Não foi possível carregar a geometria do mapa. Verifique se a API está em execução."
      />
    );
  }

  if (erroIndicadores) {
    return (
      <EstadoCarregamento
        tipo="erro"
        mensagem="Erro ao buscar os indicadores. Tente atualizar o mapa novamente."
      />
    );
  }

  return (
    <div className="mapa-container">
      {/* Feedback de carregamento dos indicadores (overlay) */}
      {carregandoIndicadores && (
        <div className="mapa-overlay">
          <EstadoCarregamento tipo="carregando" mensagem="Atualizando indicadores..." />
        </div>
      )}

      {/* Mensagem quando nenhum dado é encontrado */}
      {semDados && (
        <div className="mapa-aviso">
          Nenhum dado encontrado para os filtros selecionados.
        </div>
      )}

      {/* Mapa Leaflet */}
      {geojson && (
        <MapContainer
          center={CENTRO_SUDOESTE_PR}
          zoom={ZOOM_INICIAL}
          style={{ height: '100%', width: '100%' }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <GeoJSON
            key={geojsonKey.current}
            data={geoDados}
            style={estilizarFeature}
            onEachFeature={onEachFeature}
          />
        </MapContainer>
      )}

      {/* Legenda */}
      <LegendaMapa cortes={cortes} />
    </div>
  );
}
