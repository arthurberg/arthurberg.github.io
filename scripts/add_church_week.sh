#!/bin/sh
# Usage: scripts/add_church_week.sh YYYY-MM-DD /path/to/guide.html
# Copies the self-contained weekly guide into church/, rebuilds the index, commits and pushes (GitHub Pages deploys).
set -e
cd "$(dirname "$0")/.."
[ $# -eq 2 ] || { echo "usage: $0 YYYY-MM-DD guide.html"; exit 1; }
cp "$2" "church/$1.html"
python3 scripts/church_index.py
git add church
git commit -m "church: add $1 worship guide"
git push origin main
echo "published: https://arthurberg.com/church/$1.html"
