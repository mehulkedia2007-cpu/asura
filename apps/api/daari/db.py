"""Async SQLAlchemy engine + sessionmaker, built from Settings.DATABASE_URL."""

import ssl

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from daari.config import settings


def _to_asyncpg_url(url: str) -> str:
    """Normalize cloud libpq URLs to asyncpg without weakening TLS verification."""
    parsed = make_url(url)
    if parsed.drivername in {"postgres", "postgresql", "postgresql+asyncpg"}:
        parsed = parsed.set(drivername="postgresql+asyncpg")
    query = dict(parsed.query)
    mode = query.pop("sslmode", None)
    # channel_binding is a libpq setting; asyncpg does not accept that keyword.
    # verify-full validates both the CA chain and hostname for remote databases.
    query.pop("channel_binding", None)
    if mode:
        query["ssl"] = "verify-full" if mode in {"require", "verify-ca"} else mode
    return parsed.set(query=query).render_as_string(hide_password=False)


def _connect_args(url: str) -> dict:
    # asyncpg's string TLS modes look for ~/.postgresql/root.crt. Serverless
    # machines instead use the system CA bundle through a verified SSLContext.
    query = make_url(_to_asyncpg_url(url)).query
    if query.get("ssl") in {"require", "verify-ca", "verify-full"}:
        return {"ssl": ssl.create_default_context()}
    return {}


engine = create_async_engine(
    _to_asyncpg_url(settings.database_url), pool_pre_ping=True,
    connect_args=_connect_args(settings.database_url),
    **({"poolclass": NullPool} if settings.VERCEL else {}),
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
