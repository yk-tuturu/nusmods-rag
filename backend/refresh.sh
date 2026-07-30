#!/usr/bin/env bash
# Re-runs the full pipeline: scrape -> clean -> chunk -> embed.
#
# USAGE
#   ./refresh.sh                       # refresh the pilot course list
#   ./refresh.sh --courses CS2030,CS2040
#   ./refresh.sh --all                 # full NUSMods catalog (slow, be careful)
#   ./refresh.sh --force               # ignore scrape cache freshness
#
# Any arguments are forwarded to the scrape step; clean/chunk/embed always
# run over whatever is currently in data/raw and data/processed.

set -euo pipefail
cd "$(dirname "$0")"

echo "== 1/4 scrape =="
python src/scrape/disqus.py "$@"

echo "== 2/4 clean =="
python src/pipeline/clean.py

echo "== 3/4 chunk =="
python src/pipeline/chunk.py

echo "== 4/4 embed =="
python src/pipeline/embed.py

echo "Done."
