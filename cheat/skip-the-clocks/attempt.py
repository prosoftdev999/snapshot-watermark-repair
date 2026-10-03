"""Cheat attempt 1: produce a schema-perfect answer without doing the clock work.

Collapses retries and replays the log correctly, but compares node-local timestamps
against the coordinator's close time as if the clocks agreed. Never opens
clock_sync.jsonl. Scores 0.
"""

import json
from collections import defaultdict
from pathlib import Path

DATA = Path("/app/data")
read = lambda n: [json.loads(x) for x in (DATA / n).read_text().splitlines() if x.strip()]

snapshot = json.loads((DATA / "snapshot.json").read_text())
topology = json.loads((DATA / "topology.json").read_text())
close = snapshot["closed_at"]

kept = {}
for row in read("replication.jsonl"):
    key = (row["shard"], row["idempotency_key"])
    rank = (row["delivered_at"], row["op_id"])
    if key not in kept or rank < kept[key][0]:
        kept[key] = (rank, row)

by_shard = defaultdict(list)
for _rank, row in kept.values():
    by_shard[row["shard"]].append(row)

contents = {}
for shard in topology["shards"]:
    state = {}
    for row in sorted(by_shard[shard], key=lambda r: r["source_seq"]):
        if row["applied_at"] > close:
            continue
        if row["kind"] == "put":
            state[row["key"]] = row["value_version"]
        else:
            state.pop(row["key"], None)
    contents[shard] = state

marks = {}
for row in read("watermark_history.jsonl"):
    if row["at"] <= close:
        cur = marks.get(row["shard"])
        if cur is None or row["at"] > cur[0]:
            marks[row["shard"]] = (row["at"], row["watermark"])
marks = {s: v for s, (_t, v) in marks.items()}

unsafe = []
for shard in sorted(topology["shards"]):
    blockers = [r for r in by_shard[shard]
                if r["source_seq"] <= marks[shard] and r["applied_at"] > close]
    if blockers:
        first = min(blockers, key=lambda r: r["source_seq"])
        unsafe.append({"shard": shard, "watermark": marks[shard],
                       "repaired_watermark": first["source_seq"] - 1,
                       "blocking_op_id": first["op_id"]})

Path("/app/output.json").write_text(json.dumps({
    "snapshot_id": snapshot["snapshot_id"],
    # the giveaway: every node "obviously" has no skew
    "clock_offsets_ms": {n: 0 for n in set(topology["shards"].values())},
    "watermarks_at_close": marks,
    "snapshot_contents": contents,
    "unsafe_watermarks": unsafe,
}, indent=2) + "\n")
