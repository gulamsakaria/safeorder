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
