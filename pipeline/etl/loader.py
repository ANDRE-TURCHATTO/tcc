"""
etl/loader.py — RF-05: Carga dos dados transformados no Supabase (PostgreSQL).

Realiza UPSERT dos registros de internações, dos municípios do Sudoeste
do Paraná e do denominador populacional nas tabelas do banco, registrando o
progresso em log.
"""

import json
import logging
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from config import DATA_DIR, MUNICIPIOS_CSV, SUPABASE_DB_URL

logger = logging.getLogger(__name__)

# Tamanho do lote para inserção em massa (ajustável conforme o ambiente)
TAMANHO_LOTE: int = 1000

# Denominador populacional gerado por `baixar_populacao.py`
POPULACAO_CSV = DATA_DIR / "populacao_municipio.csv"

# Malha territorial gerada por `gerar_malha.py`
GEOJSON_PADRAO = DATA_DIR.parent.parent / "backend" / "public" / "geo" / "sudoeste-pr.geojson"


def _criar_engine():
    """
    Cria e retorna a engine SQLAlchemy conectada ao Supabase.

    Returns:
        sqlalchemy.engine.Engine: Engine de conexão com o banco.

    Raises:
        RuntimeError: Se a URL de conexão não estiver configurada.
    """
    if not SUPABASE_DB_URL or SUPABASE_DB_URL.startswith("postgresql://:"):
        raise RuntimeError(
            "Variáveis de ambiente de conexão com o Supabase não configuradas. "
            "Verifique o arquivo .env."
        )
    return create_engine(SUPABASE_DB_URL, pool_pre_ping=True)


def carregar_municipios() -> int:
    """
    Realiza o UPSERT dos municípios do Sudoeste do Paraná na tabela
    `municipios_sudoeste`.

    Lê os dados do arquivo CSV de referência e insere/atualiza os registros
    no banco, utilizando a cláusula ON CONFLICT DO UPDATE.

    Returns:
        int: Número de municípios processados.

    Raises:
        SQLAlchemyError: Em caso de erro durante a carga.
    """
    df_mun = pd.read_csv(MUNICIPIOS_CSV, dtype={"codigo_ibge": str})
    engine = _criar_engine()

    sql_upsert = text("""
        INSERT INTO municipios_sudoeste (codigo_ibge, nome, microrregiao)
        VALUES (:codigo_ibge, :nome, :microrregiao)
        ON CONFLICT (codigo_ibge) DO UPDATE
            SET nome         = EXCLUDED.nome,
                microrregiao = EXCLUDED.microrregiao
    """)

    total = 0
    try:
        with engine.begin() as conn:
            for _, row in df_mun.iterrows():
                conn.execute(sql_upsert, {
                    "codigo_ibge": str(row["codigo_ibge"]).strip(),
                    "nome": str(row["nome"]).strip(),
                    "microrregiao": str(row["microrregiao"]).strip() if pd.notna(row.get("microrregiao")) else None,
                })
                total += 1
    except SQLAlchemyError as exc:
        raise SQLAlchemyError(f"Erro ao carregar municípios: {exc}") from exc

    logger.info("Municípios carregados/atualizados: %d", total)
    return total


def carregar_populacao() -> int:
    """
    Realiza o UPSERT do denominador populacional na tabela
    `populacao_municipio` (RF-17).

    Lê o CSV gerado por `baixar_populacao.py`, que obtém os dados da API de
    agregados do IBGE. A carga é idempotente: a chave primária composta
    (codigo_ibge, ano) permite reexecutar o pipeline sem duplicar registros.

    Returns:
        int: Número de municípios processados. Zero se o arquivo não existir.

    Raises:
        SQLAlchemyError: Em caso de erro durante a carga.
    """
    if not POPULACAO_CSV.exists():
        logger.warning(
            "Denominador populacional não encontrado em %s — as taxas por 100 mil "
            "habitantes ficarão indisponíveis. Execute: python baixar_populacao.py",
            POPULACAO_CSV,
        )
        return 0

    df_pop = pd.read_csv(POPULACAO_CSV, dtype={"codigo_ibge": str})
    engine = _criar_engine()

    sql_upsert = text("""
        INSERT INTO populacao_municipio (codigo_ibge, ano, populacao, fonte)
        VALUES (:codigo_ibge, :ano, :populacao, :fonte)
        ON CONFLICT (codigo_ibge, ano) DO UPDATE
            SET populacao = EXCLUDED.populacao,
                fonte     = EXCLUDED.fonte
    """)

    total = 0
    try:
        with engine.begin() as conn:
            for _, row in df_pop.iterrows():
                conn.execute(sql_upsert, {
                    "codigo_ibge": str(row["codigo_ibge"]).strip(),
                    "ano": int(row["ano"]),
                    "populacao": int(row["populacao"]),
                    "fonte": str(row["fonte"]).strip(),
                })
                total += 1
    except SQLAlchemyError as exc:
        raise SQLAlchemyError(f"Erro ao carregar a população: {exc}") from exc

    logger.info("População carregada/atualizada: %d municípios.", total)
    return total


