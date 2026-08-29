"""Read-only database access.

SQLAlchemy's ``text()`` binds ``:name`` parameters through the driver, so the
values Seu Jader picks in a filter can never become part of the statement.
"""

import os

from sqlalchemy import create_engine, text

_engine = None


def engine():
    global _engine
    if _engine is None:
        url = (
            f"postgresql+psycopg://{os.environ['PGUSER']}:{os.environ['PGPASSWORD']}"
            f"@{os.environ['PGHOST']}:{os.environ.get('PGPORT', '5432')}"
            f"/{os.environ['PGDATABASE']}"
        )
        _engine = create_engine(url, pool_pre_ping=True, pool_size=2, max_overflow=2)
    return _engine


def executar(s) -> list[dict]:
    with engine().connect() as conexao:
        resultado = conexao.execute(text(s.sql), s.params)
        return [dict(linha) for linha in resultado.mappings()]
