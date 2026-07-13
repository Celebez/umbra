#!/usr/bin/env bash
# Publish Umbra to PyPI. Requires TWINE_USERNAME + TWINE_PASSWORD (or
# PYPI_API_TOKEN) in the environment. Build artifacts are produced by
# `python -m build` (run first, or this script does it).
set -euo pipefail

cd "$(dirname "$0")"

echo "[umbra] building dist..."
python -m build

echo "[umbra] checking artifacts..."
python -m twine check dist/*

REPO="${TWINE_REPOSITORY:-https://upload.pypi.org/legacy/}"

if [ -z "${TWINE_PASSWORD:-}" ]; then
  echo "[umbra] TWINE_PASSWORD (or PYPI_API_TOKEN) not set. Aborting."
  echo "        export TWINE_USERNAME=__token__"
  echo "        export TWINE_PASSWORD=pypi-xxxx"
  exit 1
fi

echo "[umbra] uploading to ${REPO}"
python -m twine upload --repository-url "${REPO}" dist/*

echo "[umbra] published. https://pypi.org/project/umbra/"
