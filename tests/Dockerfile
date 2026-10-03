FROM python:3.13-slim-bookworm

# Everything the verifier needs is installed at build time; test.sh installs nothing.
RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2

# Bake the tests and the sealed ground truth into the image.
COPY . /tests

# Re-prove the shape of the answer key while the image builds, so a future edit
# that quietly breaks it cannot ship.
RUN python - <<'PY'
import json
exp = json.load(open('/tests/expected.json'))
assert set(exp) == {'snapshot_id', 'clock_offsets_ms', 'watermarks_at_close',
                    'snapshot_contents', 'unsafe_watermarks'}
assert exp['snapshot_id'] == 'snap-2291'
assert len(exp['clock_offsets_ms']) == 12
assert all(type(v) is int for v in exp['clock_offsets_ms'].values())
assert len(exp['watermarks_at_close']) == 36
assert set(exp['snapshot_contents']) == set(exp['watermarks_at_close'])
assert sum(len(v) for v in exp['snapshot_contents'].values()) > 300
assert all(type(v) is int for b in exp['snapshot_contents'].values()
           for v in b.values())
rows = exp['unsafe_watermarks']
assert rows and [r['shard'] for r in rows] == sorted(r['shard'] for r in rows)
for r in rows:
    assert set(r) == {'shard', 'watermark', 'repaired_watermark', 'blocking_op_id'}
    assert r['repaired_watermark'] < r['watermark']
    assert r['shard'] in exp['watermarks_at_close']
    assert exp['watermarks_at_close'][r['shard']] == r['watermark']
assert len({r['blocking_op_id'] for r in rows}) == len(rows)
print('expected.json passed the build-time audit')
PY

RUN mkdir -p /app
WORKDIR /tests
