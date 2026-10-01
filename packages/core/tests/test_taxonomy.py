"""Failing tests for daari_core.taxonomy, written before the implementation
(T2). Loads the real T0 seed files (data/taxonomy/skills.yaml, roles.yaml)
via the conftest fixtures — the seed file *format* is proven by the
algorithm that consumes it, not by an in-test literal (D17).
"""

import ast
from pathlib import Path

from daari_core import taxonomy

CORE_DIR = Path(__file__).resolve().parent.parent / "daari_core"


def test_every_skill_node_has_a_source(skills_data):
    """data.md: 'a node without a source is not a node.'"""
    for node in skills_data:
        assert node.get("source"), f"skill {node.get('id')!r} has no source"


def test_every_node_has_en_te_hi_labels(skills_data):
    """CLAUDE.md #12 / build plan §7.1 node schema."""
    for node in skills_data:
        for field in ("label_en", "label_te", "label_hi"):
            assert node.get(field), f"skill {node.get('id')!r} missing {field}"


def _required_skill_items(raw_required):
    """`required_skills` is valid either as a `{skill_id: level}` mapping
    or as a list of `{skill_id, level}` entries; normalise to (id, level)
    pairs so the seed file's shape doesn't leak into this assertion."""
    if isinstance(raw_required, dict):
        return list(raw_required.items())
    return [(entry["skill_id"], entry["level"]) for entry in raw_required]


def test_roles_reference_only_known_skill_ids_with_levels(skills_data, roles_data):
    known_ids = {node["id"] for node in skills_data}
    assert roles_data, "expected at least one role"
    for role in roles_data:
        required = role.get("required_skills")
        assert required, f"role {role.get('id')!r} has no required_skills"
        for skill_id, level in _required_skill_items(required):
            assert skill_id in known_ids, f"role {role['id']!r} references unknown skill {skill_id!r}"
            assert isinstance(level, int) and 1 <= level <= 5, f"role {role['id']!r} skill {skill_id!r} bad level {level!r}"


def test_taxonomy_builds_from_parsed_dicts_without_io(skills_data, roles_data):
    """core.md purity: the loader takes already-parsed dicts/lists — it
    never reads a file itself. Proven two ways: the real fixture data (already
    parsed by conftest, not by taxonomy.py) builds successfully, and a static
    scan of taxonomy.py shows no `open()` call and no filesystem/YAML import.
    """
    tax = taxonomy.load(skills_data, roles_data)
    assert set(tax.skills) == {node["id"] for node in skills_data}
    assert set(tax.roles) == {role["id"] for role in roles_data}

    src = (CORE_DIR / "taxonomy.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id != "open", "taxonomy.py must not open files itself"
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in {"yaml", "pathlib", "io"}
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            assert node.module.split(".")[0] not in {"yaml", "pathlib", "io"}


def test_role_required_skills_are_reachable_on_the_taxonomy_object(skills_data, roles_data):
    tax = taxonomy.load(skills_data, roles_data)
    assert "data_analyst" in tax.roles
    assert "delivery_executive" in tax.roles
    for role in tax.roles.values():
        for skill_id in role.required_skills:
            assert skill_id in tax.skills


def test_unknown_prereq_id_raises():
    skills = [
        {
            "id": "a",
            "label_en": "A",
            "label_te": "ఎ",
            "label_hi": "ए",
            "aliases": [],
            "level": 1,
            "hours": 1,
            "source": "test",
            "prereqs": ["does_not_exist"],
        }
    ]
    try:
        taxonomy.load(skills, [])
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for unknown prereq id")


def test_unknown_role_skill_id_raises():
    skills = [
        {
            "id": "a",
            "label_en": "A",
            "label_te": "ఎ",
            "label_hi": "ए",
            "aliases": [],
            "level": 1,
            "hours": 1,
            "source": "test",
        }
    ]
    roles = [{"id": "r", "label_en": "R", "required_skills": {"does_not_exist": 2}}]
    try:
        taxonomy.load(skills, roles)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for role referencing unknown skill id")
