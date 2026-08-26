"""
tests/test_transformer.py — Testes unitários do módulo `etl.transformer`.

Os testes validam as regras especificadas em `spec/requirements.md`
(RF-02, RF-03, RF-04) e os cenários descritos em
`spec/behaviors/filtros.feature` — em especial a lista de faixas etárias
oferecidas na sidebar, que precisa corresponder exatamente às faixas
produzidas pelo pipeline.
"""

import pandas as pd
import pytest

from etl.transformer import (
    CAPITULO_DESCONHECIDO,
    EstatisticasTransformacao,
    _classificar_cid,
    _classificar_faixa_etaria,
    _decodificar_idade_sih,
    _normalizar_sexo,
    transformar_detalhado,
)

# Municípios reais presentes em pipeline/data/municipios_sudoeste.csv
CODIGO_FRANCISCO_BELTRAO = "410840"
CODIGO_PATO_BRANCO = "411850"
# Curitiba — fora do recorte do Sudoeste do Paraná
CODIGO_CURITIBA = "410690"


# ---------------------------------------------------------------------------
# RF-03 — Decodificação da idade do SIH/SUS (campos IDADE + COD_IDADE)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("idade", "cod_idade", "esperado"),
    [
        (15, "2", 0),      # 15 dias
        (0, "2", 0),       # recém-nascido, contado em dias
        (7, "3", 0),       # 7 meses
        (11, "3", 0),      # 11 meses — ainda não completou 1 ano
        (12, "1", 0),      # 12 horas
        (0, "4", 0),       # 0 anos completos
        (1, "4", 1),
        (45, "4", 45),
        (99, "4", 99),     # maior idade representável com COD_IDADE = 4
        (3, "5", 103),     # centenário: 100 + IDADE
        (0, "5", 100),     # exatamente 100 anos
    ],
)
def test_decodificar_idade_sih_por_unidade(idade, cod_idade, esperado):
    """A unidade em COD_IDADE determina a conversão para anos completos."""
    assert _decodificar_idade_sih(idade, cod_idade) == esperado


def test_decodificar_idade_aceita_codigo_numerico_e_float():
    """COD_IDADE lido como número ou como float textual é tratado igualmente."""
    assert _decodificar_idade_sih(45, 4) == 45
    assert _decodificar_idade_sih("45", "4.0") == 45
    assert _decodificar_idade_sih(45.0, 4.0) == 45


def test_decodificar_idade_sem_cod_idade_assume_anos():
    """Sem COD_IDADE, IDADE é interpretada diretamente como anos completos."""
    assert _decodificar_idade_sih(45) == 45
    assert _decodificar_idade_sih(45, None) == 45
    assert _decodificar_idade_sih(45, "") == 45


@pytest.mark.parametrize(
    ("idade", "cod_idade"),
    [
        (None, "4"),       # idade ausente
        (float("nan"), "4"),
        ("abc", "4"),      # idade não numérica
        (-1, "4"),         # idade negativa
        (30, "9"),         # unidade fora do layout
    ],
)
def test_decodificar_idade_invalida_retorna_menos_um(idade, cod_idade):
    """Valores fora do layout sinalizam registro a descartar (-1)."""
    assert _decodificar_idade_sih(idade, cod_idade) == -1


# ---------------------------------------------------------------------------
# RF-03 — Classificação em faixas etárias (bordas exatas)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("idade", "faixa"),
    [
        (0, "0-10"),
        (10, "0-10"),      # borda superior
        (11, "11-20"),     # borda inferior da faixa seguinte
        (20, "11-20"),
        (21, "21-30"),
        (30, "21-30"),
        (31, "31-40"),
        (40, "31-40"),
        (41, "41-50"),
        (50, "41-50"),
        (51, "51-60"),
        (60, "51-60"),     # borda superior
        (61, "61+"),       # borda inferior da última faixa
        (103, "61+"),
    ],
)
def test_classificar_faixa_etaria_bordas(idade, faixa):
    """As bordas 10/11 e 60/61 caem na faixa correta."""
    assert _classificar_faixa_etaria(idade) == faixa


