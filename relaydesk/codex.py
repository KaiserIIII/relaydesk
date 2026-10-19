"""Optional adapter for two known Codex local projections, always mode=ro.

This is not an official stable SDK. Fail closed on missing schema; never read
auth, settings, reasoning or tool bodies. A cross-database atomic snapshot is
not promised while Codex itself is writing.
"""
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3

REQUIRED = {
    'threads': {'id', 'title', 'thread_source', 'source'},
    'thread_items': {'thread_id', 'item_id', 'item_type', 'item_json', 'created_at_ms', 'rollout_ordinal'},
}


def read_only(path):
    path = Path(path).resolve(strict=True)
    conn = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('pragma query_only=on')
    conn.execute('begin')
    return conn


def check_schema(db, table):
    fields = {r[1] for r in db.execute('pragma table_info(' + table + ')')}
    if not REQUIRED[table] <= fields:
        raise ValueError('Unsupported Codex projection schema; existing index is preserved')


def human_text(text):
    text = re.sub(r'<(?:environment_context|in-app-browser-context|external_codex_apps_open_page|app-context)[^>]*>[\s\S]*?</(?:environment_context|in-app-browser-context|external_codex_apps_open_page|app-context)>', '', text).strip()
    if text.startswith(('# AGENTS.md instructions', '# Skills\n', '<turn_aborted>', '<subagent_notification>', '<external_codex_apps_open_page>')):
        return ''
    return text


def import_codex(store, home):
    home = Path(home).resolve(strict=True)
    with closing(read_only(home / 'state_5.sqlite')) as state, closing(read_only(home / 'thread_history_1.sqlite')) as history:
        check_schema(state, 'threads')
        check_schema(history, 'thread_items')
        threads = list(state.execute("select id,title from threads where (thread_source='user' or thread_source is null) and source='vscode' order by id"))
        def records():
            for thread in threads:
                rows = history.execute('''select item_id,item_type,item_json,created_at_ms,rollout_ordinal
                  from thread_items where thread_id=? and item_type in ('userMessage','agentMessage')
                  order by rollout_ordinal,item_id''', (thread['id'],))
                for row in rows:
                    try:
                        item = json.loads(row['item_json'])
                    except (TypeError, json.JSONDecodeError) as ex:
                        raise ValueError('Invalid Codex projection item; no partial import committed') from ex
                    if row['item_type'] == 'userMessage':
                        content = item.get('content', [])
                        text = '\n'.join(c.get('text', '') for c in content if isinstance(c, dict) and c.get('type') in ('text', 'input_text'))
                        text = human_text(text)
                        role = 'user'
                    elif item.get('phase') in ('final', 'final_answer'):
                        text = item.get('text', '')
                        role = 'assistant_final'
                    else:
                        continue
                    if not text:
                        continue
                    stamp = row['created_at_ms']
                    yield {'thread_id': thread['id'], 'title': thread['title'] or '待整理对话',
                           'item_id': row['item_id'], 'role': role, 'text': text,
                           'time': datetime.fromtimestamp(stamp / 1000, timezone.utc).isoformat() if stamp else '',
                           'ordinal': row['rollout_ordinal'] or 0}
        result = store.import_records(records())
    store.set_setting('codex_home', str(home))
    return dict(result, adapter='state_5+thread_history_1/readonly-v1', threads_examined=len(threads))
