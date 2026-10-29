import type { Network, NodeKey } from "@/lib/types";
import { pickupKey, warehouseKey } from "@/lib/types";
import type { Pt } from "@/lib/geometry";

export type NodeModel = {
  key: NodeKey;
  kind: "warehouse" | "pickupPoint";
  id: number;
  name: string;
  pos: Pt;
  totalQuantity?: number;
  totalReserved?: number;
  capacity?: number;
  incomingQuantity?: number;
  isActive?: boolean;
};

/** Доля вместимости склада (занято и входящие возвраты), от которой бейдж предупреждает о заполнении. */
export const CAPACITY_WARNING = 0.9;

export type EdgeModel = {
  key: string;
  kind: "route" | "link";
  fromKey: NodeKey;
  toKey: NodeKey;
  minutes: number;
  routeId?: number;
  pickupPointId?: number;
  warehouseId?: number;
};

export const edgePairKey = (from: NodeKey, to: NodeKey) => `${from}>${to}`;

export function buildNodes(network: Network | undefined): NodeModel[] {
  if (!network) return [];
  return [
    ...network.warehouses.map<NodeModel>((w) => ({
      key: warehouseKey(w.id),
      kind: "warehouse",
      id: w.id,
      name: w.name,
      pos: { x: w.mapX, y: w.mapY },
      totalQuantity: w.totalQuantity,
      totalReserved: w.totalReserved,
      capacity: w.capacity,
      incomingQuantity: w.incomingQuantity,
    })),
    ...network.pickupPoints.map<NodeModel>((p) => ({
      key: pickupKey(p.id),
      kind: "pickupPoint",
      id: p.id,
      name: p.name,
      pos: { x: p.mapX, y: p.mapY },
      isActive: p.isActive,
    })),
  ];
}

export function buildEdges(network: Network | undefined): EdgeModel[] {
  if (!network) return [];
  return [
    ...network.routes.map<EdgeModel>((r) => ({
      key: `r${r.id}`,
      kind: "route",
      fromKey: warehouseKey(r.fromWarehouseId),
      toKey: warehouseKey(r.toWarehouseId),
      minutes: r.minutes,
      routeId: r.id,
    })),
    ...network.links.map<EdgeModel>((l) => ({
      key: `l${l.pickupPointId}-${l.warehouseId}`,
      kind: "link",
      fromKey: warehouseKey(l.warehouseId),
      toKey: pickupKey(l.pickupPointId),
      minutes: l.minutes,
      pickupPointId: l.pickupPointId,
      warehouseId: l.warehouseId,
    })),
  ];
}
