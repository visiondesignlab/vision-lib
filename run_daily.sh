#!/usr/bin/env bash
# Daily ingest job. Call from cron / a scheduler:  bash /workspace/caselib/run_daily.sh
# Appends a JSON summary line to data/ingest.log; exit code != 0 means the run failed.
set -euo pipefail
cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:$PATH"          # yt-dlp lives here on the box
python3 ingest.py --sources inbox,github,lvg --limit 30 2>>data/ingest.err.log | tee -a data/ingest.log
