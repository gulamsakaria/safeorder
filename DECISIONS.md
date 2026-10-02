# Decisions log

Every deviation from BLUEPRINT.md and every fallback is recorded here.

## Step 0

- Added `httpx` to `requirements.txt`. The blueprint list does not include it, but FastAPI's
  `TestClient` needs it for the API tests.
- Added `app/config.py`, a small YAML loader, so code reads thresholds from
  `config/config.yaml` instead of hard-coding them.
- Frontend uses Tailwind v4 through the `@tailwindcss/vite` plugin (no `tailwind.config.js`).
  The Vite template's linter is `oxlint`.
- `dispatch_deadline_hours: 72` in `config.yaml` is an assumption. Blueprint Section 6.1 says
  "seller never dispatches before deadline" without a number. Change it freely.
- Work is committed directly to `main`, as agreed with the team.

## Step 1

- Money is stored as whole BDT integers (`amount_bdt`, ledger `debit`/`credit`, daily stats) so
  the ledger balance check in Step 2 has no float rounding.
- All datetimes are timezone-aware UTC (this SQLModel version requires it). API output uses
  `to_iso()` ("...Z").
- Main entities use string ids (`S-0001`, `O-0001`, `D-0001`, via `next_id`); append-only log
  tables (ledger, audit, evidence, snapshots, ...) use integer ids.
- `DisputeStatus` values are not specified in the blueprint; chosen: OPEN, SELLER_RESPONDED,
  ANALYZED, RESOLVED, ESCALATED.
- The simulated clock is in memory (one process). `reset_db` also rewinds it. A fixed start can
  be set for deterministic tests (`SimClock(start=...)`).
- No ORM relationships are declared (foreign keys only, enforced with `PRAGMA foreign_keys=ON`),
  so code must commit or flush a parent row before inserting its children.
- `audit_log` is append-only through SQLite triggers (UPDATE and DELETE are rejected).
  `analyst_decision.note` must be non-empty (check constraint).
- Seed wallet numbers use a `SIM-W-` prefix so they cannot look like real phone numbers.

## Step 2

- Ledger convention: a transfer debits the source account and credits the destination, so
  debits equal credits per order. Balance = credits - debits. Refunds move HOLD -> BUYER_WALLET
  as in Section 6.1; the `REFUND` account value exists in the schema but is not used.
- Assumption: an `ESCALATED` order can still be resolved by an analyst (`ANALYST_REFUND` or
  `ANALYST_REJECT`). The blueprint table has no way out of `ESCALATED`, which would leave the
  held funds stuck. Change it if upay-style policy says otherwise.
- `APPEAL` is allowed only from `DISPUTED` (as in the table). An appeal after a final
  decision is not modelled yet; Step 8 can decide how to handle it.
- The order has no "delivery code used" column, so the proof is kept in the audit log
  (`DELIVERY_CODE_CONFIRMED`). The analyzer (Step 7) reads it from there.
- Courier events only change the order while it is `HELD`: `delivered` -> `DELIVERED`,
  `lost` -> `DISPUTABLE`. In other states the event is just recorded.
- `released_at` is set to the time the release was processed. After a clock fast-forward this
  can be later than `hold_until`.
- `rules.py` holds fairness and band logic; dispute routing (Section 6.2) is added with the router
  in Step 7. Functions flush but never commit; callers own the transaction.

## Step 3

- Generator output per version (`data/synthetic/v1|v2/`, not committed): `sellers.csv`,
  `buyers.csv`, `orders.csv`, `seller_daily_stats.csv` and a `manifest.json` with row counts and
  SHA-256 hashes. The same seed reproduces identical hashes (checked on the full 3,000-seller run).
- `orders.csv` has a `cashout_latency_min` column that the database `orders` table does not have.
  The trust feature `median_cashout_latency_min` (Step 4) needs it. Only sellers, buyers and
  daily stats are loaded into the demo database (`--load-db`); orders stay in CSV files.
  **Open point for Step 4:** live Trust Check for database sellers needs precomputed features
  (a `seller_features` table or file built from the CSVs), because the orders are not in the DB.
- `repeat_buyer_ratio` in the config is the target share of a seller's buyers with 2+ orders.
  A first version controlled the share of orders instead and gave 17% for established sellers
  (blueprint: 25-60%); it now gives about 36%. Realised values are in `docs/synthetic_assumptions.md`.
- Stats window: 60-90 days, capped by account age. The average is below 60 because young
  accounts (honest_new, fake_burst) have only a few days of history.