def carregar_geometrias(caminho_geojson=None) -> int:
    """
    Carrega a geometria dos municípios na coluna espacial de
    `municipios_sudoeste`.

    As feições vêm do GeoJSON gerado por `gerar_malha.py` a partir da API de
    malhas do IBGE. A geometria é convertida para MultiPolygon e gravada em
    SRID 4674 (SIRGAS 2000), o sistema de referência oficial do IBGE.

    Armazenar a geometria no banco é o que viabiliza as consultas espaciais
    da análise de vizinhança (`backend/sql/analise_espacial.sql`).

    Args:
        caminho_geojson (Path | None): GeoJSON de origem. Quando omitido,
            usa o arquivo servido pelo backend.

    Returns:
        int: Número de municípios com geometria atualizada.

    Raises:
        SQLAlchemyError: Em caso de erro durante a carga.
    """
    caminho = Path(caminho_geojson) if caminho_geojson else GEOJSON_PADRAO
    if not caminho.exists():
        logger.warning(
            "Malha não encontrada em %s — as consultas espaciais ficarão "
            "indisponíveis. Execute: python gerar_malha.py",
            caminho,
        )
        return 0

    colecao = json.loads(caminho.read_text(encoding="utf-8"))
    engine = _criar_engine()

    # ST_Multi normaliza Polygon e MultiPolygon em um único tipo, atendendo à
    # restrição da coluna
    sql_update = text("""
        UPDATE municipios_sudoeste
           SET geometria = ST_Multi(
                   ST_SetSRID(ST_GeomFromGeoJSON(:geometria), 4674)
               )
         WHERE codigo_ibge = :codigo_ibge
    """)

    total = 0
    try:
        with engine.begin() as conn:
            for feicao in colecao.get("features", []):
                codigo = str(feicao["properties"]["codigo_ibge"]).strip()
                resultado = conn.execute(sql_update, {
                    "codigo_ibge": codigo,
                    "geometria": json.dumps(feicao["geometry"]),
                })
                total += resultado.rowcount or 0
    except SQLAlchemyError as exc:
        raise SQLAlchemyError(f"Erro ao carregar as geometrias: {exc}") from exc

    logger.info("Geometrias carregadas/atualizadas: %d municípios.", total)
    return total


def carregar_internacoes(df: pd.DataFrame) -> int:
    """
    Realiza o UPSERT em lote dos registros de internações na tabela
    `internacoes`.

    Os registros são inseridos em lotes de tamanho TAMANHO_LOTE para
    evitar sobrecarga de memória. Não há chave única natural além do
    SERIAL, portanto é utilizado INSERT simples (idempotência garantida
    pelo controle de execução do pipeline por mês/ano).

    Args:
        df (pd.DataFrame): DataFrame transformado e pronto para carga.

    Returns:
        int: Total de registros inseridos.

    Raises:
        SQLAlchemyError: Em caso de erro durante a carga.
    """
    if df.empty:
        logger.warning("DataFrame vazio — nenhum registro para carregar.")
        return 0

    engine = _criar_engine()
    total_inseridos = 0

    # Colunas esperadas pela tabela internacoes
    colunas = [
        "municipio_codigo", "idade", "sexo", "faixa_etaria",
        "cid_principal", "cid_capitulo", "valor_total",
        "ano_competencia", "mes_competencia",
    ]

    # Verifica se todas as colunas necessárias estão presentes
    colunas_faltando = [c for c in colunas if c not in df.columns]
    if colunas_faltando:
        raise ValueError(
            f"Colunas ausentes no DataFrame: {colunas_faltando}"
        )

    df_carga = df[colunas].copy()
    total_registros = len(df_carga)
    num_lotes = (total_registros + TAMANHO_LOTE - 1) // TAMANHO_LOTE

    logger.info(
        "Iniciando carga de %d registros em %d lote(s) de até %d.",
        total_registros,
        num_lotes,
        TAMANHO_LOTE,
    )

    i = 0
    try:
        with engine.begin() as conn:
            for i in range(num_lotes):
                inicio = i * TAMANHO_LOTE
                fim = min(inicio + TAMANHO_LOTE, total_registros)
                lote = df_carga.iloc[inicio:fim]

                lote.to_sql(
                    name="internacoes",
                    con=conn,
                    if_exists="append",
                    index=False,
                    method="multi",
                )

                total_inseridos += len(lote)
                logger.info(
                    "Lote %d/%d — %d registros inseridos (total acumulado: %d).",
                    i + 1,
                    num_lotes,
                    len(lote),
                    total_inseridos,
                )
    except SQLAlchemyError as exc:
        raise SQLAlchemyError(
            f"Erro ao carregar internações no lote {i + 1}: {exc}"
        ) from exc

    logger.info("Carga concluída — total de %d registros inseridos.", total_inseridos)
    return total_inseridos
