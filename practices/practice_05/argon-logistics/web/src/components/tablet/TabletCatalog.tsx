"use client";

import { useMemo, useState } from "react";
import { Chip, EmptyState, Icon, IconButton, TextField } from "@/components/ui";
import { useAllStock, useNetwork, useProducts } from "@/lib/hooks";
import { useShop } from "@/state/shop";

const ICONS = ["water_full", "bakery_dining", "emoji_food_beverage", "coffee", "nutrition", "set_meal", "icecream", "egg_alt"];

/** Доступное количество каждого товара по всем складам (без резерва). */
export function useAvailability() {
  const { data: network } = useNetwork();
  const { data: stock } = useAllStock(network?.warehouses);
  return useMemo(() => {
    const result = new Map<number, number>();
    for (const lines of Object.values(stock ?? {}))
      for (const l of lines) result.set(l.productId, (result.get(l.productId) ?? 0) + l.available);
    return result;
  }, [stock]);
}

export function TabletCatalog() {
  const { data: products } = useProducts();
  const availability = useAvailability();
  const { cart, addToCart, setQuantity, removeFromCart } = useShop();
  const [query, setQuery] = useState("");

  const filtered = (products ?? []).filter((p) => `${p.name} ${p.sku}`.toLowerCase().includes(query.trim().toLowerCase()));

  if (products && products.length === 0)
    return (
      <EmptyState icon="inventory_2" title="Каталог пуст">
        Добавьте товары на вкладке «Каталог» или загрузите демо-сеть на карте.
      </EmptyState>
    );

  return (
    <>
      <TextField dense label="Поиск товара" value={query} onChange={(e) => setQuery(e.target.value)} />
      {filtered.map((p) => {
        const inCart = cart.find((i) => i.productId === p.id);
        const available = availability.get(p.id) ?? 0;
        return (
          <div className="product-tile" key={p.id} data-product={p.sku}>
            <div className="thumb">
              <Icon name={ICONS[p.id % ICONS.length]} size={32} fill />
            </div>
            <div className="grow">
              <div className="t-title-s" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.name}</div>
              <div className="t-body-s muted">{p.sku}</div>
              <div style={{ marginTop: 4 }}>
                <Chip compact tone={available > 0 ? "ready" : "cancelled"}>
                  {available > 0 ? `в наличии ${available}` : "нет в наличии"}
                </Chip>
              </div>
            </div>
            {inCart ? (
              <div className="qty">
                <IconButton
                  small
                  icon={inCart.quantity <= 1 ? "delete" : "remove"}
                  label="Меньше"
                  onClick={() => (inCart.quantity <= 1 ? removeFromCart(p.id) : setQuantity(p.id, inCart.quantity - 1))}
                />
                <b>{inCart.quantity}</b>
                <IconButton small icon="add" label="Больше" onClick={() => setQuantity(p.id, inCart.quantity + 1)} />
              </div>
            ) : (
              <IconButton variant="tonal" icon="add_shopping_cart" label="В корзину" disabled={available <= 0} onClick={() => addToCart(p.id)} />
            )}
          </div>
        );
      })}
      {products && filtered.length === 0 && <div className="t-body-m muted" style={{ textAlign: "center", padding: 16 }}>Ничего не найдено</div>}
    </>
  );
}
