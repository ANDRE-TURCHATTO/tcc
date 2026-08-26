"""
caracterizar_base.py — Executa extração e transformação de uma série de
competências do SIH/SUS e produz a caracterização quantitativa da base.

O script não depende do banco de dados: os registros transformados são
gravados em Parquet e o funil de processamento é exportado em Markdown,
servindo de insumo para a seção de resultados do trabalho.

Uso:
    python caracterizar_base.py --ano 2023
    python caracterizar_base.py --ano 2023 --mes-inicial 1 --mes-final 6
"""

import argparse
import logging
import sys
import time
from pathlib import Path

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("caracterizacao")

from config import BASE_DIR  # noqa: E402
from etl.extractor import extrair_dados  # noqa: E402
from etl.transformer import transformar_detalhado  # noqa: E402

PROCESSED_DIR: Path = BASE_DIR / "data" / "processed"
RESULTADOS_DIR: Path = BASE_DIR.parent / "docs" / "resultados"

# Ordem fixa dos motivos de descarte nas tabelas de saída
MOTIVOS: list = [
    "idade_indecifravel",
    "sexo_invalido",
    "cid_desconhecido",
    "valor_invalido",
]


def _parse_args() -> argparse.Namespace:
    """Analisa os argumentos de linha de comando."""
    parser = argparse.ArgumentParser(
        description=(
            "Extrai e transforma competências do SIH/SUS, gravando o resultado "
            "em Parquet e a caracterização da base em Markdown."
        )
    )
    parser.add_argument("--ano", type=int, required=True, help="Ano de competência.")
    parser.add_argument(
        "--mes-inicial", type=int, default=1, choices=range(1, 13), metavar="1-12"
    )
    parser.add_argument(
        "--mes-final", type=int, default=12, choices=range(1, 13), metavar="1-12"
    )
    return parser.parse_args()


def processar_competencia(ano: int, mes: int) -> tuple:
    """
    Executa extração e transformação de uma competência.

    Args:
        ano (int): Ano de competência.
        mes (int): Mês de competência.

    Returns:
        tuple: DataFrame transformado e o dicionário com as métricas do mês.
    """
    inicio = time.time()
    df_bruto = extrair_dados(ano=ano, mes=mes)
    df_final, estatisticas = transformar_detalhado(df_bruto)
    duracao = time.time() - inicio

    metricas = {
        "competencia": f"{ano}-{mes:02d}",
        "brutos": estatisticas.brutos,
        "fora_da_regiao": estatisticas.fora_da_regiao,
        "descartados": estatisticas.total_descartados,
        "carregados": estatisticas.finais,
        "valor_total": float(df_final["valor_total"].sum()) if len(df_final) else 0.0,
        "segundos": round(duracao, 1),
    }
    for motivo in MOTIVOS:
        metricas[motivo] = estatisticas.descartes.get(motivo, 0)

    logger.info(
        "Competência %s processada em %.1fs — %d brutos, %d carregados.",
        metricas["competencia"],
        duracao,
        metricas["brutos"],
        metricas["carregados"],
    )
    return df_final, metricas


def _formatar_inteiro(valor: int) -> str:
    """Formata um inteiro com separador de milhar no padrão brasileiro."""
    return f"{valor:,}".replace(",", ".")


def _formatar_reais(valor: float) -> str:
    """Formata um valor monetário no padrão brasileiro."""
    texto = f"{valor:,.2f}"
    return "R$ " + texto.replace(",", "@").replace(".", ",").replace("@", ".")


