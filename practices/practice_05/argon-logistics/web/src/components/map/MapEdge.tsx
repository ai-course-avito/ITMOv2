"use client";

import { pointAt, tangentAt, trimEnd, NODE_RADIUS, type Curve } from "@/lib/geometry";
import type { EdgeModel } from "./model";

type Props = {
  edge: EdgeModel;
  curve: Curve;
  selected: boolean;
  preview: boolean;
  dim: boolean;
  onSelect: (edge: EdgeModel) => void;
};

export function MapEdge({ edge, curve, selected, preview, dim, onSelect }: Props) {
  const d = `M ${curve.p0.x} ${curve.p0.y} Q ${curve.c.x} ${curve.c.y} ${curve.p1.x} ${curve.p1.y}`;

  // Наконечник стоит у границы целевого узла, а не в его центре.
  const t = trimEnd(curve, NODE_RADIUS + 8);
  const tip = pointAt(curve, t);
  const dir = tangentAt(curve, t);
  const angle = (Math.atan2(dir.y, dir.x) * 180) / Math.PI;

  const mid = pointAt(curve, 0.5);
  const label = `${edge.minutes} мин`;
  const width = label.length * 7 + 16;

  const handle = (e: React.PointerEvent) => {
    e.stopPropagation();
    onSelect(edge);
  };

  return (
    <g className={`edge ${edge.kind} ${selected ? "selected" : ""} ${preview ? "preview" : ""} ${dim ? "dim" : ""}`}>
      <path d={d} fill="none" stroke="transparent" strokeWidth={22} onPointerDown={handle} />
      <path className="line" d={d} />
      <polygon className="arrow" points="0,0 -13,-7 -13,7" transform={`translate(${tip.x} ${tip.y}) rotate(${angle})`} />
      <g transform={`translate(${mid.x} ${mid.y})`} onPointerDown={handle}>
        <rect className="label-bg" x={-width / 2} y={-11} width={width} height={22} rx={11} />
        <text className="label-text" textAnchor="middle" dominantBaseline="central">
          {label}
        </text>
      </g>
    </g>
  );
}
