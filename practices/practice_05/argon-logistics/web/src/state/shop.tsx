"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import { ApiError } from "@/lib/types";

export type CartItem = { productId: number; quantity: number };

type ShopState = {
  userId: number | null;
  cart: CartItem[];
  cartCount: number;
  addToCart: (productId: number, quantity?: number) => void;
  setQuantity: (productId: number, quantity: number) => void;
  removeFromCart: (productId: number) => void;
  clearCart: () => void;
  pickupPointId: number | null;
  setPickupPointId: (id: number | null) => void;
  /** Выполняет действие от имени гостя; если сервер его не знает, создаёт нового и повторяет. */
  withUser: <T>(action: (userId: number) => Promise<T>) => Promise<T>;
};

const ShopContext = createContext<ShopState | null>(null);

export const useShop = () => {
  const ctx = useContext(ShopContext);
  if (!ctx) throw new Error("useShop вне ShopProvider");
  return ctx;
};

const KEY_USER = "argon.userId";
const KEY_CART = "argon.cart";
const KEY_PICKUP = "argon.pickup";

const read = <T,>(key: string): T | null => {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
};

const write = (key: string, value: unknown) => {
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* localStorage может быть недоступен (приватный режим): работаем без сохранения */
  }
};

async function createGuest(): Promise<number> {
  const suffix = Math.random().toString(36).slice(2, 8);
  const user = await api.createUser(`Гость ${suffix.slice(0, 4)}`, `guest-${suffix}-${Date.now()}@argon.local`);
  write(KEY_USER, user.id);
  return user.id;
}

export function ShopProvider({ children }: { children: ReactNode }) {
  const [userId, setUserId] = useState<number | null>(null);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [pickupPointId, setPickupState] = useState<number | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const userRef = useRef<number | null>(null);
  const creating = useRef<Promise<number> | null>(null);

  const ensureGuest = useCallback(async (force = false): Promise<number> => {
    if (!force && userRef.current) return userRef.current;
    // Параллельные вызовы делят одно создание, иначе заведём несколько гостей.
    creating.current ??= createGuest().finally(() => {
      creating.current = null;
    });
    const id = await creating.current;
    userRef.current = id;
    setUserId(id);
    return id;
  }, []);

  // Восстанавливаем корзину и гостя; если сохранённого гостя сервер не знает, заводим нового.
  useEffect(() => {
    setCart(read<CartItem[]>(KEY_CART) ?? []);
    setPickupState(read<number>(KEY_PICKUP));
    setHydrated(true);

    const stored = read<number>(KEY_USER);
    (async () => {
      if (stored) {
        try {
          await api.myOrders(stored);
          userRef.current = stored;
          setUserId(stored);
          return;
        } catch (e) {
          if (!(e instanceof ApiError && e.code === "user_unauthorized")) return; // сервер недоступен: попробуем позже
        }
      }
      try {
        await ensureGuest(true);
      } catch {
        /* повторим при первом заказе через withUser */
      }
    })();
  }, [ensureGuest]);

  useEffect(() => {
    if (hydrated) write(KEY_CART, cart);
  }, [cart, hydrated]);

  const setPickupPointId = useCallback((id: number | null) => {
    setPickupState(id);
    write(KEY_PICKUP, id);
  }, []);

  const addToCart = useCallback((productId: number, quantity = 1) => {
    setCart((items) => {
      const existing = items.find((i) => i.productId === productId);
      return existing
        ? items.map((i) => (i.productId === productId ? { ...i, quantity: i.quantity + quantity } : i))
        : [...items, { productId, quantity }];
    });
  }, []);

  const setQuantity = useCallback((productId: number, quantity: number) => {
    const q = Math.max(1, Math.min(100_000, Math.floor(quantity) || 1));
    setCart((items) => items.map((i) => (i.productId === productId ? { ...i, quantity: q } : i)));
  }, []);

  const removeFromCart = useCallback((productId: number) => setCart((items) => items.filter((i) => i.productId !== productId)), []);
  const clearCart = useCallback(() => setCart([]), []);

  const withUser = useCallback(
    async <T,>(action: (userId: number) => Promise<T>): Promise<T> => {
      const id = await ensureGuest();
      try {
        return await action(id);
      } catch (e) {
        if (e instanceof ApiError && e.code === "user_unauthorized") return action(await ensureGuest(true));
        throw e;
      }
    },
    [ensureGuest],
  );

  const value = useMemo<ShopState>(
    () => ({
      userId, cart, cartCount: cart.length, addToCart, setQuantity, removeFromCart, clearCart,
      pickupPointId, setPickupPointId, withUser,
    }),
    [userId, cart, addToCart, setQuantity, removeFromCart, clearCart, pickupPointId, setPickupPointId, withUser],
  );

  return <ShopContext.Provider value={value}>{children}</ShopContext.Provider>;
}
