#!/usr/bin/env python3
"""Compare a candidate reconstruction with a partial replica readback capture.

The readback is incident evidence, not a specification and not part of grading.
It covers only part of the snapshot, so a clean result does not prove the full
reconstruction is correct.  A few mismatch locations are printed to make the
capture useful for debugging without turning it into an answer key.
"""
import json
from pathlib import Path

out = Path('/app/output.json')
samples = Path('/app/data/readback_samples.jsonl')
if not out.is_file():
    raise SystemExit('no /app/output.json to check')

try:
    candidate = json.loads(out.read_text())
except Exception as exc:
    raise SystemExit(f'cannot read candidate JSON: {exc}')
contents = candidate.get('snapshot_contents')
if not isinstance(contents, dict):
    raise SystemExit('candidate has no snapshot_contents object')

rows = [json.loads(line) for line in samples.read_text().splitlines() if line.strip()]
misses = []
for row in rows:
    block = contents.get(row['shard'])
    actual = None if not isinstance(block, dict) else block.get(row['key'])
    expected = row['value_version'] if row['present'] else None
    if actual != expected:
        misses.append((row['shard'], row['key'], expected, actual))

print(f'readback samples checked: {len(rows)}')
print(f'mismatches: {len(misses)}')
for shard, key, expected, actual in misses[:4]:
    print(f'  {shard} {key}: readback={expected!r} candidate={actual!r}')
if len(misses) > 4:
    print(f'  ... {len(misses) - 4} more')
