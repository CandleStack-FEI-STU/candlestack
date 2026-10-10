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

When `main` uses API changes that prod does not have yet, point the dev server at a backend
that has them with `API_TARGET`, for example the local one from the repository root
(`docker compose up`, see the root README):

```sh
API_TARGET=http://localhost:8000 npm run dev
```

| Command | What |
| --- | --- |
| `npm run dev` | dev server with hot reload |
| `npm run build` | type-check and build into `dist/` |
| `npm test` | unit tests (Vitest) |
| `npm run lint` | oxlint (type-aware), Prettier check and knip (unused files, exports and dependencies) |
| `npm run format` | format every file with Prettier |
| `npm run api:types` | regenerate `src/api/schema.d.ts` from `docs/openapi.json` after an API change |

Run `npm run build`, `npm run lint` and `npm test` before every push.

`site/` is the placeholder page that prod serves until the app is released.