- Collusive rings: 3-6 sellers share a pool of 6-14 buyer accounts (`ring_id`, hidden ground
  truth). "Circular flows" are not modelled beyond the shared buyer pool.
- Overlaps added so the task is not trivially separable: 12% of honest_new sellers cash out
  fast, 20% of fake_burst and slow_scammer sellers are "mild" (smaller bursts or spikes).
- The festival spike (10-17 Sep 2026), weekday factors and hourly profile are invented.
- Label noise flips `is_high_risk` for about 4% of sellers at random (hidden `label_noised`).
- v2 = shifted archetype parameters (about +/-20%, listed in `generator.v2.scale`) and a different
  archetype mix.
- Run the generator from the repository root with `make data` (it sets `PYTHONPATH=backend:.`).

## Step 4

- **Conflict in the blueprint, resolved with a configurable override.** Section 6.2 hides every
  account younger than 14 days behind the neutral LIMITED_HISTORY band, but Section 12.2
  (demo 1) wants a new fake seller shown as HIGH_RISK. In the generated data every
  `fake_burst` seller is younger than 14 days, so the literal rule hides all of them
  (`reports/trust_eval.json`, policy `blueprint_literal`: fake_burst recall 0). New config value
  `rules.trust.limited_history_override_max_score` (default 20): a limited-history seller whose model
  score is at or below it is still shown as HIGH_RISK. Set it to `null` for the literal
  blueprint rule. The value 20 was fixed before looking at v2 results. **Needs a human decision
  before the pitch.** The report compares three policies (no limited-history band, literal,
  override).
- A limited-history seller's score is hidden in the API (`score: null`, `limited_history: true`)
  but still stored as `model_score` for trust snapshots and audit.
- Splits of generator v1: 60% train, 20% validation (early stopping), 20% calibration.
  Generator v2 is only used for the test numbers; nothing is tuned on it.
- Calibration is Platt scaling, not isotonic: 600 calibration rows is below the size where
  isotonic is stable.
- Metrics are reported against two labels: the dataset label `is_high_risk` (about 4% flipped
  at random, the realistic one) and the clean archetype label. The clean label is much easier and is
  a diagnostic only. Baselines: the binary rule "age under 14 days" and a continuous
  "younger is riskier" score.
- A new table `seller_features` holds precomputed features so the live Trust Check can run
  from the database; `make data --load-db` fills it. `refund_count` and `dispute_count` are stored so
  the feedback loop (Step 10) can update rates after a decision without the order history.
- `buyer_burst_ratio` follows the blueprint literally: buyers in the last 24 hours divided by the
  seller's own 30-day daily average (which includes that last day), floored at 1.
- `shared_buyer_overlap` is 0 for sellers with fewer than 5 distinct buyers
  (`trust_model.overlap_min_buyers`): a share over one or two buyers is noise.
- Reasons: 2-4 per response (in practice 4, because the minimum contribution is small).
  "High"/"low" wording compares a value with the training median. Wording is template-based
  in `i18n/reasons_en.json` and `reasons_bn.json`. **The Bangla text was drafted by the
  assistant and must be reviewed by a native speaker.** Fewer than 1% of reasons fall back to
  the generic sentence.
- SHAP plots are P1 and not built. The model card is part of Step 14.
- The trained model (`models/trust_v1.joblib`, about 200 KB) and its metadata are committed so a
  fresh clone can run the API without training. `make train` rebuilds them.

## Step 7 (done before Steps 5 and 6, see below)

- **Order change:** Step 7 was built before Steps 5 and 6 because the dispute cases (ChatGPT /
  Gemini output) are not available yet. Everything that does not need a trained classifier is
  done: injection screen, consistency checks, timeline, router, explanation templates and the
  `analyze` pipeline. Steps 5 and 6 are still open.
- **No stand-in classifier.** `app/disputes/classifier.py` only defines the interface
  (`predict_proba(text) -> 4 probabilities`, `version`). `load_classifier()` raises
  `ClassifierNotAvailable` until Step 6 trains the real model, so no screen can show invented
  probabilities. Tests use a `FixedClassifier` test double with fixed numbers.
- `app/disputes/text_format.py` (a Step 6 file) was written now because the analyzer builds the
  classifier input with it.
- **Database additions** on `dispute`: `claim_type` (optional, chosen on the buyer form),
  `seller_response_text`, `seller_responded_at`. Step 8 stores them; Step 9's form should send
  `claim_type`. If it is missing, a keyword fallback (English, Bangla, Banglish) detects a
  "not received" claim. It is a heuristic and misses unusual wording.
