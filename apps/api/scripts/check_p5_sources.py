"""Explicit public-source refresh rehearsal; reports no content or credentials."""
import asyncio
import json

from daari.db import engine
from daari.intel.corpus import search
from daari.intel.fetchers import refresh


async def main() -> None:
    try:
        refreshed = await refresh("tcs", "Prime")
        result = await search("tcs", "Prime")
        print(json.dumps({"refresh": refreshed, "coverage": result["stats"], "storage": result["storage"]}, indent=2))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
