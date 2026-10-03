# SafeOrder

**AI-assisted seller trust, held payments and dispute resolution for Facebook-commerce (F-commerce) in Bangladesh.**

> **Synthetic data. Simulated wallet. No real money. Not a product of upay.**
> A prototype for the AI Dev Fest 2026 AI Hackathon.

**Live demo:** <https://safeorder.stratifyxglobal.com/> (backend: <https://safeorder-api.onrender.com/health>)

**Team:** Gulam Sakaria (Team Leader), MD. Ashraful Islam, Sumiya Akter Nirjona

## For judges: run it in one step

Pick any one way. All of them use only synthetic data and demo money.

**A. On your computer (recommended; needs Python 3.11 or newer and internet the first time).**
Download or clone this repository, open a terminal in the folder and run:

```bash
python run_local.py          # Windows: py run_local.py, or double-click run_local.bat
                             # macOS/Linux: ./run_local.sh also works
```

It creates its own `.venv`, installs the packages, generates the synthetic sellers, starts the
server and opens `http://localhost:8000` in your browser. The first start takes a few minutes;
after that it starts in seconds. Stop with Ctrl+C. Add `--reset` to start with a clean database.
Demo admin (analyst console and the time controls under "More"): phone `01900000000`, PIN `12345`.
This admin exists **only in the local sandbox** that `run_local.py` starts; the hosted site has its own
admin account whose login is private to the owner.

**B. With Docker** (no Python needed): `docker build -t safeorder .` and then

```bash
docker run --rm -p 7860:7860 -e SAFEORDER_PERSIST=1 -e SAFEORDER_ADMIN_PHONE=01900000000 \
  -e SAFEORDER_ADMIN_PIN=12345 -e SAFEORDER_PROTECT_ADMIN=1 safeorder
```

then open `http://localhost:7860`. (The container route was not run by the author for this README;
the same Dockerfile is what Render builds for the hosted API.)

**C. Hosted copy:** https://safeorder.stratifyxglobal.com (the website) calls an API on a free
Render server. If nothing loads at once, wait one minute and reload: free servers sleep when idle.
(If it is down, use A or B.)

**What to try (3 minutes):** open the "Guide" tile, make a demo buyer and a demo seller, send money
to the seller's payment number (you see the seller's name and Trust Check first), watch the money
become "held", then confirm the delivery or report a problem and decide it as the admin.
`site.zip` is only the website files for a web host; it cannot run alone because the wallet needs the server.