- **Injection screen.** Instruction-like sentences are removed before the classifier and the
  consistency checks see the text, then the case is forced to human review (`injection_detected`,
  flag `INJECTION_DETECTED`, route reason `INJECTION_DETECTED`). Only pattern codes are stored,
  never the injected text. It is a screen, not a guarantee: obfuscated wording can slip through, and
  an ordinary sentence can be caught by mistake (that only costs a human review). Complaints such as
  "the seller did not approve my return" are deliberately not flagged. The structural protection
  is that no free text can change a label, a route or a ledger entry.
- **Judgement calls in the consistency rules** (the blueprint gives names, not definitions), all
  configurable in `analyzer`:
  - `NO_COURIER_PROOF`: no dispatch record from the courier and no proof word (tracking, receipt,
    memo, ...) in the seller's text. This also fires for real seller-fault cases (never
    dispatched), so those always go to a human. The fast lane is therefore narrow by design.
  - `EVIDENCE_EMPTY_OR_VAGUE`: fewer than 15 characters or 3 words. The seller side is checked only
    after the seller has responded.
  - `AMOUNT_MISMATCH`: flagged when amounts are written next to a currency word or sign and none
    equals the order amount (1% tolerance). A text that mentions only the delivery charge is flagged.
  - `LATE_REPORT`: filed more than 48 hours after delivery (assumption).
  - `REPEAT_CLAIMANT` is covered by the `FLAGS_PRESENT` route reason, as in the blueprint example.
- Route reasons come in a fixed order: insufficient-evidence class, flags, injection, low
  confidence, high amount. A low-confidence case still gets the recommendation of its top class;
  the route sends it to a human.
- The response has one extra field, `explanation_sections` (what happened / why it is risky /
  what upay should do next, per language). **The Bangla templates were drafted by the assistant
  and need review by a native speaker.**
- **Bug found and fixed in Step 2 code:** audit-log rows ignored the `now` passed to an event and
  used the clock instead, so the delivery-code confirmation could land in the wrong place on the
  timeline. Audit rows now carry the event's own time (regression test added).

## Step 8

- **All 16 endpoints of Section 7 exist**, plus two additions: `GET /api/sellers/search?q=`
  (the Trust Check screen needs search by name or wallet) and
  `POST /api/disputes/{id}/buyer-evidence` (without it a "request more evidence" decision would
  give the buyer no way to answer). Other additive fields: optional `claim_type` on
  `POST /api/disputes`; `requires_extra_confirmation` on the Trust Check response;
  `explanation_sections` on the analyzer response; `ledger`, `timeline`, `can_report_problem` and
  `server_time` on orders. An appeal endpoint is not in the contract and is not built (P1).
- Errors always look like `{"error": {"code", "message"}}`, including 404, 405, 422 and 500.
- The sandbox **delivery code** is returned once, in the response that creates the order. It is
  derived from the project seed so demo runs repeat exactly. It is not a security feature; a real
  system would hand the code to the recipient and the courier, not return it from an API.
- **Feedback loop (backend part of Step 10):** after a `REFUND_BUYER` or `REJECT_CLAIM` decision the
  seller's counters are updated (`orders_total` +1; a refund also adds one refund and one dispute),
  the rates are recomputed and a `DISPUTE_RESOLVED` snapshot is stored. The response carries
  `trust.before` and `trust.after`. A rejected claim does not count against the seller. Buyer
  counters are derived from the `dispute` table, not stored. Other features (orders in the last 7
  days, buyers in the last 24 hours, account age) are not refreshed. If the model or the features
  are missing, the decision still goes through and `trust` is null.
- **Model change found by an API test:** one extra refund and dispute *raised* the score for 25.6%
  of sellers on v2 (769 of 3,000 in the first measurement, up to +11 points; the retrained twin in the Kaggle notebook gives 760), so a seller-fault decision could make a seller look safer.
  Fix: LightGBM monotone constraints on `refund_rate` and `dispute_rate`
  (`trust_model.monotone_increasing_risk`). Measured before the change: PR-AUC 0.896 and
  recall at 5% false positives 0.879, honest-new false positives 1.3%; after: 0.898, 0.879 and 1.0%,
  and no seller's score rises (769 -> 0). A single dispute among about 95 orders still moves the
  score by under a point on average, so demo 3 should use a seller with few orders (Step 11).
  The model, `reports/trust_eval.json` and the numbers in this log were regenerated.
- Decision endpoint: `REQUEST_MORE_EVIDENCE` reopens the dispute with a new 48-hour window;
  `ESCALATE` moves it to the escalated queue (a later `REFUND_BUYER` or `REJECT_CLAIM` is allowed);
  a resolved dispute cannot be decided again. `followed_suggestion` is true when the decision
  matches the recommendation (a courier-issue suggestion is matched by a refund) and null without
  an analysis or on escalation. The audit log records the analyst id and the outcome.
