"use client";

import { useEffect, useMemo, useState } from "react";
import { Button, Chip, ConfirmDialog, Icon, Switch, TextField } from "@/components/ui";
import { api, describeError } from "@/lib/api";
import { refreshAll, refreshNetwork, useNetwork } from "@/lib/hooks";
import { CAPACITY_WARNING } from "@/components/map/model";
import { pickupKey, warehouseKey, type Network, type Warehouse } from "@/lib/types";
import { useApp, type Selection } from "@/state/app";
import { useToast } from "@/state/toast";
import { StockEditor } from "./StockEditor";

const QUICK = [15, 30, 60, 90, 120];

export function Inspector() {
  const { selection } = useApp();
  const { data: network } = useNetwork();

  if (!selection || !network) {
    return (
      <div className="empty">
        <Icon name="ads_click" size={48} />
        <div className="t-title-m" style={{ color: "var(--md-on-surface)" }}>Ничего не выбрано</div>
        <div className="t-body-m">Выберите склад, ПВЗ или связь на карте, чтобы изменить их свойства.</div>
      </div>
    );
  }

  if (selection.kind === "node") {
    const id = Number(selection.key.slice(1));
    return selection.key.startsWith("w") ? (
      <WarehouseInspector key={selection.key} id={id} network={network} />
    ) : (
      <PickupInspector key={selection.key} id={id} network={network} />
    );
  }
  return <EdgeInspector key={JSON.stringify(selection)} selection={selection} network={network} />;
}

/** Если выбранный объект исчез (удалили или он был удалён в другом окне), снимаем выбор. */
function useDropSelectionWhenMissing(missing: boolean) {
  const { select } = useApp();
  useEffect(() => {
    if (missing) select(null);
  }, [missing, select]);
}

function Connections({ network, nodeKey: key }: { network: Network; nodeKey: ReturnType<typeof warehouseKey> | ReturnType<typeof pickupKey> }) {
  const { select } = useApp();
  const names = useMemo(
    () => new Map<string, string>([
      ...network.warehouses.map((w) => [warehouseKey(w.id), w.name] as const),
      ...network.pickupPoints.map((p) => [pickupKey(p.id), p.name] as const),
    ]),
    [network],
  );

  const rows: { label: string; minutes: number; onClick: () => void }[] = [];
  for (const r of network.routes) {
    const from = warehouseKey(r.fromWarehouseId);
    const to = warehouseKey(r.toWarehouseId);
    if (from !== key && to !== key) continue;
    rows.push({
      label: from === key ? `→ ${names.get(to)}` : `← ${names.get(from)}`,
      minutes: r.minutes,
      onClick: () => select({ kind: "route", id: r.id }),
    });
  }
  for (const l of network.links) {
    const from = warehouseKey(l.warehouseId);
    const to = pickupKey(l.pickupPointId);
    if (from !== key && to !== key) continue;
    rows.push({
      label: from === key ? `→ ${names.get(to)}` : `← ${names.get(from)}`,
      minutes: l.minutes,
      onClick: () => select({ kind: "link", pickupPointId: l.pickupPointId, warehouseId: l.warehouseId }),
    });
  }

  return (
    <div className="stack tight">
      <div className="t-title-s">Связи</div>
      {rows.length === 0 ? (
        <div className="t-body-s muted" style={{ padding: "0 4px" }}>Нет связей. Потяните ● у объекта к другому объекту.</div>
      ) : (
        <div className="row wrap">
          {rows.map((r, i) => (
            <Chip key={i} icon="route" onClick={r.onClick}>
              {r.label} · {r.minutes} мин
            </Chip>
          ))}
        </div>
      )}
    </div>
  );
}

/** Шкала заполнения склада: занято и место, уже отданное под возвраты в пути. */
function CapacityMeter({ warehouse }: { warehouse: Warehouse }) {
  const { capacity, totalQuantity, incomingQuantity } = warehouse;
  const used = totalQuantity + incomingQuantity;
  const free = Math.max(0, capacity - used);
  const pct = (n: number) => `${Math.min(100, (n / Math.max(1, capacity)) * 100)}%`;
  const warn = used / Math.max(1, capacity) >= CAPACITY_WARNING;

  return (
    <div className="stack tight" data-testid="capacity-meter">
      <div className="capacity-meter" role="progressbar" aria-valuemin={0} aria-valuemax={capacity} aria-valuenow={used}>
        <div className={`occupied ${warn ? "warn" : ""}`} style={{ width: pct(totalQuantity) }} />
        <div className="incoming" style={{ width: pct(incomingQuantity) }} />
      </div>
      <div className="t-body-s muted">
        Занято {totalQuantity} из {capacity}
        {incomingQuantity > 0 ? ` · едет возвратом ${incomingQuantity}` : ""} · свободно {free}
      </div>
    </div>
  );
}

