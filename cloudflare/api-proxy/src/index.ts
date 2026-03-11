export interface Env {
  UPSTREAM_API_BASE: string;
}

const ALLOWED_ORIGINS = new Set([
  "https://ocypheris.com",
  "https://www.ocypheris.com",
  "https://dev.ocypheris.com",
  "http://localhost:3000",
  "http://127.0.0.1:3000",
]);

const ALLOW_METHODS = "DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT";

function applyCors(request: Request, response: Response): Response {
  const origin = request.headers.get("Origin") || "";
  if (!ALLOWED_ORIGINS.has(origin)) {
    return response;
  }

  const headers = new Headers(response.headers);
  headers.set("Access-Control-Allow-Origin", origin);
  headers.set("Access-Control-Allow-Credentials", "true");
  headers.set(
    "Access-Control-Allow-Headers",
    request.headers.get("Access-Control-Request-Headers") || "*",
  );
  headers.set("Access-Control-Allow-Methods", ALLOW_METHODS);

  const vary = headers.get("Vary");
  if (!vary) {
    headers.set("Vary", "Origin");
  } else if (!vary.split(",").map((part) => part.trim()).includes("Origin")) {
    headers.set("Vary", `${vary}, Origin`);
  }

  headers.delete("Content-Length");
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

function buildUpstreamUrl(requestUrl: URL, upstreamBase: string): URL {
  const upstreamUrl = new URL(upstreamBase);
  upstreamUrl.pathname = requestUrl.pathname;
  upstreamUrl.search = requestUrl.search;
  return upstreamUrl;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method === "OPTIONS") {
      return applyCors(request, new Response(null, { status: 204 }));
    }

    const requestUrl = new URL(request.url);
    const upstreamUrl = buildUpstreamUrl(requestUrl, env.UPSTREAM_API_BASE);
    const upstreamRequest = new Request(upstreamUrl.toString(), request);
    const upstreamResponse = await fetch(upstreamRequest, {
      redirect: "manual",
    });
    return applyCors(request, upstreamResponse);
  },
};
