"use client";

import { useMemo, useState } from "react";
import { EmptyState, IconButton } from "@/components/ui";
import { useOrders, useSimulation } from "@/lib/hooks";
import { isActiveOrder } from "@/lib/types";
import { useApp } from "@/state/app";
import { useShop } from "@/state/shop";
import { OrderCard } from "./OrderCard";

export function OrdersPanel() {
  const { data: orders } = useOrders();
  const { data: sim } = useSimulation();
  const { highlightedOrderId, setHighlightedOrderId, setOrdersOpen } = useApp();
  const { userId } = useShop();
  const [tab, setTab] = useState<"active" | "history">("active");

  const { active, history } = useMemo(() => {
    const sorted = [...(orders ?? [])].sort((a, b) => b.id - a.id);
    return { active: sorted.filter(isActiveOrder), history: sorted.filter((o) => !isActiveOrder(o)) };
  }, [orders]);

  const list = tab === "active" ? active : history;

  return (
    <aside className="panel right" aria-label="Заказы">
      <div className="panel-head">
        <h2 className="t-title-l">Заказы</h2>
        <IconButton icon="close" label="Скрыть панель" onClick={() => setOrdersOpen(false)} />
      </div>
      <div className="tabs">
        <button type="button" className={`tab ${tab === "active" ? "active" : ""}`} onClick={() => setTab("active")}>
          Активные {active.length > 0 && <span className="badge" style={{ background: "var(--md-primary)", color: "var(--md-on-primary)" }}>{active.length}</span>}
        </button>
        <button type="button" className={`tab ${tab === "history" ? "active" : ""}`} onClick={() => setTab("history")}>
          История
        </button>
      </div>
      <div className="panel-body" style={{ paddingTop: 12 }}>
        {list.length === 0 ? (
          tab === "active" ? (
            <EmptyState icon="local_shipping" title="Нет активных заказов">
              Откройте планшет, соберите корзину и оформите заказ: грузовики поедут по связям на карте.
            </EmptyState>
          ) : (
            <EmptyState icon="history" title="История пуста">
              Здесь появятся выданные и отменённые заказы.
            </EmptyState>
          )
        ) : (
          list.map((order) => (
            <OrderCard
              key={order.id}
              order={order}
              speedFactor={sim?.speedFactor ?? 1}
              simulationEnabled={sim?.enabled ?? false}
              currentUserId={userId}
              selected={highlightedOrderId === order.id}
              onSelect={() => setHighlightedOrderId(highlightedOrderId === order.id ? null : order.id)}
            />
          ))
        )}
      </div>
    </aside>
  );
}
