"use client";

import { useMemo, useState } from "react";
import { Chip, EmptyState, Icon, IconButton } from "@/components/ui";
import { OrderCard } from "@/components/orders/OrderCard";
import { useMyOrders, useSimulation } from "@/lib/hooks";
import { isActiveOrder } from "@/lib/types";
import { useApp, type TabletTab } from "@/state/app";
import { useShop } from "@/state/shop";
import { TabletCart } from "./TabletCart";
import { TabletCatalog } from "./TabletCatalog";

export function Tablet() {
  const { tabletTab, setTabletTab, setTabletOpen } = useApp();
  const { cartCount, userId } = useShop();

  const tabs: { id: TabletTab; label: string; icon: string }[] = [
    { id: "catalog", label: "Каталог", icon: "storefront" },
    { id: "cart", label: "Корзина", icon: "shopping_cart" },
    { id: "orders", label: "Заказы", icon: "local_shipping" },
  ];

  return (
    <section className="tablet" aria-label="Планшет заказа">
      <div className="camera" />
      <div className="screen">
        <div className="tablet-head">
          <div className="brand">
            <Icon name="shopping_bag" fill />
          </div>
          <div className="grow">
            <div className="t-title-m">Argon Shop</div>
            <div className="t-body-s muted">{userId ? `Гость · №${userId}` : "Подключаюсь…"}</div>
          </div>
          <IconButton icon="close" label="Закрыть планшет" onClick={() => setTabletOpen(false)} />
        </div>
        <div className="tabs" role="tablist">
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tabletTab === t.id}
              className={`tab ${tabletTab === t.id ? "active" : ""}`}
              onClick={() => setTabletTab(t.id)}
            >
              <Icon name={t.icon} size={20} />
              {t.label}
              {t.id === "cart" && cartCount > 0 && <span className="badge">{cartCount}</span>}
            </button>
          ))}
        </div>
        <div className="tablet-body">
          {tabletTab === "catalog" && <TabletCatalog />}
          {tabletTab === "cart" && <TabletCart />}
          {tabletTab === "orders" && <MyOrders />}
        </div>
      </div>
      <div className="home" />
    </section>
  );
}

function MyOrders() {
  const { userId } = useShop();
  const { data: orders } = useMyOrders(userId);
  const { data: sim } = useSimulation();
  const { highlightedOrderId, setHighlightedOrderId } = useApp();
  const [history, setHistory] = useState(false);

  const list = useMemo(() => {
    const sorted = [...(orders ?? [])].sort((a, b) => b.id - a.id);
    return sorted.filter((o) => (history ? !isActiveOrder(o) : isActiveOrder(o)));
  }, [orders, history]);

  return (
    <>
      <div className="row">
        <Chip selected={!history} onClick={() => setHistory(false)}>Активные</Chip>
        <Chip selected={history} onClick={() => setHistory(true)}>История</Chip>
      </div>
      {list.length === 0 ? (
        <EmptyState icon={history ? "history" : "local_shipping"} title={history ? "История пуста" : "Нет активных заказов"}>
          {history ? "Выданные и отменённые заказы появятся здесь." : "Оформите заказ из корзины."}
        </EmptyState>
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
    </>
  );
}
