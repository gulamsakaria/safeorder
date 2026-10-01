PY := .venv/bin/python

.PHONY: setup data train api web web-mock test test-web lint eval demo-reset openapi kaggle kaggle-models gen-api

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
	cd frontend && VITE_USE_MOCK=false npm run dev

web-mock:
	cd frontend && npm run dev:mock

test-web:
	cd frontend && npm run typecheck && npm test && npm run lint && npm run build

gen-api: openapi
	cd frontend && npm run gen:api

data:
	PYTHONPATH=backend:. $(PY) -m scripts.generate_sellers --version both --load-db

train:
	PYTHONPATH=backend:. $(PY) -m scripts.train_trust

eval:
	PYTHONPATH=backend:. $(PY) -m eval.run_all

openapi:
	PYTHONPATH=backend:. $(PY) -m scripts.export_openapi

kaggle:
	PYTHONPATH=backend:. $(PY) -m scripts.build_kaggle

kaggle-models:
	PYTHONPATH=backend:. $(PY) -m scripts.publish_models_kaggle --push

demo-reset:
	PYTHONPATH=backend:. $(PY) -m scripts.seed_demo
