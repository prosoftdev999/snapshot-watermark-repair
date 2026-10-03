"""Reference solution for snapshot-watermark-repair.

Everything below is derived from the files under /app/data. Nothing is
hard-coded: the clock offsets, the snapshot contents, the watermark in force at
close and the unsafe watermarks all come out of the shipped evidence.
"""

import json
from pathlib import Path

DATA = Path("/app/data")
OUTPUT = Path("/app/output.json")


def read_jsonl(name):
    with (DATA / name).open() as handle:
        return [json.loads(line) for line in handle if line.strip()]


def estimate_offsets(sync_rows):
    """One offset per node, from the probe round with the smallest delay."""
    best = {}
    for row in sync_rows:
        delay = (row["t3"] - row["t0"]) - (row["t2"] - row["t1"])
        current = best.get(row["node"])
        if current is None or (delay, row["t0"]) < (current[0], current[1]):
            best[row["node"]] = (delay, row["t0"], row)

    offsets = {}
    for node, (_delay, _t0, row) in best.items():
        numerator = (row["t1"] - row["t0"]) + (row["t2"] - row["t3"])
        if numerator % 2:
            raise ValueError(f"non-integer offset for {node}")
        offsets[node] = numerator // 2
    return offsets


def collapse_retries(replication, offset_of_shard):
    """One record per idempotency key: the copy that was delivered first."""
    kept = {}
    for row in replication:
        offset = offset_of_shard[row["shard"]]
        delivered = row["delivered_at"] - offset
        rank = (delivered, row["op_id"])
        key = (row["shard"], row["idempotency_key"])
        previous = kept.get(key)
        if previous is None or rank < previous[0]:
            kept[key] = (rank, {
                "shard": row["shard"],
                "op_id": row["op_id"],
                "source_seq": row["source_seq"],
                "applied_at": row["applied_at"] - offset,
                "kind": row["kind"],
                "key": row["key"],
                "value_version": row.get("value_version"),
            })
    return [record for _rank, record in kept.values()]


def replay(operations, closed_at):
    """Apply the operations the snapshot could see, in source order."""
    contents = {}
    for op in sorted(operations, key=lambda o: o["source_seq"]):
        if op["applied_at"] > closed_at:
            continue
        if op["kind"] == "put":
            contents[op["key"]] = op["value_version"]
        else:
            contents.pop(op["key"], None)
    return contents


def watermark_in_force(samples, closed_at, offset_of_shard):
    """The last watermark each shard reported at or before the close."""
    best = {}
    for row in samples:
        at = row["at"] - offset_of_shard[row["shard"]]
        if at > closed_at:
            continue
        current = best.get(row["shard"])
        if current is None or at > current[0]:
            best[row["shard"]] = (at, row["watermark"])
    return {shard: value for shard, (_at, value) in best.items()}


def main():
    snapshot = json.loads((DATA / "snapshot.json").read_text())
    topology = json.loads((DATA / "topology.json").read_text())
    replication = read_jsonl("replication.jsonl")
    samples = read_jsonl("watermark_history.jsonl")

    closed_at = snapshot["closed_at"]
    shard_node = topology["shards"]
    offsets = estimate_offsets(read_jsonl("clock_sync.jsonl"))
    offset_of_shard = {s: offsets[n] for s, n in shard_node.items()}

    operations = collapse_retries(replication, offset_of_shard)
    by_shard = {shard: [] for shard in shard_node}
    for op in operations:
        by_shard[op["shard"]].append(op)

    contents = {shard: replay(ops, closed_at) for shard, ops in by_shard.items()}
    watermarks = watermark_in_force(samples, closed_at, offset_of_shard)
    missing = set(shard_node) - set(watermarks)
    if missing:
        raise ValueError(f"no watermark before close for {sorted(missing)}")

    unsafe = []
    for shard in sorted(shard_node):
        limit = watermarks[shard]
        blockers = [op for op in by_shard[shard]
                    if op["source_seq"] <= limit and op["applied_at"] > closed_at]
        if not blockers:
            continue
        first = min(blockers, key=lambda o: o["source_seq"])
        unsafe.append({
            "shard": shard,
            "watermark": limit,
            "repaired_watermark": first["source_seq"] - 1,
            "blocking_op_id": first["op_id"],
        })

    result = {
        "snapshot_id": snapshot["snapshot_id"],
        "clock_offsets_ms": dict(sorted(offsets.items())),
        "watermarks_at_close": dict(sorted(watermarks.items())),
        "snapshot_contents": {
            shard: dict(sorted(contents[shard].items()))
            for shard in sorted(contents)
        },
        "unsafe_watermarks": unsafe,
    }
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=False) + "\n")


if __name__ == "__main__":
    main()