def gerar_relatorio(df_metricas: pd.DataFrame, ano: int, destino: Path) -> None:
    """
    Escreve a caracterização da base em Markdown.

    Args:
        df_metricas (pd.DataFrame): Métricas por competência.
        ano (int): Ano processado.
        destino (Path): Caminho do arquivo Markdown a gerar.
    """
    totais = df_metricas.sum(numeric_only=True)
    brutos = int(totais["brutos"])
    carregados = int(totais["carregados"])

    linhas = [
        f"# Caracterização da base — SIH/SUS {ano}",
        "",
        "> Gerado por `pipeline/caracterizar_base.py`. Não editar manualmente.",
        "",
        "## 1. Funil de processamento",
        "",
        "| Etapa | Registros | % dos brutos |",
        "|-------|-----------|--------------|",
        f"| Registros brutos (Paraná, grupo RD) | {_formatar_inteiro(brutos)} | 100,00% |",
        (
            f"| Descartados por residência fora do Sudoeste | "
            f"{_formatar_inteiro(int(totais['fora_da_regiao']))} | "
            f"{totais['fora_da_regiao'] / brutos * 100:.2f}% |"
        ),
        (
            f"| Descartados por inconsistência | "
            f"{_formatar_inteiro(int(totais['descartados']))} | "
            f"{totais['descartados'] / brutos * 100:.2f}% |"
        ),
        (
            f"| **Registros carregados** | **{_formatar_inteiro(carregados)}** | "
            f"**{carregados / brutos * 100:.2f}%** |"
        ),
        "",
        "## 2. Descartes por inconsistência, por motivo",
        "",
        "| Motivo | Registros | % dos brutos |",
        "|--------|-----------|--------------|",
    ]
    for motivo in MOTIVOS:
        quantidade = int(totais[motivo])
        linhas.append(
            f"| `{motivo}` | {_formatar_inteiro(quantidade)} | "
            f"{quantidade / brutos * 100:.4f}% |"
        )

    linhas += [
        "",
        "## 3. Detalhamento por competência",
        "",
        "| Competência | Brutos | Fora da região | Descartados | Carregados | Valor total | Tempo (s) |",
        "|-------------|--------|----------------|-------------|------------|-------------|-----------|",
    ]
    for _, linha in df_metricas.iterrows():
        linhas.append(
            f"| {linha['competencia']} | {_formatar_inteiro(int(linha['brutos']))} | "
            f"{_formatar_inteiro(int(linha['fora_da_regiao']))} | "
            f"{_formatar_inteiro(int(linha['descartados']))} | "
            f"{_formatar_inteiro(int(linha['carregados']))} | "
            f"{_formatar_reais(float(linha['valor_total']))} | {linha['segundos']} |"
        )

    linhas += [
        (
            f"| **Total** | **{_formatar_inteiro(brutos)}** | "
            f"**{_formatar_inteiro(int(totais['fora_da_regiao']))}** | "
            f"**{_formatar_inteiro(int(totais['descartados']))}** | "
            f"**{_formatar_inteiro(carregados)}** | "
            f"**{_formatar_reais(float(totais['valor_total']))}** | "
            f"**{totais['segundos']:.1f}** |"
        ),
        "",
    ]

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(linhas), encoding="utf-8")
    logger.info("Relatório gravado em %s", destino)


def main() -> None:
    """Ponto de entrada do script de caracterização."""
    args = _parse_args()
    if args.mes_final < args.mes_inicial:
        logger.error("--mes-final não pode ser menor que --mes-inicial.")
        sys.exit(1)

    quadros = []
    metricas = []
    for mes in range(args.mes_inicial, args.mes_final + 1):
        try:
            df_mes, metrica = processar_competencia(args.ano, mes)
        except Exception as exc:
            logger.error("Competência %d/%02d falhou: %s", args.ano, mes, exc)
            continue
        quadros.append(df_mes)
        metricas.append(metrica)

    if not quadros:
        logger.error("Nenhuma competência foi processada com sucesso.")
        sys.exit(1)

    df_total = pd.concat(quadros, ignore_index=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    caminho_parquet = PROCESSED_DIR / f"internacoes_{args.ano}.parquet"
    df_total.to_parquet(caminho_parquet, index=False)
    logger.info(
        "Parquet gravado em %s — %d registros, %.1f MB.",
        caminho_parquet,
        len(df_total),
        caminho_parquet.stat().st_size / 1e6,
    )

    df_metricas = pd.DataFrame(metricas)
    df_metricas.to_csv(PROCESSED_DIR / f"funil_{args.ano}.csv", index=False)
    gerar_relatorio(
        df_metricas, args.ano, RESULTADOS_DIR / f"caracterizacao_base_{args.ano}.md"
    )


if __name__ == "__main__":
    main()
