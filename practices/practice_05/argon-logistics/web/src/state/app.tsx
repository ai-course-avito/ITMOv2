"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import type { DeliveryPlan, NodeKey } from "@/lib/types";

export type Selection =
  | { kind: "node"; key: NodeKey }
  | { kind: "route"; id: number }
  | { kind: "link"; pickupPointId: number; warehouseId: number }
  | null;

export type TabletTab = "catalog" | "cart" | "orders";
export type View = "map" | "catalog";

type AppState = {
  view: View;
  setView: (v: View) => void;
  selection: Selection;
  select: (s: Selection) => void;
  highlightedOrderId: number | null;
  setHighlightedOrderId: (id: number | null) => void;
  /** План из корзины: его маршруты подсвечиваются на карте. */
  previewPlan: DeliveryPlan | null;
  setPreviewPlan: (p: DeliveryPlan | null) => void;
  tabletOpen: boolean;
  setTabletOpen: (open: boolean) => void;
  tabletTab: TabletTab;
  setTabletTab: (t: TabletTab) => void;
  ordersOpen: boolean;
  setOrdersOpen: (open: boolean) => void;
};

const AppContext = createContext<AppState | null>(null);

export const useApp = () => {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp вне AppProvider");
  return ctx;
};

export function AppProvider({ children }: { children: ReactNode }) {
  const [view, setView] = useState<View>("map");
  const [selection, select] = useState<Selection>(null);
  const [highlightedOrderId, setHighlightedOrderId] = useState<number | null>(null);
  const [previewPlan, setPreviewPlan] = useState<DeliveryPlan | null>(null);
  const [tabletOpen, setTabletOpen] = useState(false);
  const [tabletTab, setTabletTab] = useState<TabletTab>("catalog");
  const [ordersOpen, setOrdersOpen] = useState(true);

  const value = useMemo(
    () => ({
      view, setView, selection, select, highlightedOrderId, setHighlightedOrderId,
      previewPlan, setPreviewPlan, tabletOpen, setTabletOpen, tabletTab, setTabletTab, ordersOpen, setOrdersOpen,
    }),
    [view, selection, highlightedOrderId, previewPlan, tabletOpen, tabletTab, ordersOpen],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}
