"""
analise_espacial.py — Executa as consultas espaciais do PostGIS e produz o
documento de análise territorial.

Aplica `backend/sql/analise_espacial.sql` sobre o banco e consolida os
resultados em Markdown. As consultas operam sobre a topologia do território
— relações de vizinhança entre polígonos —, e não apenas sobre atributos das
tabelas, o que é o que justifica a exigência de um banco com extensão
espacial.

Pergunta central: as taxas altas de internação se distribuem aleatoriamente
pelo recorte, ou formam blocos contíguos de municípios limítrofes?

Uso:
    python analise_espacial.py --ano 2023
"""

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("espacial")

from config import BASE_DIR  # noqa: E402
from etl.loader import _criar_engine  # noqa: E402

SQL_ANALISE: Path = BASE_DIR.parent / "backend" / "sql" / "analise_espacial.sql"
RESULTADOS_DIR: Path = BASE_DIR.parent / "docs" / "resultados"

# Rótulos das classes de associação espacial local
CLASSES: dict = {
    "alta-alta": "Taxa alta cercada de taxas altas (aglomerado)",
    "baixa-baixa": "Taxa baixa cercada de taxas baixas (aglomerado)",
    "alta-baixa": "Taxa alta isolada entre vizinhos de taxa baixa (outlier)",
    "baixa-alta": "Taxa baixa cercada de taxas altas (outlier)",
}


def _parse_args() -> argparse.Namespace:
    """Analisa os argumentos de linha de comando."""
    parser = argparse.ArgumentParser(
        description="Executa as consultas espaciais e gera o relatório territorial."
    )
    parser.add_argument("--ano", type=int, required=True, help="Ano de competência.")
    return parser.parse_args()


def _decimal(valor, casas: int = 1) -> str:
    """Formata um número decimal no padrão brasileiro."""
    if valor is None or pd.isna(valor):
        return "—"
    texto = f"{float(valor):,.{casas}f}"
    return texto.replace(",", "@").replace(".", ",").replace("@", ".")


def aplicar_views(engine) -> None:
    """Cria ou atualiza as views espaciais no banco."""
    sql = SQL_ANALISE.read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.execute(text(sql))
    logger.info("Views espaciais aplicadas a partir de %s", SQL_ANALISE.name)


def consultar(engine, sql: str) -> pd.DataFrame:
    """Executa uma consulta e devolve o resultado como DataFrame."""
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn)


def main() -> None:
    """Ponto de entrada do script."""
    args = _parse_args()
    engine = _criar_engine()
    aplicar_views(engine)

    metricas = consultar(engine, "SELECT * FROM metricas_territoriais")
    vizinhos = consultar(
        engine,
        """
        SELECT nome, COUNT(*) AS vizinhos
        FROM vizinhos_municipios
        GROUP BY nome
        ORDER BY vizinhos DESC, nome
        """,
    )
    autocorrelacao = consultar(
        engine,
        """
        SELECT nome, taxa_por_100mil, qtd_vizinhos, taxa_media_vizinhos,
               diferenca, classificacao
        FROM autocorrelacao_espacial
        ORDER BY taxa_por_100mil DESC
        """,
    )

    total_pares = int(vizinhos["vizinhos"].sum())
    contagem_classes = autocorrelacao["classificacao"].value_counts()
    aglomerados = int(
        contagem_classes.get("alta-alta", 0) + contagem_classes.get("baixa-baixa", 0)
    )
    total_classificados = len(autocorrelacao)

    linhas = [
        f"# Análise espacial — Sudoeste do Paraná, {args.ano}",
        "",
        "> Gerado por `pipeline/analise_espacial.py`. Não editar manualmente.",
        "",
        "Consultas executadas em PostgreSQL com extensão PostGIS, sobre a malha "
        "municipal do IBGE armazenada em SRID 4674 (SIRGAS 2000). As definições "
        "estão em `backend/sql/analise_espacial.sql`.",
        "",
        "## 1. Métricas territoriais do recorte",
        "",
        "| Indicador | Valor | Consulta espacial |",
        "|-----------|-------|-------------------|",
    ]
    if not metricas.empty:
        linha = metricas.iloc[0]
        linhas += [
            f"| Municípios com geometria | {int(linha['municipios'])} | — |",
            f"| Área total | {_decimal(linha['area_km2'])} km² | `ST_Area(ST_Union(geometria)::geography)` |",
            f"| Perímetro do recorte | {_decimal(linha['perimetro_km'])} km | `ST_Perimeter(ST_Union(geometria)::geography)` |",
            f"| Pares de municípios limítrofes | {total_pares} | `ST_Touches` |",
        ]

    linhas += [
        "",
        "## 2. Vizinhança por contiguidade",
        "",
        "Municípios com maior número de limítrofes, obtidos por `ST_Touches` "
        "sobre os polígonos municipais:",
        "",
        "| Município | Municípios limítrofes |",
        "|-----------|-----------------------|",
    ]
    for _, linha in vizinhos.head(10).iterrows():
        linhas.append(f"| {linha['nome']} | {int(linha['vizinhos'])} |")

    linhas += [
        "",
        f"Média de {_decimal(vizinhos['vizinhos'].mean())} municípios limítrofes por município.",
        "",
        "## 3. Autocorrelação espacial das taxas",
        "",
        "Cada município tem sua taxa comparada à média das taxas dos municípios "
        "limítrofes, tomando a mediana regional como referência de corte. A "
        "classificação segue a lógica dos indicadores locais de associação "
        "espacial (LISA).",
        "",
        "| Classificação | Municípios | % | Interpretação |",
        "|---------------|------------|---|---------------|",
    ]
    for classe, descricao in CLASSES.items():
        quantidade = int(contagem_classes.get(classe, 0))
        linhas.append(
            f"| `{classe}` | {quantidade} | "
            f"{_decimal(quantidade / total_classificados * 100)}% | {descricao} |"
        )

    linhas += [
        "",
        (
            f"**{aglomerados} dos {total_classificados} municípios "
            f"({_decimal(aglomerados / total_classificados * 100)}%) estão em "
            "aglomerados** — isto é, têm taxa do mesmo lado da mediana que a "
            "média de seus vizinhos. Sob distribuição aleatória, esperar-se-ia "
            "algo próximo de 50%."
        ),
        "",
        "### 3.1 Municípios por taxa, com o contexto de vizinhança",
        "",
        "| Município | Taxa/100 mil | Vizinhos | Média dos vizinhos | Diferença | Classificação |",
        "|-----------|--------------|----------|--------------------|-----------|---------------|",
    ]
    for _, linha in autocorrelacao.iterrows():
        linhas.append(
            f"| {linha['nome']} | {_decimal(linha['taxa_por_100mil'])} | "
            f"{int(linha['qtd_vizinhos'])} | {_decimal(linha['taxa_media_vizinhos'])} | "
            f"{_decimal(linha['diferenca'])} | `{linha['classificacao']}` |"
        )
    linhas.append("")

    RESULTADOS_DIR.mkdir(parents=True, exist_ok=True)
    destino = RESULTADOS_DIR / f"analise_espacial_{args.ano}.md"
    destino.write_text("\n".join(linhas), encoding="utf-8")
    logger.info("Análise espacial gravada em %s", destino)


if __name__ == "__main__":
    main()
