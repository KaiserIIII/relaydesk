"""Bounded UTF-8 JSONL import; errors abort the entire Store transaction."""
import json
from pathlib import Path

MAX_IMPORT_BYTES = 20 * 1024 * 1024


def import_jsonl(store, path, role='user'):
    path = Path(path)
    if path.stat().st_size > MAX_IMPORT_BYTES:
        raise ValueError('JSONL file exceeds 20 MiB')
    def records():
        with path.open('r', encoding='utf-8-sig') as stream:
            while True:
                line = stream.readline(1024 * 1024 + 1)
                if not line:
                    break
                if len(line) > 1024 * 1024:
                    raise ValueError('JSONL line exceeds 1 MiB')
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except (json.JSONDecodeError, UnicodeError) as ex:
                    raise ValueError('Invalid UTF-8 JSONL record') from ex
                if not isinstance(row, dict):
                    raise ValueError('JSONL records must be objects')
                if row.get('context_not_human_request'):
                    continue
                yield dict(row, role=row.get('role', role), time=row.get('time', row.get('time_utc', '')))
    return store.import_records(records())
