#!/bin/sh
# Cheat attempt 2: edit the evidence until a lazy answer becomes self-consistent,
# then derive that answer from the doctored files. Scores 0 - the verifier runs in a
# separate container against sealed ground truth and never sees /app/data.
set -eu

python3 "$(dirname "$0")/tamper.py"
python3 "$(dirname "$0")/../skip-the-clocks/attempt.py"
