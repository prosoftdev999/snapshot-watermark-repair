"""Snapshot reconstruction used by the overnight audit job.

This is the production-side implementation from the incident capture.  It is
included as evidence, not as a trusted oracle: the audit that opened this
incident says its result is wrong.
"""
import json
from collections import defaultdict
from pathlib import Path

DATA = Path('/app/data')

def jsonl(name):
    with (DATA / name).open() as f:
        return [json.loads(x) for x in f if x.strip()]

def clock_offsets(rows):
    # Historical implementation: smooth all probes for a node.
    by_node = defaultdict(list)
    for r in rows:
        by_node[r['node']].append(((r['t1']-r['t0']) + (r['t2']-r['t3'])) // 2)
    return {n: round(sum(v)/len(v)) for n, v in by_node.items()}

def logical_writes(rows, shard_offset):
    # Reader emits every accepted copy; caller is expected to handle retries.
    out = []
    for r in rows:
        q = dict(r)
        off = shard_offset[r['shard']]
        q['delivered_at'] -= off
        q['applied_at'] -= off
        out.append(q)
    return out

def visible_at_close(row, close):
    return row['delivered_at'] <= close

def replay(rows):
    state = {}
    for r in sorted(rows, key=lambda x: x['delivered_at']):
        if r['kind'] == 'delete':
            state.pop(r['key'], None)
        else:
            state[r['key']] = r['value_version']
    return state
