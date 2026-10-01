# SafeOrder

AI-assisted seller trust, held payments and dispute resolution for Facebook-commerce.
Prototype for AI Dev Fest 2026 (AI Hackathon). Everything runs on **synthetic data inside a
simulated (sandbox) wallet**. No real money, no real customer data.

Full specification: [BLUEPRINT.md](BLUEPRINT.md). Working rules: [CLAUDE.md](CLAUDE.md).

## Run

Requirements: Python 3.11, Node 20+.

```bash
make setup     # Python venv + dependencies, frontend npm install
make test      # pytest + ruff (backend)
make test-web  # typecheck, vitest, lint and build (frontend)
make api       # FastAPI on http://localhost:8000  (GET /health)
make web       # Vite dev server on http://localhost:5173, talks to the real API
make web-mock  # same UI with an in-browser mock server (no backend needed)
```

`make data`, `make train`, `make eval` and `make demo-reset` are placeholders until Steps 3-12.

## Layout

See BLUEPRINT.md Section 4. All thresholds live in `config/config.yaml`.

## Build progress

Built step by step following BLUEPRINT.md Section 13. One commit per step: `step-N: title`.
