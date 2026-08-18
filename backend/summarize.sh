#!/usr/bin/env bash
# Generates/refreshes cached AI summaries for processed courses (see
# src/pipeline/summarize.py). The /courses/{code}/summary API route only
# ever serves these cached files - it never calls the LLM itself - so this
# script is what actually populates data/summaries/.
#
# USAGE
#   ./summarize.sh                       # summarize every course in data/processed/
#   ./summarize.sh --courses CS2030S,MA1521
#   ./summarize.sh --force               # regenerate even if a fresh cached copy exists
#   ./summarize.sh --max-age-days 7       # treat cached summaries older than this as stale
#
# Any arguments are forwarded as-is to src/pipeline/summarize.py.

set -euo pipefail
cd "$(dirname "$0")"

python src/pipeline/summarize.py "$@"
