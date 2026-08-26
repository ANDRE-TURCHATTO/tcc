"""
baixar_populacao.py — Obtém a população residente dos municípios do Sudoeste
do Paraná junto ao IBGE e grava o arquivo de referência do denominador
populacional.

O denominador é necessário para expressar as internações em taxa por 100 mil
habitantes, evitando que o mapa coroplético reflita apenas o tamanho da
população de cada município.

Fontes disponíveis na API de agregados do IBGE:
  - `censo2022`: Censo Demográfico 2022, agregado 4709, variável 93
    (população residente recenseada)
  - `estimativa2024`: Estimativas da População 2024, agregado 6579,
    variável 9324

A série de estimativas não cobre 2023 — o Censo Demográfico 2022 substituiu
as estimativas naquele intervalo. Para as internações de 2023 adota-se por
padrão o Censo 2022, ano imediatamente anterior à competência analisada.

Uso:
    python baixar_populacao.py
    python baixar_populacao.py --fonte estimativa2024
"""

import argparse
import csv
import gzip
import json
import logging
import sys
import urllib.request
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("populacao")

from config import DATA_DIR, MUNICIPIOS_CSV  # noqa: E402

# Código do Paraná na base de localidades do IBGE
UF_PARANA: int = 41

URL_MUNICIPIOS_UF: str = (
    "https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios"
)
URL_AGREGADO: str = (
    "https://servicodados.ibge.gov.br/api/v3/agregados/{agregado}"
    "/periodos/{periodo}/variaveis/{variavel}?localidades=N6[{municipios}]"
)

# Fontes suportadas: agregado, variável, período e rótulo para documentação
FONTES: dict = {
    "censo2022": {
        "agregado": "4709",
        "variavel": "93",
        "periodo": "2022",
        "descricao": "IBGE — Censo Demográfico 2022, população residente",
    },
    "estimativa2024": {
        "agregado": "6579",
        "variavel": "9324",
        "periodo": "2024",
        "descricao": "IBGE — Estimativas da População 2024",
    },
}

TIMEOUT: int = 120
SAIDA_CSV: Path = DATA_DIR / "populacao_municipio.csv"


def _parse_args() -> argparse.Namespace:
    """Analisa os argumentos de linha de comando."""
    parser = argparse.ArgumentParser(
        description="Baixa a população dos municípios do Sudoeste do Paraná no IBGE."
    )
    parser.add_argument(
        "--fonte",
        choices=sorted(FONTES),
        default="censo2022",
        help="Fonte populacional do IBGE (padrão: censo2022).",
    )
    return parser.parse_args()


def _requisitar(url: str):
    """
    Executa uma requisição GET e devolve o JSON decodificado.

    A API do IBGE pode responder comprimida em gzip mesmo sem negociação
    explícita, portanto a descompressão é tratada aqui.
    """
    requisicao = urllib.request.Request(
        url, headers={"Accept": "application/json", "Accept-Encoding": "gzip"}
    )
    with urllib.request.urlopen(requisicao, timeout=TIMEOUT) as resposta:
        conteudo = resposta.read()
        if resposta.headers.get("Content-Encoding") == "gzip" or conteudo[:2] == b"\x1f\x8b":
            conteudo = gzip.decompress(conteudo)
    return json.loads(conteudo.decode("utf-8"))


def carregar_municipios_referencia() -> dict:
    """
    Lê o CSV de referência dos municípios do Sudoeste do Paraná.

    Returns:
        dict: Mapa de código IBGE de 6 dígitos para o nome do município.
    """
    with open(MUNICIPIOS_CSV, encoding="utf-8") as arquivo:
        return {
            linha["codigo_ibge"].strip(): linha["nome"].strip()
            for linha in csv.DictReader(arquivo)
        }


def mapear_codigos_completos(codigos_seis_digitos: set) -> dict:
    """
    Associa os códigos de 6 dígitos aos códigos IBGE completos de 7 dígitos.

    O SIH/SUS identifica o município por 6 dígitos, omitindo o dígito
    verificador; a API do IBGE exige o código completo. O casamento é feito
    pelos seis primeiros dígitos dentro da lista de municípios do Paraná.

    Args:
        codigos_seis_digitos (set): Códigos de 6 dígitos a mapear.

    Returns:
        dict: Mapa de código de 6 dígitos para código de 7 dígitos.

    Raises:
        RuntimeError: Se algum município não for encontrado.
    """
    municipios_uf = _requisitar(URL_MUNICIPIOS_UF.format(uf=UF_PARANA))
    mapa = {
        str(municipio["id"])[:6]: str(municipio["id"])
        for municipio in municipios_uf
    }

    faltando = sorted(codigos_seis_digitos - set(mapa))
    if faltando:
        raise RuntimeError(
            f"Municípios não localizados na base do IBGE para o Paraná: {faltando}"
        )
    return {codigo: mapa[codigo] for codigo in sorted(codigos_seis_digitos)}


def buscar_populacao(codigos_completos: list, fonte: dict) -> dict:
    """
    Consulta a população dos municípios informados na API de agregados do IBGE.

    Args:
        codigos_completos (list): Códigos IBGE de 7 dígitos.
        fonte (dict): Configuração da fonte populacional.

    Returns:
        dict: Mapa de código de 7 dígitos para população.
    """
    url = URL_AGREGADO.format(
        agregado=fonte["agregado"],
        periodo=fonte["periodo"],
        variavel=fonte["variavel"],
        municipios=",".join(codigos_completos),
    )
    dados = _requisitar(url)
    if not dados:
        raise RuntimeError("A API do IBGE não retornou dados para a consulta.")

    populacoes = {}
    for serie in dados[0]["resultados"][0]["series"]:
        codigo = str(serie["localidade"]["id"])
        valor = serie["serie"].get(fonte["periodo"])
        if valor in (None, "-", "..."):
            logger.warning(
                "População indisponível para o município %s (%s).",
                codigo,
                serie["localidade"]["nome"],
            )
            continue
        populacoes[codigo] = int(valor)
    return populacoes


def main() -> None:
    """Ponto de entrada do script."""
    args = _parse_args()
    fonte = FONTES[args.fonte]
    logger.info("Fonte populacional: %s", fonte["descricao"])

    municipios = carregar_municipios_referencia()
    logger.info("Municípios de referência: %d", len(municipios))

    mapa_codigos = mapear_codigos_completos(set(municipios))
    populacoes = buscar_populacao(sorted(mapa_codigos.values()), fonte)

    linhas = []
    for codigo_seis, codigo_sete in mapa_codigos.items():
        populacao = populacoes.get(codigo_sete)
        if populacao is None:
            logger.error(
                "Município %s (%s) ficou sem população.",
                codigo_seis,
                municipios[codigo_seis],
            )
            continue
        linhas.append({
            "codigo_ibge": codigo_seis,
            "codigo_ibge_completo": codigo_sete,
            "nome": municipios[codigo_seis],
            "ano": int(fonte["periodo"]),
            "populacao": populacao,
            "fonte": fonte["descricao"],
        })

    if len(linhas) != len(municipios):
        raise RuntimeError(
            f"Esperados {len(municipios)} municípios, obtidos {len(linhas)}."
        )

    SAIDA_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(SAIDA_CSV, "w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=list(linhas[0]))
        escritor.writeheader()
        escritor.writerows(linhas)

    total = sum(linha["populacao"] for linha in linhas)
    logger.info(
        "Arquivo gravado em %s — %d municípios, população total %d habitantes.",
        SAIDA_CSV,
        len(linhas),
        total,
    )


if __name__ == "__main__":
    main()
