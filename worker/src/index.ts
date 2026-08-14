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
      return fetch(proxied);
    }

    return env.ASSETS.fetch(request);
  },
};
