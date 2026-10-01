# Runbook

Short operating notes. Grows as steps are completed (final version in Step 15).

## Start the app

1. `make setup` (once), then `make data && make train` to create the demo data and the model
2. `make api` in one terminal, `make web` in another (or `make web-mock` for a UI with no backend)
3. Open http://localhost:5173. The Sandbox banner must always be visible.
4. Reset the demo at any time on the `/demo` page or with `POST /api/demo/reset`.

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

## Kaggle explainer notebook

```bash
make data && make train && make eval      # the bundle needs the generated data, model and report
make kaggle                               # builds build/kaggle/dataset and kaggle/notebook
export KAGGLE_USERNAME=<you> KAGGLE_KEY=<token>      # or `kaggle auth login`
kaggle datasets version -p build/kaggle/dataset -m "update"   # first time: kaggle datasets create -p ...
# wait until the dataset shows as ready, then:
kaggle kernels push -p kaggle/notebook    # runs the notebook on Kaggle (private)
```

Both items are private by default. If the notebook fails right after a dataset update, it may
have started before the new dataset version was ready: push it again.

## Frontend notes

- `VITE_USE_MOCK=true|false` (see `frontend/.env.example`) is the only switch between the mock and the real API.
- The mock keeps its state in the browser tab (`sessionStorage`), so a refresh does not wipe it.
- After a backend contract change: `make gen-api`, then `make test-web`. A test fails if the generated types are stale.
