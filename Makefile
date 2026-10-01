PY := .venv/bin/python

.PHONY: setup data train api web test lint eval demo-reset

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
	@echo "not implemented yet (Steps 4 and 6)"

eval:
	@echo "not implemented yet (Step 12)"

demo-reset:
	@echo "not implemented yet (Step 11)"
