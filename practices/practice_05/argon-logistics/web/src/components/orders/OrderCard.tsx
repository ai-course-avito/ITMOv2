"use client";

import { useState } from "react";
import { Button, Chip, Icon } from "@/components/ui";
import { api, describeError } from "@/lib/api";
import { serverNow } from "@/lib/clock";
import {
  formatMinutes,
  ORDER_STATUS,
  ORDER_STEPS,
  orderColor,
  orderRefusedItems,
  orderTotalItems,
  pluralize,
  remainingMinutes,
  RETURN_STATUS,
  SHIPMENT_STATUS,
  shipmentProgress,
} from "@/lib/format";
import { RefusalDialog } from "./RefusalDialog";
import { refreshAll, useTicker } from "@/lib/hooks";
import type { Order } from "@/lib/types";
import { useToast } from "@/state/toast";

type Props = {
  order: Order;
  speedFactor: number;
  simulationEnabled: boolean;
  /** id текущего гостя: отменять можно только свои заказы (так устроен API клиента). */
  currentUserId: number | null;
  selected: boolean;
  onSelect: () => void;
};

const STEP_INDEX = { Planned: 0, InTransit: 1, ReadyForPickup: 2, Completed: 3 } as const;

export function OrderCard({ order, speedFactor, simulationEnabled, currentUserId, selected, onSelect }: Props) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [refusing, setRefusing] = useState(false);

  const moving = order.shipments.some((s) => s.status === "Dispatched") || order.returns.some((r) => r.status === "Dispatched");
  useTicker(moving);

  const status = ORDER_STATUS[order.status];
  const now = serverNow();
  const remaining = Math.max(0, ...order.shipments.map((s) => remainingMinutes(s, speedFactor, now) ?? 0));

  const eta =
    order.status === "InTransit"
      ? `осталось ≈ ${formatMinutes(remaining)}`
      : order.status === "Planned"
        ? `в пути ≈ ${formatMinutes(order.estimatedMinutes)}`
        : order.status === "ReadyForPickup"
          ? "можно забирать"
          : null;

  const act = async (action: () => Promise<unknown>, success: string) => {
    setBusy(true);
    try {
      await action();
      await refreshAll();
      toast(success, "success");
    } catch (e) {
      toast(describeError(e), "error");
    } finally {
      setBusy(false);
    }
  };

  const stop = (fn: () => void) => (e: React.MouseEvent) => {
    e.stopPropagation();
    fn();
  };

  const cancelled = order.status === "Cancelled";
  const returned = order.status === "Returned";
  const current = cancelled || returned ? -1 : STEP_INDEX[order.status as keyof typeof STEP_INDEX];
  const totalItems = orderTotalItems(order);
  const refusedItems = orderRefusedItems(order);
  const owner = currentUserId === order.userId;

  return (
    <>
    <div className={`order-card ${selected ? "selected" : ""}`} onClick={onSelect} data-order-id={order.id} data-status={order.status}>
      <div className="row">
        <span className="dot" style={{ background: orderColor(order.id) }} />
        <div className="t-title-m grow">Заказ #{order.id}</div>
        <Chip compact icon={status.icon} tone={status.tone}>
          {status.label}
        </Chip>
      </div>
      <div className="t-body-s muted" style={{ marginTop: 4 }}>
        <Icon name="storefront" size={18} className="muted" /> {order.pickupPointName} · {order.items.length}{" "}
        {pluralize(order.items.length, "позиция", "позиции", "позиций")} · {totalItems} шт
        {eta && <> · {eta}</>}
        {refusedItems > 0 && <> · возврат {refusedItems} шт</>}
      </div>

      {returned ? (
        <div className="stepper">
          <div className="step returned current">
            <div className="node">
              <Icon name="assignment_return" />
            </div>
            Клиент отказался от всех позиций, товар возвращается на склады
          </div>
        </div>
      ) : cancelled ? (
        <div className="stepper">
          <div className="step cancelled current">
            <div className="node">
              <Icon name="close" />
            </div>
            Заказ отменён, резерв снят
          </div>
        </div>
      ) : (
        <div className="stepper" aria-label="Статус заказа">
          {ORDER_STEPS.map((step, i) => {
            const state = i < current || order.status === "Completed" ? "done" : i === current ? "current" : "";
            return (
              <div key={step.status} className={`step ${state}`}>
                <div className="node">
                  <Icon name={state === "done" ? "check" : step.icon} />
                </div>
                {step.label}
              </div>
            );
          })}
        </div>
      )}

      <div className="stack tight">
        {order.shipments.map((s) => {
          const progress = shipmentProgress(s, speedFactor, now);
          const left = remainingMinutes(s, speedFactor, now) ?? 0;
          return (
            <div className="shipment-row" key={s.id}>
              <div className="row">
                <Icon name="local_shipping" size={18} className="muted" />
                <div className="t-body-s grow">
                  <b>{s.warehouseName}</b> · {SHIPMENT_STATUS[s.status]}
                  {s.status === "Dispatched" && ` · ≈ ${formatMinutes(left)}`}
                </div>
                <span className="t-body-s muted">{formatMinutes(s.totalMinutes)}</span>
              </div>
              <div className="t-body-s muted">{s.items.map((i) => `${i.name} ×${i.quantity}`).join(", ")}</div>
              {(s.status === "Dispatched" || s.status === "Delivered") && (
                <div className="progress" role="progressbar" aria-valuenow={Math.round(progress * 100)}>
                  <div style={{ width: `${progress * 100}%` }} />
                </div>
              )}
              {!simulationEnabled && (s.status === "Planned" || s.status === "Dispatched") && (
                <div className="row">
                  {s.status === "Planned" ? (
                    <Button small variant="tonal" icon="outbox" disabled={busy} onClick={stop(() => act(() => api.dispatch(s.id), "Отправка отгружена"))}>
                      Отгрузить
                    </Button>
                  ) : (
                    <Button small variant="tonal" icon="where_to_vote" disabled={busy} onClick={stop(() => act(() => api.deliver(s.id), "Отправка доставлена"))}>
                      Доставить
                    </Button>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {order.returns.length > 0 && (
        <div className="stack tight returns" style={{ marginTop: 8 }} data-testid="order-returns">
          <div className="t-label-m muted">Возвраты</div>
          {order.returns.map((r) => {
            const progress = shipmentProgress(r, speedFactor, now);
            const left = remainingMinutes(r, speedFactor, now) ?? 0;
            return (
              <div className="shipment-row return-row" key={r.id} data-return-id={r.id} data-return-status={r.status}>
                <div className="row">
                  <Icon name="assignment_return" size={18} className="muted" />
                  <div className="t-body-s grow">
                    → <b>{r.warehouseName}</b> · {RETURN_STATUS[r.status]}
                    {r.status === "Dispatched" && ` · ≈ ${formatMinutes(left)}`}
                  </div>
                  <span className="t-body-s muted">{formatMinutes(r.totalMinutes)}</span>
                </div>
                <div className="t-body-s muted">{r.items.map((i) => `${i.name} ×${i.quantity}`).join(", ")}</div>
                {(r.status === "Dispatched" || r.status === "Delivered") && (
                  <div className="progress" role="progressbar" aria-valuenow={Math.round(progress * 100)}>
                    <div style={{ width: `${progress * 100}%` }} />
                  </div>
                )}
                {!simulationEnabled && r.status !== "Delivered" && (
                  <div className="row">
                    {r.status === "Planned" ? (
                      <Button small variant="tonal" icon="outbox" disabled={busy} onClick={stop(() => act(() => api.dispatchReturn(r.id), "Возврат отгружен"))}>
                        Отгрузить возврат
                      </Button>
                    ) : (
                      <Button small variant="tonal" icon="where_to_vote" disabled={busy} onClick={stop(() => act(() => api.deliverReturn(r.id), "Возврат принят складом"))}>
                        Принять на складе
                      </Button>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {(order.status === "Planned" && owner) || order.status === "ReadyForPickup" ? (
        <div className="row" style={{ marginTop: 12, justifyContent: "flex-end" }}>
          {order.status === "Planned" && owner && (
            <Button
              small
              variant="danger"
              icon="close"
              disabled={busy}
              onClick={stop(() => act(() => api.cancelOrder(currentUserId as number, order.id), "Заказ отменён"))}
            >
              Отменить
            </Button>
          )}
          {order.status === "ReadyForPickup" && owner && (
            <Button small variant="outlined" icon="assignment_return" disabled={busy} onClick={stop(() => setRefusing(true))}>
              Отказаться от товара
            </Button>
          )}
          {order.status === "ReadyForPickup" && (
            <Button small icon="task_alt" disabled={busy} onClick={stop(() => act(() => api.pickup(order.id), "Заказ выдан"))}>
              Получить
            </Button>
          )}
        </div>
      ) : null}
    </div>
    {refusing && owner && <RefusalDialog order={order} userId={currentUserId as number} onClose={() => setRefusing(false)} />}
    </>
  );
}