- Queue order: human-review cases first, then not-yet-analysed, then fast lane; larger amounts
  first; oldest first. Filters: `route` (including `NOT_ANALYZED`), `status`, `min_amount_bdt`.
- The seller can respond only while the dispute is open and before the deadline
  (`409 DEADLINE_PASSED`). There is **no authentication**: `analyst_id` is free text. This is a
  sandbox; real roles and sign-in belong to the production path.
- Request texts are length-limited from `api.*` in the config. They are stored as received and
  escaped only where they are rendered (the React UI).
- `GET /api/metrics/summary` passes the report files through untouched; before Step 12 there is no
  `summary.json`, so `available` is false and the individual reports are listed under `reports`.
- The database is created with `create_all`, which does not migrate. After a model change run
  `make data` or `POST /api/demo/reset` to rebuild it.
- `docs/openapi.json` is generated by `make openapi`; a test fails if it is out of date.

## Kaggle explainer notebook (for the judges)

- `scripts/build_kaggle.py` builds a **private** Kaggle dataset `bmr07sakaria/safeorder-trust-bundle`
  (one zip: project code, config, trained model, evaluation report, synthetic sellers and
  features for v1 and v2; about 0.5 MB) and the notebook `kaggle/notebook/safeorder-trust-model-explainer.ipynb`
  with `kernel-metadata.json` (private, internet on only so it can `pip install sqlmodel` if missing).
  Re-publish with `make kaggle` (builds the files) and then `kaggle datasets version` /
  `kaggle kernels push` (see RUNBOOK.md).
- Every number in the notebook is computed live from the bundle and cross-checked against
  `reports/trust_eval.json` (it prints `matches the project's stored evaluation report: True`).
  It ran without errors both locally and on Kaggle's servers.
- The notebook shows: held-out v2 results against the age rule, calibration (including the weak
  middle of the curve and how few sellers sit there), the three LIMITED_HISTORY policies, live Trust
  Checks with Bangla and English reasons, the monotone-constraint comparison against an unconstrained
  twin, and the with/without-injection analyzer pair. The analyzer cell uses a clearly labelled
  **stand-in classifier** (fixed numbers), because the trained dispute classifier does not exist yet.
- **Bug found by running it on Kaggle:** `train_model` used the new LightGBM argument names
  (`eval_X`/`eval_y`), which Kaggle's older LightGBM does not know. It now picks the right form for
  the installed version (`eval_kwargs`, with a test). The trained model is unchanged.
- The retrained unconstrained twin in the notebook shows 760 sellers whose score rises after one
  extra refund and dispute (769 in the first measurement); both are about a quarter of the sellers.

## Step 9

- **Contract change:** added `GET /api/disputes/{id}` (claim, evidence, deadline, status; no analysis
  or analyst notes). The seller screen needs the claim and the response deadline, and using the
  analyst endpoint would have exposed the analysis. The OpenAPI file now declares the real error
  format (`ErrorOut`) for 400/404/409/422/503; before, it advertised the framework's default 422 body.
- **TypeScript 5.9** instead of the template's 6.x, because `openapi-typescript` still needs
  TypeScript 5 as a peer dependency. The alternative was forcing the install past the warning.
- **Generated client:** `frontend/src/api/schema.ts` comes from `docs/openapi.json`
  (`make gen-api`) and is committed. Screens call the API through `openapi-fetch`. A test fails
  when the generated types are older than the OpenAPI file.
- **One switch:** `VITE_USE_MOCK=true|false`. Real mode uses `VITE_API_BASE_URL` (default
  `http://localhost:8000`). The buyer for new orders is `VITE_DEMO_BUYER_ID` (default `B-000001`),
  because the sandbox has no sign-in. The same applies to the buyer/seller switch on the dispute page.
- **Mock server (MSW):** it implements the 12 endpoints the four screens and the demo page use. It is
  typed with the generated types, keeps its state in the tab's `sessionStorage`, and mimics the
  hold timer, the 48-hour response deadline and the dispatch deadline. Analyst endpoints are not
  mocked; they come with the analyst console (Step 10).
- **Bugs found while testing and fixed:**
  1. `useAction` kept the first render's function, so a form submitted values from before the user typed
     (an order with no amount, a dispute with no text). It now calls the latest function.
  2. The API client captured `fetch` when it was created, which bypassed a mock installed later.
  3. The mock lost all state on a page refresh.
