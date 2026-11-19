#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_DIR}"

docker compose run --rm --no-deps \
  stt python3 -c \
  'import os; from faster_whisper.utils import download_model; size = os.environ["MODEL_SIZE"]; print(f"Downloading faster-whisper {size}..."); download_model(size, output_dir="/models/faster-whisper"); print("Model is ready in /models/faster-whisper")'
