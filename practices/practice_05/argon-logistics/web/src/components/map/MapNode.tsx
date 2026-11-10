"use client";

import type { PointerEvent } from "react";
import { CAPACITY_WARNING, type NodeModel } from "./model";

const truncate = (s: string, n: number) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);

type Props = {
  node: NodeModel;
  pos: { x: number; y: number };
  selected: boolean;
  dragging: boolean;
  dropTarget: boolean;
  dim: boolean;
  readyCount: number;
  onPointerDown: (e: PointerEvent, node: NodeModel) => void;
  onHandleDown: (e: PointerEvent, node: NodeModel) => void;
};

export function MapNode({ node, pos, selected, dragging, dropTarget, dim, readyCount, onPointerDown, onHandleDown }: Props) {
  const isWarehouse = node.kind === "warehouse";
  const fill = isWarehouse ? "var(--md-primary-container)" : "var(--md-tertiary-container)";
  const ink = isWarehouse ? "var(--md-on-primary-container)" : "var(--md-on-tertiary-container)";
  const accent = isWarehouse ? "var(--md-primary)" : "var(--md-tertiary)";
  const inactive = node.kind === "pickupPoint" && node.isActive === false;

  const total = node.totalQuantity ?? 0;
  const reserved = node.totalReserved ?? 0;
  const capacity = node.capacity ?? 0;
  const incoming = node.incomingQuantity ?? 0;
  const almostFull = capacity > 0 && (total + incoming) / capacity >= CAPACITY_WARNING;
  const fillText = capacity > 0 ? `${total}/${capacity} шт` : `${total} шт`;

  return (
    <g
      className={`map-node ${selected ? "selected" : ""} ${dragging ? "dragging" : ""} ${dropTarget ? "drop-target" : ""}`}
      transform={`translate(${pos.x} ${pos.y})`}
      opacity={dim ? 0.45 : 1}
      data-node={node.key}
    >
      <g className="body" onPointerDown={(e) => onPointerDown(e, node)}>
        {selected && <rect x={-52} y={-42} width={104} height={84} rx={28} fill="none" stroke={accent} strokeWidth={3} opacity={0.35} />}
        <rect x={-42} y={-32} width={84} height={64} rx={20} fill="rgba(0,0,0,0.16)" transform="translate(0 3)" />
        <rect
          className="shape"
          x={-42}
          y={-32}
          width={84}
          height={64}
          rx={20}
          fill={fill}
          stroke={selected ? accent : "transparent"}
          strokeWidth={selected ? 3 : 0}
          strokeDasharray={inactive ? "6 5" : undefined}
          opacity={inactive ? 0.7 : 1}
        />
        <text className="glyph" x={0} y={2} textAnchor="middle" dominantBaseline="central" fill={ink}>
          {isWarehouse ? "warehouse" : "storefront"}
        </text>

        {isWarehouse && (
          <g transform="translate(14 -46)" className={almostFull ? "capacity-pill warn" : "capacity-pill"}>
            <rect
              width={Math.max(40, fillText.length * 6.4 + 20)}
              height={20}
              rx={10}
              fill={almostFull ? "var(--md-warning-container)" : "var(--md-inverse-surface)"}
              stroke={almostFull ? "var(--md-on-warning-container)" : "none"}
              strokeWidth={1.5}
            />
            <text className="pill-text" x={10} y={14} fill={almostFull ? "var(--md-on-warning-container)" : "var(--md-inverse-on-surface)"}>
              {fillText}
            </text>
            <title>{capacity > 0 ? `Занято ${total} из ${capacity}${incoming > 0 ? `, ещё ${incoming} едет возвратом` : ""}` : `${total} шт`}</title>
          </g>
        )}
        {isWarehouse && incoming > 0 && (
          <g transform="translate(-88 -46)">
            <rect width={74} height={20} rx={10} fill="var(--md-tertiary-container)" stroke="var(--md-tertiary)" strokeWidth={1} />
            <text className="pill-text" x={9} y={14} fill="var(--md-on-tertiary-container)">
              ↩ +{incoming}
            </text>
            <title>Едет возвратом на этот склад</title>
          </g>
        )}
        {isWarehouse && reserved > 0 && (
          <g transform="translate(14 -24)">
            <rect width={Math.max(54, String(reserved).length * 7 + 44)} height={18} rx={9} fill="var(--md-tertiary-container)" stroke="var(--md-tertiary)" strokeWidth={1} />
            <text className="pill-text" x={9} y={13} fill="var(--md-on-tertiary-container)">
              резерв {reserved}
            </text>
          </g>
        )}
        {!isWarehouse && readyCount > 0 && (
          <g transform="translate(14 -46)">
            <rect width={96} height={20} rx={10} fill="var(--md-success)" />
            <text className="pill-text" x={10} y={14} fill="#fff">
              к выдаче: {readyCount}
            </text>
          </g>
        )}
      </g>

      <text className="node-label" y={52} textAnchor="middle">
        {truncate(node.name, 20)}
      </text>
      <text className="node-sub" y={67} textAnchor="middle">
        {isWarehouse ? "склад" : inactive ? "ПВЗ · неактивен" : "ПВЗ"}
      </text>

      <g className="handle" transform="translate(56 0)" onPointerDown={(e) => onHandleDown(e, node)}>
        <circle r={12} fill={accent} stroke="var(--map-bg)" strokeWidth={3} />
        <path d="M-4 0h8M1 -4l4 4l-4 4" fill="none" stroke="var(--md-on-primary)" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
        <title>Потяните к другому объекту, чтобы создать связь</title>
      </g>
    </g>
  );
}