- Countdowns use the **server's simulated clock** (`server_time` sent with every order), so a
  fast-forwarded demo clock is respected. A new server time re-anchors the estimate; drift is at most
  one second.
- The sandbox delivery code is shown once and kept in the tab's `sessionStorage` so a refresh does not
  lose it. Photo upload is a disabled placeholder; evidence is described in text.
- A minimal `/demo` page exists already (courier events, move the clock, reset) because the
  screens cannot be exercised without it. Step 11 adds scenario loading.
- Verified in real Chromium at a 390 px phone width: against the real API with the generated
  3,000 sellers, and in mock mode with the backend switched off, through the same path (trust check,
  order, wrong and right code, fast-forward release, lost parcel, dispute, seller response, language
  toggle). No browser errors. Google Fonts could not be loaded in this sandbox, so the Noto Sans
  Bengali webfont itself was not seen; the system fallback rendered Bangla correctly.
- **The Bangla interface text was drafted by the assistant and needs review by a native speaker.**

## Step 10

- The backend half of this step (decision endpoint, ledger move, trust feedback, before/after
  snapshots) was built in Step 8. Step 10 is the analyst console: `/analyst` (queue),
  `/analyst/dispute/:id` (case page) and `/analyst/seller/:id` (score history). These screens use a
  wider layout than the phone-sized buyer screens.
- **Case page** answers the three guideline questions (what happened, why is it risky, what should
  upay do next) from the analyzer's bilingual sections, and shows flags, the four class probabilities
  as bars (labelled "a suggestion, not a decision"), the route and why a human must look, the model
  versions used, the timeline, and the buyer's and seller's sides next to each other. Evidence,
  claims and notes are shown as plain text (tests inject `<script>` and `<img onerror>`).
  An injection attempt gets a warning banner, and the text stays visible exactly as written.
- **Decisions:** the four buttons stay disabled until a non-blank note is written. A money-moving
  or state-changing choice asks for one more confirmation that states what will happen. The only
  one-click path is the fast-lane button, which exists only when the analyzer routed the case to
  the fast lane; it records a default note if none was typed. Nothing happens automatically, and
  under senior review only a refund or a rejection is offered.
- **Without a trained classifier** the real API answers `503 CLASSIFIER_UNAVAILABLE` on "run the
  analysis". The console says so in plain words and the human can still decide, without any
  recommendation shown. No stand-in numbers are ever displayed in real mode.
- **Mock mode** shows an *illustration* of the analysis built by simple rules, labelled
  `mock_illustration` in the model versions. It exists so the console can be shown and tested
  without a classifier; it is not a model.
- **Verified in Chromium against the real API and the real trust model**, with a stand-in
  classifier injected only for this check (a throw-away script outside the repository; the version
  shows as `fixed_test_v0` on screen). Path: buyer checks `Synthetic Shop 1334` (score 76), places
  an order, parcel delivered, buyer reports a wrong item, seller responds, analyst opens the case,
  runs the analysis, writes a note, confirms the refund. The order was still held right before the
  confirmation; afterwards it was `REFUNDED`, the books balanced, the seller's score went 76 -> 65
  and the score history showed `INITIAL:76 -> DISPUTE_RESOLVED:65`. No browser errors.
  Seller 1334 was chosen because a refund moves a seller with only about 44 orders visibly;
  for the large sellers a single refund barely moves the score (see Step 8).
- **Bug found by looking at the screenshot:** the analyzer's timeline names
  (`BUYER_DISPUTE_FILED`, `SELLER_RESPONDED`) had no translation and appeared as raw codes. A test now
  fails if any timeline event is shown untranslated.
- There is still **no sign-in**: the analyst id is a free-text field remembered in the browser.
- The Bangla text of the console was drafted by the assistant and needs native review.


## Step 11 - Demo scenarios and the trained models on Kaggle

- **The seven scenarios (BLUEPRINT.md 12.2) are set up through the real API**, not by writing rows
  directly (`backend/app/demo_scenarios.py`, run by `make demo-reset` or by `POST /api/demo/reset`
  with `scenario_set: "demo"`). A demo run therefore exercises the same code a judge would.
- **Sellers are chosen by rule from the loaded data, never by hard-coded id.** Fake seller: a
  high-risk `fake_burst` seller whose 24-hour buyer count is closest to 62 (it is exactly 62,
  S-1411, score 6). Happy path: the highest-scoring TRUSTED established seller with at least 100
  orders. Honest new seller: a LIMITED_HISTORY seller with the fewest orders. Same data gives the
  same choice (tested by building two databases and comparing).
