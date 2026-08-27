"""
gerar_resultados.py — Produz as tabelas de resultado a partir da base
transformada, para a seção de resultados do trabalho.

Consome o Parquet gerado por `caracterizar_base.py` e o denominador
populacional obtido por `baixar_populacao.py`, e escreve um documento
Markdown com:

  1. Perfil geral da base
  2. Top 10 capítulos CID-10 por volume de internações
  3. Distribuição por faixa etária e sexo
  4. Ranking dos municípios em valores absolutos e em taxa por 100 mil
     habitantes, lado a lado

A comparação entre os dois rankings do item 4 é o achado central: mostra
em que medida a leitura do mapa muda quando o indicador é normalizado pela
população residente.

Uso:
    python gerar_resultados.py --ano 2023
"""

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("resultados")

from config import BASE_DIR, DATA_DIR  # noqa: E402

PROCESSED_DIR: Path = DATA_DIR / "processed"
POPULACAO_CSV: Path = DATA_DIR / "populacao_municipio.csv"
RESULTADOS_DIR: Path = BASE_DIR.parent / "docs" / "resultados"

# Base populacional das taxas
BASE_TAXA: int = 100_000

# Rótulos dos capítulos CID-10, conforme a Classificação Estatística
# Internacional de Doenças e Problemas Relacionados à Saúde, 10ª revisão
CAPITULOS: dict = {
    "I": "Doenças infecciosas e parasitárias",
    "II": "Neoplasias (tumores)",
    "III": "Doenças do sangue e órgãos hematopoéticos",
    "IV": "Doenças endócrinas, nutricionais e metabólicas",
    "V": "Transtornos mentais e comportamentais",
    "VI": "Doenças do sistema nervoso",
    "VII": "Doenças do olho e anexos",
    "VIII": "Doenças do ouvido e da apófise mastoide",
    "IX": "Doenças do aparelho circulatório",
    "X": "Doenças do aparelho respiratório",
    "XI": "Doenças do aparelho digestivo",
    "XII": "Doenças da pele e do tecido subcutâneo",
    "XIII": "Doenças do sistema osteomuscular e conjuntivo",
    "XIV": "Doenças do aparelho geniturinário",
    "XV": "Gravidez, parto e puerpério",
    "XVI": "Afecções originadas no período perinatal",
    "XVII": "Malformações congênitas e anomalias cromossômicas",
    "XVIII": "Sintomas, sinais e achados anormais",
    "XIX": "Lesões, envenenamentos e causas externas",
    "XX": "Causas externas de morbidade e mortalidade",
    "XXI": "Fatores que influenciam o estado de saúde",
    "XXII": "Códigos para propósitos especiais",
}

FAIXAS: list = ["0-10", "11-20", "21-30", "31-40", "41-50", "51-60", "61+"]


def _parse_args() -> argparse.Namespace:
    """Analisa os argumentos de linha de comando."""
    parser = argparse.ArgumentParser(
        description="Gera as tabelas de resultado a partir da base transformada."
    )
    parser.add_argument("--ano", type=int, required=True, help="Ano de competência.")
    return parser.parse_args()


def _inteiro(valor) -> str:
    """Formata um inteiro com separador de milhar no padrão brasileiro."""
    return f"{int(valor):,}".replace(",", ".")


def _reais(valor) -> str:
    """Formata um valor monetário no padrão brasileiro."""
    texto = f"{float(valor):,.2f}"
    return "R$ " + texto.replace(",", "@").replace(".", ",").replace("@", ".")


def _decimal(valor, casas: int = 1) -> str:
    """Formata um número decimal com vírgula como separador."""
    return f"{float(valor):,.{casas}f}".replace(",", "@").replace(".", ",").replace("@", ".")


def carregar_dados(ano: int) -> tuple:
    """
    Carrega a base transformada e o denominador populacional.

    Args:
        ano (int): Ano de competência.

    Returns:
        tuple: DataFrame de internações e DataFrame de população.
    """
    caminho = PROCESSED_DIR / f"internacoes_{ano}.parquet"
    if not caminho.exists():
        raise FileNotFoundError(
            f"Base não encontrada em {caminho}. "
            f"Execute antes: python caracterizar_base.py --ano {ano}"
        )
    df = pd.read_parquet(caminho)

    if not POPULACAO_CSV.exists():
        raise FileNotFoundError(
            f"Denominador populacional não encontrado em {POPULACAO_CSV}. "
            "Execute antes: python baixar_populacao.py"
        )
    populacao = pd.read_csv(POPULACAO_CSV, dtype={"codigo_ibge": str})

    logger.info(
        "Base carregada — %d internações, %d municípios com população.",
        len(df),
        len(populacao),
    )
    return df, populacao


