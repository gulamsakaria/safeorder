"""Deploy the whole app (API + frontend, one Docker container) to a Hugging Face Space.

Usage (repository root, on a machine where you are logged in or have HF_TOKEN):
  PYTHONPATH=backend:. python -m scripts.deploy_space --repo-id <user>/safeorder --dry-run
  HF_TOKEN=... PYTHONPATH=backend:. python -m scripts.deploy_space --repo-id <user>/safeorder
  ... add --public to make the Space public (default: private; changing it later is one click)

Optional: if SAFEORDER_DEMO_CODE is set in your environment it is stored as a Space *secret* (never
printed, never written to a file) so that /api/demo and /api/sim need that code.

The staged files are scanned for secrets first. Only what the container needs is uploaded.
"""

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

from scripts import secret_scan

REPO = Path(__file__).resolve().parents[1]
FILES = ("Dockerfile", ".dockerignore", "requirements-runtime.txt")
FOLDERS = ("backend", "config", "models", "reports", "scripts", "frontend")
IGNORE = shutil.ignore_patterns(
    "__pycache__", "*.pyc", "node_modules", "dist", ".env", "tests", "*.db", ".pytest_cache"
)


def stage(folder: Path) -> list[Path]:
    for name in FILES:
        shutil.copy(REPO / name, folder / name)
    for name in FOLDERS:
        shutil.copytree(REPO / name, folder / name, ignore=IGNORE)
    shutil.copy(REPO / "deploy" / "space" / "README.md", folder / "README.md")
    return sorted(p for p in folder.rglob("*") if p.is_file())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--repo-id", required=True, help="<user>/<space name>")
    parser.add_argument("--public", action="store_true", help="create the Space as public")
    parser.add_argument("--dry-run", action="store_true", help="stage and scan, upload nothing")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        files = stage(folder)
        hits = secret_scan.scan(files)
        if hits:
            for path, number, kind in hits:
                print(f"{path.relative_to(folder)}:{number}: looks like a {kind}")
            print("refusing to upload: possible secret in the staged files")
            return 1
        total = sum(p.stat().st_size for p in files) / 1e6
        print(f"{len(files)} files ({total:.1f} MB) staged and scanned clean")
        if args.dry_run:
            print("dry run: nothing uploaded")
            return 0

        from huggingface_hub import HfApi
        from huggingface_hub.utils import RepositoryNotFoundError

        api = HfApi(token=os.environ.get("HF_TOKEN") or None)
        try:
            info = api.repo_info(args.repo_id, repo_type="space")
        except RepositoryNotFoundError:
            api.create_repo(
                args.repo_id, repo_type="space", space_sdk="docker", private=not args.public
            )
            print(f"created {'public' if args.public else 'private'} Space {args.repo_id}")
        else:
            if info.private is False and not args.public:
                print(
                    f"{args.repo_id} is PUBLIC: pass --public to confirm, or make it private first"
                )
                return 1
        code = os.environ.get("SAFEORDER_DEMO_CODE")
        if code:
            api.add_space_secret(args.repo_id, "SAFEORDER_DEMO_CODE", code)
            print("demo code stored as a Space secret")
        api.upload_folder(
            repo_id=args.repo_id, repo_type="space", folder_path=str(folder),
            commit_message="Deploy SafeOrder sandbox (synthetic data only)",
        )  # fmt: skip
        print(f"uploaded: https://huggingface.co/spaces/{args.repo_id}")
        print("the Space now builds the container; watch the Logs tab (a few minutes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
