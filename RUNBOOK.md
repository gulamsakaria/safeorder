# Runbook

Short operating notes. Grows as steps are completed (final version in Step 15).

## Start the app

1. `make setup` (once)
2. `make api` in one terminal, `make web` in another
3. Open http://localhost:5173. The Sandbox banner must always be visible.

## Checks before a commit

`make test` (pytest and ruff) and `cd frontend && npm run build`.
