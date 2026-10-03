#!/bin/sh
# Run SafeOrder locally: ./run_local.sh   (needs Python 3.11+; see README)
cd "$(dirname "$0")" || exit 1
for py in python3.12 python3.11 python3 python; do
  if command -v "$py" >/dev/null 2>&1; then exec "$py" run_local.py "$@"; fi
done
echo "Python 3.11 or newer is needed: https://www.python.org/downloads/"
exit 1
