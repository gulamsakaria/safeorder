"""Upload the trust model, its card and the evaluation reports to a PRIVATE Hugging Face repo.

Usage (repository root):
  PYTHONPATH=backend:. python -m scripts.upload_hf --repo-id <user>/<name> --dry-run
  HF_TOKEN=... PYTHONPATH=backend:. python -m scripts.upload_hf --repo-id <user>/<name>

* The token is read from the environment (HF_TOKEN) and never printed or written anywhere; when it
  is not set, huggingface_hub's own credential lookup is used.
* The repository is always created private. If it already exists and is public, nothing is
  uploaded. There is no flag to make it public: do that by hand, after a human decision.
* The staged files are scanned for secrets first, and the upload stops if anything is found.
* Run `make eval && make docs` first so the card and the reports are current.
"""

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

from scripts import secret_scan

REPO = Path(__file__).resolve().parents[1]
MODEL_FILES = ("trust_v1.joblib", "trust_v1.meta.json")
REPORT_FILES = ("trust_eval.json", "injection_eval.json", "summary.json")
DOC_FILES = ("evaluation_protocol.md", "responsible_ai.md", "licence_register.md")


def stage(folder: Path) -> list[Path]:
    """Copy what goes up. The model card becomes the repository's README.md."""
    pairs = [(REPO / "docs" / "model_card_trust.md", folder / "README.md")]
    pairs += [(REPO / "models" / n, folder / n) for n in MODEL_FILES]
    pairs += [(REPO / "reports" / n, folder / "reports" / n) for n in REPORT_FILES]
    pairs += [(REPO / "docs" / n, folder / "docs" / n) for n in DOC_FILES]
    pairs += [
        (p, folder / "reports" / "figures" / p.name)
        for p in sorted((REPO / "reports" / "figures").glob("*.png"))
    ]
    missing = [str(src.relative_to(REPO)) for src, _ in pairs if not src.exists()]
    if missing:
        raise SystemExit(f"missing files (run `make train eval docs`): {', '.join(missing)}")
    for src, dst in pairs:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)
    return [dst for _, dst in pairs]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--repo-id", required=True, help="e.g. your-username/safeorder-trust-v1")
    parser.add_argument("--dry-run", action="store_true", help="stage and scan, upload nothing")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        files = stage(folder)
        hits = secret_scan.scan(files)
        if hits:
            for path, number, kind in hits:
                print(f"{path.name}:{number}: looks like a {kind}")
            print("refusing to upload: possible secret in the staged files")
            return 1
        names = sorted(str(p.relative_to(folder)) for p in files)
        print(f"{len(names)} files staged and scanned clean:")
        for name in names:
            print(f"  {name}")
        if args.dry_run:
            print("dry run: nothing uploaded")
            return 0

        from huggingface_hub import HfApi
        from huggingface_hub.utils import RepositoryNotFoundError

        api = HfApi(token=os.environ.get("HF_TOKEN") or None)
        try:
            info = api.repo_info(args.repo_id, repo_type="model")
        except RepositoryNotFoundError:
            api.create_repo(args.repo_id, repo_type="model", private=True)
        else:
            if not info.private:
                print(f"{args.repo_id} is PUBLIC: refusing to upload; make it private first")
                return 1
        api.upload_folder(
            repo_id=args.repo_id, repo_type="model", folder_path=str(folder),
            commit_message="Upload SafeOrder trust model (synthetic data only)",
        )  # fmt: skip
        print(f"uploaded to private repository {args.repo_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
