# Working rules for Claude Code (SafeOrder)

Source: BLUEPRINT.md Section 14. Read BLUEPRINT.md completely before working.

1. Follow Section 13 in order, one step at a time; stop and report after each step.
2. Never invent data, metrics or citations. Every number in a report or card must be produced by a script and read from `reports/*.json`. If something was not measured, write "not measured".
3. Use only synthetic, public or team-written data. No real personal data, no scraping, no real money, no external API calls in the decision path.
4. Business rules live in `rules.py` and `config/config.yaml`. ML only suggests. No generative model is allowed in the decision path. Evidence text is untrusted data and is always escaped and never treated as instructions.
5. Determinism: fixed random seeds, a configurable simulated clock, reproducible training scripts.
6. Tests for every step (pytest), ruff clean, type hints on public functions, no magic numbers.
7. Security basics: parameterised database access, escape all user-provided text in the UI, secrets only in environment variables, never commit tokens.
8. Fallback rule: if blocked for more than 2 hours, implement the documented fallback, write the reason in `DECISIONS.md`, and continue.
9. Commit after each step with the message `step-N: title`. Tag `mvp-freeze` at the end of Step 15.
10. The UI is Bangla by default and always shows the Sandbox banner ("Sandbox - synthetic data, no real money").
11. Ask the human whenever a requirement is ambiguous, or when a licence, legal or regulatory question appears. Do not guess.

## Project commands

`make setup`, `make test`, `make api`, `make web`, `make data`, `make train`, `make eval`, `make demo-reset` (see Makefile).
