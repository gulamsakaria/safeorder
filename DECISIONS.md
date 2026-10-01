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
