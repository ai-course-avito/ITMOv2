import type { NextConfig } from "next";

const config: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  // Весь /api проксируется своим Route Handler (адрес API читается в рантайме), см. src/app/api/[...path]/route.ts
};

export default config;
