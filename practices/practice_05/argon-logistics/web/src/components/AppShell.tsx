"use client";

import { CatalogView } from "@/components/catalog/CatalogView";
import { MapCanvas } from "@/components/map/MapCanvas";
import { OrdersPanel } from "@/components/orders/OrdersPanel";
import { LeftPanel } from "@/components/panels/LeftPanel";
import { Tablet } from "@/components/tablet/Tablet";
import { Chip, Icon, IconButton } from "@/components/ui";
import { useOrders, useSimulation } from "@/lib/hooks";
import { isActiveOrder } from "@/lib/types";
import { useApp, type View } from "@/state/app";

const NAV: { id: View; label: string; icon: string }[] = [
  { id: "map", label: "Карта", icon: "map" },
  { id: "catalog", label: "Каталог", icon: "inventory_2" },
];

export function AppShell() {
  const { view, setView, ordersOpen, setOrdersOpen, tabletOpen } = useApp();
  const { data: sim } = useSimulation();
  const { data: orders } = useOrders();
  const activeCount = (orders ?? []).filter(isActiveOrder).length;

  return (
    <div className="app">
      <nav className="rail" aria-label="Разделы">
        <div className="logo" title="Argon Logistics">
          <Icon name="hub" size={32} fill />
        </div>
        {NAV.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`rail-item ${view === item.id ? "active" : ""}`}
            onClick={() => setView(item.id)}
            aria-current={view === item.id ? "page" : undefined}
          >
            <span className="pill">
              <Icon name={item.icon} />
            </span>
            {item.label}
          </button>
        ))}
      </nav>

      <div className="main">
        <header className="appbar">
          <h1 className="t-title-l">{view === "map" ? "Argon Logistics · карта сети" : "Argon Logistics · каталог"}</h1>
          {sim?.enabled ? (
            <Chip tone="ready" title={`1 секунда = ${sim.speedFactor} мин пути; отгрузка через ${sim.dispatchDelaySeconds} с`}>
              <span className="live-dot" /> Симуляция ×{sim.speedFactor}
            </Chip>
          ) : (
            sim && <Chip icon="pan_tool" tone="warning" title="Статусы меняются вручную кнопками в карточках заказов">Ручное управление</Chip>
          )}
          {view === "map" && (
            <div style={{ position: "relative" }}>
              <IconButton
                icon="receipt_long"
                label={ordersOpen ? "Скрыть заказы" : "Показать заказы"}
                variant={ordersOpen ? "tonal" : "standard"}
                onClick={() => setOrdersOpen(!ordersOpen)}
              />
              {activeCount > 0 && (
                <span className="badge" style={{ position: "absolute", top: 2, right: 2 }}>
                  {activeCount}
                </span>
              )}
            </div>
          )}
        </header>

        {view === "map" ? (
          <div className="workspace">
            <LeftPanel />
            <MapCanvas />
            {ordersOpen && <OrdersPanel />}
            {tabletOpen && <Tablet />}
          </div>
        ) : (
          <CatalogView />
        )}
      </div>
    </div>
  );
}
