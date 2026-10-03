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

## Live website on your own sub-domain (cPanel, no Python needed)

The whole app also exists as a **static website**: only HTML, CSS and JavaScript files. The trained
models run in the browser, so there is no backend to host. The built site is in `site/` and packed
in `site.zip` (both committed).

1. Download `site.zip` from the GitHub repository (open the file, then **Download raw file**).
2. cPanel -> **Domains / Subdomains**: create a sub-domain, for example `demo.your-domain.com`. Note the
   document root folder it gets (for example `public_html/demo`).
3. cPanel -> **File Manager** -> open that folder -> **Upload** `site.zip` -> right-click it -> **Extract**.
   `index.html` must sit directly in that folder (not in a sub-folder). In File Manager's **Settings**
   switch on "Show hidden files" to see `.htaccess`.
4. Open `https://demo.your-domain.com`. Turn on AutoSSL in cPanel if the page is not https.
5. Press **Demo** in the menu, then **Load scenarios**; follow `docs/pitch/demo_script.md`.

If you see a blank page: open the browser console (F12). A 404 for `assets/...` or `engine/...` means the
files were extracted into a sub-folder; move them up. The site does not work when opened as a local
file (`file://`): it needs a web address.

Rebuild after any change (needs Node 20+ and the Python environment):
`make eval && make static-site`, then upload the new `site.zip`. Everything the browser needs (models, seller
table, thresholds, evaluation summary) is regenerated from the trained models and reports by
`make static-data`.

What the static site is: the same screens and the same trained models and rules, ported to
TypeScript and checked against the Python code (see DECISIONS.md). State (orders, disputes, the simulated
clock) lives in the browser tab; there is no database and no sign-in. Everything it needs, including the model
weights, is downloadable by anyone who has the link: share the link with the judges and the team only.

## Website on a sub-domain that calls a backend on Render

The same `site.zip` can talk to a real backend instead of running the models in the browser. Use this
if you want the live site to show the real API (database, ledger, audit log).

**A. Backend on Render (free plan)**

1. render.com -> sign up -> **New +** -> **Blueprint** -> connect the GitHub repository
   `gulamsakaria/safeorder` (if it is private, give Render access to it). Render reads `render.yaml`.
2. It asks for one secret: `SAFEORDER_DEMO_CODE`. Type a code you choose (it protects the demo
   controls). The other settings are in the file: Docker build, `/health` check, the allowed website
   `https://safeorder.stratifyxglobal.com`, demo scenarios loaded on every start.
3. Press **Apply**. The first build takes about 5 to 10 minutes (Render logs show progress). When the
   service is **Live**, copy its address, for example `https://safeorder-api.onrender.com`, and open
   `<address>/health`: it must show `{"status":"ok"}`.
4. Free plan facts: the service sleeps after about 15 minutes without a visitor and needs up to a minute
   to wake (the website shows a "server is waking up" notice meanwhile); memory is 512 MB and the app peaks
   near 300 MB; the data resets on every start and the scenarios are loaded again. **Open the website a
   few minutes before a demonstration.** For a demo day without risk, Render's paid plan stays awake.

**B. The website on `safeorder.stratifyxglobal.com`**

1. cPanel -> Subdomains: create `safeorder` (document root, for example `public_html/safeorder`).
2. File Manager -> that folder -> upload `site.zip` -> Extract (`index.html` directly in the folder).
3. Open `config.js` in that folder (File Manager -> Edit) and set the one line to your Render address,
   without a slash at the end:
   `window.SAFEORDER_API = 'https://safeorder-api.onrender.com'`
   Save and reload the site (Ctrl+F5). Leave it as `''` to run without a backend.
4. On the demo page type the demo code from step A2, then **Load scenarios**.

Check: browser F12 -> Network shows requests to the Render address; a red CORS error means the
`SAFEORDER_CORS_ORIGINS` value on Render does not equal the website's address exactly (https, no slash).

## Accounts, wallet and the live website (Neon + Render + the sub-domain)

The website is a sandbox wallet: people open an account with a phone number and a PIN, get demo
money, pay sellers (the money is held), sellers enter the order number, buyers confirm delivery,
problems go to the AI analysis and an admin. Everything is demo money. Seller trust checks, held
payments, delivery proof, the 24-hour and 72-hour timers and the admin area are in
`backend/app/{accounts,auth,wallet,payments,proof}.py` and `backend/app/api/{accounts,admin}.py`.

