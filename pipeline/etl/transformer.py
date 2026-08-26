"""
etl/transformer.py — RF-02, RF-03, RF-04: Transformações dos dados do SIH/SUS.

Aplica as seguintes transformações ao DataFrame bruto:
  - RF-02: Filtro por municípios do Sudoeste do Paraná
  - RF-03: Criação da coluna de faixas etárias
  - RF-04: Criação da coluna de capítulos CID-10
  - RF-16: Descarte de registros inconsistentes, com contabilização por motivo

A contabilização dos descartes é exposta em `EstatisticasTransformacao` para
permitir a caracterização quantitativa da base (número de registros brutos,
filtrados, descartados e carregados).
"""

import logging
from dataclasses import dataclass, field

import pandas as pd

from config import MUNICIPIOS_CSV

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# RF-04 — Mapeamento completo dos capítulos do CID-10
# Chave: prefixo do código CID-10; Valor: numeral romano do capítulo
# ---------------------------------------------------------------------------
_CID_CAPITULOS: dict[tuple[str, ...], str] = {
    # Capítulo I — Algumas doenças infecciosas e parasitárias (A00–B99)
    ("A", "B"): "I",
    # Capítulo II — Neoplasias (C00–D48)
    ("C", "D0", "D1", "D2", "D3", "D4"): "II",
    # Capítulo III — Doenças do sangue (D50–D89)
    ("D5", "D6", "D7", "D8"): "III",
    # Capítulo IV — Doenças endócrinas, nutricionais e metabólicas (E00–E89)
    ("E",): "IV",
    # Capítulo V — Transtornos mentais e comportamentais (F00–F99)
    ("F",): "V",
    # Capítulo VI — Doenças do sistema nervoso (G00–G99)
    ("G",): "VI",
    # Capítulo VII — Doenças do olho e anexos (H00–H59)
    ("H0", "H1", "H2", "H3", "H4", "H5"): "VII",
    # Capítulo VIII — Doenças do ouvido (H60–H95)
    ("H6", "H7", "H8", "H9"): "VIII",
    # Capítulo IX — Doenças do aparelho circulatório (I00–I99)
    ("I",): "IX",
    # Capítulo X — Doenças do aparelho respiratório (J00–J99)
    ("J",): "X",
    # Capítulo XI — Doenças do aparelho digestivo (K00–K93)
    ("K",): "XI",
    # Capítulo XII — Doenças da pele (L00–L99)
    ("L",): "XII",
    # Capítulo XIII — Doenças do sistema osteomuscular (M00–M99)
    ("M",): "XIII",
    # Capítulo XIV — Doenças do aparelho geniturinário (N00–N99)
    ("N",): "XIV",
    # Capítulo XV — Gravidez, parto e puerpério (O00–O99)
    ("O",): "XV",
    # Capítulo XVI — Afecções do período perinatal (P00–P96)
    ("P",): "XVI",
    # Capítulo XVII — Malformações congênitas (Q00–Q99)
    ("Q",): "XVII",
    # Capítulo XVIII — Sintomas, sinais e achados anormais (R00–R99)
    ("R",): "XVIII",
    # Capítulo XIX — Lesões, envenenamentos (S00–T98)
    ("S", "T"): "XIX",
    # Capítulo XX — Causas externas (V01–Y98)
    ("V", "W", "X", "Y"): "XX",
    # Capítulo XXI — Fatores que influenciam o estado de saúde (Z00–Z99)
    ("Z",): "XXI",
    # Capítulo XXII — Códigos para propósitos especiais (U00–U99)
    ("U",): "XXII",
}

# Índice plano: prefixo → capítulo (construído uma única vez)
_PREFIXO_PARA_CAPITULO: dict[str, str] = {
    prefixo: capitulo
    for prefixos, capitulo in _CID_CAPITULOS.items()
    for prefixo in prefixos
}

# Marcador de código CID-10 não classificável em nenhum capítulo
CAPITULO_DESCONHECIDO: str = "Desconhecido"

# ---------------------------------------------------------------------------
# Códigos de unidade do campo COD_IDADE no SIH/SUS
# ---------------------------------------------------------------------------
# 0 — idade ignorada        3 — idade em meses
# 1 — idade em horas        4 — idade em anos (0 a 99)
# 2 — idade em dias         5 — idade em anos, 100 ou mais (idade = 100 + IDADE)
_COD_IDADE_ANOS: str = "4"
_COD_IDADE_CENTENARIO: str = "5"
_COD_IDADE_SUBANUAL: frozenset = frozenset({"0", "1", "2", "3"})

