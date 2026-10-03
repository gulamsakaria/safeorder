# SafeOrder

AI-assisted seller trust, held payments and dispute resolution for Facebook-commerce.
Prototype for AI Dev Fest 2026 (AI Hackathon). Everything runs on **synthetic data inside a
simulated (sandbox) wallet**. No real money, no real customer data, not a product of upay.

Full specification: [BLUEPRINT.md](BLUEPRINT.md). Working rules: [WORKING_RULES.md](WORKING_RULES.md).
Decisions, measurements and caveats: [DECISIONS.md](DECISIONS.md). Runbook: [RUNBOOK.md](RUNBOOK.md).
Model cards, dataset cards, evaluation protocol: [docs/](docs/README.md).

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

**B. With Docker** (no Python needed): `docker build -t safeorder .` and then

```bash
docker run --rm -p 7860:7860 -e SAFEORDER_PERSIST=1 -e SAFEORDER_ADMIN_PHONE=01900000000 \
  -e SAFEORDER_ADMIN_PIN=12345 -e SAFEORDER_PROTECT_ADMIN=1 safeorder
```

then open `http://localhost:7860`.

**C. Hosted copy:** https://safeorder.stratifyxglobal.com (the website) calls an API on a free
Render server. If nothing loads at once, wait one minute and reload: free servers sleep when idle.
(If it is down, use A or B.)

**What to try (3 minutes):** open the "Guide" tile, make a demo buyer and a demo seller, send money
to the seller's payment number (you see the seller's name and Trust Check first), watch the money
become "held", then confirm the delivery or report a problem and decide it as the admin.
`site.zip` is only the website files for a web host; it cannot run alone because the wallet needs the server.

## What it does

1. **Trust Check** before paying: a score, a band and plain Bangla/English reasons (LightGBM, calibrated).
2. **Safe Order**: the money is held (simulated) until the buyer confirms with a delivery code.
3. **Evidence analyzer** for disputes: timeline, consistency flags, a four-class text classifier,
   a prompt-injection screen and a router. It only *suggests*; a human analyst decides every dispute.
4. **Metrics page** (`/metrics`) showing the evaluation numbers exactly as the scripts wrote them.

The website is a sandbox wallet with accounts, held payments and an admin area (RUNBOOK.md,
"Accounts, wallet and the live website"). The interface has a dark animated 3D look (see RUNBOOK.md, "Look and feel").

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

## Honest status

- All data is synthetic. **The dispute cases were written by an AI assistant, not by ChatGPT,
  Gemini or the team, and no person has reviewed them** (`raw/PROVENANCE.md`). The classifier's
  scores therefore show that the pipeline works, not how it would do on real disputes.
- Not done: the optional transformer classifier (Step 13), the team's own test cases, the 10%
  manual case review, the analyst time study, native-speaker review of the Bangla text.

## Use of AI tools

An AI coding assistant (Claude, by Anthropic) was used while building this project: it helped write
parts of the code, the tests and the documents, and it wrote the synthetic dispute cases (see
`raw/PROVENANCE.md`). This is a disclosure of a tool, not an author: the project and its content
belong to its owner, who is responsible for them. Not everything the assistant wrote has been
reviewed by a person yet (see "Honest status" above).

AI is kept out of every decision about money. The machine-learning models and the evidence analyzer
only **suggest**; rules in `rules.py` and `config/config.yaml` decide, and a human admin decides every
dispute. Evidence text is treated as untrusted data and is never followed as an instruction. All data
is synthetic or entered by testers in a sandbox with demo money, and no real personal data is used.

## Layout

See BLUEPRINT.md Section 4. All thresholds live in `config/config.yaml`.