| | |
|---|---|
| 1. [Project overview](#1-project-overview) | 8. [Live deployment](#8-live-deployment) |
| 2. [Features](#2-features) | 9. [Testing and the 5-minute judge quick start](#9-testing-and-the-5-minute-judge-quick-start) |
| 3. [Technology stack](#3-technology-stack) | 10. [Other configuration](#10-other-configuration) |
| 4. [Requirements](#4-requirements) | 11. [Evaluation results and limits](#11-evaluation-results-and-limits) |
| 5. [Installation and setup](#5-installation-and-setup) | 12. [Pre-existing components and disclosures](#12-pre-existing-components-and-disclosures) |
| 6. [Environment variables](#6-environment-variables) | 13. [Repository layout and documentation index](#13-repository-layout-and-documentation-index) |
| 7. [Run and build commands](#7-run-and-build-commands) | |

Full specification: [BLUEPRINT.md](BLUEPRINT.md). Working rules: [WORKING_RULES.md](WORKING_RULES.md).
Decisions and caveats: [DECISIONS.md](DECISIONS.md). Operating notes: [RUNBOOK.md](RUNBOOK.md).

---

## 1. Project overview

### The problem

In Bangladesh a large amount of small retail runs through Facebook pages. Two trust problems feed each
other (from the public reports cited in BLUEPRINT.md, Appendix C; the team's own field interviews are
not part of this repository):

- **Buyers pay in advance** to pages they cannot verify. Fake pages collect advance payments and
  disappear.
- **Honest sellers** fear fake orders, so they ask for advance payment too. Scammers copy that habit, and
  an honest new seller with no record looks the same as a scammer.
- **Disputes** ("I did not receive it", "wrong item") are settled by phone calls and arguments. There is
  no neutral, evidence-based process and it is slow.

### The proposed solution

SafeOrder sits on top of a **simulated wallet**:

1. **Trust Check.** Before paying, the buyer sees a score, a band (TRUSTED, CAUTION, HIGH_RISK or
   LIMITED_HISTORY) and plain Bangla or English reasons for the seller.
2. **Held Safe Order.** The payment goes to the seller but stays held (simulated) until delivery is
   confirmed. The seller takes the order by entering the order number; the buyer confirms delivery.
3. **Evidence analyzer.** If something goes wrong, the buyer reports it. The analyzer builds a timeline,
   checks consistency, classifies the text, screens for attempts to instruct the AI, and **suggests** an
   outcome with an explanation.
4. **A human decides.** An admin (analyst) reads the suggestion and decides every dispute and writes a
   reason. The AI never moves money.

### Purpose

To show, on synthetic data and with every number measured and published, how AI can *assist* trust and
dispute decisions in a way that is explainable, fair to new honest sellers, hard to manipulate, and
always under human control. It is a hackathon prototype, not a production system.

---

## 2. Features

### What is implemented

- **Wallet app** (the live site): sign-up with phone number and PIN, demo money, **Send Money** and
  **Make Payment**, history, seller mode, Bangla and English, mobile-first, with a public home page.
- **Held payments tied to an order number.** Paying a seller account always holds the money. The seller
  must enter the order number within 24 hours or the money goes back to the buyer. The buyer presses
  "I received it" to pay the seller.
- **Delivery proof.** The seller submits a tracking number and a photo. A clean proof releases the money
  after 72 hours of buyer silence; a proof with a warning (repeated photo, repeated tracking number,
  bad tracking format, high-risk seller) waits for an admin.
- **Problem reports.** A report freezes the held money, runs the AI analysis at once, lets the seller
  answer, and goes to the admin's analyst console.
- **Admin area.** Orders and proofs, users (freeze, demo-money grant), the demo clock ("move time
  forward 24 or 72 hours"), and the analyst console with score before and after a decision.
- **Metrics page** (`/metrics`) that shows `reports/summary.json` exactly as the scripts wrote it
  ("not measured" where nothing was measured).
- **Classic demo screens** (seller search, order tracker, dispute pages, `/demo` controls) that the
  seven demo scenarios use.
- **Security basics:** PINs stored as salted scrypt hashes, five wrong PINs lock the account for 15
  minutes, orders are visible only to their buyer, seller and an admin, request-size and rate limits,
  an append-only audit log, a double-entry ledger.

### Where AI is used, and where it is not

| Component | What it does | File |
|---|---|---|
| **Trust model** | LightGBM classifier on 13 seller-behaviour features (account age, orders in 7 and 30 days, unique buyers in 24 hours and 30 days, buyer burst ratio, repeat-buyer ratio, buyer concentration, refund rate, dispute rate, cash-out latency, ticket-vs-category ratio, shared-buyer overlap). Probabilities are **Platt-calibrated**; `refund_rate` and `dispute_rate` have a **monotone constraint** (more refunds never look safer). Each score comes with 2 to 4 **reasons** taken from the feature contributions. | `backend/app/trust/` |
| **Dispute classifier** | **TF-IDF** (word 1-2 grams plus character 2-5 grams) with a class-balanced **logistic regression**, sigmoid-calibrated on the validation split. Four classes: `SELLER_FAULT`, `BUYER_FALSE_CLAIM`, `COURIER_ISSUE`, `INSUFFICIENT_EVIDENCE`. | `backend/app/disputes/baseline.py` |
| **Injection screen** | Pattern rules (English and Bangla) that find sentences giving instructions to an AI ("approve the refund", "ignore previous rules"). Matching sentences are removed from what the classifier and checks see, and the case is forced to human review. | `backend/app/disputes/injection.py` |
| **Consistency checks** | Plain rules that raise flags: code contradicts the claim, no courier proof, empty or vague evidence, repeat claimant, amount mismatch, late report, injection detected. | `backend/app/analyzer/consistency.py` |
| **Router** | Rules on top of the model output: a "fast lane" (one-click confirmation) only for confident, simple, low-amount cases; everything unusual goes to a human. | `backend/app/analyzer/router.py` |
| **Explanations** | **Templates** in Bangla and English filled from flags, probabilities and facts. No generative model writes any text. | `backend/app/analyzer/explain.py` |
| **Proof checks** | Plain rules for the seller's delivery proof (see above). No model. | `backend/app/proof.py` |

**Where AI is not used.** Money moves only through the order state machine and the ledger
(`backend/app/state_machine.py`, `ledger.py`, `wallet.py`) under the rules in `backend/app/rules.py` and
`config/config.yaml`. The models and the analyzer only **suggest**; **a human admin decides every
dispute**. There is no generative model and no external API call in any decision path. Evidence text
is treated as untrusted data and is never followed as an instruction.

### The seven demo scenarios

Set up by `make demo-reset` (or the `/demo` page, or `SAFEORDER_FULL_DEMO=1` on a persistent database);
they use the classic screens and the real API.

| # | Scenario | What it shows |
|---|---|---|
| 1 | Fake seller | Trust Check gives HIGH_RISK with reasons |
| 2 | Honest seller, happy path | Confirm with the delivery code, move the clock 72 hours: the hold is released |
| 3 | Seller fault | The analyst refunds the buyer; the seller's score drops (before and after) |
| 4 | False buyer claim | The code was used but the buyer says "not received", third claim: human review |
| 5 | Honest new seller | LIMITED_HISTORY: not treated as a scammer |
| 6 | Injection attempt | The evidence tells the AI to approve; only the injection flag changes |
| 7 | Judge case | A judge reports a problem on a held order in their own words; the console shows probabilities and route |

---

## 3. Technology stack

Versions come from `requirements-runtime.txt` (the versions the committed models were trained and are
served with), `frontend/package.json` and `frontend/package-lock.json`.

| Layer | Technology |
|---|---|
| Languages | Python 3.11 (Docker image; the author also ran everything on 3.12.10), TypeScript 5.9, YAML, SQL |
| Backend | FastAPI 0.142.2, Uvicorn 0.54.0, Starlette 1.7.0, SQLModel 0.0.47, SQLAlchemy 2.0.54, Pydantic 2.13.5 |
| Database | SQLite (default, file `data/safeorder.db`); PostgreSQL through `DATABASE_URL` (psycopg2-binary 2.9.10), used by the live site on Neon |
| AI and data | LightGBM 4.7.0, scikit-learn 1.9.1, pandas 3.0.6, NumPy 2.4.6, SciPy 1.17.1, joblib 1.6.0, networkx 3.6.1, PyYAML 6.0.3, matplotlib (figures) |
| Frontend | React 19.3 (`^19.2.8`), React Router 7.18.4, Vite 8.3.2, Tailwind CSS 4.3.3, openapi-fetch 0.17, three.js 0.186.1 (the 3D look of the app) |
| Tests and quality | pytest 9.1.1, ruff, Vitest 5.0.3, Testing Library, MSW 2.15, oxlint |
| Services | Render (Docker web service for the API), Neon (PostgreSQL), a cPanel host (static website), Hugging Face Spaces (optional one-container deployment), Kaggle (explainer notebook and a private model dataset; optional) |

---

## 4. Requirements

| | |
|---|---|
| **Python** | 3.11 (the Dockerfile image and the `ruff` target). The author ran everything on 3.12.10 on Windows 11. The Makefile calls `python3.11` in `make setup`. |
| **Node.js** | 20.19 or newer, or 22.12 or newer (Vite 8 requires it; Vitest 5 needs 22.12+ or 24+). The Dockerfile uses `node:22-slim`; the author ran Node 24.21.0 and npm 11.19.0. |
| **Operating system** | Linux or macOS for `make` as written. Windows: use the PowerShell commands in section 5 (the Makefile uses `.venv/bin/python` and Unix environment-variable syntax). |
| **Optional tools** | `make` (any GNU Make), Docker (only for the container), Git. A Kaggle or Hugging Face account only for the optional upload scripts. |
| **Disk** | About 1 GB free. Measured in a fresh clone: virtual environment about 530 MB, `frontend/node_modules` about 227 MB, generated data about 57 MB (13.8 MB of it the SQLite file), the repository itself about 25 MB with history. |
| **Memory** | `RUNBOOK.md` records that the deployed service peaks near 300 MB on a 512 MB Render free instance (the author's note, not re-measured for this README). |
| **Network** | Needed for `pip install`, `npm install` and the live demo. After installation nothing in the app calls an external API. The only third-party request a browser makes is the Google Fonts stylesheet for the Noto Sans Bengali font; the text falls back to a system font without it. |

What works without a network once installed: the API, all tests, the evaluation, the classic UI in mock
mode, and the in-browser static site.

---

## 5. Installation and setup

### The shortest way (any operating system)

`python run_local.py` does everything below for you (virtual environment, the **pinned** packages of
`requirements-runtime.txt`, the synthetic data, the server and the browser); see "For judges" at the top.
The rest of this section is the manual way, which also installs the development tools (pytest, ruff).

Synthetic data is **not committed** (it is regenerated from fixed seeds), so `make data` is a required
step. The trained models (`models/*.joblib`) **are committed**, so `make train` is optional.

### Linux or macOS (with `make`)

```bash
git clone https://github.com/gulamsakaria/safeorder.git
cd safeorder

make setup      # python3.11 -m venv .venv; pip install -r requirements.txt; cd frontend && npm install
make data       # generates the synthetic sellers (about 15 s) and loads them into data/safeorder.db
```

Then `make api` and `make web` (section 7) give you a running app. Optional steps:

```bash
make train           # retrain the trust model (models are already committed)
make cases           # validate and split the dispute cases in raw/ -> data/cases/
make train-dispute   # retrain the dispute classifier
make eval            # regenerate reports/*.json, reports/summary.json and the figures
make demo-reset      # reset the database and load the seven demo scenarios
```

If you only have another Python 3.11+ than `python3.11`, create the environment yourself
(`python3 -m venv .venv`) and continue with `make` as usual.

### Windows (PowerShell, without `make`)

These commands were run in a fresh clone, in this order, on Windows 11 with Python 3.12.10 and Node 24.21.0.

```powershell
git clone https://github.com/gulamsakaria/safeorder.git
cd safeorder

python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt     # about 90 s
cd frontend; npm install; cd ..                                   # about 10 s

# Use UTF-8 for Python (the repository holds Bangla text; without this some tests fail on Windows).
$env:PYTHONUTF8 = "1"
# Python looks for the project packages here (the Makefile sets this to "backend:." on Linux).
$env:PYTHONPATH = "backend;."

# make data  (about 15 s)
.\.venv\Scripts\python.exe -m scripts.generate_sellers --version both --load-db
```

Equivalent commands for the other `make` targets (keep the two environment variables above set):

| `make ...` | PowerShell |
|---|---|
| `train` | `.\.venv\Scripts\python.exe -m scripts.train_trust` |
| `cases` | `.\.venv\Scripts\python.exe -m scripts.validate_cases` then `-m scripts.split_cases` |
| `train-dispute` | `.\.venv\Scripts\python.exe -m scripts.train_dispute` |
| `eval` | `.\.venv\Scripts\python.exe -m eval.run_all` |
| `demo-reset` | `.\.venv\Scripts\python.exe -m scripts.seed_demo` |
| `test` | `.\.venv\Scripts\python.exe -m pytest -q` and `.\.venv\Scripts\python.exe -m ruff check .` |
| `secret-scan` | `.\.venv\Scripts\python.exe -m scripts.secret_scan` |
| `openapi` | `.\.venv\Scripts\python.exe -m scripts.export_openapi` |
| `static-data` | `.\.venv\Scripts\python.exe -m scripts.export_static` |

Known Windows quirks (the code is unchanged; these are limits of running it on Windows):

- Without `PYTHONUTF8=1`, six tests that read Bangla files fail with `UnicodeDecodeError`.
- `make rehearse` and `make static-data` finish their work and then stop with a `PermissionError` while
  deleting a temporary SQLite file (Windows keeps it open). See sections 7 and 9.
- Scripts that write text files write Windows line endings; `.gitattributes` makes Git store LF.

### After changing the database models

Tables are created with `create_all`, which does not migrate. Delete `data/safeorder.db` (it is not in
Git) and run `make data` again.

---

## 6. Environment variables

Variables are read from the process environment (`run_local.py` sets the right ones for a local run). `.env.example` lists `HF_TOKEN` and `SAFEORDER_CONFIG`
as a template, but **no `.env` file is loaded automatically** (the code has no dotenv loader): export the
variables in your shell or set them in the host's dashboard. Nothing is required to run the app locally.

### Backend and deployment

| Variable | Purpose | Default | Required |
|---|---|---|---|
| `SAFEORDER_CONFIG` | Path of the configuration file | `config/config.yaml` | no |
| `DATABASE_URL` | Database link. `postgres://` or `postgresql://` is accepted; empty means SQLite in `data/safeorder.db` | empty (SQLite) | **yes for a deployment that must keep accounts** (the live site uses a Neon link) |
| `SAFEORDER_PERSIST` | `1`: keep the database between restarts (accounts), load a small sample of synthetic sellers only when the database is empty, never wipe anything, switch `/api/demo/reset` off | off | yes for the live wallet |
| `SAFEORDER_PROTECT_ADMIN` | `1`: the analyst console, `/api/sim` and `/api/demo` need an admin account | off | yes for the live wallet |
| `SAFEORDER_ADMIN_PHONE`, `SAFEORDER_ADMIN_PIN` | Create or update the admin account on start (phone `01XXXXXXXXX`, 5-digit PIN). **Secrets: never published here.** | unset (no admin) | yes, to have an admin |
| `SAFEORDER_FULL_DEMO` | With `SAFEORDER_PERSIST=1`: load all 3,000 synthetic sellers and the seven demo scenarios (about 15 minutes on a free host) | off | no |
| `SAFEORDER_SERVE_FRONTEND` | `1`: the API also serves the built frontend (`frontend/dist`, or the committed `site/` when `frontend/dist` is not built) on the same address | off (the Dockerfile and `run_local.py` set `1`) | no |
| `SAFEORDER_AUTOSEED` | `1`: on start, reset the SQLite database and load the seven demo scenarios. Refuses to touch a non-SQLite database. Ignored when `SAFEORDER_PERSIST=1` | off (the Dockerfile sets `1`) | no |
| `SAFEORDER_AUTOSEED_BACKGROUND` | `1`: do the start-up work in a background thread so the port opens at once (Render needs this) | off | no |
| `SAFEORDER_TRUST_PROXY` | `1`: take the client address from `X-Forwarded-For` (only behind a proxy) | off (the Dockerfile sets `1`) | no |
| `SAFEORDER_RATE_LIMIT` | Requests per minute per client (0 switches the limit off) | `240` (from `config.yaml`) | no |
| `SAFEORDER_CORS_ORIGINS` | Comma-separated browser origins allowed to call the API | `http://localhost:5173` | yes for a website on another address (the live API allows `https://safeorder.stratifyxglobal.com`) |
| `SAFEORDER_DEMO_CODE` | A shared **secret** that protects `/api/demo` and `/api/sim` when `SAFEORDER_PROTECT_ADMIN` is off (header `X-Demo-Code`). **It is not published in this repository.** | unset (no code) | no |
| `PORT` | Port of the container's server | `7860` | no (Render sets it) |
| `RENDER` | Set by Render; the app uses it only to log a warning when it runs on a throw-away SQLite file | - | no |

### Frontend build (Vite)

| Variable | Purpose | Default |
|---|---|---|
| `VITE_USE_MOCK` | `true`: an in-browser mock server answers (no backend needed). `false`: the real API | `true` in `frontend/.env.example` |
| `VITE_API_BASE_URL` | Address of the API. Empty means the address the page was loaded from | `http://localhost:8000` |
| `VITE_STATIC` | `true`: static website build (hash routes, backend address read from `config.js`) | unset |
| `VITE_WALLET` | `true`: build the wallet app (home page, accounts, held payments). Unset builds the classic screens | unset (the Dockerfile and `npm run build:static` set `true`) |
| `VITE_DEMO_BUYER_ID` | Buyer used for new orders in the classic screens | `B-000001` |

### Scripts and tools

| Variable | Purpose |
|---|---|
| `HF_TOKEN` | Hugging Face token for `scripts/deploy_space.py` and `scripts/upload_hf.py` (read from the environment, never printed or written). Use a placeholder such as `<your-token>`; never commit it. |
| `KAGGLE_USERNAME`, `KAGGLE_KEY` | For the Kaggle CLI used by `make kaggle-models` and the explainer notebook (see RUNBOOK.md) |
| `PYTHONPATH` | The Makefile sets `backend:.` so the scripts find the `app`, `scripts` and `eval` packages (on Windows: `backend;.`) |
| `PYTHONUTF8` | Set to `1` on Windows (see section 5) |

---

## 7. Run and build commands

| What | Command | Address |
|---|---|---|
| API (development, reload) | `make api` (runs `uvicorn app.main:app --reload --port 8000` in `backend/`) | <http://localhost:8000>, interactive docs at `/docs`, health at `/health` |
| Frontend, classic screens, real API | `make web` (`VITE_USE_MOCK=false npm run dev`) | <http://localhost:5173> (run `make api` first) |
| Frontend, classic screens, mock mode | `make web-mock` (no backend needed) | <http://localhost:5173> |
| One command, everything | `python run_local.py` (Windows: `py run_local.py` or `run_local.bat`; Unix: `./run_local.sh`) | <http://localhost:8000> (the next free port if busy; `--port`, `--no-browser`, `--reset`) |
| Container (API + built frontend) | `docker build -t safeorder .` then the `docker run` line under "For judges" | <http://localhost:7860> |

On Windows, set the variable first instead of the Unix prefix (verified):

```powershell
# API (from the repository root; keep PYTHONUTF8 and PYTHONPATH from section 5 unset or set, both work here)
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000

# frontend, real API:   (second terminal)
cd frontend; $env:VITE_USE_MOCK = "false"; npm run dev
# frontend, mock mode (`npm run dev:mock` does not work in cmd/PowerShell because of its Unix syntax):
cd frontend; $env:VITE_USE_MOCK = "true"; npx vite
```

### The wallet app on your own computer

The classic screens above are the original demo. To run the **wallet app** (accounts, held payments, admin)
locally, start the API with the wallet settings and the frontend with `VITE_WALLET=true`
(verified on Windows with a separate SQLite file; register, sign in and the admin login all worked):

```bash
# terminal 1: API, with an admin account (choose your own PIN)
SAFEORDER_PERSIST=1 SAFEORDER_PROTECT_ADMIN=1 SAFEORDER_ADMIN_PHONE=01900000000 \
SAFEORDER_ADMIN_PIN=<5-digit-pin> make api

# terminal 2
cd frontend && VITE_WALLET=true VITE_USE_MOCK=false npm run dev     # http://localhost:5173
```

```powershell
# Windows: terminal 1
$env:SAFEORDER_PERSIST="1"; $env:SAFEORDER_PROTECT_ADMIN="1"; $env:SAFEORDER_ADMIN_PHONE="01900000000"; $env:SAFEORDER_ADMIN_PIN="<5-digit-pin>"
cd backend; ..\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
# Windows: terminal 2
cd frontend; $env:VITE_WALLET="true"; $env:VITE_USE_MOCK="false"; npm run dev
```

Open `http://localhost:5173/`, use the home page, then the **Guide** tile ("Create demo accounts").

### Static website

```bash
make static-site     # make static-data; cd frontend && npm run build:static; python -m scripts.zip_site
```

This builds the **wallet** website into `site/` and packs `site/` into `site.zip` (about 1.3 MB).
It needs a backend: set its address in `site/config.js` (section 8). To build the **classic in-browser**
variant (the trained models run in the browser, no backend), run the same build without `VITE_WALLET`
(verified: the seller search ran in the browser with no server):

```bash
cd frontend
VITE_STATIC=true VITE_USE_MOCK=false VITE_API_BASE_URL= npm run build -- --outDir ../site-classic --emptyOutDir
rm -f ../site-classic/mockServiceWorker.js
```

Windows PowerShell equivalent of `make static-site` (verified; the `npm run build:static` line itself uses
Unix syntax and fails in cmd and PowerShell):

```powershell
.\.venv\Scripts\python.exe -m scripts.export_static          # ends with a PermissionError on Windows; the files are already written
cd frontend
$env:VITE_WALLET="true"; $env:VITE_STATIC="true"; $env:VITE_USE_MOCK="false"; $env:VITE_API_BASE_URL=""
npx tsc -b; npx vite build --outDir ../site --emptyOutDir
Remove-Item ../site/mockServiceWorker.js -ErrorAction SilentlyContinue
cd ..; .\.venv\Scripts\python.exe -m scripts.zip_site
```

Serve `site/` with any web server (for example `python -m http.server` inside `site/`) or upload it to a
host (RUNBOOK.md has the cPanel steps). The site uses hash routes, so no rewrite rules are needed.

### Hugging Face Space (optional)

`HF_TOKEN=<your-token> python -m scripts.deploy_space --repo-id <your-user>/safeorder` uploads one
container (API and UI). `--dry-run` stages and scans the files without uploading (verified: "231 files
(6.1 MB) staged and scanned clean").

### Ports at a glance

`8000` API in development, `5173` Vite dev server, `7860` container (or `$PORT`).

---

## 8. Live deployment

**Live demo: <https://safeorder.stratifyxglobal.com/>**

```
 visitor's browser
   │  static website (HTML, CSS, JavaScript), on a cPanel host:  https://safeorder.stratifyxglobal.com/
   ▼
 API (Docker web service on Render, free plan):                   https://safeorder-api.onrender.com
   ▼
 PostgreSQL (Neon, free plan): accounts, orders, ledger, audit log   (kept between restarts)
```

- `GET https://safeorder-api.onrender.com/health` answers `{"status":"ok"}`.
- `GET https://safeorder-api.onrender.com/health/db` tells which kind of database the API uses
  (the link itself is never shown); `"keeps_data": true` means accounts survive restarts.
- The website finds the API through one line in `config.js` on the host:
  `window.SAFEORDER_API = 'https://safeorder-api.onrender.com'`. The file is loaded with a changing query
  string, so a host or CDN that caches script files cannot serve an old copy.
- The admin phone number and PIN are secrets and are **not published here** (see the judge quick start).

### The two modes of the website

| Mode | How it is built | What it needs |
|---|---|---|
| **Backend mode (wallet)**: the live site | `make static-site` (wallet build) and an API address in `config.js` | The API. Accounts, held payments, admin. |
| **In-browser mode (classic)** | The same build without `VITE_WALLET` (section 7), `config.js` left as `''` | No server: the trained models run in the browser and the state lives in the browser tab |

An earlier classic in-browser build, made before the wallet existed, is kept at
<https://safeorder.stratifyxglobal.com/old/>. `site.zip` holds only the website files for a web host; the
wallet build cannot run from it alone because it needs the API.

### Render free-tier wake-up delay

A free Render service sleeps after about 15 minutes without a request and needs up to a minute to wake
up (the classic screens show a "server is waking up" notice; in the wallet app a request sent during the
wake-up can fail or take about a minute, so wait a minute and retry). A free uptime monitor that calls
`/health` every 5 minutes keeps the live service awake (set up by the owner); **open the site a few
minutes before a demonstration**. Neon also suspends an idle database; waking it added about one second
in a test (0.4 s warm, 1.2 s after 6 idle minutes).

### Deploying your own copy

Render: **New + -> Blueprint** -> this repository (`render.yaml`). It asks for three secrets:
`DATABASE_URL` (a Postgres link, for example from Neon), `SAFEORDER_ADMIN_PHONE` and
`SAFEORDER_ADMIN_PIN`. The website is then uploaded to a sub-domain and `config.js` points to the
service. Step-by-step instructions, including cPanel, are in [RUNBOOK.md](RUNBOOK.md).

---

## 9. Testing and the 5-minute judge quick start

### Commands and what a pass looks like

Results below are from a **fresh clone on Windows 11** (Python 3.12.10, Node 24.21.0) with
`PYTHONUTF8=1`. Linux, macOS and Docker were not available to the author for this README.

| Command | A passing result | Verified result |
|---|---|---|
| `make test` | pytest ends with `N passed`, ruff with `All checks passed!` | **513 passed** in about 100 s; ruff: All checks passed |
| `make test-web` | typecheck prints nothing, Vitest `Test Files N passed`, lint has no errors, build `built in ...` | typecheck clean; **13 test files, 488 tests passed** (about 30 s); oxlint: 0 errors, 4 warnings; build ok |
| `make eval` | prints each section as `measured`; writes `reports/summary.json` and figures | trust, fairness, dispute classifier, routing: `measured`; injection: `measured_on_developer_phrases`; time study: `not_measured`; about 10 s |
| `make secret-scan` | `scanned N files, 0 possible secret(s)` and exit code 0 | 0 possible secrets |
| `make rehearse` | `run 1..3: scenarios 1-7 passed`, then `3 clean runs, identical results` | see the note below |
| `make openapi` | rewrites `docs/openapi.json`; a test fails when the file is stale | in sync |
| `python run_local.py` | `READY: open http://localhost:PORT`, then the site loads and the admin can sign in | ready in about 90 s on a first run (warm pip cache); the home page loaded from the API's own address, the login form appeared, the demo admin signed in, the analyst queue held the 3 demo disputes |

- **Retraining is reproducible.** Running `make train cases train-dispute eval` in the fresh clone gave
  every number in `reports/summary.json` back to within 3.3e-16 (only the timing numbers differ between
  machines).
- **`make rehearse` on Windows** runs the seven scenarios and then stops with a `PermissionError` while
  deleting a temporary SQLite file, so it exits with an error even though the scenarios ran. The same
  work with the clean-up switched off gave three runs, each reporting scenarios 1 to 7 passed and
  identical results. Use Linux, macOS or the container for the clean `3 clean runs, identical results`
  line (not run by the author).
- **Static site check.** `backend/tests/test_static_export.py` compares `site/` with `site.zip`. The
  repository's `.gitattributes` keeps LF line endings so the check also passes after a clone on Windows.

### Judge quick start (about 5 minutes)

Use the live site (<https://safeorder.stratifyxglobal.com/>; the first request after a quiet period can
take up to a minute, section 8) **or** your own copy with `python run_local.py`
(<http://localhost:8000>), where the demo admin is phone `01900000000`, PIN `12345`.

1. **Read.** Open <https://safeorder.stratifyxglobal.com/>. The home page explains the problem, the five
   steps, what is new, the technology, the safety measures, a FAQ and the limits. Use the menu at the top.
2. **Make two demo accounts.** Home page -> **Demo guide** button -> **Create demo accounts**. One click creates a
   buyer and a seller (PIN `12345`, the numbers are shown) and signs you in as the buyer. A real
   sign-up works too (**Get started**): any made-up phone number `01XXXXXXXXX` and 5-digit PIN.
3. **Trust Check.** Home -> **Check Seller**, search `Synthetic Shop 0001`: **HIGH_RISK** (score 3) with
   reasons. `Synthetic Shop 0002`: **TRUSTED** (95). `Synthetic Shop 0037`: **LIMITED_HISTORY** (a new honest
   seller, no score shown).
4. **Place an order.** Home -> **Make Payment**: type the demo seller's number, press **Check** (you see
   the trust check), enter an amount, an optional order number and the PIN. The money is **held**; the
   receipt shows the order number (for example `O-0012`).
5. **Seller takes the order.** More -> *Switch to Demo Seller* (or use a second browser tab) -> **Seller** ->
   type the order number -> **Take the order**. The seller could not see the number before this.
6. **Happy path.** Switch back to the buyer, open the order (History -> Orders) -> **I received it**. The
   held money moves to the seller (compare *Account* on both sides).
7. **Dispute path.** Make a second payment, take the order as the seller, then as the buyer press
   **Report a problem** and write a sentence such as "The parcel never arrived and nobody answers my
   calls." The **AI analysis runs at once**; the seller can answer on the same order page. The money
   stays held.
8. **Analyst decision (admin).** Sign in as the admin, then More -> **Admin panel** -> *Dispute console*.
   On a local copy the admin is `01900000000` / `12345`. **The hosted site's admin login is private to the
   owner and is not published here (TODO for the owner: give the judges that phone and PIN privately).**
   Open the case: timeline, flags, class probabilities,
   route, template explanation in Bangla and English. Choose a decision, write the required note,
   confirm. The case page then shows the seller's **score before and after**.
9. **Time rules.** Admin panel -> **Time** -> `+24` or `+72` hours: an order nobody took is refunded, and
   a clean seller proof is released after 72 hours of buyer silence.
10. **Metrics.** Home page -> **Evaluation results** button (`/#/metrics`): the numbers exactly as the scripts wrote them.

The seven classic demo scenarios (section 2) are loaded by `python run_local.py` (it sets
`SAFEORDER_FULL_DEMO=1`, so the analyst console already holds their disputes) or by `make demo-reset`; the
classic controls are at `/demo`.

---

## 10. Other configuration

### `config/config.yaml`

Every threshold and path lives here, not in the code. Starting values for the demo; none of them is a
claim about any company's policy.

| Setting | Value | Meaning |
|---|---|---|
| `rules.hold_period_hours` | 72 | Hold after delivery (classic orders) |
| `rules.seller_response_deadline_hours` | 48 | Time the seller has to answer a dispute |
| `rules.dispatch_deadline_hours` | 72 | A classic order the seller never dispatches becomes disputable |
| `rules.seller_claim_deadline_hours` | 24 | Wallet payment: the seller must enter the order number, or the money goes back |
| `rules.buyer_silence_hours` | 72 | Wallet payment: a clean seller proof releases the money after this silence |
| `rules.trust.trusted_min`, `caution_min` | 70, 40 | Score bands: TRUSTED 70-100, CAUTION 40-69, HIGH_RISK 0-39 |
| `rules.trust.limited_history_max_age_days`, `..._min_orders` | 14, 10 | A younger or thinner account gets LIMITED_HISTORY instead of a low score |
| `rules.trust.limited_history_override_max_score` | 20 | ...unless the model score is at or below this (strong evidence of risk) |
| `rules.routing.min_class_probability` | 0.80 | Below this a case goes to a human |
| `rules.routing.high_amount_bdt` | 5000 | At or above this a case always goes to a human |
| `rules.routing.repeat_claimant_count` / `_window_days` | 3 / 90 | The repeat-claimant flag |
| `api.max_amount_bdt` | 200000 | Largest payment |
| `api.max_body_bytes` | 65536 | Larger request bodies get 413 (the proof upload has its own 600,000 byte limit) |
| `api.rate_limit_per_minute` | 240 | Per client address; 0 switches it off |
| `wallet.signup_bonus_bdt` | 2000 | Demo money of a new account |
| `wallet.add_money_max_bdt`, `add_money_total_cap_bdt` | 5000, 20000 | Limits of "Add Money" per request and per account |
| `wallet.max_pin_attempts`, `lock_minutes` | 5, 15 | PIN lockout |
| `wallet.sample_sellers_per_archetype` | 12 | A new persistent database gets 72 synthetic sellers (12 of each of 6 kinds) |
| `paths.database` | `data/safeorder.db` | The SQLite file (not in Git) |

### `config.js` (the website's backend address)

`site/config.js` holds one line, `window.SAFEORDER_API = ''`. Empty means "no backend" (in-browser mode
for a classic build; the wallet build then shows "the server is not set up"). Set it to the API address,
without a trailing slash, on the host and reload; no rebuild is needed.

### The hidden `/demo` route and the demo code

The classic screens include a sandbox control page at `/demo` (`/#/demo` on the static site): courier
events, moving the simulated clock, resetting the data and loading the seven scenarios. It is not in the
menu. When the API is started with `SAFEORDER_DEMO_CODE`, the `/api/demo` and `/api/sim` calls need that
code in the `X-Demo-Code` header (the page has a field for it). **The demo code is a secret and is not
published in this repository.** On a persistent, admin-protected server (the live site) the reset is
switched off and `/api/sim` needs an admin sign-in instead; the admin panel's **Time** tab replaces the
clock controls.

### Data location and access

- SQLite file: `data/safeorder.db`, created by `make data`; generated data in `data/synthetic/v1/`;
  dispute cases in `raw/` (source) and `data/cases/` (the split).
- The live site's data is in Neon (PostgreSQL), reachable only through the API.
- Anyone can open an account on the live site; each person sees only their own orders. The admin
  account and the Neon, Render and host credentials are private to the owner.

---

## 11. Evaluation results and limits

Every number below is read from [`reports/summary.json`](reports/summary.json) (written by `make eval`
from the trained models and the held-out test data) and rounded. The same numbers are on the live
site's metrics page.

> **All data is synthetic.** The seller data comes from our own generator and the dispute cases were
> **written by an AI assistant and have not been reviewed by a person**. These results show that the
> pipeline works and how it behaves on data we made ourselves. They say nothing about how it would
> perform on real sellers or real disputes.

### Trust model (synthetic test set "v2": 3,000 sellers made by a shifted generator, never used in training)

| Measure | Trust model | Account-age-only baseline |
|---|---|---|
| PR-AUC (label with about 4% noise) | **0.898** | 0.585 |
| ROC-AUC (noisy label) | **0.929** | 0.803 |
| Share of risky sellers caught at about a 5% false-alarm target (noisy label) | **87.9%** (actual false-alarm rate 3.4%) | 35.3% |
| Calibration error (ECE) / Brier score | 0.030 / 0.044 | - |
| PR-AUC on the clean label (easy, shown for completeness) | 0.9965 | 0.613 |
| Time per score (p95; budget 50 ms) | 0.54 ms | - |

**Fairness for new honest sellers** (same test data, three policies): the policy in use
(`override_default`) catches **97.7%** of high-risk sellers with a precision of **98.7%** in the
HIGH_RISK band, flags **1.0%** of honest new sellers as risky, and puts **38.8%** of honest new sellers
in the neutral LIMITED_HISTORY band instead of a low score. The literal blueprint rule (no override)
caught only 54.3% of high-risk sellers and 0% of the fast "fake burst" sellers, which is why the override
exists.

### Dispute classifier (TF-IDF + logistic regression, four classes)

Trained on 383 cases, calibrated on 89. "Wrong refund" = a true false claim for which a refund would be
suggested; "wrong rejection" = a true seller-fault or courier case for which a rejection would be suggested.

| Split | Cases | Accuracy | Macro-F1 | Calibration error | Wrong refunds | Wrong rejections |
|---|---|---|---|---|---|---|
| Test 1 (batch `ai_b`) | 310 | 77.7% | 0.779 | 0.090 | 5.3% (4) | 3.8% (6) |
| Test 2 (batch `ai_c`) | 244 | 70.1% | 0.696 | 0.062 | 8.5% (5) | 11.1% (14) |
| Validation (also used to calibrate: **not an honest test**) | 89 | 77.5% | 0.777 | 0.103 | 13.0% (3) | 13.0% (6) |

All splits were written by the same author. Test 1 holds 132 distinct stories and Test 2 only 28, so Test 2 is a weak test. Prediction time p95
5.3 ms (budget 100 ms).

### Routing through the whole analyzer

| Test split | Fast lane (one-click confirmation) | Accuracy inside the fast lane | Wrong refunds in the fast lane | Sent to a human |
|---|---|---|---|---|
| Test 1 | 17.4% of cases | 96.3% | 0 | 82.6% |
| Test 2 | 14.8% of cases | 86.1% | 0 | 85.2% |

### Injection screen: a first filter, not a guarantee

- On 22 injection phrases and 9 harmless phrases written by the developers, the screen found **22 of
  22** with **0 of 9** false alarms. **That is not an independent result**: its patterns were written
  while looking at those phrases.
- On 12 phrases written afterwards and never used to change the screen it found **1 of 12 (8.3%)**.
- On 24 AI-written cases with an injected sentence, the screen itself caught 8 (33%); 20 of 24 were
  still forced to human review through other flags, 16 got past the screen, and for 4 the suggested
  outcome changed compared with the same case without the sentence.
- The real protection is structural: no free text can change a label, a route or a ledger entry, and no
  generative model is in the decision path. A held-out injection test set is **not measured**.

### Not measured

The analyst time study (`time_study`) is `not_measured`: no timed analyst sessions exist yet.

### Honest status

- All data is synthetic. **The dispute cases were written by an AI assistant, not by ChatGPT,
  Gemini or the team, and no person has reviewed them** (`raw/PROVENANCE.md`). The classifier's
  scores therefore show that the pipeline works, not how it would do on real disputes.
- Not done: the optional transformer classifier (Step 13), the team's own test cases, the 10%
  manual case review, the analyst time study, native-speaker review of the Bangla text, a real wallet,
  SMS one-time codes and courier integration, and field interviews (a draft consent note exists in
  `docs/drafts/`; no interview results are in this repository).
- The repository has no licence file yet, so all rights are reserved by default (`docs/licence_register.md`
  lists the open licence and terms-of-use questions).

---

## 12. Pre-existing components and disclosures

**Libraries (all open source, installed from PyPI and npm):** the Python and JavaScript packages listed in
section 3, with their licences read from the installed metadata in
[`docs/licence_register.md`](docs/licence_register.md) (MIT, BSD, Apache-2.0 and similar).
three.js draws the 3D background of the app; the browser loads the **Noto Sans Bengali** font from Google
Fonts (its licence is marked "to confirm" in the register).

**Pre-trained or third-party models:** none. Both models are trained from scratch in this repository
(`scripts/train_trust.py`, `scripts/train_dispute.py`) on data made here.

**Datasets:** no third-party dataset is used (`data/public/` is empty). The seller data is generated by
`scripts/generate_sellers.py` from fixed seeds in `config/config.yaml`; the dispute cases in `raw/`
were written by an AI assistant (provenance in [`raw/PROVENANCE.md`](raw/PROVENANCE.md)). Nothing in
the data is real.

**External services:** Render (API), Neon (database), a cPanel host (website), optionally Hugging Face
and Kaggle. No external API is called in any decision path.

**Kaggle copies of the models:** the explainer notebook
<https://www.kaggle.com/code/bmr07sakaria/safeorder-trust-model-explainer> and the dataset
<https://www.kaggle.com/datasets/bmr07sakaria/safeorder-trust-bundle> (the trained models and the
evaluation reports; no raw cases or synthetic data). RUNBOOK.md records that both were made public for
the judges.

### Use of AI tools

An AI coding assistant (Claude, by Anthropic) was used while building this project: it helped write
parts of the code, the tests and the documents, and it wrote the synthetic dispute cases (see
`raw/PROVENANCE.md`). This is a disclosure of a tool, not an author: the project and its content
belong to its owner, who is responsible for them. Not everything the assistant wrote has been
reviewed by a person yet (see "Honest status" above).

AI is kept out of every decision about money. The machine-learning models and the evidence analyzer
only **suggest**; rules in `rules.py` and `config/config.yaml` decide, and a human admin decides every
dispute. Evidence text is treated as untrusted data and is never followed as an instruction. All data
is synthetic or entered by testers in a sandbox with demo money, and no real personal data is used.

### Development history

The full history is in the Git log (`git log --reverse`); every commit is dated between **1 October
and 3 October 2026**. The problem was published on Thursday, 1 October 2026 at 9:01 AM and the
submission deadline is 4 October 2026 at 10:00 AM; the work in this repository was done in that window.

---

## 13. Repository layout and documentation index

```
backend/app/        FastAPI app: api/ (routes), trust/ (model, features, reasons), disputes/ (classifier,
                    injection screen), analyzer/ (timeline, checks, router, explanations), rules.py,
                    state_machine.py, ledger.py, wallet.py, payments.py, proof.py, auth.py, accounts.py
backend/tests/      pytest tests (513 in a fresh clone)
frontend/           React + TypeScript app: src/wallet/ (wallet app and home page), src/pages/ (classic
                    screens), src/engine/ (the models ported to TypeScript for in-browser mode), src/test/
config/config.yaml  every threshold and path
data/               generated data (synthetic, not committed), data/cases/ (dispute case split)
raw/                the dispute case files and PROVENANCE.md
models/             the trained models (committed)
reports/            evaluation output: summary.json and figures
eval/               evaluation code        scripts/   data generation, training, build and deploy scripts
docs/               model cards, dataset cards, protocol, responsible-AI note, pitch material
deploy/space/       the Hugging Face Space card        kaggle/notebook/   the Kaggle explainer notebook
site/, site.zip     the built static website           Dockerfile, render.yaml   container and Render blueprint
run_local.py        one-command local run (also run_local.sh, run_local.bat)
```

| Document | File |
|---|---|
| Full specification and build plan | [BLUEPRINT.md](BLUEPRINT.md) |
| Working rules for the AI assistant | [WORKING_RULES.md](WORKING_RULES.md) |
| Decisions, measurements and caveats | [DECISIONS.md](DECISIONS.md) |
| Operating notes (deploy, cPanel, Render, Hugging Face, Kaggle) | [RUNBOOK.md](RUNBOOK.md) |
| Documentation index | [docs/README.md](docs/README.md) |
| Model card, trust model | [docs/model_card_trust.md](docs/model_card_trust.md) |
| Model card, dispute classifier | [docs/model_card_dispute_classifier.md](docs/model_card_dispute_classifier.md) |
| Dataset card, synthetic sellers | [docs/dataset_card_synthetic_sellers.md](docs/dataset_card_synthetic_sellers.md) |
| Dataset card, dispute cases | [docs/dataset_card_dispute_cases.md](docs/dataset_card_dispute_cases.md) |
| Synthetic data assumptions | [docs/synthetic_assumptions.md](docs/synthetic_assumptions.md) |
| Evaluation protocol | [docs/evaluation_protocol.md](docs/evaluation_protocol.md) |
| Responsible AI note | [docs/responsible_ai.md](docs/responsible_ai.md) |
| Licence register | [docs/licence_register.md](docs/licence_register.md) |
| API contract | [docs/openapi.json](docs/openapi.json) |
| Pitch outline, demo script, judge questions | [docs/pitch/](docs/pitch/) |
| Human-document drafts (team agreement, logic chain, consent note, terms, regulatory note) | [docs/drafts/](docs/drafts/) |
| Case provenance | [raw/PROVENANCE.md](raw/PROVENANCE.md) |
