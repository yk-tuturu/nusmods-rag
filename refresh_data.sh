#!/usr/bin/env bash
# refresh_data.sh
#
# Safely refreshes backend/data without ever exposing the live backend to a
# half-written directory. The scraper container writes to backend/data.new
# (see the `scraper` service's volume mount) - a completely separate path
# from what `backend` has mounted - so nothing overlaps until the mv swap
# below, which is atomic on a single filesystem: the backend can only ever
# see the fully-old or fully-new data/, never a partial mix of the two.
#
# This matters specifically because Chroma's persistence is several files
# (sqlite metadata + separate vector index files) that all have to agree
# with each other - copying/updating them one at a time in place risks a
# request landing mid-update and reading a mix that doesn't correspond.
#
# USAGE
#   ./refresh_data.sh                       # default pilot course list
#   ./refresh_data.sh --courses CS2030,CS2040
#   ./refresh_data.sh --all
#   ./refresh_data.sh --test                # fixed small test course list
#
# Any arguments are forwarded to refresh.sh's scrape step, except --test,
# which is handled here and translated into a --courses list.

TEST_COURSES="CS2030S,CS2040S,MA1521,MA1522,GEA1000N,CS2103T"

set -euo pipefail
cd "$(dirname "$0")"

if [ "${1:-}" = "--test" ]; then
    set -- --courses "$TEST_COURSES"
fi

# Run the scraper container as this user, not root — otherwise it writes
# to the bind mount as root and we can't clean up data.old without sudo.
export HOST_UID="$(id -u)"
export HOST_GID="$(id -g)"

echo "== running scraper into staging directory (backend/data.new) =="
rm -rf backend/data.new
mkdir -p backend/data.new
docker compose run --rm scraper "$@"

echo "== atomically swapping staged data into place =="
rm -rf backend/data.old
if [ -d backend/data ]; then
    mv backend/data backend/data.old
fi
mv backend/data.new backend/data

echo "== restarting backend to pick up new data =="
docker compose restart backend

rm -rf backend/data.old
echo "Done."
