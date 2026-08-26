"""
config.py — Configurações centralizadas do pipeline Longevus.

Carrega variáveis de ambiente a partir do arquivo .env e expõe
as constantes utilizadas em todo o projeto.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Carrega o .env localizado na raiz da pasta pipeline/
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

# ---------------------------------------------------------------------------
# Conexão com o Supabase (PostgreSQL)
# ---------------------------------------------------------------------------
SUPABASE_HOST: str = os.getenv("SUPABASE_HOST", "")
SUPABASE_PORT: str = os.getenv("SUPABASE_PORT", "5432")
SUPABASE_DB: str = os.getenv("SUPABASE_DB", "postgres")
SUPABASE_USER: str = os.getenv("SUPABASE_USER", "postgres")
SUPABASE_PASSWORD: str = os.getenv("SUPABASE_PASSWORD", "")

# URL de conexão SQLAlchemy.
#
# `DATABASE_URL` tem precedência quando definida, o que permite apontar o
# pipeline para o PostgreSQL local do `docker-compose.yml` sem alterar as
# variáveis de Supabase. Na ausência dela, a URL é montada a partir das
# variáveis individuais.
SUPABASE_DB_URL: str = os.getenv("DATABASE_URL", "") or (
    f"postgresql://{SUPABASE_USER}:{SUPABASE_PASSWORD}"
    f"@{SUPABASE_HOST}:{SUPABASE_PORT}/{SUPABASE_DB}"
)

# ---------------------------------------------------------------------------
# Caminhos internos do projeto
# ---------------------------------------------------------------------------
BASE_DIR: Path = Path(__file__).parent
DATA_DIR: Path = BASE_DIR / "data"
SQL_DIR: Path = BASE_DIR / "sql"

# Arquivo CSV com os municípios do Sudoeste do PR
MUNICIPIOS_CSV: Path = DATA_DIR / "municipios_sudoeste.csv"

# ---------------------------------------------------------------------------
# Constantes do domínio
# ---------------------------------------------------------------------------

# Estado do Paraná no DATASUS
ESTADO_DATASUS: str = "PR"
