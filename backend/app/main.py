"""FastAPI entry point. The full API contract (BLUEPRINT.md Section 7) arrives in Step 8."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import load_config

config = load_config()

app = FastAPI(title=config["project"]["name"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=config["api"]["cors_origins"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
