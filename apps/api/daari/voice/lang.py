"""Small, predictable language detector; Tenglish follows the selected locale."""

from typing import Literal

Locale = Literal["en", "te", "hi"]


def detect(text: str, selected: Locale = "en") -> Locale:
    telugu = sum("\u0c00" <= char <= "\u0c7f" for char in text)
    hindi = sum("\u0900" <= char <= "\u097f" for char in text)
    if telugu > hindi and telugu:
        return "te"
    if hindi > telugu and hindi:
        return "hi"
    return selected


def speech_locale(locale: Locale) -> str:
    return {"en": "en-IN", "te": "te-IN", "hi": "hi-IN"}[locale]
