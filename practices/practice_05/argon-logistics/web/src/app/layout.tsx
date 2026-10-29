import type { Metadata, Viewport } from "next";
import "@fontsource/roboto/400.css";
import "@fontsource/roboto/500.css";
import "@fontsource/roboto/700.css";
import "@fontsource-variable/material-symbols-rounded";
import "./globals.css";

export const metadata: Metadata = {
  title: "Argon Logistics",
  description: "Склады, ПВЗ, связи между ними и живая логистика заказов",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#fef7ff" },
    { media: "(prefers-color-scheme: dark)", color: "#141218" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
