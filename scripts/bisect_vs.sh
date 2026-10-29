#!/bin/bash
# Bisect which vertex shader produces the sky wedges, against a running game started with
# REX_DRAW_DEBUG_FILE=work/drawdbg.txt and parked on the start line.
# Usage: scripts/bisect_vs.sh <file with candidate VS hashes, one per line> [shots]
# Skipping a guilty set gives 0 artifact frames; 1 hit is retested once.
cd "$(dirname "$0")/.."
mapfile -t cand < "$1"
shots=${2:-60}
round=0
while [ ${#cand[@]} -gt 1 ]; do
  half=$(( ${#cand[@]} / 2 ))
  first=("${cand[@]:0:half}")
  rest=("${cand[@]:half}")
  round=$((round + 1))
  out=$(python scripts/skip_probe.py "bis$round" "$shots" "$(IFS=,; echo "${first[*]}")")
  k=$(echo "$out" | sed -E 's/.*: ([0-9]+)\/.*/\1/')
  if [ "$k" = 1 ]; then
    out=$(python scripts/skip_probe.py "bis${round}b" "$shots" "$(IFS=,; echo "${first[*]}")")
    k=$(echo "$out" | sed -E 's/.*: ([0-9]+)\/.*/\1/')
  fi
  echo "round $round: skip ${#first[@]} of ${#cand[@]} -> $out"
  if [ "$k" = 0 ]; then cand=("${first[@]}"); else cand=("${rest[@]}"); fi
done
echo "culprit VS: ${cand[0]}"
python scripts/skip_probe.py confirm "$shots" "${cand[0]}"
