"""Scan files for secrets before they are committed or uploaded.

Usage (repository root): python -m scripts.secret_scan [paths...]
Without paths every git-tracked file is scanned.
Exit status 1 when something that looks like a credential is found; the match itself is never
printed, only the file, the line number and the kind of secret.
"""

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PATTERNS: dict[str, re.Pattern[str]] = {
    "Hugging Face token": re.compile(r"\bhf_[A-Za-z0-9]{30,}\b"),
    "GitHub token": re.compile(
        r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b|\bgithub_pat_\w{40,}\b"
    ),
    "OpenAI-style key": re.compile(r"\bsk-[A-Za-z0-9_-]{32,}\b"),
    "Anthropic key": re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
    "AWS access key id": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "Slack token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    "private key block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY"),
    "Kaggle key in JSON": re.compile(r'"key"\s*:\s*"[0-9a-f]{32}"'),
    "assigned secret": re.compile(
        r"""(?i)\b(?:api[_-]?key|secret|token|password)\b\s*[:=]\s*["'][A-Za-z0-9_\-/+=]{20,}["']"""
    ),
}
# Documented placeholders that are not secrets.
ALLOWED = ("placeholder", "your-token", "<token>", "example", "xxxxxxxx")
SKIP_SUFFIXES = {".png", ".jpg", ".joblib", ".zip", ".ico", ".woff", ".woff2", ".db", ".gz"}
MAX_BYTES = 5_000_000


def tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    return [REPO / name for name in out]


def scan_file(path: Path) -> list[tuple[int, str]]:
    if path.suffix in SKIP_SUFFIXES or not path.is_file() or path.stat().st_size > MAX_BYTES:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        if any(word in line.lower() for word in ALLOWED):
            continue
        for kind, pattern in PATTERNS.items():
            if pattern.search(line):
                found.append((number, kind))
    return found


def scan(paths: list[Path]) -> list[tuple[Path, int, str]]:
    return [(p, n, k) for p in paths for n, k in scan_file(p)]


def main(argv: list[str]) -> int:
    paths = [Path(a) for a in argv] if argv else tracked_files()
    expanded: list[Path] = []
    for path in paths:
        expanded += [p for p in path.rglob("*") if p.is_file()] if path.is_dir() else [path]
    hits = scan(expanded)
    for path, number, kind in hits:
        shown = path.relative_to(REPO) if path.is_relative_to(REPO) else path
        print(f"{shown}:{number}: looks like a {kind}")
    print(f"scanned {len(expanded)} files, {len(hits)} possible secret(s)")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
