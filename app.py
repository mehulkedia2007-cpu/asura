"""Vercel's ASGI entrypoint; both deployments use the same monorepo engine."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / "apps/api"), str(ROOT / "packages/core")]

from daari.main import app  # noqa: F401 — exported ASGI entrypoint