function WarehouseInspector({ id, network }: { id: number; network: Network }) {
  const warehouse = network.warehouses.find((w) => w.id === id);
  const { select } = useApp();
  const toast = useToast();
  const [name, setName] = useState(warehouse?.name ?? "");
  const [address, setAddress] = useState(warehouse?.address ?? "");
  const [capacity, setCapacity] = useState(String(warehouse?.capacity ?? ""));
  const [confirm, setConfirm] = useState(false);
  useDropSelectionWhenMissing(!warehouse);
  if (!warehouse) return null;

  const capacityValue = Number(capacity);
  const capacityValid = Number.isInteger(capacityValue) && capacityValue >= 1 && capacityValue <= 10_000_000;
  const dirty =
    name.trim() !== warehouse.name || address.trim() !== warehouse.address || (capacityValid && capacityValue !== warehouse.capacity);
  const valid = name.trim().length > 0 && address.trim().length > 0 && capacityValid;

  const save = async () => {
    try {
      await api.updateWarehouse(id, { name, address, capacity: capacityValue });
      await refreshNetwork();
      toast("Склад сохранён", "success");
    } catch (e) {
      toast(describeError(e), "error");
    }
  };

  const remove = async () => {
    setConfirm(false);
    try {
      await api.deleteWarehouse(id);
      select(null);
      await refreshAll();
      toast("Склад удалён", "success");
    } catch (e) {
      toast(describeError(e), "error");
    }
  };

  return (
    <div className="stack">
      <div className="row">
        <Icon name="warehouse" fill />
        <div className="t-title-m grow">Склад</div>
        <Chip compact icon="inventory_2">{warehouse.totalQuantity} шт</Chip>
      </div>
      <TextField label="Название" value={name} onChange={(e) => setName(e.target.value)} error={name.trim() ? undefined : "Обязательно"} />
      <TextField label="Адрес" value={address} onChange={(e) => setAddress(e.target.value)} error={address.trim() ? undefined : "Обязательно"} />
      <TextField
        label="Вместимость, шт"
        type="number"
        min={1}
        value={capacity}
        onChange={(e) => setCapacity(e.target.value)}
        hint="Максимум суммы по всем товарам склада"
        error={capacityValid ? undefined : "Целое число от 1 до 10 000 000"}
      />
      <CapacityMeter warehouse={warehouse} />
      <div className="row">
        <Button variant="tonal" icon="save" onClick={save} disabled={!dirty || !valid}>Сохранить</Button>
        <div className="grow" />
        <Button variant="danger" icon="delete" onClick={() => setConfirm(true)}>Удалить</Button>
      </div>
      <hr className="divider" />
      <StockEditor warehouseId={id} />
      <hr className="divider" />
      <Connections network={network} nodeKey={warehouseKey(id)} />
      {confirm && (
        <ConfirmDialog
          danger
          title="Удалить склад?"
          message={`Склад «${warehouse.name}» и все его связи будут удалены. Если на складе есть товар или едут отправки, удаление будет отклонено.`}
          confirmLabel="Удалить"
          onConfirm={remove}
          onClose={() => setConfirm(false)}
        />
      )}
    </div>
  );
}

function PickupInspector({ id, network }: { id: number; network: Network }) {
  const point = network.pickupPoints.find((p) => p.id === id);
  const { select } = useApp();
  const toast = useToast();
  const [name, setName] = useState(point?.name ?? "");
  const [address, setAddress] = useState(point?.address ?? "");
  const [active, setActive] = useState(point?.isActive ?? true);
  const [confirm, setConfirm] = useState(false);
  useDropSelectionWhenMissing(!point);
  if (!point) return null;

  const dirty = name.trim() !== point.name || address.trim() !== point.address || active !== point.isActive;
  const valid = name.trim().length > 0 && address.trim().length > 0;

  const save = async () => {
    try {
      await api.updatePickupPoint(id, { name, address, isActive: active });
      await refreshNetwork();
      toast("ПВЗ сохранён", "success");
    } catch (e) {
      toast(describeError(e), "error");
    }
  };

  const remove = async () => {
    setConfirm(false);
    try {
      await api.deletePickupPoint(id);
      select(null);
      await refreshAll();
      toast("ПВЗ удалён", "success");
    } catch (e) {
      toast(describeError(e), "error");
    }
  };

  return (
    <div className="stack">
      <div className="row">
        <Icon name="storefront" fill />
        <div className="t-title-m grow">Пункт выдачи</div>
        <Chip compact tone={point.isActive ? "ready" : "warning"}>{point.isActive ? "активен" : "неактивен"}</Chip>
      </div>
      <TextField label="Название" value={name} onChange={(e) => setName(e.target.value)} error={name.trim() ? undefined : "Обязательно"} />
      <TextField label="Адрес" value={address} onChange={(e) => setAddress(e.target.value)} error={address.trim() ? undefined : "Обязательно"} />
      <Switch checked={active} onChange={setActive} label="Принимает заказы" />
      <div className="row">
        <Button variant="tonal" icon="save" onClick={save} disabled={!dirty || !valid}>Сохранить</Button>
        <div className="grow" />
        <Button variant="danger" icon="delete" onClick={() => setConfirm(true)}>Удалить</Button>
      </div>
      <hr className="divider" />
      <Connections network={network} nodeKey={pickupKey(id)} />
      {confirm && (
        <ConfirmDialog
          danger
          title="Удалить ПВЗ?"
          message={`ПВЗ «${point.name}» и его связи будут удалены. Если в него едут незавершённые заказы, удаление будет отклонено.`}
          confirmLabel="Удалить"
          onConfirm={remove}
          onClose={() => setConfirm(false)}
        />
      )}
    </div>
  );
}