# ---------------------------------------------------------------------------
# Códigos do campo SEXO no SIH/SUS
# ---------------------------------------------------------------------------
# 1 — masculino    2 — feminino (layouts anteriores a 2008)    3 — feminino
# 0/9 — ignorado. Registros com sexo ignorado são descartados.
_MAPA_SEXO: dict[str, str] = {
    "1": "M",
    "M": "M",
    "2": "F",
    "3": "F",
    "F": "F",
}


@dataclass
class EstatisticasTransformacao:
    """
    Contabiliza o funil de transformação, do registro bruto ao registro carregado.

    Attributes:
        brutos: registros recebidos do SIH/SUS (estado do Paraná inteiro).
        fora_da_regiao: descartados por MUNIC_RES fora do Sudoeste do Paraná.
        descartes: descartados por inconsistência, por motivo.
        finais: registros prontos para carga.
    """

    brutos: int = 0
    fora_da_regiao: int = 0
    descartes: dict = field(default_factory=dict)
    finais: int = 0

    @property
    def total_descartados(self) -> int:
        """Soma dos descartes por inconsistência (não inclui o filtro regional)."""
        return sum(self.descartes.values())

    def registrar_descarte(self, motivo: str, quantidade: int) -> None:
        """Acumula `quantidade` descartes sob o `motivo` informado."""
        if quantidade > 0:
            self.descartes[motivo] = self.descartes.get(motivo, 0) + quantidade


def _classificar_cid(codigo: str) -> str:
    """
    Retorna o capítulo CID-10 em numeral romano dado um código CID.

    A classificação ocorre pelo maior prefixo correspondente encontrado
    (prioridade: 2 caracteres sobre 1), cobrindo os capítulos que
    compartilham a mesma letra inicial (ex: D, H).

    Args:
        codigo (str): Código CID-10 (ex: 'J18', 'K35').

    Returns:
        str: Numeral romano do capítulo (ex: 'X', 'XI') ou 'Desconhecido'.
    """
    if not isinstance(codigo, str) or len(codigo.strip()) < 1:
        return CAPITULO_DESCONHECIDO
    codigo = codigo.strip().upper()
    # Tenta prefixo de 2 caracteres primeiro (ex: 'D5', 'H6')
    prefixo2 = codigo[:2]
    if prefixo2 in _PREFIXO_PARA_CAPITULO:
        return _PREFIXO_PARA_CAPITULO[prefixo2]
    # Tenta prefixo de 1 caractere (ex: 'J', 'K')
    prefixo1 = codigo[:1]
    if prefixo1 in _PREFIXO_PARA_CAPITULO:
        return _PREFIXO_PARA_CAPITULO[prefixo1]
    return CAPITULO_DESCONHECIDO


def _decodificar_idade_sih(idade, cod_idade=None) -> int:
    """
    Decodifica a idade do SIH/SUS a partir dos campos IDADE e COD_IDADE.

    No layout do SIH/SUS a idade é representada por dois campos: `IDADE`
    guarda o número e `COD_IDADE` guarda a unidade de medida. Idades
    subanuais (horas, dias, meses) são convertidas para 0 anos completos,
    e a faixa "0-10" as absorve.

    Quando `COD_IDADE` não é informado (None/NaN/vazio), assume-se que
    `IDADE` já está expressa em anos — situação de bases pré-processadas.

    Args:
        idade: Valor do campo IDADE.
        cod_idade: Valor do campo COD_IDADE (unidade de medida).

    Returns:
        int: Idade em anos completos. Retorna -1 quando indecifrável,
        sinalizando registro inconsistente a ser descartado.
    """
    if idade is None or pd.isna(idade):
        return -1
    try:
        numero = int(float(idade))
    except (TypeError, ValueError):
        return -1
    if numero < 0:
        return -1

    unidade = "" if cod_idade is None or pd.isna(cod_idade) else str(cod_idade).strip()
    # Normaliza códigos numéricos lidos como float (ex: '4.0' vira '4')
    if unidade.endswith(".0"):
        unidade = unidade[:-2]

    if unidade == "":
        return numero  # IDADE já em anos
    if unidade == _COD_IDADE_ANOS:
        return numero
    if unidade == _COD_IDADE_CENTENARIO:
        return 100 + numero
    if unidade in _COD_IDADE_SUBANUAL:
        return 0  # horas, dias ou meses: menos de 1 ano completo
    return -1  # unidade não prevista no layout


