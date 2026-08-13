#!/usr/bin/env bash
# Re-runs the full pipeline: scrape -> clean -> chunk -> embed.
#
# USAGE
#   ./refresh.sh                       # defaults to --all (full NUSMods catalog, slow, be careful)
#   ./refresh.sh --courses CS2030,CS2040
#   ./refresh.sh --all
#   ./refresh.sh --force               # ignore scrape cache freshness
#   ./refresh.sh --test                # fixed small test course list
#
# Any arguments are forwarded to the scrape step (except --test, translated
# below into --courses); clean/chunk/embed always run over whatever is
# currently in data/raw and data/processed.

TEST_COURSES="CS2030S,CS2040S,MA1521,MA1522,GEA1000N,CS2103T"

set -euo pipefail
cd "$(dirname "$0")"

if [ "${1:-}" = "--test" ]; then
    set -- --courses "$TEST_COURSES"
elif [ "$#" -eq 0 ]; then
    set -- --all
fi

echo "== 1/4 scrape =="
python src/scrape/disqus.py "$@"

echo "== 1/4 scrape (retry failures) =="
python src/scrape/disqus.py --retry-failed

echo "== 2/4 clean =="
python src/pipeline/clean.py

echo "== 3/4 chunk =="
python src/pipeline/chunk.py

echo "== 4/4 embed =="
python src/pipeline/embed.py

echo "Done."
