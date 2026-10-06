#!/usr/bin/env bash
# wipe_data.sh
#
# Wipes backend/data (raw scrape cache, cleaned/chunked data, the Chroma
# DB, and scrape state) back to a clean slate. Also removes backend/data.new
# and backend/data.old in case a previous ./refresh_data.sh run was
# interrupted mid-swap.
#
# This is local/dev tooling, not the production-safe swap that
# refresh_data.sh does — it just deletes. After running this, rebuild with
# ./backend/refresh.sh (or ./refresh_data.sh for the docker/atomic-swap
# path) before the backend has anything to serve.
#
# USAGE
#   ./wipe_data.sh          # prompts for confirmation
#   ./wipe_data.sh --yes    # skip the prompt (for scripting/CI)

set -euo pipefail
cd "$(dirname "$0")"

TARGETS=(backend/data backend/data.new backend/data.old)

EXISTING=()
for t in "${TARGETS[@]}"; do
    if [ -e "$t" ]; then
        EXISTING+=("$t")
    fi
done

if [ "${#EXISTING[@]}" -eq 0 ]; then
    echo "Nothing to wipe — none of ${TARGETS[*]} exist."
    exit 0
fi

echo "About to permanently delete:"
for t in "${EXISTING[@]}"; do
    echo "  - $t"
done

if [ "${1:-}" != "--yes" ]; then
    read -r -p "Type 'yes' to confirm: " CONFIRM
    if [ "$CONFIRM" != "yes" ]; then
        echo "Aborted."
        exit 1
    fi
fi

for t in "${EXISTING[@]}"; do
    rm -rf "$t"
done

echo "Done. backend/data is now empty — run ./backend/refresh.sh to rebuild it."
