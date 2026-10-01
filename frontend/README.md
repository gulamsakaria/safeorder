# SafeOrder frontend

Vite + React 19 + TypeScript + Tailwind v4. Bangla by default, English toggle, mobile first.
The yellow **Sandbox banner is part of the layout** and cannot be hidden by any screen.

## Screens

| Route | Screen |
|---|---|
| `/` | Trust Check: search a seller, score, band, reasons; extra confirmation for HIGH_RISK; place a Safe Order |
| `/order/:id` | Safe Order tracker: status, courier, delivery code entry, hold countdown, timeline, ledger, "report a problem" |
| `/order/:id/report` | Buyer dispute form (photo upload is a disabled placeholder; evidence is described in text) |
| `/dispute/:id` | Dispute page with a buyer view (add evidence) and a seller view (respond before the deadline) |
| `/analyst` | Analyst queue: human-review cases first, filter by route |
| `/analyst/dispute/:id` | Case page: the three guideline questions, flags, probabilities, both sides, timeline, decision panel with a required note, score before and after |
| `/analyst/seller/:id` | A seller's trust-score history |
| `/demo` | Sandbox controls: courier events, move the simulated clock, reset |

## Data source: one switch

```bash
cp .env.example .env.local     # then edit
VITE_USE_MOCK=true             # in-browser mock server, no backend needed
VITE_USE_MOCK=false            # the real API at VITE_API_BASE_URL (default http://localhost:8000)
```

From the repository root: `make web-mock` or `make web` (real API, run `make api` first).

## API client

`src/api/schema.ts` is **generated** from `../docs/openapi.json` (`npm run gen:api`, or `make gen-api`
from the root, which also refreshes the OpenAPI file). Calls go through `openapi-fetch`, so a
renamed field in the backend fails the TypeScript build. The mock server (`src/mocks`, MSW) is typed
with the same generated types.

## Checks

```bash
npm run typecheck && npm test && npm run lint && npm run build     # or: make test-web
```
