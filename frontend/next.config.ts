import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",

  // Dev-only: proxy `/api/*` to the Python (FastHTML/FastAPI) backend.
  //
  // In production Caddy fronts both containers and routes `/api/*` to the
  // Python service automatically — the browser sees one origin. On localhost
  // there's no Caddy, so any client-side `fetch("/api/...")` hits the Next.js
  // dev server itself, which returns its 404 HTML page → `JSON.parse('<!DOCTYPE')`
  // crashes (e.g. the "Unexpected token '<'" toast on Передать в закупки).
  //
  // The rewrite forwards those calls to whatever `PYTHON_API_URL` points at.
  // Default in `.env.local.example` is `http://localhost:5001` (locally-running
  // Python container — safest, isolated). If you set it to a remote URL like
  // `https://kvotaflow.ru`, localhost UI will hit that instance's API/data.
  // **Side effects (workflow transitions, notifications, document writes) will
  // happen on whatever PYTHON_API_URL points at.** Choose accordingly.
  //
  // Production builds still go through Caddy and ignore this rewrite.
  async rewrites() {
    const pythonApi = process.env.PYTHON_API_URL;
    if (!pythonApi) return [];
    return [
      { source: "/api/:path*", destination: `${pythonApi}/api/:path*` },
    ];
  },
};

export default nextConfig;
