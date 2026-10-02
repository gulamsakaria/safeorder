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
- `POST /api/disputes/{id}/analyze` needs the trained dispute classifier (`make cases train-dispute`).
  Without `models/dispute_baseline_v1.joblib` the call answers `503 CLASSIFIER_UNAVAILABLE`.
- `/api/sim/*` and `/api/demo/*` are sandbox-only; set `api.demo_endpoints_enabled: false` to disable them.

## Dispute cases and the classifier

```bash
make make-cases      # rewrites raw/ from the assistant-written bank (deterministic; skip if you add your own)
make cases           # validate_cases + split_cases -> data/cases/*.jsonl, reports/dispute_cases_*.json
make train-dispute   # fits models/dispute_baseline_v1.joblib
make eval && make docs
```

To add the team's cases: drop `team_<SUBTYPE>.jsonl` (fields: BLUEPRINT.md Section 8.3, `source`
`team`) into `raw/`, run `make cases train-dispute eval docs`: they fill Test 2 and are reported
separately. Read `raw/PROVENANCE.md` first.

## Live demo on Hugging Face (free Space)

One container serves the API and the frontend on one address. Do this on your own computer, where
you are logged in to Hugging Face (or have a token with write access; never paste it in a chat):

```bash
git pull
HF_TOKEN=<token> SAFEORDER_DEMO_CODE=<a code you choose> \
  PYTHONPATH=backend:. .venv/bin/python -m scripts.deploy_space --repo-id <your-user>/safeorder
```

It creates a **private** Space (add `--public` for judges; it can be switched in the Space
settings), stores the demo code as a Space secret, and uploads the app. Watch the **Logs** tab: the
first build takes a few minutes. Then open `https://<your-user>-safeorder.hf.space`.

- Open the link once shortly before the demonstration: a free Space sleeps when idle and needs a
  minute or two to wake up.
- `/demo` asks for the demo code (the field is on the page). Everything else is open to anyone
  with the link, so keep the Space private or share the link only with judges and the team.
- Each (re)start resets the data and reloads the seven scenarios (the trained classifier is in the image).
- Try the container locally first, if Docker is installed:
  `docker build -t safeorder . && docker run -p 7860:7860 safeorder`.

## Rehearsal and limits

```bash
make rehearse        # three clean demo runs from a reset, with the real classifier (--stand-in: fixed one)
make secret-scan
```

Config `api.max_body_bytes` and `api.rate_limit_per_minute` (0 = off) control the request limits;
`api.demo_endpoints_enabled: false` removes the `/api/sim` and `/api/demo` routes. Tag the freeze
(`git tag mvp-freeze && git push origin mvp-freeze`) only after the dispute classifier is in and
`make test`, `make rehearse` and the browser check pass.

## Documents, secret scan, Hugging Face (private)

```bash
make eval && make docs                                  # regenerate docs/*.md from reports/*.json
.venv/bin/python -m scripts.secret_scan                 # exit 1 if anything looks like a credential
PYTHONPATH=backend:. .venv/bin/python -m scripts.upload_hf --repo-id <you>/<name> --dry-run
HF_TOKEN=<token> PYTHONPATH=backend:. .venv/bin/python -m scripts.upload_hf --repo-id <you>/<name>
```

The upload creates or reuses a **private** model repository and refuses a public one. Never put a
token in a file; pass it through the environment.

## Evaluation report and metrics page

```bash
make eval        # trust evaluation + injection checks + time study -> reports/summary.json, figures
```

The metrics page (`/metrics`) shows `reports/summary.json` as it is; anything not measured reads
"not measured". For the analyst time study, copy `docs/time_study_template.json` to
`data/time_study.json`, replace the example with real timings (seconds per case, with and without
the tool), and run `make eval` again.

## Demo scenarios

```bash
make data && make train && make demo-reset   # prints the ids to use (sellers, orders, disputes)
```

The same set loads from the hidden `/demo` page ("load scenarios"). Scenarios 3, 4 and 6 are analysed
by the trained dispute classifier while loading (without it they show "analysis pending"). Scenario 7
is a held order: a judge reports a problem on it in their own words, then runs the analysis in the
analyst console.

## Trained models on Kaggle (private)

```bash
export KAGGLE_USERNAME=<you> KAGGLE_KEY=<token>      # or `kaggle auth login`
make kaggle-models    # uploads models/ and the evaluation reports as a new version of the
                      # private dataset safeorder-trained-models (creates it the first time)
```

Run it after every training run. It never uploads raw cases or synthetic data.

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
