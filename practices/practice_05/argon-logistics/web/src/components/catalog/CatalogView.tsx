"use client";

import { useMemo, useState } from "react";
import { Button, Chip, ConfirmDialog, Dialog, EmptyState, Icon, IconButton, TextField } from "@/components/ui";
import { api, describeError } from "@/lib/api";
import { refreshAll, useAllStock, useNetwork, useProducts } from "@/lib/hooks";
import { ApiError, type Product } from "@/lib/types";
import { useToast } from "@/state/toast";

export function CatalogView() {
  const { data: products } = useProducts();
  const { data: network } = useNetwork();
  const { data: stock } = useAllStock(network?.warehouses);
  const toast = useToast();

  const [editing, setEditing] = useState<Product | "new" | null>(null);
  const [deleting, setDeleting] = useState<Product | null>(null);

  const perProduct = useMemo(() => {
    const map = new Map<number, { warehouse: string; quantity: number; reserved: number }[]>();
    for (const w of network?.warehouses ?? []) {
      for (const line of stock?.[w.id] ?? []) {
        const rows = map.get(line.productId) ?? [];
        rows.push({ warehouse: w.name, quantity: line.quantity, reserved: line.reserved });
        map.set(line.productId, rows);
      }
    }
    return map;
  }, [network, stock]);

  const remove = async () => {
    const product = deleting;
    setDeleting(null);
    if (!product) return;
    try {
      await api.deleteProduct(product.id);
      await refreshAll();
      toast(`Товар «${product.name}» удалён`, "success");
    } catch (e) {
      toast(describeError(e), "error");
    }
  };

  return (
    <div className="page">
      <div className="page-head">
        <div className="grow">
          <div className="t-headline-s">Каталог товаров</div>
          <div className="t-body-m muted">Общий список: из него клиенты заказывают, а склады берут номенклатуру.</div>
        </div>
        <Button icon="add" onClick={() => setEditing("new")}>
          Новый товар
        </Button>
      </div>

      {products && products.length === 0 ? (
        <EmptyState icon="inventory_2" title="Товаров пока нет">
          Создайте первый товар, затем добавьте его на склады на карте.
        </EmptyState>
      ) : (
        <div className="grid-cards">
          {(products ?? []).map((p) => {
            const rows = perProduct.get(p.id) ?? [];
            const total = rows.reduce((s, r) => s + r.quantity, 0);
            const reserved = rows.reduce((s, r) => s + r.reserved, 0);
            return (
              <article className="product-card" key={p.id} data-product={p.sku}>
                <div className="row">
                  <Chip compact icon="tag">{p.sku}</Chip>
                  <div className="grow" />
                  <IconButton small icon="edit" label="Изменить" onClick={() => setEditing(p)} />
                  <IconButton small variant="danger" icon="delete" label="Удалить" onClick={() => setDeleting(p)} />
                </div>
                <div>
                  <div className="t-title-l">{p.name}</div>
                  <div className="t-body-m muted">{p.description || "Без описания"}</div>
                </div>
                <div>
                  <div className="row t-body-m">
                    <Icon name="inventory_2" size={20} className="muted" />
                    <span className="grow">
                      Всего <b>{total}</b>
                      {reserved > 0 && <span className="muted"> · в резерве {reserved}</span>}
                    </span>
                  </div>
                  <div className="bar" style={{ marginTop: 8 }} aria-hidden>
                    <span style={{ width: total ? `${((total - reserved) / total) * 100}%` : 0 }} />
                    <span className="res" style={{ width: total ? `${(reserved / total) * 100}%` : 0 }} />
                  </div>
                </div>
                <div className="row wrap">
                  {rows.length === 0 ? (
                    <span className="t-body-s muted">Нет на складах</span>
                  ) : (
                    rows.map((r) => (
                      <Chip key={r.warehouse} compact icon="warehouse">
                        {r.warehouse}: {r.quantity}
                      </Chip>
                    ))
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}

      {editing && <ProductDialog product={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
      {deleting && (
        <ConfirmDialog
          danger
          title="Удалить товар?"
          message={`«${deleting.name}» исчезнет из каталога. Если товар лежит на складах, удаление будет отклонено.`}
          confirmLabel="Удалить"
          onConfirm={remove}
          onClose={() => setDeleting(null)}
        />
      )}
    </div>
  );
}

function ProductDialog({ product, onClose }: { product: Product | null; onClose: () => void }) {
  const toast = useToast();
  const [sku, setSku] = useState(product?.sku ?? "");
  const [name, setName] = useState(product?.name ?? "");
  const [description, setDescription] = useState(product?.description ?? "");
  const [skuError, setSkuError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const valid = sku.trim().length > 0 && sku.trim().length <= 64 && name.trim().length > 0 && name.trim().length <= 200;

  const submit = async () => {
    if (!valid || busy) return;
    setBusy(true);
    setSkuError(null);
    try {
      const body = { sku: sku.trim(), name: name.trim(), description: description.trim() || undefined };
      if (product) await api.updateProduct(product.id, body);
      else await api.createProduct(body);
      await refreshAll();
      toast(product ? "Товар сохранён" : "Товар создан", "success");
      onClose();
    } catch (e) {
      if (e instanceof ApiError && e.code === "product_sku_duplicate") setSkuError("SKU уже занят");
      toast(describeError(e), "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      title={product ? "Изменить товар" : "Новый товар"}
      onClose={onClose}
      actions={
        <>
          <Button variant="text" onClick={onClose}>Отмена</Button>
          <Button icon="save" onClick={submit} disabled={!valid || busy}>Сохранить</Button>
        </>
      }
    >
      <div className="stack">
        <TextField label="SKU" value={sku} autoFocus maxLength={64} onChange={(e) => { setSku(e.target.value); setSkuError(null); }} error={skuError ?? undefined} />
        <TextField label="Название" value={name} maxLength={200} onChange={(e) => setName(e.target.value)} />
        <TextField label="Описание" value={description} maxLength={1000} onChange={(e) => setDescription(e.target.value)} onKeyDown={(e) => e.key === "Enter" && submit()} />
      </div>
    </Dialog>
  );
}
