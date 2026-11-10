import type { NextRequest } from "next/server";

// Прокси /api/* на бэкенд. Адрес читается в рантайме (API_URL), поэтому один и тот же образ работает везде.
export const dynamic = "force-dynamic";

const API_URL = () => (process.env.API_URL ?? "http://localhost:5281").replace(/\/$/, "");
const FORWARDED_HEADERS = ["content-type", "x-user-id", "accept"];

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const target = `${API_URL()}/api/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;

  const headers = new Headers();
  for (const name of FORWARDED_HEADERS) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }

  const hasBody = !["GET", "HEAD"].includes(request.method);
  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body: hasBody ? await request.arrayBuffer() : undefined,
      cache: "no-store",
    });

    const responseHeaders = new Headers();
    const contentType = upstream.headers.get("content-type");
    if (contentType) responseHeaders.set("content-type", contentType);
    return new Response(upstream.status === 204 ? null : await upstream.arrayBuffer(), {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch {
    return Response.json(
      { status: 502, title: "bad_gateway", detail: "API недоступен", code: "api_unreachable" },
      { status: 502, headers: { "content-type": "application/problem+json" } },
    );
  }
}

export { proxy as GET, proxy as POST, proxy as PUT, proxy as DELETE, proxy as PATCH };
