"""Pack the built static site (site/) into site.zip, ready to upload to a web host.

Usage (repository root): python -m scripts.zip_site   (run by `make static-site`)
The zip holds the files of site/ at its top level, so unpacking it in the folder of a sub-domain
gives index.html, assets/, engine/ and .htaccess right there. The order and timestamps are fixed,
so the same build always gives the same zip.
"""

import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SITE = REPO / "site"
OUT = REPO / "site.zip"
FIXED_TIME = (2026, 10, 1, 0, 0, 0)


def main() -> None:
    if not (SITE / "index.html").exists():
        raise SystemExit("site/ is missing: run `make static-site` first")
    files = sorted(p for p in SITE.rglob("*") if p.is_file())
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            info = zipfile.ZipInfo(path.relative_to(SITE).as_posix(), FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    print(f"wrote {OUT.name}: {len(files)} files, {OUT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
