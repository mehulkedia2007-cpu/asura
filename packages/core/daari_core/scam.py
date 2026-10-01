"""Explainable rule-based scam signals. Unknown pay medians add no score."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ScamResult:
    score: float
    reasons: tuple[str, ...]
    badge: str


def score(description: str, org: str, contact: str = "", pay: float | None = None,
          district_median: float | None = None) -> ScamResult:
    content = f"{description} {contact}".casefold()
    reasons: list[str] = []
    value = 0.0
    payment_pattern = (
        r"(?:registration|training|application|joining|security|processing|రిజిస్ట్రేషన్|"
        r"నమోదు|శిక్షణ|దరఖాస్తు|చేరిక|సెక్యూరిటీ|ప్రాసెసింగ్|पंजीकरण|आवेदन|ప్రशिक्षण|"
        r"जॉइनिंग|सिक्योरिटी|प्रोसेसिंग)\s*"
        r"(?:fee|charge|deposit|payment|ఫీజు|రుసుము|చార్జ్|డిపాజిట్|చెల్లింపు|"
        r"फीस|शुल्क|जमा|भुगतान)|pay\s+(?:a|the)?\s*(?:fee|deposit)|"
        r"(?:చెల్లించ(?:ండి|ాలి)|भुगतान\s+करें)\s*(?:fee|ఫీజు|రుసుము|फीस|शुल्क)?|"
        r"upfront\s+payment|refundable\s+deposit|"
        r"(?:transfer|send|gpay|paytm|upi|బదిలీ|పంపండి|ट्रांसफर|भेजें)\s*"
        r"(?:₹|rs\.?\s*)?\d+(?:\s+rupees?)?"
    )
    payment_negation = (
        r"\b(?:no|without|never|do not charge|don't charge|not required to pay|"
        r"beware of scams asking you to)\b|(?:ఫీజు లేదు|రుసుము లేదు|చార్జ్ లేదు|"
        r"చెల్లింపు లేదు|చెల్లించాల్సిన అవసరం లేదు|ఫీసు లేదు|फीस नहीं|शुल्क नहीं|"
        r"कोई शुल्क नहीं|भुगतान नहीं|भुगतान की आवश्यकता नहीं)"
    )
    asks_payment = any(
        not re.search(
            r"(?:" + payment_negation + r")(?:(?![.!?;]).){0,45}$",
            content[max(0, match.start() - 80):match.start()],
        )
        for match in re.finditer(payment_pattern, content)
    )
    if asks_payment:
        value += 0.5
        reasons.append("Asks for an application, training or joining payment")
    if re.search(
        r"(?:whatsapp|telegram|వాట్సాప్|టెలిగ్రామ్|व्हाट्सऐप|टेलीग्राम)[- ]only|"
        r"only\s+(?:on|via|through)\s+(?:whatsapp|telegram)|"
        r"(?:whatsapp|telegram|వాట్సాప్|టెలిగ్రామ్|व्हाट्सऐप|टेलीग्राम)\s*"
        r"(?:ద్వారా మాత్రమే|మాత్రమే|కేవలం|केवल|के जरिए)",
        content,
    ):
        value += 0.2
        reasons.append("Contact is restricted to WhatsApp or Telegram")
    if pay is not None and district_median is not None and district_median > 0 and pay > 3 * district_median:
        value += 0.2
        reasons.append("Advertised pay exceeds three times the district role median")
    if not org.strip() or org.strip().casefold() in {"confidential", "unknown", "private"}:
        value += 0.1
        reasons.append("Employer is not identified")
    if re.search(r"earn\s+from\s+home", content) and re.search(r"no\s+(?:skill|experience)", content):
        value += 0.2
        reasons.append("Promises home earnings without skills or experience")
    if re.search(r"[\w.+-]+@(?:gmail|yahoo|outlook|hotmail)\.[\w.-]+", contact, re.IGNORECASE):
        value += 0.1
        reasons.append("Employer uses a free email domain")
    value = min(1.0, round(value, 2))
    return ScamResult(value, tuple(reasons), "red" if value >= 0.5 else "amber" if value >= 0.3 else "none")
