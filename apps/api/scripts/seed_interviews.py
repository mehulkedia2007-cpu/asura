"""Seed only reviewed, dated source excerpts into the P5 corpus."""
import asyncio

from daari.db import engine
from daari.intel.corpus import seed, upsert


async def main() -> None:
    try:
        await upsert(seed())
        print(f"Seeded {len(seed())} reviewed interview questions")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
