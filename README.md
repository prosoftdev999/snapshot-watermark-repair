# Snapshot Watermark Repair

A distributed-database incident reconstruction challenge focused on recovering a cross-shard snapshot and identifying unsafe replication watermarks.

The project models an overnight consistency incident in a replicated key-value store. A published snapshot was rejected because one or more shard watermarks may have advanced beyond the writes that were actually readable when the snapshot closed.

The objective is to reconstruct the real snapshot state from the available replication evidence and determine which published watermarks were safe.

## Overview

A distributed snapshot cannot be reconstructed correctly by simply taking the newest record from every shard.

The historical state depends on several interacting factors:

- independent shard histories
- replicated writes
- unsynchronized node clocks
- client retries
- duplicate accepted records
- puts and deletes
- source-sequence watermarks
- snapshot-close timing
- per-shard log order

The reconstruction therefore combines timing, replication history, logical-write identity, and state replay.

Conceptually:

```text
raw replication evidence
        ↓
recover clock offsets
        ↓
convert events to coordinator time
        ↓
collapse logical retry duplicates
        ↓
determine snapshot-close frontier
        ↓
recover watermark at close
        ↓
replay shard logs
        ↓
reconstruct surviving keys
        ↓
audit watermark safety
        ↓
produce repaired snapshot report
```

## Repository Structure

```text
snapshot-watermark-repair/
├── cheat/
├── environment/
├── solution/
├── tests/
├── instruction.md
└── task.toml
```

### `instruction.md`

Defines the incident, reconstruction semantics, required output, and watermark rules.

### `environment/`

Contains the reproducible runtime, incident capture, and captured snapshot reconstruction code.

### `solution/`

Contains the reference incident-reconstruction implementation.

### `tests/`

Contains the independent verifier.

### `task.toml`

Defines task metadata and execution configuration.

## Snapshot Incident

The target snapshot was rejected by a consistency audit.

The challenge is to determine:

1. what the snapshot actually contained;
2. which watermark was in force for every shard when the snapshot closed;
3. which watermarks were unsafe;
4. what the greatest safe replacement watermark should have been.

The captured reconstruction program is part of the incident evidence rather than automatically trusted ground truth.

Its assumptions must be checked against the replication records.

## Watermark Semantics

A watermark represents a claim that:

```text
every logical write through source sequence N
has become readable
```

For example:

```text
watermark = 120
```

means that every required logical write through source sequence `120` should already be readable.

If sequence `118` had not become readable before the snapshot closed, a watermark of `120` would be unsafe.

The repaired watermark must therefore stop before the first write that violates this guarantee.

## Clock Reconciliation

The database nodes do not share a perfectly synchronized clock.

An event timestamp recorded on one node cannot safely be compared directly with a timestamp recorded on another node or by the coordinator.

The reconstruction first derives a coordinator-relative clock offset for every node.

Conceptually:

```text
node timestamp
      +
recovered node offset
      =
coordinator timestamp
```

Only after this conversion can delivery events be correctly compared with the snapshot-close time. :chatgpt-content-reference{index="3"}

## Client Retry Deduplication

A client retry may create several accepted physical records for one logical write.

For example:

```text
logical write W42

├── op-a  accepted on node A
├── op-b  accepted on node C
└── op-c  accepted on node B
```

These are not three independent application writes.

They represent copies of the same logical operation.

After converting delivery timestamps into coordinator time, the authoritative accepted copy is selected using:

```text
earliest corrected delivered_at
```

If two copies have the same corrected delivery time, the lexicographically smaller `op_id` wins. :chatgpt-content-reference{index="4"}

This prevents retries from being double-counted during snapshot reconstruction.

## Snapshot-Close Frontier

The snapshot represents state at one historical cutoff.

Records occurring after the snapshot closed belong to later database activity.

This is particularly important for watermark history.

A watermark publication that occurs after the close cannot be applied retroactively to the snapshot.

Conceptually:

```text
time ───────────────────────────────>

writes       writes       CLOSE        writes

WM=40        WM=47                     WM=55
                           ↑
                   snapshot uses 47,
                   not the later 55
```

