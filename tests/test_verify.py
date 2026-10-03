"""Grade /app/output.json against ground truth baked into the verifier image."""

import json
from pathlib import Path

import pytest

OUTPUT = Path("/app/output.json")
EXPECTED = Path("/tests/expected.json")
FIELDS = {
    "snapshot_id",
    "clock_offsets_ms",
    "watermarks_at_close",
    "snapshot_contents",
    "unsafe_watermarks",
}


@pytest.fixture(scope="module")
def expected():
    return json.loads(EXPECTED.read_text())


@pytest.fixture(scope="module")
def produced():
    if not OUTPUT.is_file():
        pytest.fail("/app/output.json was not produced")
    try:
        data = json.loads(OUTPUT.read_text())
    except json.JSONDecodeError as exc:
        pytest.fail(f"/app/output.json is not valid JSON: {exc}")
    if not isinstance(data, dict):
        pytest.fail("/app/output.json must hold a JSON object")
    return data


def test_field_set(produced):
    assert set(produced) == FIELDS


def test_snapshot_id(produced, expected):
    assert isinstance(produced["snapshot_id"], str)
    assert produced["snapshot_id"] == expected["snapshot_id"]


def test_clock_offsets(produced, expected):
    got = produced["clock_offsets_ms"]
    want = expected["clock_offsets_ms"]
    assert isinstance(got, dict)
    assert set(got) == set(want), "one entry per node in topology.json is required"
    assert all(type(v) is int for v in got.values()), "offsets must be integers"
    wrong = sorted(n for n in want if got[n] != want[n])
    assert not wrong, f"{len(wrong)} node offsets are wrong: {wrong[:6]}"


def test_watermarks_at_close(produced, expected):
    got = produced["watermarks_at_close"]
    want = expected["watermarks_at_close"]
    assert isinstance(got, dict)
    assert set(got) == set(want), "one entry per shard is required"
    assert all(type(v) is int for v in got.values()), "watermarks must be integers"
    wrong = sorted(s for s in want if got[s] != want[s])
    assert not wrong, f"{len(wrong)} shard watermarks are wrong: {wrong[:6]}"


def test_snapshot_contents(produced, expected):
    got = produced["snapshot_contents"]
    want = expected["snapshot_contents"]
    assert isinstance(got, dict)
    assert set(got) == set(want), "one entry per shard is required, empty ones included"
    for shard in sorted(want):
        block = got[shard]
        assert isinstance(block, dict), f"{shard} must map keys to versions"
        assert all(type(v) is int for v in block.values()), \
            f"{shard} versions must be integers"
    missing = sum(len(set(want[s]) - set(got[s])) for s in want)
    extra = sum(len(set(got[s]) - set(want[s])) for s in want)
    stale = sum(1 for s in want for k in want[s]
                if k in got[s] and got[s][k] != want[s][k])
    assert (missing, extra, stale) == (0, 0, 0), (
        f"{missing} keys missing, {extra} keys that should not survive, "
        f"{stale} keys carrying the wrong version"
    )


def test_unsafe_watermarks(produced, expected):
    got = produced["unsafe_watermarks"]
    want = expected["unsafe_watermarks"]
    assert isinstance(got, list)
    for entry in got:
        assert isinstance(entry, dict), "each entry must be an object"
        assert set(entry) == {"shard", "watermark", "repaired_watermark",
                              "blocking_op_id"}
        assert isinstance(entry["shard"], str)
        assert isinstance(entry["blocking_op_id"], str)
        assert type(entry["watermark"]) is int
        assert type(entry["repaired_watermark"]) is int
    shards = [e["shard"] for e in got]
    assert shards == sorted(shards), "entries must be sorted by shard name"
    assert len(set(shards)) == len(shards), "one entry per shard at most"
    assert shards == [e["shard"] for e in want], "wrong set of unsafe shards"
    assert got == want, "unsafe shards identified, but the repair details differ"
