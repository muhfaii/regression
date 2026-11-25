interface Env {
  ASSETS: Fetcher;
  BACKEND_URL: string; // e.g. https://infera-backend.onrender.com
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname.startsWith("/api/")) {
      const backendUrl = new URL(url.pathname + url.search, env.BACKEND_URL);
      const proxied = new Request(backendUrl, request);
      // Pass the visitor's IP through for backend rate limiting; overwrite any
      // client-supplied value so it can't be spoofed via the Worker.
      proxied.headers.set("X-Infera-Client-IP", request.headers.get("CF-Connecting-IP") ?? "");
      return fetch(proxied);
    }

    return env.ASSETS.fetch(request);
  },
};
