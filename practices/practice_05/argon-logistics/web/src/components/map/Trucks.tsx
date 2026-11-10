"use client";

import { useEffect, useMemo, useState } from "react";
import { serverNow } from "@/lib/clock";
import { legsToCurves, truckPosition, type Pt } from "@/lib/geometry";
import { formatMinutes, orderColor, RETURN_COLOR } from "@/lib/format";
import type { NodeKey, Order, ReturnShipment, Shipment } from "@/lib/types";

type Props = {
  orders: Order[];
  speedFactor: number;
  position: (key: NodeKey) => Pt | undefined;
  hasOpposite: (from: NodeKey, to: NodeKey) => boolean;
  highlightedOrderId: number | null;
  /** Масштаб карты: подсказка рисуется в обратном масштабе, чтобы не менять размер при зуме. */
  scale: number;
  onSelectOrder: (orderId: number) => void;
};

/** Едущая отправка: доставка склад → ПВЗ или возврат ПВЗ → склад (у возврата legs начинаются в ПВЗ). */
type Active = { key: string; order: Order; shipment: Shipment | ReturnShipment; isReturn: boolean };

export function Trucks({ orders, speedFactor, position, hasOpposite, highlightedOrderId, scale, onSelectOrder }: Props) {
  const [, setFrame] = useState(0);
  const [hovered, setHovered] = useState<string | null>(null);

  const active = useMemo<Active[]>(
    () =>
      orders.flatMap((order) => [
        ...order.shipments
          .filter((s) => s.status === "Dispatched" && s.dispatchedAt)
          .map((shipment) => ({ key: `s${shipment.id}`, order, shipment, isReturn: false })),
        ...order.returns
          .filter((r) => r.status === "Dispatched" && r.dispatchedAt)
          .map((shipment) => ({ key: `r${shipment.id}`, order, shipment, isReturn: true })),
      ]),
    [orders],
  );

  // Кадры нужны только пока есть грузовики в пути.
  const hasTrucks = active.length > 0;
  useEffect(() => {
    if (!hasTrucks) return;
    let raf = requestAnimationFrame(function loop() {
      setFrame((f) => (f + 1) % 1_000_000);
      raf = requestAnimationFrame(loop);
    });
    return () => cancelAnimationFrame(raf);
  }, [hasTrucks]);

  const now = serverNow();

  return (
    <g>
      {active.map(({ key, order, shipment, isReturn }) => {
        const legs = legsToCurves(shipment.legs, position, hasOpposite);
        if (!legs) return null;
        const elapsedMinutes = ((now - Date.parse(shipment.dispatchedAt as string)) / 1000) * speedFactor;
        const state = truckPosition(legs, elapsedMinutes);
        if (!state) return null;

        const color = isReturn ? RETURN_COLOR : orderColor(order.id);
        const flip = Math.cos(state.angle) < 0 ? -1 : 1; // не едем «вверх колёсами»
        const dimmed = highlightedOrderId !== null && highlightedOrderId !== order.id;
        const remaining = Math.max(0, shipment.totalMinutes - elapsedMinutes);
        const cargo = shipment.items.reduce((sum, i) => sum + i.quantity, 0);
        const isHovered = hovered === key;

        return (
          <g
            key={key}
            transform={`translate(${state.pos.x} ${state.pos.y})`}
            opacity={dimmed ? 0.3 : 1}
            className={isReturn ? "truck-body return-truck" : "truck-body"}
            data-truck={key}
            style={{ cursor: "pointer" }}
            onPointerEnter={() => setHovered(key)}
            onPointerLeave={() => setHovered((h) => (h === key ? null : h))}
            onPointerDown={(e) => {
              e.stopPropagation();
              onSelectOrder(order.id);
            }}
          >
            <circle r={26} fill="transparent" />
            <g transform={`rotate(${(state.angle * 180) / Math.PI}) scale(1 ${flip})`}>
              <ellipse cx={-1} cy={11} rx={22} ry={5} fill="rgba(0,0,0,0.2)" />
              <g className="truck-bounce">
                <rect x={-23} y={-10} width={27} height={19} rx={3.5} fill={color} />
                <rect x={-23} y={-10} width={27} height={5} rx={3} fill="rgba(255,255,255,0.22)" />
                <path d="M6 -6.5 h8.5 l6 6.5 v9 h-14.5 z" style={{ fill: `color-mix(in srgb, ${color} 72%, black)` }} />
                <rect x={11} y={-4} width={5.5} height={5.5} rx={1} fill="#d6ecff" />
                <circle cx={-13} cy={10} r={3.8} fill="#25232a" />
                <circle cx={12} cy={10} r={3.8} fill="#25232a" />
                <circle cx={-13} cy={10} r={1.5} fill="#9a97a3" />
                <circle cx={12} cy={10} r={1.5} fill="#9a97a3" />
                <circle cx={20.5} cy={5} r={1.4} fill="#ffe27a" />
              </g>
            </g>

            <g transform="translate(0 -30)">
              <rect x={isReturn ? -28 : -24} y={-11} width={isReturn ? 56 : 48} height={20} rx={10} fill={color} stroke="var(--map-bg)" strokeWidth={2} />
              <text textAnchor="middle" y={3.5} fontSize={11} fontWeight={600} fill="#fff">
                {isReturn ? "↩ " : ""}#{order.id}
              </text>
            </g>

            {isHovered && (
              <g transform={`translate(0 -52) scale(${1 / scale})`} style={{ pointerEvents: "none" }}>
                <Tooltip order={order} shipment={shipment} isReturn={isReturn} cargo={cargo} remaining={remaining} />
              </g>
            )}
          </g>
        );
      })}
    </g>
  );
}

function Tooltip({
  order,
  shipment,
  isReturn,
  cargo,
  remaining,
}: {
  order: Order;
  shipment: Shipment | ReturnShipment;
  isReturn: boolean;
  cargo: number;
  remaining: number;
}) {
  const title = isReturn
    ? `Возврат · заказ #${order.id} · ${order.pickupPointName} → ${shipment.warehouseName}`
    : `Заказ #${order.id} · ${shipment.warehouseName} → ${order.pickupPointName}`;
  const lines = shipment.items.slice(0, 4).map((i) => `${i.name} ×${i.quantity}`);
  if (shipment.items.length > 4) lines.push(`ещё ${shipment.items.length - 4}…`);
  const footer = `Груз: ${cargo} шт · осталось ≈ ${formatMinutes(remaining)}`;
  const longest = Math.max(title.length, footer.length, ...lines.map((l) => l.length));
  const width = Math.min(340, longest * 6.4 + 24);
  const height = 20 + (lines.length + 2) * 17;

  return (
    <g transform={`translate(${-width / 2} ${-height})`}>
      <rect width={width} height={height} rx={12} fill="var(--md-inverse-surface)" opacity={0.96} />
      <text x={12} y={21} fontSize={12} fontWeight={600} fill="var(--md-inverse-on-surface)">
        {title}
      </text>
      {lines.map((line, i) => (
        <text key={i} x={12} y={40 + i * 17} fontSize={12} fill="var(--md-inverse-on-surface)" opacity={0.9}>
          {line}
        </text>
      ))}
      <text x={12} y={40 + lines.length * 17 + 4} fontSize={12} fontWeight={500} fill="var(--md-inverse-on-surface)">
        {footer}
      </text>
    </g>
  );
}
