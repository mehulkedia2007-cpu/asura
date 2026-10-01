"""Reviewed trilingual feedback templates anchored to lexical measurements."""

import re

from daari_core.interview_metrics import FILLERS, measure, weakest_star

from daari.interview.guard import validate

COPY = {
    "situation": ("Situation cue not detected", "Add the context of one real example.", "సందర్భ సూచన కనిపించలేదు", "ఒక నిజమైన ఉదాహరణ నేపథ్యాన్ని చెప్పండి.", "स्थिति का संकेत नहीं मिला", "एक वास्तविक उदाहरण का संदर्भ जोड़ें।"),
    "task": ("Task cue not detected", "State your responsibility or goal.", "పని సూచన కనిపించలేదు", "మీ బాధ్యత లేదా లక్ష్యాన్ని చెప్పండి.", "कार्य का संकेत नहीं मिला", "अपनी जिम्मेदारी या लक्ष्य बताएँ।"),
    "action": ("Action cue not detected", "Describe what you personally did.", "చర్య సూచన కనిపించలేదు", "మీరు స్వయంగా ఏం చేశారో చెప్పండి.", "कार्रवाई का संकेत नहीं मिला", "बताएँ कि आपने खुद क्या किया।"),
    "result": ("Result cue not detected", "Describe the outcome without inventing a number.", "ఫలిత సూచన కనిపించలేదు", "సంఖ్యను కల్పించకుండా ఫలితాన్ని చెప్పండి.", "परिणाम का संकेत नहीं मिला", "बिना संख्या गढ़े परिणाम बताएँ।"),
    "quantifiers": ("No numeric detail detected", "Add a measured detail only if you can verify it.", "సంఖ్యాత్మక వివరాలు కనిపించలేదు", "ధృవీకరించగలిగితేనే కొలిచిన వివరాన్ని జోడించండి.", "संख्यात्मक विवरण नहीं मिला", "मापा हुआ विवरण तभी जोड़ें जब सत्यापित कर सकें।"),
    "fillers": ("Filler words detected", "Try a short silent pause before the next point.", "ఊత పదాలు కనిపించాయి", "తర్వాతి విషయానికి ముందు చిన్న విరామం ఇవ్వండి.", "भराव शब्द मिले", "अगली बात से पहले छोटा मौन विराम लें।"),
    "keywords": ("Some job keywords are absent", "Explain a relevant skill with a truthful example.", "కొన్ని ఉద్యోగ పదాలు లేవు", "సంబంధిత నైపుణ్యాన్ని నిజమైన ఉదాహరణతో వివరించండి.", "कुछ नौकरी के शब्द अनुपस्थित हैं", "संबंधित कौशल का सच्चा उदाहरण दें।"),
    "structure": ("Review the example structure", "Check that context, responsibility, action and outcome connect.", "ఉదాహరణ నిర్మాణాన్ని సమీక్షించండి", "సందర్భం, బాధ్యత, చర్య, ఫలితం అనుసంధానంగా ఉన్నాయో చూడండి.", "उदाहरण की संरचना देखें", "संदर्भ, जिम्मेदारी, कार्रवाई और परिणाम का संबंध जाँचें।"),
    "evidence": ("Check the evidence in this answer", "Keep only details you can explain from your own experience.", "సమాధానంలోని ఆధారాన్ని తనిఖీ చేయండి", "మీ అనుభవం నుంచి వివరించగల వివరాలనే ఉంచండి.", "उत्तर के प्रमाण जाँचें", "अपने अनुभव से समझा सकने वाले विवरण ही रखें।"),
    "focus": ("Practice a focused retelling", "Retell this example with one main point per sentence.", "స్పష్టంగా మళ్లీ చెప్పడం సాధన చేయండి", "ఒక్కో వాక్యంలో ఒక ముఖ్య విషయం చెప్పండి.", "केंद्रित उत्तर का अभ्यास करें", "हर वाक्य में एक मुख्य बात रखें।"),
}
FOLLOWUP = {
    "situation": ("What was happening at the start?", "మొదట ఏం జరుగుతోంది?", "शुरुआत में क्या हो रहा था?"),
    "task": ("What were you responsible for?", "మీ బాధ్యత ఏమిటి?", "आपकी जिम्मेदारी क्या थी?"),
    "action": ("What did you do yourself?", "మీరు స్వయంగా ఏం చేశారు?", "आपने खुद क्या किया?"),
    "result": ("What changed after your action?", "మీ చర్య తర్వాత ఏం మారింది?", "आपकी कार्रवाई के बाद क्या बदला?"),
}


def feedback(transcript: str, locale: str = "en", duration: float | None = None,
             keywords: tuple[str, ...] = ()) -> dict:
    metrics = measure(transcript, duration, keywords)
    index = {"en": 0, "te": 2, "hi": 4}[locale]
    quote = transcript.strip()[:200]
    codes = [key for key, found in metrics["star"].items() if not found]
    if not metrics["quantifiers"]:
        codes.append("quantifiers")
    if metrics["filler_count"]:
        codes.insert(0, "fillers")
    if metrics["missing_keywords"]:
        codes.insert(0, "keywords")
    for code in ("structure", "evidence", "focus"):
        if len(codes) < 3:
            codes.append(code)
    items = [{"code": code, "point": COPY[code][index], "fix": COPY[code][index+1], "quote": quote,
              "source": "text", "severity": "info" if code in {"structure", "evidence", "focus"} else "practice"}
             for code in codes[:6]] if quote else []
    for item in items:
        if item["code"] == "fillers":
            match = re.search(r"(?<!\w)(?:" + "|".join(re.escape(word) for word in FILLERS) + r")(?!\w)", transcript, re.IGNORECASE)
            if match:
                item["quote"] = transcript[max(0, match.start()-30):min(len(transcript), match.end()+60)]
    weakest = weakest_star(metrics)
    return {"metrics": metrics, "feedback": validate(items, transcript, items),
            "followup": FOLLOWUP[weakest][index // 2] if weakest else None,
            "weakest_star": weakest, "mode": "metrics_template", "prosody": {"status": "not_measured"},
            "specificity": 1.0 if items else None,
            "limitations": "lexical_indicators_not_semantic_grading"}
