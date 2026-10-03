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
