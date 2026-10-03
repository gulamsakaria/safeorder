# One container: the API and the built frontend on one address (port 7860, as Hugging Face Spaces
# expect). Synthetic data only; the demo scenarios are loaded each time the service starts.

# ---- frontend build ----
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Empty API address: the page calls the API on the same address it was loaded from.
ENV VITE_USE_MOCK=false VITE_API_BASE_URL=
RUN npm run build

# ---- service ----
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 user
USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /home/user/app

COPY --chown=user requirements-runtime.txt ./
RUN pip install --no-cache-dir -r requirements-runtime.txt

COPY --chown=user backend ./backend
COPY --chown=user config ./config
COPY --chown=user models ./models
COPY --chown=user reports ./reports
COPY --chown=user scripts ./scripts
COPY --chown=user --from=web /web/dist ./frontend/dist

# Generated at build time (deterministic from the seeds in config/config.yaml), not stored in git.
RUN mkdir -p data docs \
    && PYTHONPATH=backend:. python -m scripts.generate_sellers --version both \
    && PYTHONPATH=backend:. python -c "from app.trust.dataset import load_features; load_features('v1'); load_features('v2')"

ENV SAFEORDER_SERVE_FRONTEND=1 SAFEORDER_AUTOSEED=1 SAFEORDER_TRUST_PROXY=1
EXPOSE 7860
# Render sets PORT; a Hugging Face Space uses 7860.
CMD ["sh", "-c", "exec python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port ${PORT:-7860}"]
