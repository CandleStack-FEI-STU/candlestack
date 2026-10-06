# CandleStack frontend

React + TypeScript app built with Vite, styled with Tailwind CSS and shadcn/ui. The stack and
why: [docs/frontend.md](../docs/frontend.md).

## Run locally

Needs Node.js 20.19 or newer (`node -v`).

```sh
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The dev server forwards `/api/*` to the prod API
(https://app.candlestack.tech), so no local backend and no Alpaca keys are needed.

| Command | What |
| --- | --- |
| `npm run dev` | dev server with hot reload |
| `npm run build` | type-check and build into `dist/` |
| `npm run lint` | oxlint |
| `npm run api:types` | regenerate `src/api/schema.d.ts` from `docs/openapi.json` after an API change |
