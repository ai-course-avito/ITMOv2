"use client";

import { useEffect, useMemo, useState } from "react";
import { Button, Dialog, Icon, IconButton } from "@/components/ui";
import { api, describeError } from "@/lib/api";
import { formatMinutes } from "@/lib/format";
import { refreshAll } from "@/lib/hooks";
import type { DeliveryPlan, Order } from "@/lib/types";
import { useApp } from "@/state/app";
import { useToast } from "@/state/toast";

type Props = {
  order: Order;
  /** id текущего гостя: отказ оформляется от имени владельца заказа. */
  userId: number;
  onClose: () => void;
};

/**
 * Отказ от товара в ПВЗ: выбираем сколько вернуть по каждой позиции и сразу видим, на какие склады поедет товар
 * (план строит сервер, маршруты подсвечиваются на карте).
 */
export function RefusalDialog({ order, userId, onClose }: Props) {
  const toast = useToast();
  const { setPreviewPlan } = useApp();

  const lines = useMemo(
    () => order.items.map((i) => ({ ...i, left: i.quantity - i.refusedQuantity })).filter((i) => i.left > 0),
    [order.items],
  );
  const [quantities, setQuantities] = useState<Record<number, number>>({});
  const [plan, setPlan] = useState<DeliveryPlan | null>(null);
  const [planError, setPlanError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);

  const selected = useMemo(
    () => lines.filter((l) => (quantities[l.productId] ?? 0) > 0).map((l) => ({ productId: l.productId, quantity: quantities[l.productId] })),
    [lines, quantities],
  );
  const total = selected.reduce((sum, i) => sum + i.quantity, 0);

  useEffect(() => {
    if (selected.length === 0) {
      setPlan(null);
      setPlanError(null);
      setPreviewPlan(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    const timer = setTimeout(async () => {
      try {
        const result = await api.planReturn(order.pickupPointId, selected);
        if (cancelled) return;
        setPlan(result);
        setPlanError(null);
        setPreviewPlan(result);
      } catch (e) {
        if (cancelled) return;
        setPlan(null);
        setPreviewPlan(null);
        setPlanError(describeError(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [selected, order.pickupPointId, setPreviewPlan]);

  // Закрыли диалог: подсветка на карте больше не нужна.
  useEffect(() => () => setPreviewPlan(null), [setPreviewPlan]);

  const set = (productId: number, value: number, max: number) =>
    setQuantities((q) => ({ ...q, [productId]: Math.min(max, Math.max(0, value)) }));

  const confirm = async () => {
    if (!plan || busy) return;
    setBusy(true);
    try {
      const updated = await api.refuse(userId, order.id, selected);
      await refreshAll();
      toast(
        updated.status === "Returned"
          ? `Заказ #${order.id} возвращён целиком: товар едет на склады`
          : `Отказ оформлен: ${total} шт едет на склады`,
        "success",
      );
      onClose();
    } catch (e) {
      setPlan(null);
      setPlanError(describeError(e));
      toast(describeError(e), "error");
      await refreshAll();
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      title={`Отказ от товара · заказ #${order.id}`}
      onClose={onClose}
      actions={
        <>
          <Button variant="text" onClick={onClose}>Закрыть</Button>
          <Button icon="assignment_return" onClick={confirm} disabled={!plan || busy || total === 0}>
            Оформить отказ
          </Button>
        </>
      }
    >
      <div className="stack refusal" data-testid="refusal-dialog">
        <div className="t-body-m muted">
          Товар, от которого вы откажетесь, поедет обратно из «{order.pickupPointName}» на ближайший склад со свободным местом.
        </div>

        {lines.map((line) => {
          const value = quantities[line.productId] ?? 0;
          return (
            <div className="list-row refusal-row" key={line.productId} data-product={line.sku}>
              <Icon name="inventory_2" size={20} className="muted" />
              <div className="grow">
                <div className="t-body-m">{line.name}</div>
                <div className="t-body-s muted">
                  {line.sku} · можно вернуть {line.left} из {line.quantity}
                </div>
              </div>
              <div className="qty">
                <IconButton small icon="remove" label="Меньше" disabled={value <= 0} onClick={() => set(line.productId, value - 1, line.left)} />
                <b>{value}</b>
                <IconButton small icon="add" label="Больше" disabled={value >= line.left} onClick={() => set(line.productId, value + 1, line.left)} />
              </div>
              <Button small variant="text" onClick={() => set(line.productId, value === line.left ? 0 : line.left, line.left)}>
                {value === line.left ? "Сбросить" : "Всё"}
              </Button>
            </div>
          );
        })}

        {total === 0 && <div className="t-body-s muted">Выберите, от чего отказываетесь.</div>}
        {planError && (
          <div className="banner" role="alert">
            <Icon name="error" />
            <div>{planError}</div>
          </div>
        )}
        {plan && <ReturnPreview plan={plan} loading={loading} />}
      </div>
    </Dialog>
  );
}

function ReturnPreview({ plan, loading }: { plan: DeliveryPlan; loading: boolean }) {
  return (
    <div className="summary stack tight" style={{ opacity: loading ? 0.6 : 1 }} data-testid="return-preview">
      <div className="row">
        <Icon name="route" />
        <div className="t-title-s grow">Куда поедет товар</div>
        <span className="t-body-s muted">≈ {formatMinutes(plan.estimatedMinutes)}</span>
      </div>
      {plan.shipments.map((s) => {
        // Склады, через которые проходит маршрут, кроме склада-получателя, это транзит (они могут быть заполнены).
        const transit = s.legs.slice(1).map((l) => l.from.name);
        return (
          <div className="shipment-row" key={s.warehouseId} data-warehouse={s.warehouseId}>
            <div className="row">
              <Icon name="warehouse" size={18} className="muted" />
              <div className="t-body-s grow">
                <b>{s.warehouseName}</b> · {s.items.reduce((sum, i) => sum + i.quantity, 0)} шт
              </div>
              <span className="t-body-s muted">{formatMinutes(s.totalMinutes)}</span>
            </div>
            <div className="t-body-s muted">{s.items.map((i) => `${i.name} ×${i.quantity}`).join(", ")}</div>
            {transit.length > 0 && (
              <div className="t-body-s muted" data-testid="return-transit">
                Через {transit.join(", ")}: ближе, но места нет
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
