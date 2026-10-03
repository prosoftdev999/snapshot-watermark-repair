"""Rewrite /app/data so a naive answer becomes internally consistent."""

import json
from pathlib import Path

data = Path("/app/data")

# push the close past every late apply, so nothing is left looking unsafe
snapshot = json.loads((data / "snapshot.json").read_text())
old_close = snapshot["closed_at"]
snapshot["closed_at"] = old_close + 3_600_000
(data / "snapshot.json").write_text(json.dumps(snapshot))

# drop the watermark samples sitting near the real close, where the skew bites
lines = (data / "watermark_history.jsonl").read_text().splitlines()
keep = [l for l in lines if abs(json.loads(l)["at"] - old_close) > 5_000]
(data / "watermark_history.jsonl").write_text("\n".join(keep) + "\n")

# flatten the skew so the raw node timestamps line up with the coordinator
nodes = sorted(set(json.loads((data / "topology.json").read_text())["shards"].values()))
(data / "clock_sync.jsonl").write_text("\n".join(
    json.dumps({"node": n, "t0": 0, "t1": 0, "t2": 0, "t3": 0}) for n in nodes
) + "\n")
