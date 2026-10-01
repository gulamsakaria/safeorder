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
