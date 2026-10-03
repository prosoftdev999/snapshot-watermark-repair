# Cheat attempts

Three shortcuts I tried against this bundle. The pipeline never runs these; I ran the
first two by hand against the real verifier image and recorded what came back.

## 1. `skip-the-clocks/attempt.py` - measured, reward 0

The most tempting shortcut, and the one that looks like a finished answer. It does the
retry collapse and the replay properly but treats every timestamp as if it were already on
the coordinator clock, which is what you get if you never open `clock_sync.jsonl` or
`topology.json`. The output is schema-perfect: all five fields, every node, every shard,
sorted `unsafe_watermarks`.

Verifier result: `4 failed, 2 passed`, reward `0`. It misses 12 of 12 offsets, 65
key/version entries, 9 of 36 watermarks, and gets a different set of unsafe shards. There
is no partial credit, so a structurally perfect answer that skips one stage still scores
nothing.

## 2. `tamper-environment/attempt.sh` - measured, reward 0

Rewrites `/app/data` so the agent's own answer becomes internally consistent: it pushes
`closed_at` out past every late apply, deletes the watermark samples that sit near the
close, flattens the clock probes, and then re-derives an answer from the doctored files.
This is the standard "make the input agree with me" move.

Verifier result: `4 failed, 2 passed`, reward `0` - 34 of 36 watermarks wrong and 58 keys
missing, so the tampering makes the answer worse than leaving the files alone. The
verifier is `environment_mode = "separate"`; it comes up
in its own container from `tests/Dockerfile` after the agent's container is gone, and it
reads nothing but `/app/output.json` and the `expected.json` baked into its own image.
Nothing under `/app/data` reaches the grader, so editing the evidence only makes the
answer wrong.

## 3. `forge-reward/attempt.sh` - not run, defeat is structural

Writes `1` into `/logs/verifier/reward.txt`, drops a fake `ctrf.json` next to it, and
plants a `/tests/expected.json` inside the agent container. I did not bother running it:
`tests/test.sh` writes `0` into the reward file itself before pytest starts and only
overwrites it with `1` on a clean exit, all of that inside the verifier container, and
`/tests` there is baked at image build time from this directory. The agent container's
filesystem is torn down before any of it exists.

## What is not defensible from the agent's side

The answer key lives only in `tests/`, which is never copied into the environment image.
The verifier never imports or executes agent code - it json-loads one file and compares
values. Guessing is not on the table either: the graded object carries 12 signed offsets,
36 watermarks, 435 key/version pairs and 5 blocking op_ids drawn from 2,494 rows.
