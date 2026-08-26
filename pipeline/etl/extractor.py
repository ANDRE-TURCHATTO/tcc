"""
etl/extractor.py — RF-01: Extração dos dados do SIH/SUS via DATASUS.

Baixa os arquivos `.dbc` do Sistema de Informações Hospitalares (SIH/SUS),
grupo RD (AIH Reduzida), diretamente do servidor FTP público do DATASUS,
converte para `.dbf` e devolve um DataFrame pandas com as colunas
consumidas pelo transformador.

O acesso direto ao FTP é o caminho primário por ser o mais estável: a
interface HTTP da biblioteca pysus apresentou `ReadTimeout` recorrente
durante o desenvolvimento. A extração via pysus permanece disponível como
alternativa em `_extrair_via_pysus`.

Os arquivos `.dbc` baixados são mantidos em `data/raw/` como cache local,
evitando novo download a cada execução do pipeline.
"""

import logging
from ftplib import FTP
from pathlib import Path

import pandas as pd

from config import DATA_DIR, ESTADO_DATASUS

logger = logging.getLogger(__name__)

# Grupo do SIH/SUS utilizado: RD = AIH Reduzida (uma linha por internação)
GRUPO_SIH: str = "RD"

# Servidor FTP público do DATASUS
FTP_HOST: str = "ftp.datasus.gov.br"
FTP_DIRETORIO: str = "/dissemin/publicos/SIHSUS/200801_/Dados"
FTP_TIMEOUT: int = 120

# Diretório de cache dos arquivos brutos baixados
RAW_DIR: Path = DATA_DIR / "raw"

# Codificação dos arquivos do DATASUS
ENCODING_DATASUS: str = "iso-8859-1"

# Colunas efetivamente consumidas pelo transformador. O arquivo RD possui
# 113 campos; restringir a leitura a estes oito reduz de forma expressiva o
# consumo de memória.
COLUNAS_NECESSARIAS: list = [
    "MUNIC_RES",    # município de residência (código IBGE, 6 dígitos)
    "IDADE",        # idade (número)
    "COD_IDADE",    # unidade de medida da idade
    "SEXO",         # sexo (código numérico)
    "DIAG_PRINC",   # diagnóstico principal (CID-10)
    "VAL_TOT",      # valor total da AIH (R$)
    "ANO_CMPT",     # ano de competência
    "MES_CMPT",     # mês de competência
]


def nome_arquivo_dbc(ano: int, mes: int) -> str:
    """
    Monta o nome do arquivo `.dbc` conforme a convenção do DATASUS.

    O padrão é `RD` + sigla do estado + ano com dois dígitos + mês com dois
    dígitos — por exemplo, `RDPR2306.dbc` para o Paraná em junho de 2023.

    Args:
        ano (int): Ano de competência (ex: 2023).
        mes (int): Mês de competência (ex: 6).

    Returns:
        str: Nome do arquivo no FTP do DATASUS.
    """
    return f"{GRUPO_SIH}{ESTADO_DATASUS}{ano % 100:02d}{mes:02d}.dbc"


