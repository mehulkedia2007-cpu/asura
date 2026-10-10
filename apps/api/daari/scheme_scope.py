"""Restrict source records to the AP / national scheme catalog."""
import re


def ap_or_national(record: dict) -> bool:
    purpose = " ".join(str(record.get(field) or "") for field in (
        "summary_en", "benefit_text", "eligibility_text")).casefold()
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