def _normalizar_sexo(valor):
    """
    Converte o campo SEXO do SIH/SUS para o domínio 'M' / 'F'.

    O SIH/SUS codifica o sexo numericamente (1 = masculino, 3 = feminino;
    layouts anteriores a 2008 usam 2 para feminino). O modelo de dados do
    Longevus armazena 'M' ou 'F'.

    Args:
        valor: Valor bruto do campo SEXO.

    Returns:
        str | None: 'M', 'F', ou None quando ignorado/inválido.
    """
    if valor is None or pd.isna(valor):
        return None
    texto = str(valor).strip().upper()
    if texto.endswith(".0"):
        texto = texto[:-2]
    return _MAPA_SEXO.get(texto)


def _classificar_faixa_etaria(idade: int) -> str:
    """
    Retorna a faixa etária padronizada com base na idade em anos.

    Faixas definidas:
      0-10, 11-20, 21-30, 31-40, 41-50, 51-60, 61+

    Args:
        idade (int): Idade em anos.

    Returns:
        str: String da faixa etária correspondente.
    """
    if idade <= 10:
        return "0-10"
    if idade <= 20:
        return "11-20"
    if idade <= 30:
        return "21-30"
    if idade <= 40:
        return "31-40"
    if idade <= 50:
        return "41-50"
    if idade <= 60:
        return "51-60"
    return "61+"


def _carregar_codigos_municipios() -> set:
    """
    Carrega os códigos IBGE dos municípios do Sudoeste do Paraná a partir
    do arquivo CSV de referência.

    Returns:
        set[str]: Conjunto de códigos IBGE (strings de 6 dígitos).
    """
    df_mun = pd.read_csv(MUNICIPIOS_CSV, dtype={"codigo_ibge": str})
    return set(df_mun["codigo_ibge"].str.strip())


def filtrar_municipios(df: pd.DataFrame) -> pd.DataFrame:
    """
    RF-02 — Filtra o DataFrame mantendo apenas registros cujo código IBGE
    do município de residência (MUNIC_RES) pertence ao Sudoeste do Paraná.

    O campo MUNIC_RES no SIH/SUS possui 6 dígitos. O CSV utiliza o mesmo
    padrão de 6 dígitos.

    Args:
        df (pd.DataFrame): DataFrame bruto do SIH/SUS.

    Returns:
        pd.DataFrame: DataFrame filtrado pelos municípios do Sudoeste do PR.
    """
    codigos = _carregar_codigos_municipios()
    # Garante que a coluna seja tratada como string sem zeros à esquerda perdidos
    df = df.copy()
    df["MUNIC_RES"] = df["MUNIC_RES"].astype(str).str.strip().str.zfill(6)
    antes = len(df)
    df = df[df["MUNIC_RES"].isin(codigos)].reset_index(drop=True)
    logger.info(
        "Filtro de municípios: %d para %d registros (%d removidos).",
        antes,
        len(df),
        antes - len(df),
    )
    return df


def criar_faixa_etaria(df: pd.DataFrame) -> pd.DataFrame:
    """
    RF-03 — Cria as colunas `idade_anos` e `faixa_etaria` a partir dos campos
    IDADE e COD_IDADE do SIH/SUS.

    Args:
        df (pd.DataFrame): DataFrame com as colunas IDADE e, opcionalmente,
            COD_IDADE.

    Returns:
        pd.DataFrame: DataFrame com `idade_anos` e `faixa_etaria` adicionadas.
            Registros indecifráveis recebem `idade_anos = -1`.
    """
    df = df.copy()
    if "COD_IDADE" in df.columns:
        df["idade_anos"] = [
            _decodificar_idade_sih(idade, cod)
            for idade, cod in zip(df["IDADE"], df["COD_IDADE"])
        ]
    else:
        logger.warning(
            "Coluna COD_IDADE ausente — IDADE será interpretada como anos completos."
        )
        df["idade_anos"] = df["IDADE"].apply(_decodificar_idade_sih)
    df["faixa_etaria"] = df["idade_anos"].apply(_classificar_faixa_etaria)
    logger.info("Coluna 'faixa_etaria' criada com sucesso.")
    return df


def criar_cid_capitulo(df: pd.DataFrame) -> pd.DataFrame:
    """
    RF-04 — Cria a coluna `cid_capitulo` a partir do campo DIAG_PRINC (CID-10),
    mapeando cada código para o respectivo capítulo em numeral romano.

    Args:
        df (pd.DataFrame): DataFrame com a coluna DIAG_PRINC.

    Returns:
        pd.DataFrame: DataFrame com a coluna `cid_capitulo` adicionada.
    """
    df = df.copy()
    df["cid_capitulo"] = df["DIAG_PRINC"].apply(_classificar_cid)
    logger.info("Coluna 'cid_capitulo' criada com sucesso.")
    return df


