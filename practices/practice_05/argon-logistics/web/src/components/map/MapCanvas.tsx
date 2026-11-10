"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent, type PointerEvent } from "react";
import { Button, Chip, Icon, IconButton } from "@/components/ui";
import { api, describeError } from "@/lib/api";
import { ADD_BUILDING_EVENT, BUILDING_MIME, createBuilding, isBuildingType } from "@/lib/buildings";
import { seedDemo } from "@/lib/demo";
import { edgeCurve, NODE_RADIUS, OPPOSITE_BEND, type Pt } from "@/lib/geometry";
import { refreshAll, refreshNetwork, useNetwork, useOrders, useSimulation } from "@/lib/hooks";
import { nodeKey, type NodeKey, type PlanLeg } from "@/lib/types";
import { useApp } from "@/state/app";
import { useShop } from "@/state/shop";
import { useToast } from "@/state/toast";
import { LinkDialog } from "./LinkDialog";
import { MapEdge } from "./MapEdge";
import { MapNode } from "./MapNode";
import { buildEdges, buildNodes, edgePairKey, type EdgeModel, type NodeModel } from "./model";
import { Trucks } from "./Trucks";

type View = { x: number; y: number; k: number };
type Interaction =
  | { type: "pan"; sx: number; sy: number; vx: number; vy: number; moved: boolean }
  | { type: "drag"; key: NodeKey; ox: number; oy: number; sx: number; sy: number; moved: boolean }
  | { type: "link"; from: NodeKey };

const MIN_K = 0.3;
const MAX_K = 2.5;
const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