def secao_perfil(df: pd.DataFrame, populacao: pd.DataFrame, ano: int) -> list:
    """Monta a seção de perfil geral da base."""
    total = len(df)
    habitantes = int(populacao["populacao"].sum())
    taxa_geral = total / habitantes * BASE_TAXA
    return [
        "## 1. Perfil geral",
        "",
        "| Indicador | Valor |",
        "|-----------|-------|",
        f"| Internações analisadas | {_inteiro(total)} |",
        f"| Municípios do recorte | {populacao['codigo_ibge'].nunique()} |",
        f"| População residente (Censo IBGE 2022) | {_inteiro(habitantes)} |",
        f"| Taxa geral de internação | {_decimal(taxa_geral)} por 100 mil habitantes |",
        f"| Valor total das AIH | {_reais(df['valor_total'].sum())} |",
        f"| Valor médio por internação | {_reais(df['valor_total'].mean())} |",
        f"| Idade média | {_decimal(df['idade'].mean())} anos |",
        f"| Período | janeiro a dezembro de {ano} |",
        "",
    ]


def secao_capitulos(df: pd.DataFrame) -> list:
    """Monta a tabela dos dez capítulos CID-10 mais frequentes."""
    agregado = (
        df.groupby("cid_capitulo")
        .agg(
            internacoes=("cid_capitulo", "size"),
            valor_total=("valor_total", "sum"),
            valor_medio=("valor_total", "mean"),
        )
        .sort_values("internacoes", ascending=False)
    )
    total = len(df)

    linhas = [
        "## 2. Dez capítulos CID-10 mais frequentes",
        "",
        "| # | Capítulo | Descrição | Internações | % | Valor total | Valor médio |",
        "|---|----------|-----------|-------------|---|-------------|-------------|",
    ]
    for posicao, (capitulo, linha) in enumerate(agregado.head(10).iterrows(), start=1):
        linhas.append(
            f"| {posicao} | {capitulo} | {CAPITULOS.get(capitulo, '—')} | "
            f"{_inteiro(linha['internacoes'])} | "
            f"{_decimal(linha['internacoes'] / total * 100, 2)}% | "
            f"{_reais(linha['valor_total'])} | {_reais(linha['valor_medio'])} |"
        )
    cobertura = agregado.head(10)["internacoes"].sum() / total * 100
    linhas += [
        "",
        f"Os dez capítulos concentram {_decimal(cobertura, 2)}% das internações.",
        "",
    ]
    return linhas


def secao_faixa_sexo(df: pd.DataFrame) -> list:
    """Monta a distribuição cruzada por faixa etária e sexo."""
    tabela = pd.crosstab(df["faixa_etaria"], df["sexo"]).reindex(FAIXAS, fill_value=0)
    for coluna in ("F", "M"):
        if coluna not in tabela.columns:
            tabela[coluna] = 0
    tabela["Total"] = tabela["F"] + tabela["M"]
    total = int(tabela["Total"].sum())

    linhas = [
        "## 3. Distribuição por faixa etária e sexo",
        "",
        "| Faixa etária | Feminino | Masculino | Total | % do total |",
        "|--------------|----------|-----------|-------|------------|",
    ]
    for faixa, linha in tabela.iterrows():
        linhas.append(
            f"| {faixa} | {_inteiro(linha['F'])} | {_inteiro(linha['M'])} | "
            f"{_inteiro(linha['Total'])} | {_decimal(linha['Total'] / total * 100, 2)}% |"
        )
    linhas.append(
        f"| **Total** | **{_inteiro(tabela['F'].sum())}** | "
        f"**{_inteiro(tabela['M'].sum())}** | **{_inteiro(total)}** | **100,00%** |"
    )
    linhas.append("")
    return linhas


def montar_ranking(df: pd.DataFrame, populacao: pd.DataFrame) -> pd.DataFrame:
    """
    Monta o ranking de municípios em valores absolutos e em taxa.

    Args:
        df (pd.DataFrame): Base de internações.
        populacao (pd.DataFrame): Denominador populacional.

    Returns:
        pd.DataFrame: Ranking com as duas ordenações e a variação de posição.
    """
    agregado = (
        df.groupby("municipio_codigo")
        .agg(internacoes=("municipio_codigo", "size"), valor_total=("valor_total", "sum"))
        .reset_index()
        .rename(columns={"municipio_codigo": "codigo_ibge"})
    )
    ranking = populacao.merge(agregado, on="codigo_ibge", how="left")
    ranking[["internacoes", "valor_total"]] = ranking[
        ["internacoes", "valor_total"]
    ].fillna(0)
    ranking["taxa"] = ranking["internacoes"] / ranking["populacao"] * BASE_TAXA

    ranking["posicao_absoluto"] = (
        ranking["internacoes"].rank(ascending=False, method="min").astype(int)
    )
    ranking["posicao_taxa"] = (
        ranking["taxa"].rank(ascending=False, method="min").astype(int)
    )
    ranking["variacao"] = ranking["posicao_absoluto"] - ranking["posicao_taxa"]
    return ranking