How the pieces fit: the website (static files on the sub-domain) calls the API on Render; the API
keeps its data in a Postgres database that survives restarts.

1. **Database (once).** neon.tech -> create a project -> copy the connection string
   (`postgresql://user:password@host/dbname?sslmode=require`). Keep it private.
2. **Render.** New + -> Blueprint -> this repository. Fill the three secrets Render asks for:
   `DATABASE_URL` (the Neon link), `SAFEORDER_ADMIN_PHONE` (for example `01900000000`) and
   `SAFEORDER_ADMIN_PIN` (5 digits). Press Apply. The first start loads a small sample of synthetic
   sellers (72, a few of every kind, so the seller check has examples) into the empty database in
   seconds. Later starts keep everything. Set `SAFEORDER_FULL_DEMO=1` only if you want all 3,000
   synthetic sellers and the seven old demo stories (about 15 minutes on a free host; registration
   answers "starting" meanwhile). Never change `DATABASE_URL` on a running site: a new, empty
   database means a new start and the accounts of the old one are gone.
3. **Check.** `<render address>/health` shows `{"status":"ok"}`. Sign in on the website with the admin
   number and PIN: the admin panel is under "More".
4. **Website.** Upload `site.zip` to the sub-domain folder (see the cPanel section above) and set
   `window.SAFEORDER_API = 'https://<your-service>.onrender.com'` in `config.js`.
5. **Role-play.** Open the "Guide" tile: one click makes a demo buyer and a demo seller. Use two
   tabs (or "More" -> switch account). The admin moves time forward (24 or 72 hours) under
   "Time" to show the timers.

Rules in short: paying a seller account always holds the money; the seller must enter the order
number within 24 hours or the money goes back; the buyer presses "I received it" to pay the seller;
a seller proof (tracking number and photo) releases the money by itself only after 72 hours of buyer
silence and only when the checks find nothing (a repeated photo or tracking number, a bad number,
a high-risk seller), otherwise an admin decides. A problem report freezes the money until an admin
decides in the analyst console. PINs are stored as salted hashes, five wrong PINs lock the account
for 15 minutes, and the website tells people never to use a real PIN.

Locally: `SAFEORDER_PERSIST=1 SAFEORDER_PROTECT_ADMIN=1 SAFEORDER_ADMIN_PHONE=... SAFEORDER_ADMIN_PIN=...
make api` (SQLite in `data/safeorder.db`, which is not in git). Delete that file after a model change:
tables are created with `create_all`, which does not migrate. The static site is built with
`VITE_WALLET=true` (that is what `npm run build:static` does).

## Look and feel (3D background and motion)

The interface has a dark animated 3D background (three.js, `frontend/src/components/Scene3D.tsx`),
glass cards that tilt towards the pointer, and entrance animations (`frontend/src/index.css`, classes
`so-*`). It is decoration only and never part of a decision:

- three.js is a separate lazy-loaded file (about 130 KB gzipped), so the first screen does not wait for it.
- It switches itself off where WebGL is missing (old phones, the test runner), and the animations stop
  for visitors who set "reduce motion" in their system.
- After a UI change rebuild the static site: run the commands of `npm run build:static` (see
  `frontend/package.json`), then `python -m scripts.zip_site`, and upload `site.zip` again.

## Render checklist (tested locally with the same settings)

Before a demonstration, with the service set up as in "Website on a sub-domain that calls a backend on Render":

1. `<render address>/health` answers `{"status":"ok"}`.
2. `<render address>/api/analyst/queue` lists three disputes (the demo scenarios are loaded on start,
   in a background thread, so wait about 10 to 60 seconds after a wake-up).
3. `SAFEORDER_CORS_ORIGINS` is exactly `https://safeorder.stratifyxglobal.com` (https, no slash).
4. `config.js` on the website holds the Render address, without a slash at the end.
5. Run the tests on Linux or macOS, or with `PYTHONUTF8=1` on Windows. `.gitattributes` keeps LF line
   endings: without it a Windows checkout turns files into CRLF and two tests (the dataset hash and the
   site.zip comparison) fail even though the code is fine.

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
