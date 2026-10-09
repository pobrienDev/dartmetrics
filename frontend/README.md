# DartMetrics frontend

The React 19 + TypeScript single-page app for DartMetrics: sign in,
start a match against a guest or a bot, score it dart by dart (501,
Cricket, Halve It), and read the statistics the API derives from the
raw throws.

Everything you need to run it is in the [root README](../README.md)
("Local development"): the Vite dev server proxies `/api` to the
FastAPI backend on port 8000.

```bash
npm ci          # Node 22.22+ or 24.15+
npm run dev     # http://localhost:5173
npm test        # Vitest + Testing Library
npm run lint    # oxlint
npm run build   # tsc -b && vite build -> dist/, which the API container serves
npx playwright test   # end-to-end, needs both servers (or lets Playwright start them)
```

Layout: `src/pages` (one component per route), `src/api` (typed fetch
wrapper and response types mirroring the backend schemas), `src/auth`
(token storage and the protected-route guard), `src/utils` (the few
scoring rules the UI mirrors to know when a visit is complete; the
server remains the judge), `e2e` (Playwright).