def transformar_detalhado(df: pd.DataFrame):
    """
    Aplica todas as transformações e devolve o funil quantitativo da execução.

    Etapas executadas em ordem:
      1. Filtro por municípios do Sudoeste do Paraná (RF-02)
      2. Decodificação da idade e faixas etárias (RF-03)
      3. Capítulos CID-10 (RF-04)
      4. Descarte de registros inconsistentes (RF-16)
      5. Seleção e renomeação das colunas finais

    Critérios de descarte por inconsistência:
      - `idade_indecifravel`: IDADE/COD_IDADE fora do layout do SIH/SUS
      - `sexo_invalido`: SEXO ignorado ou fora do domínio 1/2/3
      - `cid_desconhecido`: DIAG_PRINC sem capítulo CID-10 correspondente
      - `valor_invalido`: VAL_TOT ausente ou negativo

    Args:
        df (pd.DataFrame): DataFrame bruto do SIH/SUS.

    Returns:
        tuple[pd.DataFrame, EstatisticasTransformacao]: DataFrame pronto para
        carga e as estatísticas da transformação.
    """
    estatisticas = EstatisticasTransformacao(brutos=len(df))
    logger.info("Iniciando transformações — %d registros brutos.", len(df))

    # RF-02: filtro de municípios
    df = filtrar_municipios(df)
    estatisticas.fora_da_regiao = estatisticas.brutos - len(df)

    # RF-03 e RF-04
    df = criar_faixa_etaria(df)
    df = criar_cid_capitulo(df)

    df = df.copy()
    df["sexo_normalizado"] = df["SEXO"].apply(_normalizar_sexo)
    df["valor_numerico"] = pd.to_numeric(df["VAL_TOT"], errors="coerce")

    # RF-16: descarte de inconsistências, avaliado em cascata para que cada
    # registro seja contabilizado uma única vez, sob o primeiro motivo aplicável
    criterios = [
        ("idade_indecifravel", df["idade_anos"] < 0),
        ("sexo_invalido", df["sexo_normalizado"].isna()),
        ("cid_desconhecido", df["cid_capitulo"] == CAPITULO_DESCONHECIDO),
        ("valor_invalido", df["valor_numerico"].isna() | (df["valor_numerico"] < 0)),
    ]
    validos = pd.Series(True, index=df.index)
    for motivo, invalido in criterios:
        atingidos = validos & invalido
        estatisticas.registrar_descarte(motivo, int(atingidos.sum()))
        validos &= ~invalido

    df = df[validos].reset_index(drop=True)

    for motivo, quantidade in estatisticas.descartes.items():
        logger.info("Descartados por %s: %d registros.", motivo, quantidade)

    # Seleção e renomeação para o esquema da tabela `internacoes`
    df_final = pd.DataFrame({
        "municipio_codigo": df["MUNIC_RES"],
        "idade": df["idade_anos"].astype(int),
        "sexo": df["sexo_normalizado"],
        "faixa_etaria": df["faixa_etaria"],
        "cid_principal": df["DIAG_PRINC"].astype(str).str.strip().str.upper(),
        "cid_capitulo": df["cid_capitulo"],
        "valor_total": df["valor_numerico"].astype(float),
        "ano_competencia": df["ANO_CMPT"].astype(int) if "ANO_CMPT" in df.columns else 0,
        "mes_competencia": df["MES_CMPT"].astype(int) if "MES_CMPT" in df.columns else 0,
    })

    estatisticas.finais = len(df_final)
    logger.info(
        "Transformações concluídas — %d brutos, %d fora da região, "
        "%d descartados por inconsistência, %d prontos para carga.",
        estatisticas.brutos,
        estatisticas.fora_da_regiao,
        estatisticas.total_descartados,
        estatisticas.finais,
    )
    return df_final, estatisticas


def transformar(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica todas as transformações ao DataFrame bruto do SIH/SUS.

    Wrapper de `transformar_detalhado` para os casos em que apenas o
    DataFrame resultante interessa.

    Args:
        df (pd.DataFrame): DataFrame bruto do SIH/SUS.

    Returns:
        pd.DataFrame: DataFrame transformado e pronto para carga.
    """
    df_final, _ = transformar_detalhado(df)
    return df_final
