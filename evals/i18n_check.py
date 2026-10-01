"""Fail CI when a product locale lacks a translation key or has an empty value."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "apps/web/messages"


def unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    data = {}
    for key, value in pairs:
        if key in data:
            raise ValueError(f"duplicate translation key: {key}")
        data[key] = value
    return data


def flatten(data: dict, prefix: str = "") -> dict[str, str]:
    result = {}
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.update(flatten(value, path))
        else:
            result[path] = value
    return result


def main() -> int:
    locales = {locale: flatten(json.loads((ROOT / f"{locale}.json").read_text(),
                                          object_pairs_hook=unique_pairs))
               for locale in ("en", "te", "hi")}
    reference = set(locales["en"])
    failures = []
    for locale, values in locales.items():
        failures.extend(f"{locale}: missing {key}" for key in sorted(reference - set(values)))
        failures.extend(f"{locale}: extra {key}" for key in sorted(set(values) - reference))
        failures.extend(f"{locale}: empty {key}" for key, value in values.items()
                        if not isinstance(value, str) or not value.strip())
    if failures:
        print("\n".join(failures))
        return 1
    print(f"i18n: {len(reference)} keys complete in en, te and hi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
