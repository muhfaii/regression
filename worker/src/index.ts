import { Container, getContainer } from "@cloudflare/containers";

// Single instance for now — no sticky/multi-instance routing yet.
export class InferaBackend extends Container {
  defaultPort = 8000;
  sleepAfter = "10m";
}

interface Env {
  BACKEND: DurableObjectNamespace<InferaBackend>;
  ASSETS: Fetcher;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname.startsWith("/api/")) {
      const backend = getContainer(env.BACKEND); // single named instance
      return backend.fetch(request);
    }

    return env.ASSETS.fetch(request);
  },
};
