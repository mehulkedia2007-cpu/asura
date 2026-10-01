"""daari_core.taxonomy — the skill/role graph's node data.

Pure and I/O-free: `load()` takes already-parsed dicts/lists (the caller's
job is reading and parsing `data/taxonomy/skills.json` / `roles.json`; this
module never opens a file or reads the network).
It validates and shapes that data into `Taxonomy`, `SkillNode` and `Role`.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SkillNode:
    id: str
    label_en: str
    label_te: str
    label_hi: str
    aliases: tuple[str, ...]
    level: int
    hours: float
    source: str
    prereqs: tuple[str, ...] = ()


@dataclass(frozen=True)
class Role:
    id: str
    label_en: str
    label_te: str
    label_hi: str
    required_skills: dict[str, int] = field(default_factory=dict)
    source: str = ""


@dataclass(frozen=True)
class Taxonomy:
    skills: dict[str, SkillNode]
    roles: dict[str, Role]


def _build_skill_node(raw: dict) -> SkillNode:
    skill_id = raw["id"]
    node = SkillNode(
        id=skill_id,
        label_en=raw.get("label_en", ""),
        label_te=raw.get("label_te", ""),
        label_hi=raw.get("label_hi", ""),
        aliases=tuple(raw.get("aliases", [])),
        level=raw["level"],
        hours=raw["hours"],
        source=raw.get("source", ""),
        prereqs=tuple(raw.get("prereqs", [])),
    )
    if not node.source:
        raise ValueError(f"skill {skill_id!r} has no source (data.md: a node without a source is not a node)")
    if not (node.label_en and node.label_te and node.label_hi):
        raise ValueError(f"skill {skill_id!r} is missing an en/te/hi label")
    return node


def _parse_required_skills(raw_required: dict | list) -> dict[str, int]:
    """`required_skills` in the seed data may be written either as a
    mapping (`{skill_id: level}`) or as a list of `{skill_id, level}`
    entries — both are valid, equivalent shapes; normalise to a dict."""
    if isinstance(raw_required, dict):
        return dict(raw_required)
    return {entry["skill_id"]: entry["level"] for entry in raw_required}


def _build_role(raw: dict, known_skill_ids: set[str]) -> Role:
    role_id = raw["id"]
    required = _parse_required_skills(raw.get("required_skills", {}))
    for skill_id in required:
        if skill_id not in known_skill_ids:
            raise ValueError(f"role {role_id!r} references unknown skill {skill_id!r}")
    return Role(
        id=role_id,
        label_en=raw.get("label_en", role_id),
        label_te=raw.get("label_te", ""),
        label_hi=raw.get("label_hi", ""),
        required_skills=required,
        source=raw.get("source", ""),
    )


def load(skills: list[dict], roles: list[dict]) -> Taxonomy:
    """Build a `Taxonomy` from already-parsed skill and role dicts.

    Raises `ValueError` on a skill with no source, a skill missing an
    en/te/hi label, a skill whose prereq id doesn't exist, or a role that
    references a skill id not present in `skills`.
    """
    nodes: dict[str, SkillNode] = {}
    for raw in skills:
        node = _build_skill_node(raw)
        nodes[node.id] = node

    for node in nodes.values():
        for prereq_id in node.prereqs:
            if prereq_id not in nodes:
                raise ValueError(f"skill {node.id!r} has unknown prereq {prereq_id!r}")

    known_skill_ids = set(nodes)
    role_objs: dict[str, Role] = {}
    for raw in roles:
        role = _build_role(raw, known_skill_ids)
        role_objs[role.id] = role

    return Taxonomy(skills=nodes, roles=role_objs)
