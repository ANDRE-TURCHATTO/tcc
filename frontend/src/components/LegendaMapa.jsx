/**
 * LegendaMapa
 *
 * Exibe a legenda de cores do mapa coroplético.
 * Cada nível da escala de amarelo → vermelho é apresentado com seu rótulo,
 * expresso na unidade do indicador que colore o mapa: internações por 100 mil
 * habitantes (RF-11).
 */

import { obterIntervaloLegenda } from '../utils/colorScale';

/**
 * @param {{ cortes: Array<number> }} props - cortes quantílicos em vigor
 */
export default function LegendaMapa({ cortes }) {
  const intervalos = obterIntervaloLegenda(cortes);

  return (
    <div className="legenda-mapa">
      <p className="legenda-titulo">
        Internações por 100 mil hab.
      </p>
      <ul className="legenda-lista">
        {intervalos.map((item) => (
          <li key={item.rotulo} className="legenda-item">
            <span
              className="legenda-cor"
              style={{ backgroundColor: item.cor }}
              aria-hidden="true"
            />
            <span className="legenda-rotulo">{item.rotulo}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
