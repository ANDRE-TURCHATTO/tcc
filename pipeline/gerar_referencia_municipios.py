"""
gerar_referencia_municipios.py — Gera o arquivo de referência dos municípios
do Sudoeste do Paraná a partir da base oficial de localidades do IBGE.

O arquivo `data/municipios_sudoeste.csv` define o recorte territorial de todo
o sistema: é ele que determina quais registros do SIH/SUS são mantidos pelo
filtro regional (RF-02). Os códigos IBGE precisam, portanto, ser exatos.

Critério do recorte
-------------------
O recorte adotado é a área de abrangência da Associação dos Municípios do
Sudoeste do Paraná (AMSOP), composta por 42 municípios. Em termos da divisão
territorial do IBGE, essa área corresponde à união de quatro microrregiões:

  - Capanema (8 municípios)
  - Francisco Beltrão (19 municípios)
  - Pato Branco (10 municípios)
  - Palmas (5 municípios)

As três primeiras formam a mesorregião Sudoeste Paranaense (37 municípios);
a microrregião de Palmas pertence à mesorregião Centro-Sul Paranaense, mas
integra a AMSOP. Definir o recorte por microrregiões torna o critério
verificável e reprodutível a partir de uma fonte oficial única.

Uso:
    python gerar_referencia_municipios.py
    python gerar_referencia_municipios.py --conferir
"""

import argparse
import csv
import gzip
import json
import logging
import sys
import urllib.request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("municipios")

from config import MUNICIPIOS_CSV  # noqa: E402

# Código do Paraná na base de localidades do IBGE
UF_PARANA: int = 41
URL_MUNICIPIOS_UF: str = (
    "https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios"
)
TIMEOUT: int = 120

# Microrregiões do IBGE que compõem o recorte territorial da AMSOP
MICRORREGIOES: tuple = ("Capanema", "Francisco Beltrão", "Pato Branco", "Palmas")

# Total esperado de municípios no recorte
TOTAL_ESPERADO: int = 42

CABECALHO: list = ["codigo_ibge", "nome", "microrregiao"]


def _parse_args() -> argparse.Namespace:
    """Analisa os argumentos de linha de comando."""
    parser = argparse.ArgumentParser(
        description=(
            "Gera data/municipios_sudoeste.csv a partir das microrregiões do IBGE "
            "que compõem a AMSOP."
        )
    )
    parser.add_argument(
        "--conferir",
        action="store_true",
        help="Apenas confere o arquivo atual, sem regravar. Sai com código 1 se divergir.",
    )
    return parser.parse_args()


def _requisitar(url: str):
    """Executa uma requisição GET e devolve o JSON decodificado."""
    requisicao = urllib.request.Request(
        url, headers={"Accept": "application/json", "Accept-Encoding": "gzip"}
    )
    with urllib.request.urlopen(requisicao, timeout=TIMEOUT) as resposta:
        conteudo = resposta.read()
        if resposta.headers.get("Content-Encoding") == "gzip" or conteudo[:2] == b"\x1f\x8b":
            conteudo = gzip.decompress(conteudo)
    return json.loads(conteudo.decode("utf-8"))


def montar_recorte() -> list:
    """
    Monta o recorte territorial a partir das microrregiões do IBGE.

    O SIH/SUS identifica o município por 6 dígitos, omitindo o dígito
    verificador do código IBGE de 7 dígitos; o arquivo de referência adota o
    mesmo padrão de 6 dígitos.

    Returns:
        list: Linhas do recorte, ordenadas por código IBGE.

    Raises:
        RuntimeError: Se alguma microrregião não for encontrada.
    """
    municipios = _requisitar(URL_MUNICIPIOS_UF.format(uf=UF_PARANA))
    logger.info("Municípios do Paraná na base do IBGE: %d", len(municipios))

    encontradas = set()
    linhas = []
    for municipio in municipios:
        microrregiao = (municipio.get("microrregiao") or {}).get("nome")
        if microrregiao is None:
            continue
        encontradas.add(microrregiao)
        if microrregiao in MICRORREGIOES:
            linhas.append({
                "codigo_ibge": str(municipio["id"])[:6],
                "nome": municipio["nome"],
                "microrregiao": microrregiao,
            })

    ausentes = [m for m in MICRORREGIOES if m not in encontradas]
    if ausentes:
        raise RuntimeError(
            f"Microrregiões não encontradas na base do IBGE para o Paraná: {ausentes}"
        )

    linhas.sort(key=lambda linha: linha["codigo_ibge"])
    return linhas


def carregar_referencia_atual() -> dict:
    """
    Lê o arquivo de referência atual, se existir.

    Returns:
        dict: Mapa de código IBGE para nome do município.
    """
    if not MUNICIPIOS_CSV.exists():
        return {}
    with open(MUNICIPIOS_CSV, encoding="utf-8") as arquivo:
        return {
            linha["codigo_ibge"].strip(): linha["nome"].strip()
            for linha in csv.DictReader(arquivo)
        }


def main() -> None:
    """Ponto de entrada do script."""
    args = _parse_args()
    recorte = montar_recorte()

    por_microrregiao = {}
    for linha in recorte:
        por_microrregiao[linha["microrregiao"]] = (
            por_microrregiao.get(linha["microrregiao"], 0) + 1
        )
    for microrregiao in MICRORREGIOES:
        logger.info(
            "Microrregião %-20s %d municípios",
            microrregiao,
            por_microrregiao.get(microrregiao, 0),
        )

    if len(recorte) != TOTAL_ESPERADO:
        logger.error(
            "Recorte com %d municípios, esperado %d. "
            "Verificar a divisão territorial vigente do IBGE.",
            len(recorte),
            TOTAL_ESPERADO,
        )
        sys.exit(1)

    atual = carregar_referencia_atual()
    novos = {linha["codigo_ibge"]: linha["nome"] for linha in recorte}

    faltando = sorted(set(novos) - set(atual))
    sobrando = sorted(set(atual) - set(novos))
    renomeados = [
        (codigo, atual[codigo], novos[codigo])
        for codigo in sorted(set(atual) & set(novos))
        if atual[codigo] != novos[codigo]
    ]

    for codigo in faltando:
        logger.warning("Ausente no arquivo atual: %s %s", codigo, novos[codigo])
    for codigo in sobrando:
        logger.warning("Fora do recorte, será removido: %s %s", codigo, atual[codigo])
    for codigo, antigo, novo in renomeados:
        logger.warning("Nome divergente em %s: %r → %r", codigo, antigo, novo)

    if not (faltando or sobrando or renomeados):
        logger.info("Arquivo atual já corresponde ao recorte oficial.")

    if args.conferir:
        sys.exit(1 if (faltando or sobrando or renomeados) else 0)

    with open(MUNICIPIOS_CSV, "w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=CABECALHO)
        escritor.writeheader()
        escritor.writerows(recorte)

    logger.info(
        "Arquivo gravado em %s — %d municípios (%d incluídos, %d removidos).",
        MUNICIPIOS_CSV,
        len(recorte),
        len(faltando),
        len(sobrando),
    )


if __name__ == "__main__":
    main()
