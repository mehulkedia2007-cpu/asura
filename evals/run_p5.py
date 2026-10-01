"""Offline P5 regression gates. Synthetic notices/answers; reviewed public corpus."""
import json
from datetime import UTC, datetime
from pathlib import Path

from daari.intel.corpus import seed, select
from daari.interview.feedback import feedback
from daari.interview.guard import validate
from daari.prep.notice import extract

HERE = Path(__file__).resolve().parent


def rows(name: str) -> list[dict]:
    return [json.loads(line) for line in (HERE / name).read_text().splitlines() if line.strip()]


def evaluate() -> dict:
    correct = total = privacy = 0
    notices = rows("notices_golden.jsonl")
    for case in notices:
        result = extract(case["text"])
        for key, expected in case["expected"].items():
            total += 1
            correct += result["fields"][key]["value"] == expected
        privacy += sum(word in json.dumps(result, ensure_ascii=False) for word in case["forbidden"])
    recalled = relevant = no_data_violations = 0
    intel = rows("intel_golden.jsonl")
    for case in intel:
        result = select(seed(), case["company"], case["role"], case["query"], limit=5)
        actual = {r["id"] for r in result["questions"]}
        relevant += len(case["relevant_ids"])
        recalled += len(actual.intersection(case["relevant_ids"]))
        if not case["relevant_ids"]:
            no_data_violations += bool(actual)
    mentioned = wanted = quotes = items = 0
    adversarial = 0
    cases = rows("feedback_golden.jsonl")
    for case in cases:
        result = feedback(case["transcript"], case["locale"])
        actual = {row["code"] for row in result["feedback"]}
        mentioned += len(actual.intersection(case["must_mention"]))
        wanted += len(case["must_mention"])
        for row in result["feedback"]:
            quotes += row["quote"] in case["transcript"]
            items += 1
            for bad in ({**row, "quote": "invented quote"}, {**row, "point": "You will be hired"},
                        {**row, "code": "unmeasured_trait"}, {**row, "source": "prosody"}):
                adversarial += bool(validate([bad], case["transcript"], result["feedback"]))
    report = {"checked_at": datetime.now(UTC).isoformat(), "scope": "development regression; not an independent holdout or field validation",
              "intel": {"cases": len(intel), "recall_at_5": recalled/max(1,relevant), "no_data_violations": no_data_violations},
              "notices": {"cases": len(notices), "field_accuracy": correct/total, "privacy_violations": privacy},
              "feedback": {"cases": len(cases), "must_mention_recall": mentioned/wanted, "quote_specificity": quotes/items,
                           "adversarial_violations": adversarial, "adversarial_cases": items*4}}
    report["passed"] = (report["intel"]["recall_at_5"] >= .7 and report["notices"]["field_accuracy"] >= .9
                        and report["feedback"]["must_mention_recall"] >= .8 and privacy+no_data_violations+adversarial == 0)
    return report


if __name__ == "__main__":
    report = evaluate()
    (HERE / "p5_report.json").write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["passed"] else 1)
