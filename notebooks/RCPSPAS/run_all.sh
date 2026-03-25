#!/bin/bash
# Run all solver/formulation/dataset combinations sequentially.
# Usage (inside Docker container):
#   bash run_all.sh
#
# Results go to results/<solver>_<formulation>_ASLIB<N>.csv
# Uses --resume so you can restart safely after interruption.

set -euo pipefail

TIME_LIMIT=5
WORKERS=32
ASLIB_DIR="ASLIB"
RESULTS_DIR="results"

mkdir -p "$RESULTS_DIR"

SOLVERS="optalcp cpsat cpo"
FORMULATIONS="original"

for SOLVER in $SOLVERS; do
    for FORMULATION in $FORMULATIONS; do
        for N in $(seq 0 6); do
            DATA_DIR="$ASLIB_DIR/ASLIB${N}"
            CSV="$RESULTS_DIR/${SOLVER}_${FORMULATION}_ASLIB${N}.csv"

            if [ ! -d "$DATA_DIR" ]; then
                echo "SKIP: $DATA_DIR not found"
                continue
            fi

            echo ""
            echo "============================================================"
            echo "  $SOLVER / $FORMULATION / ASLIB${N} -> $CSV"
            echo "============================================================"

            python solve_rcpspas.py \
                -d "$DATA_DIR" \
                --solver "$SOLVER" \
                -f "$FORMULATION" \
                -t "$TIME_LIMIT" \
                -w "$WORKERS" \
                -q \
                -o "$CSV" \
                --resume
        done
    done
done

echo ""
echo "ALL DONE"
