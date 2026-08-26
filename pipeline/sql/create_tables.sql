-- ============================================================
-- Script de criação das tabelas do sistema Longevus
-- Banco: PostgreSQL + PostGIS
-- Versão: 1.1
-- ============================================================

-- Extensão espacial. A geometria dos municípios é armazenada no banco, o que
-- permite executar consultas topológicas (vizinhança, contiguidade) sobre o
-- recorte territorial — ver `backend/sql/analise_espacial.sql`.
CREATE EXTENSION IF NOT EXISTS postgis;

-- Tabela de referência dos municípios do Sudoeste do Paraná.
--
-- A geometria usa SRID 4674 (SIRGAS 2000), sistema de referência oficial
-- adotado pelo IBGE para a cartografia brasileira.
CREATE TABLE IF NOT EXISTS municipios_sudoeste (
    codigo_ibge  VARCHAR(7)   PRIMARY KEY,
    nome         VARCHAR(100) NOT NULL,
    microrregiao VARCHAR(100),
    geometria    GEOMETRY(MultiPolygon, 4674)
);

-- Índice espacial: sustenta os predicados topológicos (ST_Touches, ST_Intersects)
CREATE INDEX IF NOT EXISTS idx_municipios_geometria
    ON municipios_sudoeste USING GIST (geometria);

-- Tabela principal com dados brutos filtrados e transformados do SIH/SUS
CREATE TABLE IF NOT EXISTS internacoes (
    id               SERIAL         PRIMARY KEY,
    municipio_codigo VARCHAR(7)     NOT NULL,   -- Código IBGE do município de residência
    idade            INTEGER        NOT NULL,   -- Idade em anos
    sexo             CHAR(1)        NOT NULL,   -- 'M' = Masculino, 'F' = Feminino
    faixa_etaria     VARCHAR(10)    NOT NULL,   -- Ex: '0-10', '11-20', ..., '61+'
    cid_principal    VARCHAR(4)     NOT NULL,   -- Código CID-10 (ex: 'J18')
    cid_capitulo     VARCHAR(5)     NOT NULL,   -- Capítulo CID-10 em numeral romano (ex: 'X', 'XI')
    valor_total      NUMERIC(12, 2) NOT NULL,   -- Valor pago pela internação (R$)
    ano_competencia  INTEGER        NOT NULL,   -- Ano de referência
    mes_competencia  INTEGER        NOT NULL,   -- Mês de referência
    CONSTRAINT fk_internacoes_municipio
        FOREIGN KEY (municipio_codigo)
        REFERENCES municipios_sudoeste (codigo_ibge)
);

-- Índices para otimizar as queries de filtro da API
CREATE INDEX IF NOT EXISTS idx_internacoes_cid_capitulo
    ON internacoes (cid_capitulo);

CREATE INDEX IF NOT EXISTS idx_internacoes_sexo
    ON internacoes (sexo);

CREATE INDEX IF NOT EXISTS idx_internacoes_faixa_etaria
    ON internacoes (faixa_etaria);

CREATE INDEX IF NOT EXISTS idx_internacoes_municipio
    ON internacoes (municipio_codigo);

CREATE INDEX IF NOT EXISTS idx_internacoes_competencia
    ON internacoes (ano_competencia, mes_competencia);

-- Denominador populacional das taxas de internação (RF-17)
CREATE TABLE IF NOT EXISTS populacao_municipio (
    codigo_ibge  VARCHAR(7)   NOT NULL,   -- Código IBGE do município
    ano          INTEGER      NOT NULL,   -- Ano de referência da contagem
    populacao    INTEGER      NOT NULL,   -- População residente
    fonte        VARCHAR(120) NOT NULL,   -- Ex: 'IBGE — Censo Demográfico 2022'
    PRIMARY KEY (codigo_ibge, ano),
    CONSTRAINT fk_populacao_municipio
        FOREIGN KEY (codigo_ibge)
        REFERENCES municipios_sudoeste (codigo_ibge)
);
