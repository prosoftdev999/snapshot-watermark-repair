#!/bin/sh
set -u
mkdir -p /logs/verifier
reward=/logs/verifier/reward.txt
report=/logs/verifier/ctrf.json
printf '0' > "$reward"
if pytest -q /tests/test_verify.py --ctrf "$report"; then
  printf '1' > "$reward"
  exit 0
fi
exit 1