def secao_ranking(ranking: pd.DataFrame) -> list:
    """Monta as tabelas de ranking absoluto e por taxa."""
    por_absoluto = ranking.sort_values("internacoes", ascending=False)
    por_taxa = ranking.sort_values("taxa", ascending=False)

    linhas = [
        "## 4. Ranking dos municípios",
        "",
        "### 4.1 Por número absoluto de internações",
        "",
        "| # | Município | População | Internações | Taxa/100 mil | Posição na taxa | Variação |",
        "|---|-----------|-----------|-------------|--------------|-----------------|----------|",
    ]
    for posicao, (_, linha) in enumerate(por_absoluto.head(10).iterrows(), start=1):
        variacao = int(linha["variacao"])
        marcador = f"+{variacao}" if variacao > 0 else str(variacao)
        linhas.append(
            f"| {posicao} | {linha['nome']} | {_inteiro(linha['populacao'])} | "
            f"{_inteiro(linha['internacoes'])} | {_decimal(linha['taxa'])} | "
            f"{int(linha['posicao_taxa'])}º | {marcador} |"
        )

    linhas += [
        "",
        "### 4.2 Por taxa de internação por 100 mil habitantes",
        "",
        "| # | Município | População | Internações | Taxa/100 mil | Posição no absoluto | Variação |",
        "|---|-----------|-----------|-------------|--------------|---------------------|----------|",
    ]
    for posicao, (_, linha) in enumerate(por_taxa.head(10).iterrows(), start=1):
        variacao = int(linha["variacao"])
        marcador = f"+{variacao}" if variacao > 0 else str(variacao)
        linhas.append(
            f"| {posicao} | {linha['nome']} | {_inteiro(linha['populacao'])} | "
            f"{_inteiro(linha['internacoes'])} | {_decimal(linha['taxa'])} | "
            f"{int(linha['posicao_absoluto'])}º | {marcador} |"
        )

    # Achado: quanto a normalização altera a leitura do território.
    # O coeficiente de Spearman equivale ao de Pearson calculado sobre os
    # postos, o que dispensa dependência adicional.
    correlacao = (
        ranking["internacoes"]
        .rank(ascending=False)
        .corr(ranking["taxa"].rank(ascending=False))
    )
    maior_queda = ranking.loc[ranking["variacao"].idxmin()]
    maior_subida = ranking.loc[ranking["variacao"].idxmax()]

    linhas += [
        "",
        "### 4.3 Efeito da normalização",
        "",
        f"- Correlação de postos (Spearman) entre os dois rankings: **{_decimal(correlacao, 3)}**",
        (
            f"- Maior queda ao normalizar: **{maior_queda['nome']}**, "
            f"do {int(maior_queda['posicao_absoluto'])}º lugar em absoluto para o "
            f"{int(maior_queda['posicao_taxa'])}º em taxa "
            f"({_inteiro(maior_queda['populacao'])} habitantes)"
        ),
        (
            f"- Maior subida ao normalizar: **{maior_subida['nome']}**, "
            f"do {int(maior_subida['posicao_absoluto'])}º lugar em absoluto para o "
            f"{int(maior_subida['posicao_taxa'])}º em taxa "
            f"({_inteiro(maior_subida['populacao'])} habitantes)"
        ),
        (
            f"- Amplitude das taxas: de {_decimal(ranking['taxa'].min())} a "
            f"{_decimal(ranking['taxa'].max())} internações por 100 mil habitantes "
            f"(razão de {_decimal(ranking['taxa'].max() / ranking['taxa'].min())} entre "
            "o extremo superior e o inferior)"
        ),
        "",
    ]
    return linhas


def main() -> None:
    """Ponto de entrada do script."""
    args = _parse_args()
    df, populacao = carregar_dados(args.ano)
    ranking = montar_ranking(df, populacao)

    conteudo = [
        f"# Resultados — internações do SIH/SUS no Sudoeste do Paraná, {args.ano}",
        "",
        "> Gerado por `pipeline/gerar_resultados.py`. Não editar manualmente.",
        "",
        "Fontes: DATASUS/SIH-SUS (AIH Reduzida, competências de janeiro a dezembro "
        f"de {args.ano}) e IBGE (Censo Demográfico 2022, população residente).",
        "",
    ]
    conteudo += secao_perfil(df, populacao, args.ano)
    conteudo += secao_capitulos(df)
    conteudo += secao_faixa_sexo(df)
    conteudo += secao_ranking(ranking)

    RESULTADOS_DIR.mkdir(parents=True, exist_ok=True)
    destino = RESULTADOS_DIR / f"resultados_{args.ano}.md"
    destino.write_text("\n".join(conteudo), encoding="utf-8")

    ranking_ordenado = ranking.sort_values("taxa", ascending=False)
    ranking_ordenado.to_csv(
        PROCESSED_DIR / f"ranking_municipios_{args.ano}.csv", index=False
    )

    logger.info("Resultados gravados em %s", destino)


if __name__ == "__main__":
    main()
