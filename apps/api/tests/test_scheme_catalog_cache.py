import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from daari import scheme_index


@pytest.mark.asyncio
async def test_catalog_reuse_does_not_share_profile_mutations_and_invalidates(monkeypatch):
    record = {"id": "public-source", "name_en": "Public scheme", "level": "Central", "state": None,
              "fetched_at": "2026-10-10T00:00:00+00:00"}
    rows = MagicMock()
    rows.scalars.return_value = [record]
    checks = MagicMock()
    checks.mappings.return_value.all.return_value = []
    conn = AsyncMock()
    conn.execute.side_effect = [rows, checks, rows, checks]
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=conn)
    context.__aexit__ = AsyncMock(return_value=False)
    engine = MagicMock()
    engine.connect.return_value = context
    monkeypatch.setattr(scheme_index, "engine", engine)
    monkeypatch.setattr(scheme_index, "_catalog_cache", None)
    monkeypatch.setattr(scheme_index, "_catalog_lock", asyncio.Lock())
    first = await scheme_index.browse()
    first[0]["eligibility"] = {"status": "true"}
    second = await scheme_index.browse()
    coverage = await scheme_index.coverage()
    assert "eligibility" not in second[0]
    assert coverage["indexed"] == 1
    assert engine.connect.call_count == 1
    scheme_index.invalidate_catalog()
    await scheme_index.browse()
    assert engine.connect.call_count == 2
