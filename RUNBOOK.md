# Runbook

Short operating notes. Grows as steps are completed (final version in Step 15).

## Start the app

1. `make setup` (once)
2. `make api` in one terminal, `make web` in another
3. Open http://localhost:5173. The Sandbox banner must always be visible.

## Checks before a commit

`make test` (pytest and ruff) and `cd frontend && npm run build`.

## Rebuild the demo database

The database (`data/safeorder.db`) is created with `create_all`, which does not migrate old tables.
After pulling model changes, or when something looks stale:

```bash
make data          # regenerate synthetic data (about 15 s) and rebuild the database
# or, with the API running:
curl -X POST localhost:8000/api/demo/reset -H 'content-type: application/json' \
     -d '{"scenario_set": "default"}'
```

`scenario_set` is `default` (generated sellers) or `empty` (no data).

## API notes

- Interactive docs: http://localhost:8000/docs. The contract file is `docs/openapi.json`
  (`make openapi` rewrites it; a test fails when it is stale).
- `POST /api/disputes/{id}/analyze` needs the trained dispute classifier (Step 6). Until it exists the
  call answers `503 CLASSIFIER_UNAVAILABLE`.
- `/api/sim/*` and `/api/demo/*` are sandbox-only; set `api.demo_endpoints_enabled: false` to disable them.