- **The "score drops" seller is chosen by simulation, and the finding is uncomfortable.** For
  honest established sellers one refund moves the score by 0 to 4 points (1359 of 1439 sellers
  move 0). Only younger sellers with a short good record move visibly, so scenario 3 uses the
  TRUSTED `honest_new` seller with the largest simulated drop of at least 5 points (S-1334,
  76 -> 65). The demo must not suggest that one refund wrecks a long-standing seller.
- **Scenario 4 builds a real repeat claimant**: the buyer files two earlier claims on other
  sellers, each rejected by a seed analyst called `demo-seed` (visible in the audit log), then
  the third claim comes after the code was used. These two earlier cases add one completed order
  each to those two sellers' counters, as the feedback loop does for any rejected claim.
- **The scenarios stop where the presenter takes over.** Orders are held, disputes are filed and
  seller responses are in, but nothing is released, refunded or decided.
- **Analysis (scenarios 3, 4, 6) runs only if a trained classifier exists.** There is none yet
  (Step 6 needs the dispute cases), so these show `pending_classifier` and no numbers. Scenario 7
  (judge types a case) also needs it. Tests inject a fixed test classifier to check the rule-based
  parts: the false claim carries CODE_CONTRADICTION and REPEAT_CLAIMANT, and the injection case
  carries the injection flag; both route to human review.
- **UI:** the hidden `/demo` page loads the scenarios and shows a card per scenario with links to
  Trust Check, the order and the analyst case, plus the sandbox delivery code. Trust Check accepts
  `/?q=<seller name>` and runs the check at once when exactly one seller matches. Mock mode covers
  scenarios 1, 2 and 5 only; the dispute scenarios are set up by the real backend.
- **Trained models are kept on the user's Kaggle, private** (`make kaggle-models`, script
  `scripts/publish_models_kaggle.py`): dataset `safeorder-trained-models` holds `models/`,
  the evaluation reports and `MODELS.md`, an index generated from the files (sizes, SHA-256 and the
  values read from each `*.meta.json`, so no number is typed by hand). Raw dispute cases and the
  generated synthetic data are never included. Rerun it after every training run; later models
  (dispute classifier, any fine-tuned transformer) are picked up automatically.


## Step 12 - Evaluation summary and metrics page

- `python -m eval.run_all` (`make eval`) re-runs the trust evaluation from the saved model, runs the
  injection checks, aggregates the optional time study, then writes `reports/summary.json` and
  three figures (`reports/figures`). `summary.json` copies numbers from the individual reports; it
  does not recompute or round them (a test compares them). Every section without a report says
  `"status": "not_measured"` with the reason. The trust evaluation's latency numbers change a
  little on every run, because they are timings.
- **The metrics page (`/metrics`) shows the file as it is.** A missing number reads "not measured"
  (a test deletes one number and checks this). In mock mode the page shows an empty state: the mock
  has no reports and never invents any.
