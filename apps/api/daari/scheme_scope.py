"""Restrict source records to the AP / national scheme catalog."""
import re

_OTHER_REGIONS = (
    "arunachal pradesh", "assam", "bihar", "chhattisgarh", "goa", "gujarat",
    "haryana", "himachal pradesh", "jharkhand", "karnataka", "kerala",
    "madhya pradesh", "maharashtra", "manipur", "meghalaya", "mizoram",
    "nagaland", "odisha", "orissa", "punjab", "rajasthan", "sikkim",
    "tamil nadu", "telangana", "tripura", "uttar pradesh", "uttarakhand",
    "west bengal", "jammu and kashmir", "ladakh", "delhi", "chandigarh",
    "puducherry", "lakshadweep", "andaman and nicobar",
)


def ap_or_national(record: dict) -> bool:
    title = str(record.get("name_en") or "").casefold()
    purpose = " ".join(str(record.get(field) or "") for field in (
        "summary_en", "benefit_text", "eligibility_text")).casefold()
    # Older snapshots may omit beneficiaryState. A central sponsor does not
    # make a scheme national when its source names a restricted region.
    if re.search(r"north[ -]?east(?:ern)?", title) or re.search(
        r"(?:in|within|for) (?:the )?north[ -]?east(?:ern)? (?:region|states)", purpose
    ):
        return False
    if any(re.search(r"\b" + re.escape(region) + r"\b", title) for region in _OTHER_REGIONS):
        return False
    if re.search(r"(?:for|to) (?:afghan|foreign|international|non.indian) (?:students|nationals|citizens)", title):
        return False
    if re.search(r"(?:of|from) asean member countries|foreign nationals only|non.indian citizens only", purpose):
        return False
    state = str(record.get("state") or "").strip().casefold()
    beneficiaries = str(record.get("beneficiary_states") or "").casefold()
    broad = not beneficiaries or any(term in beneficiaries for term in (
        "all states", "all india", "pan india", "all-state", "allstate", "nationwide"))
    if beneficiaries and not broad and "andhra pradesh" not in beneficiaries:
        return False
    if state and state != "andhra pradesh":
        return False
    return state == "andhra pradesh" or "andhra pradesh" in str(record.get("level") or "").casefold() or (
        not state and "central" in str(record.get("level") or "").casefold())
