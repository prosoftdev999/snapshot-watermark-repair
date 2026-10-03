# Diagnose snapshot `snap-2291`

The overnight consistency audit rejected a cross-shard snapshot from our replicated key-value store. The incident capture is under `/app/data`, and the reconstruction code that was running at the time is under `/app/snapshotter`.

Work out what the snapshot actually contained and which shard watermarks were unsafe. The shipped reconstruction code is part of the evidence: inspect it, compare its assumptions with the raw records, and correct for anything that would make its result disagree with the replication history. This is an incident-analysis task, not a request to patch the captured program.

A watermark means that every logical write through that source sequence has become readable. Client retries can create more than one accepted log record for the same logical write. After converting delivery times to coordinator time, keep the accepted copy with the earliest corrected `delivered_at`; if two copies have the same corrected delivery time, keep the one with the lexicographically smaller `op_id`. Node clocks are not synchronized with the coordinator, and puts/deletes must be interpreted according to the shard's log order. Watermark history after the snapshot closed belongs to later activity.

Write `/app/output.json` with exactly these fields:

- `snapshot_id`: the snapshot identifier.
- `clock_offsets_ms`: integer coordinator-relative clock offset for every node.
- `watermarks_at_close`: the watermark in force for every shard when the snapshot closed.
- `snapshot_contents`: every shard mapped to its surviving `key -> value_version` pairs at the close, including empty shards.
- `unsafe_watermarks`: unsafe shards sorted by shard name. Each entry must contain `shard`, `watermark`, `repaired_watermark`, and `blocking_op_id`. The repaired value is the greatest watermark that would have been safe at the close; `blocking_op_id` is the first logical write proving the published watermark was too far ahead.

Use the timestamps and identifiers in the capture as recorded; do not invent missing events. JSON object key order does not matter. Only `/app/output.json` is graded.


You have 7200 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