def baixar_dbc(ano: int, mes: int, forcar: bool = False) -> Path:
    """
    Baixa o arquivo `.dbc` da competência informada do FTP do DATASUS.

    Se o arquivo já existir em `data/raw/`, o download é dispensado, salvo
    quando `forcar` for verdadeiro.

    Args:
        ano (int): Ano de competência.
        mes (int): Mês de competência.
        forcar (bool): Refaz o download mesmo havendo cópia local.

    Returns:
        Path: Caminho local do arquivo `.dbc`.

    Raises:
        RuntimeError: Se o download falhar.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    nome = nome_arquivo_dbc(ano, mes)
    destino = RAW_DIR / nome

    if destino.exists() and destino.stat().st_size > 0 and not forcar:
        logger.info(
            "Arquivo %s já disponível em cache (%.1f MB) — download dispensado.",
            nome,
            destino.stat().st_size / 1e6,
        )
        return destino

    logger.info("Baixando %s de %s%s ...", nome, FTP_HOST, FTP_DIRETORIO)
    parcial = destino.with_suffix(".dbc.parcial")
    try:
        ftp = FTP(FTP_HOST, timeout=FTP_TIMEOUT)
        try:
            ftp.login()
            ftp.cwd(FTP_DIRETORIO)
            with open(parcial, "wb") as arquivo:
                ftp.retrbinary(f"RETR {nome}", arquivo.write)
        finally:
            try:
                ftp.quit()
            except Exception:  # pragma: no cover - encerramento best-effort
                ftp.close()
    except Exception as exc:
        parcial.unlink(missing_ok=True)
        raise RuntimeError(
            f"Falha ao baixar {nome} do FTP do DATASUS: {exc}"
        ) from exc

    parcial.replace(destino)
    logger.info("Download concluído — %s (%.1f MB).", nome, destino.stat().st_size / 1e6)
    return destino


def ler_dbc(caminho: Path, manter_dbf: bool = False) -> pd.DataFrame:
    """
    Converte um arquivo `.dbc` do DATASUS para `.dbf` e o lê em memória.

    Apenas as colunas de `COLUNAS_NECESSARIAS` presentes no arquivo são
    materializadas no DataFrame.

    Args:
        caminho (Path): Caminho do arquivo `.dbc`.
        manter_dbf (bool): Preserva o `.dbf` intermediário, que é bem maior
            que o `.dbc` original.

    Returns:
        pd.DataFrame: DataFrame com as colunas necessárias.

    Raises:
        ImportError: Se `pyreaddbc` ou `dbfread` não estiverem instalados.
    """
    try:
        from dbfread import DBF
        from pyreaddbc import dbc2dbf
    except ImportError as exc:
        raise ImportError(
            "Leitura de arquivos .dbc exige pyreaddbc e dbfread. "
            "Execute: pip install -r requirements.txt"
        ) from exc

    dbf = caminho.with_suffix(".dbf")
    logger.info("Convertendo %s para .dbf ...", caminho.name)
    dbc2dbf(str(caminho), str(dbf))

    try:
        tabela = DBF(str(dbf), encoding=ENCODING_DATASUS, load=False)
        disponiveis = [c for c in COLUNAS_NECESSARIAS if c in tabela.field_names]
        ausentes = [c for c in COLUNAS_NECESSARIAS if c not in tabela.field_names]
        if ausentes:
            logger.warning(
                "Colunas ausentes em %s: %s. O transformador aplicará as "
                "regras de contingência previstas.",
                caminho.name,
                ausentes,
            )
        logger.info("Lendo %s — extraindo %d colunas.", dbf.name, len(disponiveis))
        registros = [
            {coluna: registro.get(coluna) for coluna in disponiveis}
            for registro in tabela
        ]
        df = pd.DataFrame(registros, columns=disponiveis)
    finally:
        if not manter_dbf:
            dbf.unlink(missing_ok=True)

    return df


def _extrair_via_pysus(ano: int, mes: int) -> pd.DataFrame:
    """
    Extrai os dados usando a biblioteca pysus, como alternativa ao FTP.

    Suporta a interface do pysus 2.x (`pysus.sih`) e a do pysus 1.x
    (`pysus.online_data.SIH.download`).

    Args:
        ano (int): Ano de competência.
        mes (int): Mês de competência.

    Returns:
        pd.DataFrame: DataFrame com os registros brutos.
    """
    import pysus

    if hasattr(pysus, "sih"):
        return pysus.sih(
            ESTADO_DATASUS,
            year=ano,
            month=mes,
            group=GRUPO_SIH,
            columns=COLUNAS_NECESSARIAS,
            as_dataframe=True,
        )

    from pysus.online_data.SIH import download

    arquivos = download(ESTADO_DATASUS, year=ano, month=mes, group=GRUPO_SIH)
    if not isinstance(arquivos, list):
        arquivos = [arquivos]
    if not arquivos:
        raise RuntimeError(
            f"Nenhum arquivo encontrado para {ESTADO_DATASUS} {ano}/{mes:02d}."
        )

    quadros = []
    for arquivo in arquivos:
        try:
            quadros.append(arquivo.to_dataframe())
        except AttributeError:
            # Versões mais antigas retornam o DataFrame diretamente
            quadros.append(arquivo)
    return pd.concat(quadros, ignore_index=True)


def extrair_dados(ano: int, mes: int, usar_pysus: bool = False) -> pd.DataFrame:
    """
    Extrai os dados brutos do SIH/SUS para o estado do Paraná.

    Por padrão baixa o arquivo `.dbc` diretamente do FTP do DATASUS. Caso
    `usar_pysus` seja verdadeiro, ou o FTP falhe, a extração é tentada pela
    biblioteca pysus.

    Args:
        ano (int): Ano de competência (ex: 2023).
        mes (int): Mês de competência (ex: 6).
        usar_pysus (bool): Usa a biblioteca pysus em vez do FTP direto.

    Returns:
        pd.DataFrame: DataFrame com os dados brutos do SIH/SUS.

    Raises:
        RuntimeError: Se todas as estratégias de extração falharem.
    """
    logger.info(
        "Iniciando extração SIH/SUS — estado: %s, grupo: %s, competência: %d/%02d",
        ESTADO_DATASUS,
        GRUPO_SIH,
        ano,
        mes,
    )

    df = None
    if not usar_pysus:
        try:
            df = ler_dbc(baixar_dbc(ano, mes))
        except Exception as exc:
            logger.warning(
                "Extração via FTP falhou (%s). Tentando via pysus...", exc
            )

    if df is None:
        try:
            df = _extrair_via_pysus(ano, mes)
        except ImportError as exc:
            raise RuntimeError(
                "Extração via FTP indisponível e a biblioteca pysus não está "
                f"instalada: {exc}"
            ) from exc
        except Exception as exc:
            raise RuntimeError(
                f"Falha ao obter dados do DATASUS para {ESTADO_DATASUS} "
                f"{ano}/{mes:02d}: {exc}"
            ) from exc

    if df is None:
        raise RuntimeError(
            f"O DATASUS não retornou dados para {ESTADO_DATASUS} {ano}/{mes:02d}."
        )

    if df.empty:
        logger.warning(
            "O arquivo do SIH/SUS para %s %d/%02d está vazio.",
            ESTADO_DATASUS,
            ano,
            mes,
        )

    logger.info("Extração concluída — %d registros brutos obtidos.", len(df))
    return df