export function MapCanvas() {
  const { data: network } = useNetwork();
  const { data: orders } = useOrders();
  const { data: sim } = useSimulation();
  const { selection, select, highlightedOrderId, setHighlightedOrderId, previewPlan, setOrdersOpen, tabletOpen, setTabletOpen } = useApp();
  const { cartCount } = useShop();
  const toast = useToast();

  const svgRef = useRef<SVGSVGElement>(null);
  const [view, setView] = useState<View>({ x: 480, y: 320, k: 1 });
  const viewRef = useRef(view);
  viewRef.current = view;

  const [draft, setDraft] = useState<Record<string, Pt>>({});
  const [draggingKey, setDraggingKey] = useState<NodeKey | null>(null);
  const [panning, setPanning] = useState(false);
  const [rubber, setRubber] = useState<{ from: NodeKey; to: Pt } | null>(null);
  const [dropKey, setDropKey] = useState<NodeKey | null>(null);
  const [pendingLink, setPendingLink] = useState<{ from: NodeModel; to: NodeModel } | null>(null);
  const [seeding, setSeeding] = useState(false);
  const interaction = useRef<Interaction | null>(null);
  const fitted = useRef(false);

  const nodes = useMemo(() => buildNodes(network), [network]);
  const edges = useMemo(() => buildEdges(network), [network]);
  const nodesByKey = useMemo(() => new Map(nodes.map((n) => [n.key, n])), [nodes]);
  const routePairs = useMemo(
    () => new Set(edges.filter((e) => e.kind === "route").map((e) => edgePairKey(e.fromKey, e.toKey))),
    [edges],
  );

  const position = useCallback((key: NodeKey): Pt | undefined => draft[key] ?? nodesByKey.get(key)?.pos, [draft, nodesByKey]);
  const hasOpposite = useCallback((from: NodeKey, to: NodeKey) => routePairs.has(edgePairKey(to, from)), [routePairs]);

  const toWorld = (clientX: number, clientY: number): Pt => {
    const rect = svgRef.current!.getBoundingClientRect();
    const v = viewRef.current;
    return { x: (clientX - rect.left - v.x) / v.k, y: (clientY - rect.top - v.y) / v.k };
  };

  // ---- Вид: вписать в экран, зум ----

  const fit = useCallback((list: NodeModel[]) => {
    const el = svgRef.current;
    if (!el) return;
    const { width, height } = el.getBoundingClientRect();
    if (list.length === 0) {
      setView({ x: width / 2, y: height / 2, k: 1 });
      return;
    }
    const xs = list.map((n) => n.pos.x);
    const ys = list.map((n) => n.pos.y);
    const pad = 110;
    const w = Math.max(...xs) - Math.min(...xs) + pad * 2;
    const h = Math.max(...ys) - Math.min(...ys) + pad * 2;
    const k = clamp(Math.min(width / w, height / h), 0.35, 1.2);
    const cx = (Math.max(...xs) + Math.min(...xs)) / 2;
    const cy = (Math.max(...ys) + Math.min(...ys)) / 2;
    setView({ k, x: width / 2 - cx * k, y: height / 2 - cy * k });
  }, []);

  useEffect(() => {
    if (network === undefined) return;
    if (nodes.length === 0) {
      fitted.current = false;
      if (!svgRef.current) return;
      fit([]);
      return;
    }
    if (!fitted.current) {
      fitted.current = true;
      fit(nodes);
    }
  }, [network, nodes, fit]);

  const zoomBy = useCallback((factor: number, px?: number, py?: number) => {
    const el = svgRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const cx = px ?? rect.width / 2;
    const cy = py ?? rect.height / 2;
    setView((v) => {
      const k = clamp(v.k * factor, MIN_K, MAX_K);
      const f = k / v.k;
      return { k, x: cx - (cx - v.x) * f, y: cy - (cy - v.y) * f };
    });
  }, []);

  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      zoomBy(Math.exp(-e.deltaY * 0.0015), e.clientX - rect.left, e.clientY - rect.top);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [zoomBy]);

  // ---- Создание строений (перетаскиванием из палитры или кнопкой) ----

  const addBuilding = useCallback(
    async (type: "warehouse" | "pickupPoint", at: Pt) => {
      try {
        const key = await createBuilding(type, at, network);
        await refreshNetwork();
        select({ kind: "node", key });
      } catch (e) {
        toast(describeError(e), "error");
      }
    },
    [network, select, toast],
  );

  useEffect(() => {
    const onAdd = (e: Event) => {
      const type = (e as CustomEvent<{ type: string }>).detail?.type;
      const el = svgRef.current;
      if (!el || !isBuildingType(type)) return;
      const rect = el.getBoundingClientRect();
      const v = viewRef.current;
      // Лёгкий случайный сдвиг, чтобы повторные нажатия не накладывали объекты друг на друга.
      const jitter = () => (Math.random() - 0.5) * 120;
      void addBuilding(type, { x: (rect.width / 2 - v.x) / v.k + jitter(), y: (rect.height / 2 - v.y) / v.k + jitter() });
    };
    window.addEventListener(ADD_BUILDING_EVENT, onAdd);
    return () => window.removeEventListener(ADD_BUILDING_EVENT, onAdd);
  }, [addBuilding]);

  const onDragOver = (e: DragEvent) => {
    if (e.dataTransfer.types.includes(BUILDING_MIME)) {
      e.preventDefault();
      e.dataTransfer.dropEffect = "copy";
    }
  };

  const onDrop = (e: DragEvent) => {
    const type = e.dataTransfer.getData(BUILDING_MIME);
    if (!isBuildingType(type)) return;
    e.preventDefault();
    void addBuilding(type, toWorld(e.clientX, e.clientY));
  };

  // ---- Указатель: панорама, перетаскивание объектов, протягивание связи ----

  const hitTest = (world: Pt, except: NodeKey): NodeKey | null => {
    for (const n of nodes) {
      if (n.key === except) continue;
      const p = position(n.key);
      if (p && Math.hypot(p.x - world.x, p.y - world.y) < NODE_RADIUS + 6) return n.key;
    }
    return null;
  };

  const onBackgroundDown = (e: PointerEvent<SVGSVGElement>) => {
    if (e.button !== 0) return;
    svgRef.current!.setPointerCapture(e.pointerId);
    interaction.current = { type: "pan", sx: e.clientX, sy: e.clientY, vx: view.x, vy: view.y, moved: false };
    setPanning(true);
  };

  const onNodeDown = (e: PointerEvent, node: NodeModel) => {
    if (e.button !== 0) return;
    e.stopPropagation();
    svgRef.current!.setPointerCapture(e.pointerId);
    const w = toWorld(e.clientX, e.clientY);
    const p = position(node.key) ?? node.pos;
    interaction.current = { type: "drag", key: node.key, ox: w.x - p.x, oy: w.y - p.y, sx: e.clientX, sy: e.clientY, moved: false };
    select({ kind: "node", key: node.key });
  };

  const onHandleDown = (e: PointerEvent, node: NodeModel) => {
    if (e.button !== 0) return;
    e.stopPropagation();
    svgRef.current!.setPointerCapture(e.pointerId);
    interaction.current = { type: "link", from: node.key };
    setRubber({ from: node.key, to: toWorld(e.clientX, e.clientY) });
  };

  const onPointerMove = (e: PointerEvent<SVGSVGElement>) => {
    const it = interaction.current;
    if (!it) return;

    if (it.type === "pan") {
      const dx = e.clientX - it.sx;
      const dy = e.clientY - it.sy;
      if (!it.moved && Math.hypot(dx, dy) > 3) it.moved = true;
      setView((v) => ({ ...v, x: it.vx + dx, y: it.vy + dy }));
    } else if (it.type === "drag") {
      if (!it.moved && Math.hypot(e.clientX - it.sx, e.clientY - it.sy) > 3) {
        it.moved = true;
        setDraggingKey(it.key);
      }
      if (it.moved) {
        const w = toWorld(e.clientX, e.clientY);
        setDraft((d) => ({ ...d, [it.key]: { x: w.x - it.ox, y: w.y - it.oy } }));
      }
    } else {
      const w = toWorld(e.clientX, e.clientY);
      setRubber({ from: it.from, to: w });
      setDropKey(hitTest(w, it.from));
    }
  };

  const onPointerUp = (e: PointerEvent<SVGSVGElement>) => {
    const it = interaction.current;
    interaction.current = null;
    if (svgRef.current?.hasPointerCapture(e.pointerId)) svgRef.current.releasePointerCapture(e.pointerId);
    if (!it) return;

    if (it.type === "pan") {
      setPanning(false);
      if (!it.moved) {
        select(null);
        setHighlightedOrderId(null);
      }
    } else if (it.type === "drag") {
      setDraggingKey(null);
      if (it.moved) void persistPosition(it.key, e.clientX, e.clientY, it.ox, it.oy);
    } else {
      const w = toWorld(e.clientX, e.clientY);
      const target = hitTest(w, it.from);
      setRubber(null);
      setDropKey(null);
      if (target) connect(it.from, target);
    }
  };

  const persistPosition = async (key: NodeKey, clientX: number, clientY: number, ox: number, oy: number) => {
    const node = nodesByKey.get(key);
    if (!node) return;
    const w = toWorld(clientX, clientY);
    const x = Math.round(w.x - ox);
    const y = Math.round(w.y - oy);
    try {
      if (node.kind === "warehouse") await api.moveWarehouse(node.id, x, y);
      else await api.movePickupPoint(node.id, x, y);
      await refreshNetwork();
    } catch (e) {
      toast(describeError(e), "error");
    } finally {
      setDraft((d) => {
        const { [key]: _removed, ...rest } = d;
        return rest;
      });
    }
  };

  // ---- Связи ----

  const connect = (fromKey: NodeKey, toKey: NodeKey) => {
    let from = nodesByKey.get(fromKey);
    let to = nodesByKey.get(toKey);
    if (!from || !to) return;
    if (from.kind === "pickupPoint" && to.kind === "warehouse") [from, to] = [to, from]; // направление всегда «склад → ПВЗ»
    if (from.kind === "pickupPoint") {
      toast("ПВЗ нельзя соединить с другим ПВЗ: связи идут от склада", "error");
      return;
    }
    setPendingLink({ from, to });
  };

  const submitLink = async (minutes: number, bidirectional: boolean) => {
    if (!pendingLink) return;
    const { from, to } = pendingLink;
    try {
      if (to.kind === "warehouse") {
        const route = await api.createRoute(from.id, to.id, minutes, bidirectional);
        select({ kind: "route", id: route.id });
      } else {
        await api.putLink(to.id, from.id, minutes);
        select({ kind: "link", pickupPointId: to.id, warehouseId: from.id });
      }
      await refreshNetwork();
      setPendingLink(null);
      toast("Связь создана", "success");
    } catch (e) {
      toast(describeError(e), "error");
    }
  };

  const selectEdge = (edge: EdgeModel) => {
    setHighlightedOrderId(null);
    select(
      edge.kind === "route"
        ? { kind: "route", id: edge.routeId as number }
        : { kind: "link", pickupPointId: edge.pickupPointId as number, warehouseId: edge.warehouseId as number },
    );
  };

  const isEdgeSelected = (edge: EdgeModel) =>
    selection?.kind === "route"
      ? edge.routeId === selection.id
      : selection?.kind === "link" && edge.pickupPointId === selection.pickupPointId && edge.warehouseId === selection.warehouseId;

  // ---- Подсветка маршрутов (предпросмотр заказа или выбранный заказ) ----

  const highlight = useMemo(() => {
    const legs: PlanLeg[] = [];
    previewPlan?.shipments.forEach((s) => legs.push(...s.legs));
    if (highlightedOrderId !== null) {
      const highlighted = orders?.find((o) => o.id === highlightedOrderId);
      highlighted?.shipments.forEach((s) => legs.push(...s.legs));
      highlighted?.returns.forEach((r) => legs.push(...r.legs));
    }
    const edgeKeys = new Set<string>();
    const nodeKeys = new Set<NodeKey>();
    for (const leg of legs) {
      const from = nodeKey(leg.from.type, leg.from.id);
      const to = nodeKey(leg.to.type, leg.to.id);
      // Возврат едет из ПВЗ по привязке склад → ПВЗ в обратную сторону: подсвечиваем её ребро.
      edgeKeys.add(leg.from.type === "pickupPoint" ? edgePairKey(to, from) : edgePairKey(from, to));
      nodeKeys.add(from);
      nodeKeys.add(to);
    }
    return { active: legs.length > 0, edgeKeys, nodeKeys };
  }, [previewPlan, highlightedOrderId, orders]);

  const readyByPickup = useMemo(() => {
    const counts = new Map<number, number>();
    for (const o of orders ?? []) if (o.status === "ReadyForPickup") counts.set(o.pickupPointId, (counts.get(o.pickupPointId) ?? 0) + 1);
    return counts;
  }, [orders]);

  const loadDemo = async () => {
    setSeeding(true);
    try {
      await seedDemo();
      fitted.current = false;
      await refreshAll();
      toast("Демо-сеть загружена", "success");
    } catch (e) {
      toast(describeError(e), "error");
      await refreshAll();
    } finally {
      setSeeding(false);
    }
  };

  const curveFor = (edge: EdgeModel) => {
    const a = position(edge.fromKey) ?? { x: 0, y: 0 };
    const b = position(edge.toKey) ?? { x: 0, y: 0 };
    return edgeCurve(a, b, hasOpposite(edge.fromKey, edge.toKey) ? OPPOSITE_BEND : 0);
  };

  const sortedEdges = [...edges].sort((a, b) => Number(isEdgeSelected(a)) - Number(isEdgeSelected(b)));
  const sortedNodes = [...nodes].sort((a, b) => Number(selection?.kind === "node" && selection.key === a.key) - Number(selection?.kind === "node" && selection.key === b.key));
  const loaded = network !== undefined;
  const rubberFrom = rubber ? position(rubber.from) : undefined;

  return (
    <div className="map-wrap">
      <svg
        ref={svgRef}
        className={`map-svg ${panning ? "panning" : ""} ${rubber ? "linking" : ""}`}
        onPointerDown={onBackgroundDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onDragOver={onDragOver}
        onDrop={onDrop}
        role="application"
        aria-label="Карта логистической сети"
      >
        <defs>
          <pattern id="dots" width={32 * view.k} height={32 * view.k} patternUnits="userSpaceOnUse" x={view.x} y={view.y}>
            <circle cx={1} cy={1} r={1.3} fill="var(--md-outline-variant)" opacity={0.8} />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#dots)" />

        <g transform={`translate(${view.x} ${view.y}) scale(${view.k})`}>
          <g>
            {sortedEdges.map((edge) => {
              const pairKey = edgePairKey(edge.fromKey, edge.toKey);
              const inHighlight = highlight.edgeKeys.has(pairKey);
              return (
                <MapEdge
                  key={edge.key}
                  edge={edge}
                  curve={curveFor(edge)}
                  selected={isEdgeSelected(edge)}
                  preview={inHighlight}
                  dim={highlight.active && !inHighlight}
                  onSelect={selectEdge}
                />
              );
            })}
          </g>

          {rubber && rubberFrom && (
            <g style={{ pointerEvents: "none" }}>
              <line x1={rubberFrom.x} y1={rubberFrom.y} x2={rubber.to.x} y2={rubber.to.y} stroke="var(--md-primary)" strokeWidth={3} strokeDasharray="8 6" strokeLinecap="round" />
              <circle cx={rubber.to.x} cy={rubber.to.y} r={7} fill="var(--md-primary)" />
            </g>
          )}

          <g>
            {sortedNodes.map((node) => (
              <MapNode
                key={node.key}
                node={node}
                pos={position(node.key) ?? node.pos}
                selected={selection?.kind === "node" && selection.key === node.key}
                dragging={draggingKey === node.key}
                dropTarget={dropKey === node.key}
                dim={highlight.active && !highlight.nodeKeys.has(node.key)}
                readyCount={node.kind === "pickupPoint" ? (readyByPickup.get(node.id) ?? 0) : 0}
                onPointerDown={onNodeDown}
                onHandleDown={onHandleDown}
              />
            ))}
          </g>

          <Trucks
            orders={orders ?? []}
            speedFactor={sim?.speedFactor ?? 1}
            position={position}
            hasOpposite={hasOpposite}
            highlightedOrderId={highlightedOrderId}
            scale={view.k}
            onSelectOrder={(id) => {
              setHighlightedOrderId(id);
              setOrdersOpen(true);
            }}
          />
        </g>
      </svg>

      <div className="map-tools">
        <IconButton icon="add" label="Приблизить" onClick={() => zoomBy(1.25)} />
        <IconButton icon="remove" label="Отдалить" onClick={() => zoomBy(0.8)} />
        <IconButton icon="fit_screen" label="Вписать в экран" onClick={() => fit(nodes)} />
      </div>

      <div className="map-hint">
        <Chip icon="drag_pan">Колесо: масштаб</Chip>
        <Chip icon="arrow_circle_right">Тяните ● у объекта, чтобы связать</Chip>
      </div>

      {!tabletOpen && (
        <button type="button" className="fab tablet-fab stateful" onClick={() => setTabletOpen(true)} aria-label="Открыть планшет заказа">
          <Icon name="tablet_mac" fill />
          Заказать
          {cartCount > 0 && <span className="badge">{cartCount}</span>}
        </button>
      )}

      {loaded && nodes.length === 0 && (
        <div className="map-empty">
          <div className="card">
            <Icon name="hub" size={48} />
            <div className="t-title-l">Карта пуста</div>
            <div className="t-body-m muted">
              Перетащите «Склад» и «ПВЗ» из панели слева, соедините их связями и укажите время в пути. Или загрузите готовую демо-сеть.
            </div>
            <Button icon="auto_awesome" onClick={loadDemo} disabled={seeding}>
              {seeding ? "Загружаю…" : "Загрузить демо-сеть"}
            </Button>
          </div>
        </div>
      )}

      {pendingLink && (
        <LinkDialog from={pendingLink.from} to={pendingLink.to} onClose={() => setPendingLink(null)} onSubmit={submitLink} />
      )}
    </div>
  );
}
