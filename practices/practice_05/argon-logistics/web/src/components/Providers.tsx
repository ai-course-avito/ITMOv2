"use client";

import type { ReactNode } from "react";
import { SWRConfig } from "swr";
import { AppProvider } from "@/state/app";
import { ShopProvider } from "@/state/shop";
import { ToastProvider } from "@/state/toast";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <SWRConfig value={{ revalidateOnFocus: true, dedupingInterval: 500, errorRetryInterval: 3000 }}>
      <ToastProvider>
        <AppProvider>
          <ShopProvider>{children}</ShopProvider>
        </AppProvider>
      </ToastProvider>
    </SWRConfig>
  );
}
