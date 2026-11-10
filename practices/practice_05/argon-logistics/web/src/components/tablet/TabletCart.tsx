"use client";

import { useEffect, useMemo, useState } from "react";
import { Button, Chip, EmptyState, Icon, IconButton } from "@/components/ui";
import { api, describeError } from "@/lib/api";
import { formatMinutes } from "@/lib/format";
import { refreshAll, useNetwork, useProducts } from "@/lib/hooks";
import type { DeliveryPlan } from "@/lib/types";
import { useApp } from "@/state/app";
import { useShop } from "@/state/shop";
import { useToast } from "@/state/toast";

export function TabletCart() {
  const { data: network } = useNetwork();
  const { data: products } = useProducts();
  const { cart, setQuantity, removeFromCart, clearCart, pickupPointId, setPickupPointId, withUser } = useShop();
  const { setPreviewPlan, setTabletTab, setHighlightedOrderId } = useApp();
  const toast = useToast();

  const [plan, setPlan] = useState<DeliveryPlan | null>(null);
  const [planError, setPlanError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [ordering, setOrdering] = useState(false);

  const activePoints = useMemo(() => (network?.pickupPoints ?? []).filter((p) => p.isActive), [network]);
  const productById = useMemo(() => new Map((products ?? []).map((p) => [p.id, p])), [products]);

  // Выбранный ПВЗ должен существовать и быть активным; иначе берём первый подходящий.
  const effectivePickup = activePoints.find((p) => p.id === pickupPointId)?.id ?? activePoints[0]?.id ?? null;
  useEffect(() => {
    if (network && effectivePickup !== pickupPointId) setPickupPointId(effectivePickup);
  }, [network, effectivePickup, pickupPointId, setPickupPointId]);

  // Перестраиваем план при изменении корзины, ПВЗ или остатков (подпись остатков меняется при резервах).
  const stockSignature = (network?.warehouses ?? []).map((w) => `${w.id}:${w.totalQuantity - w.totalReserved}`).join(",");
  const routeSignature = `${network?.routes.length ?? 0}/${network?.links.map((l) => `${l.pickupPointId}-${l.warehouseId}-${l.minutes}`).join(",") ?? ""}`;

  useEffect(() => {
    if (!effectivePickup || cart.length === 0) {
      setPlan(null);
      setPlanError(null);
      setPreviewPlan(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    const timer = setTimeout(async () => {
      try {
        const result = await api.plan(effectivePickup, cart);
        if (cancelled) return;
        setPlan(result);
        setPlanError(null);
        setPreviewPlan(result);
      } catch (e) {
        if (cancelled) return;
        setPlan(null);
        setPreviewPlan(null);
        setPlanError(describeError(e, products));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 350);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [effectivePickup, cart, stockSignature, routeSignature, products, setPreviewPlan]);

  // Уходим с вкладки или закрываем планшет: подсветка маршрутов на карте больше не нужна.
  useEffect(() => () => setPreviewPlan(null), [setPreviewPlan]);

  const order = async () => {
    if (!effectivePickup || !plan || ordering) return;
    setOrdering(true);
    try {
      const created = await withUser((userId) => api.createOrder(userId, effectivePickup, cart));
      clearCart();
      setPreviewPlan(null);
      await refreshAll();
      setHighlightedOrderId(created.id);
      setTabletTab("orders");
      toast(`Заказ #${created.id} оформлен: грузовики скоро выедут`, "success");
    } catch (e) {
      setPlan(null);
      setPlanError(describeError(e, products));
      toast(describeError(e, products), "error");
      await refreshAll();
    } finally {
      setOrdering(false);
    }
  };

  if (cart.length === 0)
    return (
      <EmptyState icon="shopping_cart" title="Корзина пуста">
        Добавьте товары на вкладке «Каталог».
      </EmptyState>
    );

  const routeText = (legs: DeliveryPlan["shipments"][number]["legs"]) => [legs[0].from.name, ...legs.map((l) => l.to.name)].join(" → ");

  return (
    <>
      {cart.map((item) => {
        const product = productById.get(item.productId);
        return (
          <div className="product-tile" key={item.productId}>
            <div className="grow">
              <div className="t-title-s">{product?.name ?? `Товар ${item.productId}`}</div>
              <div className="t-body-s muted">{product?.sku}</div>
            </div>
            <div className="qty">
              <IconButton small icon="remove" label="Меньше" disabled={item.quantity <= 1} onClick={() => setQuantity(item.productId, item.quantity - 1)} />
              <b>{item.quantity}</b>
              <IconButton small icon="add" label="Больше" onClick={() => setQuantity(item.productId, item.quantity + 1)} />
            </div>
            <IconButton small variant="danger" icon="delete" label="Убрать из корзины" onClick={() => removeFromCart(item.productId)} />
          </div>
        );
      })}

      <div className="t-title-s" style={{ padding: "4px 4px 0" }}>Пункт выдачи</div>
      {activePoints.length === 0 ? (
        <div className="banner">
          <Icon name="warning" />
          <span>Нет активных ПВЗ. Создайте ПВЗ на карте.</span>
        </div>
      ) : (
        <div className="row wrap">
          {activePoints.map((p) => (
            <Chip key={p.id} icon="storefront" selected={p.id === effectivePickup} onClick={() => setPickupPointId(p.id)}>
              {p.name}
            </Chip>
          ))}
        </div>
      )}

      {planError && (
        <div className="banner" role="alert">
          <Icon name="error" />
          <span>{planError}</span>
        </div>
      )}

      {loading && !plan && !planError && (
        <div className="summary stack tight">
          <div className="skeleton" style={{ width: "60%" }} />
          <div className="skeleton" />
          <div className="skeleton" style={{ width: "80%" }} />
        </div>
      )}

      {plan && (
        <div className="summary stack tight" style={{ opacity: loading ? 0.6 : 1, transition: "opacity 150ms" }}>
          <div className="row">
            <Icon name="route" />
            <div className="t-title-s grow">План доставки</div>
            <Chip compact icon="schedule" tone="transit">≈ {formatMinutes(plan.estimatedMinutes)}</Chip>
          </div>
          {plan.shipments.map((s) => (
            <div className="shipment-row" key={s.warehouseId}>
              <div className="t-body-s"><b>{routeText(s.legs)}</b> · {formatMinutes(s.totalMinutes)}</div>
              <div className="t-body-s muted">{s.items.map((i) => `${i.name} ×${i.quantity}`).join(", ")}</div>
            </div>
          ))}
          <div className="t-body-s muted">Маршруты подсвечены на карте.</div>
        </div>
      )}

      <div className="row" style={{ marginTop: 4 }}>
        <Button variant="text" onClick={clearCart}>Очистить</Button>
        <div className="grow" />
        <Button icon="shopping_bag" onClick={order} disabled={!plan || loading || ordering || !effectivePickup}>
          {ordering ? "Оформляю…" : "Заказать"}
        </Button>
      </div>
    </>
  );
}
