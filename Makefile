PY := .venv/bin/python

.PHONY: setup data train api web test lint eval demo-reset openapi kaggle

setup:
	python3.11 -m venv .venv
	$(PY) -m pip install -q -r requirements.txt
	cd frontend && npm install

test:
	$(PY) -m pytest -q
	$(PY) -m ruff check .

lint:
	$(PY) -m ruff check .

api:
	cd backend && ../$(PY) -m uvicorn app.main:app --reload --port 8000

web:
	cd frontend && npm run dev

data:
	PYTHONPATH=backend:. $(PY) -m scripts.generate_sellers --version both --load-db

train:
	PYTHONPATH=backend:. $(PY) -m scripts.train_trust

eval:
	PYTHONPATH=backend:. $(PY) -m eval.trust_eval

openapi:
	PYTHONPATH=backend:. $(PY) -m scripts.export_openapi

kaggle:
	PYTHONPATH=backend:. $(PY) -m scripts.build_kaggle

demo-reset:
	@echo "not implemented yet (Step 11)"
