"use client";

import { useState } from "react";
import { Button, EmptyState, Icon, IconButton, SelectField, TextField } from "@/components/ui";
import { api, describeError } from "@/lib/api";
import { refreshAll, useNetwork, useProducts, useStock } from "@/lib/hooks";
import type { StockLine } from "@/lib/types";
import { useToast } from "@/state/toast";

/** Остатки склада: добавить товар с количеством, поправить количество, убрать строку. */
export function StockEditor({ warehouseId }: { warehouseId: number }) {
  const { data: lines } = useStock(warehouseId);
  const { data: products } = useProducts();
  const toast = useToast();

  const [productId, setProductId] = useState("");
  const [quantity, setQuantity] = useState("10");
  const [busy, setBusy] = useState(false);

  const { data: network } = useNetwork();
  const warehouse = network?.warehouses.find((w) => w.id === warehouseId);
  // Свободное место: вместимость минус занятое минус место под возвраты в пути.
  const free = warehouse ? Math.max(0, warehouse.capacity - warehouse.totalQuantity - warehouse.incomingQuantity) : null;

  const qty = Number(quantity);
  const validQty = Number.isInteger(qty) && qty >= 1 && qty <= 1_000_000 && (free === null || qty <= free);
  const qtyError = !Number.isInteger(qty) || qty < 1 ? "Целое от 1" : free !== null && qty > free ? `На складе нет места: свободно ${free}` : undefined;

  const run = async (action: () => Promise<unknown>, success?: string) => {
    try {
      await action();
      await refreshAll();
      if (success) toast(success, "success");
      return true;
    } catch (e) {
      toast(describeError(e, products), "error");
      return false;
    }
  };

  const add = async () => {
    if (!productId || !validQty || busy) return;
    setBusy(true);
    await run(() => api.addStock(warehouseId, Number(productId), qty), "Товар добавлен на склад");
    setBusy(false);
  };

  return (
    <div className="stack tight">
      <div className="t-title-s">Товары на складе</div>

      {lines && lines.length === 0 && (
        <div className="t-body-s muted" style={{ padding: "0 4px" }}>
          Склад пуст. Добавьте товары из каталога.
        </div>
      )}

      {lines?.map((line) => (
        <StockRow
          key={line.productId}
          line={line}
          onSet={(value) => run(() => api.setStock(warehouseId, line.productId, value))}
          onRemove={() => run(() => api.removeStock(warehouseId, line.productId), "Строка убрана")}
        />
      ))}

      <div className="card filled stack tight" style={{ padding: 12 }}>
        {products && products.length === 0 ? (
          <EmptyState icon="inventory_2" title="Каталог пуст">
            Сначала создайте товары на вкладке «Каталог».
          </EmptyState>
        ) : (
          <>
            <SelectField dense label="Товар" value={productId} onChange={(e) => setProductId(e.target.value)}>
              <option value="">Выберите товар…</option>
              {products?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.sku})
                </option>
              ))}
            </SelectField>
            <div className="row">
              <TextField
                dense
                className="grow"
                label="Количество"
                type="number"
                min={1}
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && add()}
                hint={free !== null ? `Свободно на складе: ${free}` : undefined}
                error={qtyError}
              />
              <Button variant="tonal" icon="add" onClick={add} disabled={!productId || !validQty || busy}>
                Добавить
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function StockRow({ line, onSet, onRemove }: { line: StockLine; onSet: (v: number) => Promise<boolean>; onRemove: () => void }) {
  const [value, setValue] = useState<string | null>(null);
  const shown = value ?? String(line.quantity);

  const commit = async () => {
    if (value === null) return;
    const n = Number(value);
    const changed = Number.isInteger(n) && n >= 0 && n !== line.quantity;
    if (changed) await onSet(n);
    setValue(null); // дальше показываем то, что на сервере (при отказе значение откатывается)
  };

  return (
    <div className="list-row">
      <Icon name="inventory_2" size={20} className="muted" />
      <div className="grow">
        <div className="t-body-m">{line.name}</div>
        <div className="t-body-s muted">
          {line.sku} · доступно {line.available}
          {line.reserved > 0 ? ` · резерв ${line.reserved}` : ""}
        </div>
      </div>
      <input
        className="inline-number"
        type="number"
        min={0}
        aria-label={`Количество ${line.name}`}
        value={shown}
        onChange={(e) => setValue(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") (e.target as HTMLInputElement).blur();
          if (e.key === "Escape") setValue(null);
        }}
      />
      <IconButton small icon="delete" label="Убрать строку" variant="danger" onClick={onRemove} />
    </div>
  );
}
