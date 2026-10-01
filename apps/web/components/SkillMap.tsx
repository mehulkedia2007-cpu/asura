"use client";
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
  type SimulationNodeDatum,
} from "d3-force";
import { useLocale, useTranslations } from "next-intl";
import { useMemo, useState } from "react";
export type MapSkill = {
  id: string;
  label_en: string;
  label_te: string;
  label_hi: string;
  prereqs: string[];
  source: string;
};
type Node = SimulationNodeDatum & { id: string; radius: number };
export function SkillMap({
  skills,
  missing,
  held,
  demand,
}: {
  skills: MapSkill[];
  missing: string[];
  held: Record<string, number>;
  demand: Record<string, number>;
}) {
  const t = useTranslations("path");
  const locale = useLocale();
  const [selected, setSelected] = useState<string | null>(null);
  const graph = useMemo(() => {
    const relevant = new Set([...missing, ...Object.keys(held)]);
    const visit = (id: string) => {
      for (const parent of skills.find((skill) => skill.id === id)?.prereqs ??
        []) {
        if (!relevant.has(parent)) {
          relevant.add(parent);
          visit(parent);
        }
      }
    };
    for (const id of [...relevant]) visit(id);
    const nodes: Node[] = skills
      .filter((skill) => relevant.has(skill.id))
      .map((skill) => ({
        id: skill.id,
        radius:
          13 + Math.min(10, Math.max(0, (demand[skill.id] ?? 1) - 1) * 12),
      }));
    const edges = skills
      .filter((skill) => relevant.has(skill.id))
      .flatMap((skill) =>
        skill.prereqs
          .filter((parent) => relevant.has(parent))
          .map((parent) => ({ source: parent, target: skill.id })),
      );
    const simulation = forceSimulation(nodes)
      .force(
        "link",
        forceLink<Node, { source: string; target: string }>(edges)
          .id((node) => node.id)
          .distance(65),
      )
      .force("charge", forceManyBody().strength(-40))
      .force(
        "collision",
        forceCollide<Node>().radius((node) => node.radius + 15),
      )
      .force("center", forceCenter(250, 135))
      .force("x", forceX(250).strength(0.1))
      .force("y", forceY(135).strength(0.3))
      .stop();
    simulation.tick(160);
    simulation.stop();
    const positions = new Map(nodes.map((node) => [node.id, node]));
    return {
      nodes,
      viewBox: nodes.length
        ? `${Math.min(...nodes.map((n) => n.x ?? 0)) - 30} ${Math.min(...nodes.map((n) => n.y ?? 0)) - 30} ${Math.max(...nodes.map((n) => n.x ?? 0)) - Math.min(...nodes.map((n) => n.x ?? 0)) + 60} ${Math.max(...nodes.map((n) => n.y ?? 0)) - Math.min(...nodes.map((n) => n.y ?? 0)) + 60}`
        : "0 0 500 270",
      links: skills
        .filter((skill) => relevant.has(skill.id))
        .flatMap((skill) =>
          skill.prereqs
            .filter((parent) => relevant.has(parent))
            .map((parent) => ({
              source: positions.get(parent),
              target: positions.get(skill.id),
            })),
        ),
    };
  }, [skills, missing, held, demand]);
  const label = (skill: MapSkill) =>
    locale === "te"
      ? skill.label_te
      : locale === "hi"
        ? skill.label_hi
        : skill.label_en;
  const detail = skills.find((skill) => skill.id === selected);
  return (
    <section className="skill-map surface" aria-label={t("mapTitle")}>
      <div className="skill-map-heading">
        <h2>{t("mapTitle")}</h2>
        <p>{t("mapHint")}</p>
      </div>
      <svg viewBox={graph.viewBox} role="img" aria-label={t("mapTitle")}>
        <title>{t("mapTitle")}</title>
        {graph.links.map((link) => (
          <line
            key={`${link.source?.id}-${link.target?.id}`}
            x1={link.source?.x}
            y1={link.source?.y}
            x2={link.target?.x}
            y2={link.target?.y}
          />
        ))}
        {graph.nodes.map((node, index) => (
          <g
            key={node.id}
            className={held[node.id] ? "map-held" : "map-missing"}
          >
            <circle cx={node.x} cy={node.y} r={node.radius} />
            <text x={node.x} y={(node.y ?? 0) + 4} textAnchor="middle">
              {index + 1}
            </text>
          </g>
        ))}
      </svg>
      <div className="map-key">
        <span>{t("heldTitle")}</span>
        <span>{t("steps")}</span>
      </div>
      <div className="map-node-list">
        {graph.nodes.map((node, index) => {
          const skill = skills.find((entry) => entry.id === node.id);
          return (
            skill && (
              <button
                key={node.id}
                type="button"
                aria-pressed={selected === node.id}
                onClick={() => setSelected(node.id)}
              >
                <span>{index + 1}</span>
                {label(skill)}
              </button>
            )
          );
        })}
      </div>
      {detail && (
        <div className="map-detail" role="status">
          <strong>{label(detail)}</strong>
          <p>
            {t("prerequisite")}:{" "}
            {detail.prereqs
              .map((id) => skills.find((skill) => skill.id === id))
              .filter((skill): skill is MapSkill => Boolean(skill))
              .map(label)
              .join(", ") || t("none")}
          </p>
          <p className="source-stamp">{detail.source}</p>
        </div>
      )}
    </section>
  );
}