function EdgeInspector({ selection, network }: { selection: Exclude<Selection, null | { kind: "node" }>; network: Network }) {
  const { select } = useApp();
  const toast = useToast();

  const warehouseName = (id: number) => network.warehouses.find((w) => w.id === id)?.name ?? `Склад ${id}`;
  const pickupName = (id: number) => network.pickupPoints.find((p) => p.id === id)?.name ?? `ПВЗ ${id}`;

  const route = selection.kind === "route" ? network.routes.find((r) => r.id === selection.id) : undefined;
  const link = selection.kind === "link" ? network.links.find((l) => l.pickupPointId === selection.pickupPointId && l.warehouseId === selection.warehouseId) : undefined;
  const current = route?.minutes ?? link?.minutes;

  const [minutes, setMinutes] = useState(String(current ?? 30));
  const [confirm, setConfirm] = useState(false);
  useDropSelectionWhenMissing(current === undefined);
  if (current === undefined) return null;

  const value = Number(minutes);
  const valid = Number.isInteger(value) && value >= 1 && value <= 10080;

  const title = route
    ? `${warehouseName(route.fromWarehouseId)} → ${warehouseName(route.toWarehouseId)}`
    : `${warehouseName(link!.warehouseId)} → ${pickupName(link!.pickupPointId)}`;

  const save = async () => {
    try {
      if (route) await api.updateRoute(route.id, value);
      else await api.putLink(link!.pickupPointId, link!.warehouseId, value);
      await refreshNetwork();
      toast("Время обновлено", "success");
    } catch (e) {
      toast(describeError(e), "error");
    }
  };

  const remove = async () => {
    setConfirm(false);
    try {
      if (route) await api.deleteRoute(route.id);
      else await api.deleteLink(link!.pickupPointId, link!.warehouseId);
      select(null);
      await refreshNetwork();
      toast("Связь удалена", "success");
    } catch (e) {
      toast(describeError(e), "error");
    }
  };

  return (
    <div className="stack">
      <div className="row">
        <Icon name={route ? "route" : "add_road"} />
        <div className="t-title-m grow">{route ? "Путь между складами" : "Путь склад → ПВЗ"}</div>
      </div>
      <div className="t-title-s">{title}</div>
      <TextField
        label="Время в пути, минут"
        type="number"
        min={1}
        max={10080}
        value={minutes}
        onChange={(e) => setMinutes(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && valid && value !== current && save()}
        error={valid ? undefined : "Целое число от 1 до 10080"}
      />
      <div className="row wrap">
        {QUICK.map((q) => (
          <Chip key={q} selected={value === q} onClick={() => setMinutes(String(q))}>{q} мин</Chip>
        ))}
      </div>
      <div className="row">
        <Button variant="tonal" icon="save" onClick={save} disabled={!valid || value === current}>Сохранить</Button>
        <div className="grow" />
        <Button variant="danger" icon="delete" onClick={() => setConfirm(true)}>Удалить</Button>
      </div>
      <div className="t-body-s muted">Связь направленная: товар едет только в указанную сторону.</div>
      {confirm && (
        <ConfirmDialog
          danger
          title="Удалить связь?"
          message={`Связь «${title}» исчезнет, и планирование перестанет использовать этот путь. Уже созданные заказы не изменятся.`}
          confirmLabel="Удалить"
          onConfirm={remove}
          onClose={() => setConfirm(false)}
        />
      )}
    </div>
  );
}
