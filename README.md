# SafeOrder

AI-assisted seller trust, held payments and dispute resolution for Facebook-commerce.
Prototype for AI Dev Fest 2026 (AI Hackathon). Everything runs on **synthetic data inside a
simulated (sandbox) wallet**. No real money, no real customer data, not a product of upay.

Full specification: [BLUEPRINT.md](BLUEPRINT.md). Working rules: [CLAUDE.md](CLAUDE.md).
Decisions, measurements and caveats: [DECISIONS.md](DECISIONS.md). Runbook: [RUNBOOK.md](RUNBOOK.md).
Model cards, dataset cards, evaluation protocol: [docs/](docs/README.md).

## What it does

1. **Trust Check** before paying: a score, a band and plain Bangla/English reasons (LightGBM, calibrated).
2. **Safe Order**: the money is held (simulated) until the buyer confirms with a delivery code.
3. **Evidence analyzer** for disputes: timeline, consistency flags, a four-class text classifier,
   a prompt-injection screen and a router. It only *suggests*; a human analyst decides every dispute.
4. **Metrics page** (`/metrics`) showing the evaluation numbers exactly as the scripts wrote them.

## Run

Requirements: Python 3.11, Node 20+.

```bash
make setup           # Python venv + dependencies, frontend npm install
make data train      # synthetic sellers, trust model
make cases train-dispute eval   # dispute cases (split), classifier, evaluation report
make test            # pytest + ruff (backend)
make test-web        # typecheck, vitest, lint and build (frontend)
make api             # FastAPI on http://localhost:8000
make web             # Vite dev server on http://localhost:5173, talks to the real API
make web-mock        # same UI with an in-browser mock server (no backend needed)
make demo-reset      # reset the database and load the seven demo scenarios
make rehearse        # three clean demo runs from a reset
```

A live demo as one free Hugging Face Space (API + UI in one container): see RUNBOOK.md.

## Honest status

- All data is synthetic. **The dispute cases were written by an AI assistant, not by ChatGPT,
  Gemini or the team, and no person has reviewed them** (`raw/PROVENANCE.md`). The classifier's
  scores therefore show that the pipeline works, not how it would do on real disputes.
- Not done: the optional transformer classifier (Step 13), the team's own test cases, the 10%
  manual case review, the analyst time study, native-speaker review of the Bangla text.

## Layout

See BLUEPRINT.md Section 4. All thresholds live in `config/config.yaml`.