def test_faixas_produzidas_correspondem_a_sidebar():
    """
    Cenário "Seleção de faixa etária" (spec/behaviors/filtros.feature):
    as faixas geradas pelo pipeline devem ser exatamente as sete oferecidas
    no drop-down da sidebar.
    """
    faixas_da_sidebar = {
        "0-10", "11-20", "21-30", "31-40", "41-50", "51-60", "61+",
    }
    faixas_geradas = {_classificar_faixa_etaria(idade) for idade in range(0, 121)}
    assert faixas_geradas == faixas_da_sidebar


# ---------------------------------------------------------------------------
# RF-04 — Mapeamento CID-10 para capítulo em numeral romano
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("codigo", "capitulo"),
    [
        ("A09", "I"),      # doenças infecciosas
        ("B20", "I"),
        ("C50", "II"),     # neoplasias
        ("D48", "II"),     # limite superior do capítulo II
        ("D50", "III"),    # doenças do sangue começam em D50
        ("D89", "III"),
        ("E11", "IV"),
        ("F20", "V"),
        ("G40", "VI"),
        ("H10", "VII"),    # olho
        ("H59", "VII"),
        ("H60", "VIII"),   # ouvido
        ("H95", "VIII"),
        ("I21", "IX"),
        ("J18", "X"),
        ("K35", "XI"),
        ("L03", "XII"),
        ("M54", "XIII"),
        ("N39", "XIV"),
        ("O80", "XV"),
        ("P07", "XVI"),
        ("Q21", "XVII"),
        ("R10", "XVIII"),
        ("S72", "XIX"),
        ("T14", "XIX"),
        ("V89", "XX"),
        ("W19", "XX"),
        ("X60", "XX"),
        ("Y83", "XX"),
        ("Z38", "XXI"),
        ("U07", "XXII"),
    ],
)
def test_classificar_cid_cobre_todos_os_capitulos(codigo, capitulo):
    """Cada capítulo I–XXII tem ao menos um código representativo mapeado."""
    assert _classificar_cid(codigo) == capitulo


def test_classificar_cid_normaliza_caixa_e_espacos():
    """Códigos em minúsculas ou com espaços são normalizados antes do mapeamento."""
    assert _classificar_cid(" j18 ") == "X"
    assert _classificar_cid("k35") == "XI"


@pytest.mark.parametrize("codigo", ["", "   ", "999", None, 42])
def test_classificar_cid_invalido(codigo):
    """Código ausente ou fora do CID-10 resulta em capítulo Desconhecido."""
    assert _classificar_cid(codigo) == CAPITULO_DESCONHECIDO


# ---------------------------------------------------------------------------
# Normalização do campo SEXO
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (1, "M"),
        ("1", "M"),
        ("1.0", "M"),
        ("M", "M"),
        (3, "F"),
        ("3", "F"),
        ("F", "F"),
        (2, "F"),        # layouts anteriores a 2008
        (0, None),       # ignorado
        (9, None),
        ("", None),
        (None, None),
    ],
)
def test_normalizar_sexo(valor, esperado):
    """O código numérico do SIH/SUS é convertido para o domínio 'M'/'F'."""
    assert _normalizar_sexo(valor) == esperado


# ---------------------------------------------------------------------------
# Pipeline completo de transformação e contabilização do funil
# ---------------------------------------------------------------------------


def _linha(**overrides):
    """Constrói uma linha bruta do SIH/SUS com valores padrão válidos."""
    linha = {
        "MUNIC_RES": CODIGO_FRANCISCO_BELTRAO,
        "IDADE": 45,
        "COD_IDADE": "4",
        "SEXO": "1",
        "DIAG_PRINC": "J18",
        "VAL_TOT": 1500.50,
        "ANO_CMPT": 2023,
        "MES_CMPT": 6,
    }
    linha.update(overrides)
    return linha


def test_transformar_detalhado_registro_valido():
    """Um registro íntegro atravessa todas as etapas e chega à carga."""
    df_bruto = pd.DataFrame([_linha()])
    df_final, estatisticas = transformar_detalhado(df_bruto)

    assert len(df_final) == 1
    registro = df_final.iloc[0]
    assert registro["municipio_codigo"] == CODIGO_FRANCISCO_BELTRAO
    assert registro["idade"] == 45
    assert registro["sexo"] == "M"
    assert registro["faixa_etaria"] == "41-50"
    assert registro["cid_principal"] == "J18"
    assert registro["cid_capitulo"] == "X"
    assert registro["valor_total"] == pytest.approx(1500.50)
    assert registro["ano_competencia"] == 2023
    assert registro["mes_competencia"] == 6