- **Not measured yet, and why:** the dispute classifier, routing coverage and the wrong-refund /
  wrong-rejection rates (no classifier: the team's cases are not in `raw/`), the held-out injection
  set (same reason) and the analyst time study (nobody has timed real sessions; the template is
  `docs/time_study_template.json`, the input is `data/time_study.json`, and the script refuses the
  template's example values).
- **Injection numbers, honestly:** the screen detects 22 of 22 phrases it was built on (a regression
  check only: its patterns were written while looking at them) but **1 of 12** phrases written
  afterwards with different wording (paraphrases, spaced-out or leetspeak "ignore", Bangla and
  Banglish variants). These 12 were not used to change the screen, so the number stays an
  indication. Conclusion for the pitch: the pattern screen is a first filter, not a defence. The
  protection that holds is structural (no free text can change a label, a route or a ledger entry,
  and every case with a detected injection goes to a human). Phrases the screen misses reach the
  classifier as ordinary text, so the trained classifier must be checked on the team's own
  injection set (Step 6).
- **Invariance check:** 176 pairs (22 detected phrases x buyer or seller evidence x 4 base cases):
  the classifier text, the probabilities, the recommendation and the other flags never changed,
  and human review was always forced. This holds by construction with a stand-in classifier; it
  does not show that a trained classifier resists the same text.
- The phrase lists moved to `eval/injection_samples.py`, shared by the unit tests and the report.
- `make kaggle-models` now also uploads `summary.json`, `injection_eval.json` and the figures.


## Step 14 - Documentation set, secret scan, private Hugging Face upload

- `make docs` (`scripts/build_docs.py`) writes the model card, dataset card, evaluation protocol,
  responsible-AI note, licence register and an index into `docs/`. Numbers are read from
  `reports/*.json`; a test regenerates each file and fails if the committed copy is stale. Every
  document states that the data is synthetic and the system not validated on real data.
- **The evaluation protocol discloses that v2 influenced the design.** The limited-history override
  threshold was fixed before looking at v2, but the policy comparison is measured on v2, and the
  monotone constraints were added after a behavioural check on v2 sellers. v2 is therefore a
  held-out *generator*, not a pristine blind test.
- **The licence register is read from installed package metadata**, so it records what is installed
  here and is not a legal opinion. Items a script cannot know are listed as "to confirm": the
  LLM terms-of-use question (needed before dispute cases written with ChatGPT or Gemini are used
  for training), the font licence, and our own licence (the repository has none, so all rights are
  reserved by default).
- **Not written, because it needs the dispute cases or people:** the dispute classifier's model
  card and dataset card, the team agreement, logic chain, interview consent note, draft Safe Order
  terms, regulatory note, organiser questions and the prompt log. The index says so.
- `scripts/secret_scan.py` (also a test over every tracked file) looks for tokens and keys and
  prints only the file, line and kind, never the match.
- `scripts/upload_hf.py` stages the model, card, reports and figures, scans them, and uploads to a
  **private** Hugging Face repository only (the token is read from `HF_TOKEN`; a public existing
  repository is refused; there is no flag to publish). **It has only been run with `--dry-run`:
  nothing has been uploaded to Hugging Face**, because the repository name and the decision to
  put the model there belong to the team.


## Step 15 - Hardening (the freeze itself is NOT done)

- **`backend/app/security.py`**, one small ASGI middleware: request bodies over
  `api.max_body_bytes` (64 KB) get 413, announced or streamed; at most `api.rate_limit_per_minute`
  (240) requests per client address in a sliding minute, then 429 with `Retry-After` (`/health`
  exempt, 0 switches it off); `nosniff`, `X-Frame-Options: DENY` and `Cache-Control: no-store` on
  every response. The limit is in memory and per process: enough for the sandbox demo, not a
  defence against a distributed attack. Behind a proxy every request would share the proxy's
  address, so put a proper limiter in front before any real deployment.
- **Input validation was already in the request models** (length and range limits). New tests send
  20 hostile values (wrong types, huge numbers, control and right-to-left characters, SQL and
  script text, deep nesting) into every field of every write endpoint and require no 5xx and valid
  JSON back, plus malformed JSON bodies. HTML escaping on screen is covered by the earlier
  frontend tests that inject `<script>` and `<img onerror>`.
- **`make rehearse`** (`scripts/demo_rehearsal.py`): three runs from a clean reset (fresh database,
  reset clock), each loading the demo scenarios through the API and playing scenarios 1 to 6;
  results must be identical across runs. **It uses a fixed stand-in classifier**, because the
  dispute classifier is not trained, so it rehearses flags, routing, the injection screen, the
  ledger and the trust feedback, not classification quality. Scenario 7 is not rehearsed.
  Result: 3 clean runs, identical.
- **`make secret-scan`**: 0 findings over every tracked file; also a test.
- **Not done on purpose:** the `mvp-freeze` tag. The blueprint's P0 list still lacks Steps 5 and 6
  (dispute cases and classifier), so freezing now would freeze an incomplete MVP. Also not done:
  the backup video (a person must record it) and a run of the real demo with a trained classifier.


## One-address deployment (Hugging Face Space)

- **Why:** the team's cPanel hosting cannot run Python, the demo must be shown live, and paid hosting
  is not an option. A free Docker Space can run the API and the built frontend in one container, so
  the whole app is one link.
- **How:** `Dockerfile` (two stages: build the frontend with an empty API address so it calls the
  address it was loaded from; then a Python 3.11 image that installs `requirements-runtime.txt`,
  generates the synthetic data at build time and starts the server on port 7860). Everything is
  switched on by environment variables so local development and the tests are unchanged
  (`backend/app/deploy.py`): serve the frontend with a fallback to `index.html` for client-side
  routes (files outside the build folder are never served), load the seven demo scenarios on every
  start (the Space's disk is temporary), optionally protect `/api/demo` and `/api/sim` with a demo
  code, and read the client address from `X-Forwarded-For` behind the proxy.
- **Library versions are pinned to what the trust model was trained with** (a test compares them
  with `models/trust_v1.meta.json`), because a pickled model must be loaded by the same versions.
- **Bug found while testing the container steps:** the demo scenarios are set up through an
  in-process copy of the API; with a demo code set, that copy refused its own setup calls
  (403 on start-up). It now uses a private app without code, rate limit or frontend; a test covers it.
- **The demo code is a gate for the sandbox controls, not authentication.** The buyer and analyst
  screens stay open; anyone with the link can use them. A public Space is therefore only suitable
  for the sandbox with synthetic data. The code is stored as a Space secret and sent by the browser
  in a header from the code field on `/demo`.
- **Rate limit behind the proxy:** every visitor would share the proxy's address, so
  `SAFEORDER_TRUST_PROXY=1` (set in the Dockerfile) makes the limit per forwarded client. A
  spoofed header gains nothing when the setting is off (tested). The limit stays 240/minute per
  client.
- **What could not be verified here:** there is no Docker daemon in this environment, so the
  `Dockerfile` itself was not built. Its steps were replayed by hand in a clean virtual environment
  with the pinned requirements (frontend build, data generation, start-up seeding, serving) and
  checked in Chromium. The apt step (`libgomp1`, needed by LightGBM) and the real Space build are
  untested until the first deploy. The Hugging Face account was not reachable from this session
  (the stored credential is not accepted by the Hub API), so nothing has been deployed: the team
  runs `scripts/deploy_space.py` with their own token.


## Steps 5 and 6 - dispute cases and the baseline classifier (done without the team's cases)

- **Why I wrote the cases myself:** the blueprint expects ChatGPT, Gemini and team-written cases in
  `raw/`; none arrived, and the project owner told me to finish the project. So the Claude assistant
  wrote the case bank (`scripts/case_bank/`: 7 claim families x 16 wordings, and per sub-type 10
  seller responses, 8 buyer and 8 seller evidence texts, in standard, Banglish, regional and mixed
  Bangla) and `scripts/make_cases.py` combines them with seeded choices. **Nothing was written by
  ChatGPT, Gemini or the team, no real text was used, and no human has reviewed any case.**
  `raw/PROVENANCE.md` says so; the dataset card and the model card repeat it.
- **What this does and does not show.** The blueprint's cross-source test is not reproduced: every
  split has the same author, so the scores show that the pipeline works and that unseen wording is
  handled, not how the model does on other people's text or real disputes. They are probably
  optimistic for that. The test pools are small: Test 1 has 132 distinct stories in 310 cases, Test
  2 has 28 in 244, so every report also gives the numbers on one case per story (lower: macro-F1
  0.74 and 0.58).
- **Splits:** by source and batch (`dispute.cases.roles`); an unknown source stops the script;
  a claim text or a combination of source texts never appears in two of train, validation, Test 1,
  Test 2 (enforced in `scripts/split_cases.py`, tested on fixtures and on the real files). The
  injection set (24 test-style cases with an added instruction sentence) is never trained on.
- **Classifier:** TF-IDF (word 1-2 and char 2-5 grams) + class-balanced logistic regression, sigmoid
  calibration fitted on the validation split. Hyperparameters were set once before the first
  evaluation and never changed. Results: macro-F1 0.78 (Test 1) and 0.70 (Test 2); wrong-refund
  rate 5.3% and 8.5%; wrong-rejection rate 3.8% and 11.1%; calibration error 0.09 and 0.06
  (not well calibrated, ~0.09); about 17% of Test 1 cases reach the fast lane, 96% of them correct,
  none a wrong refund. INSUFFICIENT_EVIDENCE is the weakest class. Prediction takes about 4-7 ms.
- **Injection, classifier level:** the screen detects 8 of the 24 injection cases (33%); the
  recommendation changed in 4 of 24 compared with each case's twin (the same case without the
  sentence), and 20 of 24 went to a human (the rest for other reasons). A sentence the screen misses
  reaches a bag-of-words model as ordinary words.
- **The demo now uses the real classifier.** Scenarios 3, 4 and 6 are analysed when the scenarios
  load: seller fault -> refund suggested (55% seller fault), false claim -> rejection suggested
  (74%), injection -> injection flag, human review, "needs more evidence". Scenario 7 is a held order
  on which the judge reports a problem in their own words; the analyst console then shows the
  probabilities. `make rehearse` passes three identical runs with the real classifier.
- **Not done:** the transformer fine-tune (Step 13, P1): it needs a GPU run, a licence check of a
  Bangla base model, and honest data to beat the baseline on; a model trained on one author's
  templates would only learn the templates better. The 10% manual review of the cases (a person
  must do it). The team's own Test 2 cases.
- **Open question for a person:** the assistant's terms on using its output to train another model,
  even a small linear classifier (licence register).