## Shard Log Replay

Puts and deletes are interpreted according to each shard's log order.

A simplified example:

```text
seq 10: PUT    user-7 = v1
seq 11: PUT    user-7 = v2
seq 12: DELETE user-7
seq 13: PUT    user-9 = v4
```

At the appropriate snapshot frontier:

```text
user-7 → absent
user-9 → v4
```

The final snapshot therefore cannot be reconstructed by collecting only PUT operations or selecting records without replaying their ordering semantics.

## Cross-Shard Reconstruction

Each shard has an independent history:

```text
snapshot
├── shard-00
├── shard-01
├── shard-02
├── ...
└── shard-N
```

The output must include every shard, including shards with no surviving keys.

The complete snapshot is built by evaluating each shard against the same historical close while respecting its own replication and watermark state.

## Watermark Safety Audit

Once the logical write history has been reconstructed, each published watermark can be tested.

Suppose a shard claims:

```text
watermark = 91
```

but the first logical write not readable at snapshot close is:

```text
source sequence = 88
```

then the watermark is unsafe.

The report identifies:

```text
shard
published watermark
repaired watermark
blocking operation
```

The repaired watermark is the greatest value that was actually safe at the snapshot close.

## Why Naive Approaches Fail

Several simple approaches produce plausible but incorrect snapshots.

### Trusting local timestamps directly

Unsynchronized clocks can classify a write as before or after the snapshot incorrectly.

### Counting every retry as a different write

This duplicates logical operations.

### Choosing the latest retry

The required representative is based on earliest corrected delivery time, not simply the newest physical record.

### Applying the final watermark

A watermark published after snapshot close belongs to later activity.

### Ignoring deletes

Snapshot contents require full PUT/DELETE replay.

### Trusting the captured snapshotter blindly

The incident exists precisely because assumptions in the reconstruction path may disagree with the underlying replication evidence.

## Reconstruction Pipeline

A robust implementation follows approximately:

```text
incident capture
      ↓
inspect snapshotter assumptions
      ↓
recover node clock offsets
      ↓
normalize delivery times
      ↓
group retry copies
      ↓
select authoritative logical writes
      ↓
recover close-time watermarks
      ↓
replay shard histories
      ↓
construct snapshot contents
      ↓
identify unsafe watermarks
      ↓
calculate repaired frontiers
      ↓
write output.json
```

## Output

The solver writes:

```text
/app/output.json
```

with exactly these top-level fields:

```json
{
  "snapshot_id": "...",
  "clock_offsets_ms": {},
  "watermarks_at_close": {},
  "snapshot_contents": {},
  "unsafe_watermarks": []
}
```

The fields represent:

### `snapshot_id`

The snapshot being diagnosed.

### `clock_offsets_ms`

Coordinator-relative integer clock offsets for all nodes.

### `watermarks_at_close`

The watermark active for every shard when the snapshot closed.

### `snapshot_contents`

Every shard mapped to its surviving:

```text
key -> value_version
```

entries, including empty shards.

### `unsafe_watermarks`

Unsafe shards sorted by shard name.

Each row contains:

```text
shard
watermark
repaired_watermark
blocking_op_id
```

These output requirements come directly from the incident contract. :chatgpt-content-reference{index="5"}

## Technical Areas

This project exercises:

- distributed databases
- replicated key-value stores
- cross-shard snapshots
- replication-log replay
- consistency analysis
- watermark protocols
- logical operation deduplication
- clock-skew correction
- historical state reconstruction
- PUT/DELETE replay
- fault analysis
- incident forensics
- deterministic data processing
- Python

## Design Principle

The central distinction is between:

```text
what the system claimed was visible
```

and:

```text
what replication history proves was visible
```

A watermark is safe only when every logical write it covers was actually readable before the snapshot closed.

## Goal

Snapshot Watermark Repair reconstructs the database state that truly existed at a historical snapshot boundary and identifies where published progress markers advanced ahead of durable readable state.

The core principle is:

> Reconstruct the snapshot from replication history first, then judge the watermarks against that history.

## License

No license is currently specified.