def test_transformar_detalhado_filtra_fora_da_regiao():
    """RF-02 — registros de municípios fora do Sudoeste do PR são removidos."""
    df_bruto = pd.DataFrame([
        _linha(),
        _linha(MUNIC_RES=CODIGO_PATO_BRANCO),
        _linha(MUNIC_RES=CODIGO_CURITIBA),
    ])
    df_final, estatisticas = transformar_detalhado(df_bruto)

    assert estatisticas.brutos == 3
    assert estatisticas.fora_da_regiao == 1
    assert estatisticas.finais == 2
    assert CODIGO_CURITIBA not in set(df_final["municipio_codigo"])


def test_transformar_detalhado_contabiliza_descartes_por_motivo():
    """Cada registro inconsistente é contado uma única vez, sob um motivo."""
    df_bruto = pd.DataFrame([
        _linha(),                          # válido
        _linha(IDADE=30, COD_IDADE="9"),   # idade indecifrável
        _linha(SEXO="0"),                  # sexo ignorado
        _linha(DIAG_PRINC="999"),          # CID fora do padrão
        _linha(VAL_TOT="-10"),             # valor negativo
    ])
    df_final, estatisticas = transformar_detalhado(df_bruto)

    assert estatisticas.brutos == 5
    assert estatisticas.fora_da_regiao == 0
    assert estatisticas.descartes == {
        "idade_indecifravel": 1,
        "sexo_invalido": 1,
        "cid_desconhecido": 1,
        "valor_invalido": 1,
    }
    assert estatisticas.total_descartados == 4
    assert estatisticas.finais == 1
    assert len(df_final) == 1


def test_transformar_detalhado_recem_nascido_cai_na_primeira_faixa():
    """Idade em dias é convertida para 0 anos e classificada em '0-10'."""
    df_bruto = pd.DataFrame([_linha(IDADE=3, COD_IDADE="2", DIAG_PRINC="P07")])
    df_final, _ = transformar_detalhado(df_bruto)

    assert df_final.iloc[0]["idade"] == 0
    assert df_final.iloc[0]["faixa_etaria"] == "0-10"
    assert df_final.iloc[0]["cid_capitulo"] == "XVI"


def test_transformar_detalhado_centenario():
    """COD_IDADE = 5 soma 100 à idade e classifica o registro em '61+'."""
    df_bruto = pd.DataFrame([_linha(IDADE=4, COD_IDADE="5")])
    df_final, _ = transformar_detalhado(df_bruto)

    assert df_final.iloc[0]["idade"] == 104
    assert df_final.iloc[0]["faixa_etaria"] == "61+"


def test_transformar_detalhado_sem_coluna_cod_idade():
    """Bases sem COD_IDADE tratam IDADE como anos completos."""
    linha = _linha()
    del linha["COD_IDADE"]
    df_final, _ = transformar_detalhado(pd.DataFrame([linha]))

    assert df_final.iloc[0]["idade"] == 45
    assert df_final.iloc[0]["faixa_etaria"] == "41-50"


# ---------------------------------------------------------------------------
# Estatísticas
# ---------------------------------------------------------------------------


def test_estatisticas_acumulam_descartes_por_motivo():
    """Chamadas repetidas com o mesmo motivo somam; quantidade zero é ignorada."""
    estatisticas = EstatisticasTransformacao()
    estatisticas.registrar_descarte("sexo_invalido", 2)
    estatisticas.registrar_descarte("sexo_invalido", 3)
    estatisticas.registrar_descarte("cid_desconhecido", 0)

    assert estatisticas.descartes == {"sexo_invalido": 5}
    assert estatisticas.total_descartados == 5


def test_transformar_devolve_apenas_o_dataframe():
    """O wrapper `transformar` expõe o mesmo resultado sem as estatísticas."""
    from etl.transformer import transformar

    df_bruto = pd.DataFrame([_linha(), _linha(MUNIC_RES=CODIGO_CURITIBA)])
    df_final = transformar(df_bruto)

    assert isinstance(df_final, pd.DataFrame)
    assert len(df_final) == 1
    assert df_final.iloc[0]["cid_capitulo"] == "X"
