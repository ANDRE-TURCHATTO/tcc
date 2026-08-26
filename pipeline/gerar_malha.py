"""
gerar_malha.py — Gera a malha territorial dos municípios do Sudoeste do
Paraná em GeoJSON, a partir da API de malhas do IBGE.

O arquivo produzido é servido pelo endpoint `GET /api/geometria` (RF-08) e
consumido pelo mapa coroplético do frontend (RF-10). O requisito RNF-03
limita o GeoJSON a 500 KB, portanto o script mede o resultado e permite
escolher a qualidade da malha.

Qualidades oferecidas pelo IBGE, da mais leve à mais detalhada:
`minima`, `intermediaria` e `maxima`.

As propriedades de cada feição são normalizadas para o contrato esperado
pelo frontend: `codigo_ibge` (6 dígitos, o mesmo padrão do SIH/SUS) e `nome`.

Uso:
    python gerar_malha.py
    python gerar_malha.py --qualidade minima
    python gerar_malha.py --comparar
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
logger = logging.getLogger("malha")

from config import BASE_DIR, MUNICIPIOS_CSV  # noqa: E402

# Código do Paraná na base de localidades do IBGE
UF_PARANA: int = 41

URL_MALHA_UF: str = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/estados/{uf}"
    "?intrarregiao=municipio&formato=application/vnd.geo+json&qualidade={qualidade}"
)

QUALIDADES: tuple = ("minima", "intermediaria", "maxima")
TIMEOUT: int = 300

# Limite de tamanho definido em RNF-03
LIMITE_BYTES: int = 500 * 1024

DESTINO: Path = BASE_DIR.parent / "backend" / "public" / "geo" / "sudoeste-pr.geojson"


def _parse_args() -> argparse.Namespace:
    """Analisa os argumentos de linha de comando."""
    parser = argparse.ArgumentParser(
        description="Gera a malha GeoJSON do Sudoeste do Paraná a partir do IBGE."
    )
    parser.add_argument(
        "--qualidade",
        choices=QUALIDADES,
        default="intermediaria",
        help="Qualidade da malha do IBGE (padrão: intermediaria).",
    )
    parser.add_argument(
        "--comparar",
        action="store_true",
        help="Mede todas as qualidades sem gravar o arquivo final.",
    )
    return parser.parse_args()


def _requisitar(url: str) -> bytes:
    """Executa uma requisição GET e devolve o corpo já descomprimido."""
    requisicao = urllib.request.Request(url, headers={"Accept-Encoding": "gzip"})
    with urllib.request.urlopen(requisicao, timeout=TIMEOUT) as resposta:
        conteudo = resposta.read()
    if conteudo[:2] == b"\x1f\x8b":
        conteudo = gzip.decompress(conteudo)
    return conteudo


def carregar_municipios() -> dict:
    """
    Lê o arquivo de referência dos municípios do recorte.

    Returns:
        dict: Mapa de código IBGE de 6 dígitos para o nome do município.
    """
    with open(MUNICIPIOS_CSV, encoding="utf-8") as arquivo:
        return {
            linha["codigo_ibge"].strip(): linha["nome"].strip()
            for linha in csv.DictReader(arquivo)
        }


def montar_malha(qualidade: str, municipios: dict) -> dict:
    """
    Baixa a malha do Paraná e recorta as feições do Sudoeste.

    A API do IBGE identifica cada feição por `codarea`, com o código de 7
    dígitos. O casamento com o recorte é feito pelos seis primeiros dígitos.

    Args:
        qualidade (str): Qualidade da malha.
        municipios (dict): Mapa de código de 6 dígitos para nome.

    Returns:
        dict: FeatureCollection com as feições do recorte.

    Raises:
        RuntimeError: Se algum município do recorte não tiver geometria.
    """
    logger.info("Baixando malha do Paraná — qualidade %s ...", qualidade)
    bruto = _requisitar(URL_MALHA_UF.format(uf=UF_PARANA, qualidade=qualidade))
    colecao = json.loads(bruto.decode("utf-8"))
    logger.info(
        "Malha recebida — %.2f MB, %d feições.",
        len(bruto) / 1e6,
        len(colecao.get("features", [])),
    )

    feicoes = []
    for feicao in colecao.get("features", []):
        codarea = str(feicao.get("properties", {}).get("codarea", ""))
        codigo = codarea[:6]
        if codigo not in municipios:
            continue
        feicoes.append({
            "type": "Feature",
            "properties": {
                "codigo_ibge": codigo,
                "nome": municipios[codigo],
            },
            "geometry": feicao["geometry"],
        })

    encontrados = {feicao["properties"]["codigo_ibge"] for feicao in feicoes}
    faltando = sorted(set(municipios) - encontrados)
    if faltando:
        raise RuntimeError(
            "Municípios do recorte sem geometria na malha do IBGE: "
            + ", ".join(f"{c} ({municipios[c]})" for c in faltando)
        )

    feicoes.sort(key=lambda feicao: feicao["properties"]["codigo_ibge"])
    return {"type": "FeatureCollection", "features": feicoes}


def serializar(colecao: dict) -> bytes:
    """
    Serializa a coleção em JSON compacto, sem espaços supérfluos.

    Args:
        colecao (dict): FeatureCollection.

    Returns:
        bytes: JSON codificado em UTF-8.
    """
    return json.dumps(colecao, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def main() -> None:
    """Ponto de entrada do script."""
    args = _parse_args()
    municipios = carregar_municipios()
    logger.info("Municípios do recorte: %d", len(municipios))

    if args.comparar:
        logger.info("Comparando qualidades disponíveis (RNF-03: limite de 500 KB):")
        for qualidade in QUALIDADES:
            try:
                dados = serializar(montar_malha(qualidade, municipios))
            except Exception as exc:
                logger.warning("Qualidade %s indisponível: %s", qualidade, exc)
                continue
            tamanho = len(dados)
            logger.info(
                "  %-14s %7.1f KB  %s",
                qualidade,
                tamanho / 1024,
                "atende" if tamanho <= LIMITE_BYTES else "EXCEDE o limite",
            )
        return

    dados = serializar(montar_malha(args.qualidade, municipios))
    tamanho = len(dados)

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_bytes(dados)

    logger.info(
        "Malha gravada em %s — %d feições, %.1f KB (RNF-03: limite de %.0f KB, %s).",
        DESTINO,
        len(municipios),
        tamanho / 1024,
        LIMITE_BYTES / 1024,
        "atendido" if tamanho <= LIMITE_BYTES else "EXCEDIDO",
    )
    if tamanho > LIMITE_BYTES:
        logger.error(
            "Use --qualidade minima para reduzir o arquivo abaixo do limite."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
