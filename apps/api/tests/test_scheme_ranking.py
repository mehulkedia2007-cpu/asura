"""Behavior regressions use new records and queries, not golden-set IDs."""

from daari.scheme_index import _content
from daari.scheme_ranking import rank_records, tokens
from daari.schemes import merge_detail, normalize


def record(sid, title, body="", **extra):
    return {"id": sid, "name_en": title, "benefit_text": body, **extra}


def test_targeted_training_beats_boilerplate_and_unrelated_benefits():
    records = [
        record("mobility", "Disability pension", "Support for disabled people"),
        record(
            "course",
            "Accessible vocational training",
            "Skills for persons with disabilities",
        ),
        record("general", "Training course", "Employment skills"),
    ]
    assert (
        rank_records("training for disabled applicants", records, 1)[0]["id"]
        == "course"
    )
    assert rank_records("వికలాంగులకు శిక్షణ", records, 1)[0]["id"] == "course"


def test_application_instructions_do_not_define_scheme_purpose():
    records = [
        record(
            "unrelated",
            "Housing support",
            "Build a home",
            apply_text="digital training " * 1000,
        ),
        record("relevant", "Electronics skills course", "Digital training"),
    ]
    assert rank_records("digital training", records, 1)[0]["id"] == "relevant"


def test_it_pronoun_is_not_information_technology():
    assert "digital" not in tokens("It offers a loan and it covers fees")
    assert "digital" in tokens("IT course")
    assert "digital" in tokens("ఐటీ శిక్షణ")
    assert "digital" in tokens("FutureSkills Prime Incentive Program")


def test_empty_and_unmatched_queries_abstain_and_native_titles_work():
    records = [record("one", "Housing support", name_te="గృహనిర్మాణం")]
    assert rank_records("", records) == []
    assert rank_records("quantum astrophysics", records) == []
    assert rank_records("గృహనిర్మాణం", records)[0]["id"] == "one"
    assert rank_records("housing", records, 0) == []


def test_duplicate_source_cards_do_not_use_two_top_five_slots():
    records = [
        record("my-scheme", "Enterprise Development and Skills Programme", "Training grants"),
        record("ap-directory", "Enterprise Development and Skills Programme", ""),
        record("other", "Youth Business Training", "Training for entrepreneurs"),
    ]
    results = rank_records("development skills training", records, 2, dedupe_duplicates=True)
    assert len(results) == 2
    assert len({row["name_en"].casefold() for row in results}) == 2
    assert results[0]["id"] == "my-scheme"


def test_ranking_uses_evidence_not_record_ids_or_input_order():
    records = [record("a", "Apprenticeship training"), record("b", "Housing support")]
    assert (
        rank_records("apprentice", records)[0]["name_en"] == "Apprenticeship training"
    )
    renamed = [{**r, "id": str(i)} for i, r in enumerate(reversed(records))]
    assert (
        rank_records("apprentice", renamed)[0]["name_en"] == "Apprenticeship training"
    )


def test_detail_merge_preserves_search_description_and_tags():
    scheme = normalize(
        {
            "slug": "new-course",
            "schemeName": "New course",
            "level": "Central",
            "briefDescription": "Training in robotics",
            "tags": ["Robotics"],
        },
        "2026-09-25T00:00:00+00:00",
    )
    assert scheme is not None
    merge_detail(
        scheme,
        {
            "en": {"schemeContent": {"benefits_md": "Course fees reimbursed"}},
            "te": {},
            "documents": {},
            "channels": [],
            "fetched_at": "2026-09-25T01:00:00+00:00",
            "stale": False,
        },
    )
    assert scheme["summary_en"] == "Training in robotics"
    assert scheme["tags"] == ["Robotics"]
    assert "robotics" in _content(scheme, "en")
    assert not scheme["rules_complete"]


def test_semantic_candidates_survive_when_lexical_vocabulary_misses():
    records = [record("one", "Information systems course")]
    assert rank_records("computer science", records) == []
    assert (
        rank_records("computer science", records, prior={"one": 0.01})[0]["id"] == "one"
    )
    assert rank_records("", records, prior={"one": 0.01}) == []
