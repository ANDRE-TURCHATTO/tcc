"""
main.py — Entry point do pipeline ETL Longevus.

Orquestra as etapas de extração, transformação e carga dos dados do SIH/SUS
para o banco de dados do Supabase.

Uso:
    python main.py --ano 2023 --mes 6
"""

import argparse
import logging
import sys
import time

# ---------------------------------------------------------------------------
# Configuração de logging antes de qualquer importação do projeto
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("pipeline")


def _parse_args() -> argparse.Namespace:
    """
    Analisa os argumentos de linha de comando.

    Returns:
        argparse.Namespace: Objeto com os atributos `ano` e `mes`.
    """
    parser = argparse.ArgumentParser(
        description="Pipeline ETL Longevus — extrai dados do SIH/SUS e carrega no Supabase."
    )
    parser.add_argument(
        "--ano",
        type=int,
        required=True,
        help="Ano de competência (ex: 2023).",
    )
    parser.add_argument(
        "--mes",
        type=int,
        required=True,
        choices=range(1, 13),
        metavar="MES (1-12)",
        help="Mês de competência (ex: 6 para junho).",
    )
    return parser.parse_args()


def executar_pipeline(ano: int, mes: int) -> None:
    """
    Orquestra as etapas do pipeline ETL.

    Etapas:
      1. Extração dos dados brutos do SIH/SUS via DATASUS (RF-01)
      2. Transformações: filtro, faixas etárias, capítulos CID (RF-02 a RF-04)
      3. Carga dos municípios e internações no Supabase (RF-05)

    Args:
        ano (int): Ano de competência.
        mes (int): Mês de competência.
    """
    from etl.extractor import extrair_dados
    from etl.loader import (
        carregar_internacoes,
        carregar_municipios,
        carregar_populacao,
    )
    from etl.transformer import transformar_detalhado

    inicio = time.time()
    logger.info("=" * 60)
    logger.info("Pipeline ETL Longevus iniciado — competência: %d/%02d", ano, mes)
    logger.info("=" * 60)

    # -----------------------------------------------------------------------
    # Etapa 1 — Extração (RF-01)
    # -----------------------------------------------------------------------
    logger.info("[1/3] Extraindo dados do SIH/SUS...")
    df_bruto = extrair_dados(ano=ano, mes=mes)
    logger.info("[1/3] Extração concluída — %d registros brutos.", len(df_bruto))

    # -----------------------------------------------------------------------
    # Etapa 2 — Transformação (RF-02, RF-03, RF-04, RF-16)
    # -----------------------------------------------------------------------
    logger.info("[2/3] Aplicando transformações...")
    df_transformado, estatisticas = transformar_detalhado(df_bruto)
    logger.info(
        "[2/3] Funil de transformação — brutos: %d | fora da região: %d | "
        "descartados por inconsistência: %d | prontos para carga: %d",
        estatisticas.brutos,
        estatisticas.fora_da_regiao,
        estatisticas.total_descartados,
        estatisticas.finais,
    )
    for motivo, quantidade in sorted(estatisticas.descartes.items()):
        logger.info("[2/3] Descarte '%s': %d registros.", motivo, quantidade)

    # -----------------------------------------------------------------------
    # Etapa 3 — Carga (RF-05)
    # -----------------------------------------------------------------------
    logger.info("[3/3] Carregando dados no Supabase...")
    total_municipios = carregar_municipios()
    total_populacao = carregar_populacao()
    total_internacoes = carregar_internacoes(df_transformado)
    logger.info(
        "[3/3] Carga concluída — %d municípios, %d denominadores populacionais, "
        "%d internações inseridas.",
        total_municipios,
        total_populacao,
        total_internacoes,
    )

    # -----------------------------------------------------------------------
    # Resumo final
    # -----------------------------------------------------------------------
    duracao = time.time() - inicio
    logger.info("=" * 60)
    logger.info(
        "Pipeline finalizado em %.1f segundos — %d registros processados.",
        duracao,
        total_internacoes,
    )
    logger.info("=" * 60)


def main() -> None:
    """Ponto de entrada principal do pipeline."""
    args = _parse_args()
    try:
        executar_pipeline(ano=args.ano, mes=args.mes)
    except Exception as exc:
        logger.error("Pipeline encerrado com erro: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
