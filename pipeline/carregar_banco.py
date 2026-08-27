"""
carregar_banco.py — Carrega no banco os dados já processados pelo pipeline.

Diferente de `main.py`, que executa o ciclo completo a partir do DATASUS,
este script parte do Parquet produzido por `caracterizar_base.py`. Isso
permite recarregar o banco sem repetir download e transformação, o que é
conveniente ao reconstruir o ambiente ou ao medir o tempo de carga isolado
das demais etapas.

Ordem de carga, ditada pelas chaves estrangeiras:
  1. `municipios_sudoeste`  — recorte territorial
  2. Geometrias             — malha do IBGE na coluna espacial
  3. `populacao_municipio`  — denominador das taxas
  4. `internacoes`          — fato principal

Uso:
    python carregar_banco.py --ano 2023
    python carregar_banco.py --ano 2023 --limpar
"""

import argparse
import logging
import sys
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("carga")

from config import DATA_DIR  # noqa: E402
from etl.loader import (  # noqa: E402
    _criar_engine,
    carregar_geometrias,
    carregar_internacoes,
    carregar_municipios,
    carregar_populacao,
)

PROCESSED_DIR: Path = DATA_DIR / "processed"


def _parse_args() -> argparse.Namespace:
    """Analisa os argumentos de linha de comando."""
    parser = argparse.ArgumentParser(
        description="Carrega no banco os dados já processados pelo pipeline."
    )
    parser.add_argument("--ano", type=int, required=True, help="Ano de competência.")
    parser.add_argument(
        "--limpar",
        action="store_true",
        help="Esvazia a tabela de internações antes da carga, evitando duplicação.",
    )
    return parser.parse_args()


def limpar_internacoes() -> None:
    """Remove os registros de internações previamente carregados."""
    engine = _criar_engine()
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE internacoes RESTART IDENTITY"))
    logger.info("Tabela `internacoes` esvaziada.")


def main() -> None:
    """Ponto de entrada do script."""
    args = _parse_args()

    caminho = PROCESSED_DIR / f"internacoes_{args.ano}.parquet"
    if not caminho.exists():
        logger.error(
            "Base não encontrada em %s. Execute antes: python caracterizar_base.py --ano %d",
            caminho,
            args.ano,
        )
        sys.exit(1)

    df = pd.read_parquet(caminho)
    logger.info("Base carregada do Parquet — %d registros.", len(df))

    if args.limpar:
        limpar_internacoes()

    inicio = time.time()
    total_municipios = carregar_municipios()
    total_geometrias = carregar_geometrias()
    total_populacao = carregar_populacao()
    total_internacoes = carregar_internacoes(df)
    duracao = time.time() - inicio

    logger.info("=" * 60)
    logger.info(
        "Carga concluída em %.1fs — %d municípios, %d geometrias, "
        "%d denominadores populacionais, %d internações.",
        duracao,
        total_municipios,
        total_geometrias,
        total_populacao,
        total_internacoes,
    )
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
