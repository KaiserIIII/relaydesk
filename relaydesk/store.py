"""Private transactional index. Imported source text is not editable task state."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import unicodedata
import uuid

from .privacy import redact
from .artifacts import ArtifactStore

STATUSES = {'unreviewed', 'active', 'waiting', 'accepted', 'paused'}
CATEGORIES = {'general', 'study', 'game', 'research', 'software', 'personal'}
EDITABLE = {'title', 'category', 'status', 'goal', 'corrections', 'open_items', 'next_step', 'verification'}


def now():
    return datetime.now(timezone.utc).isoformat()


def normalized(text):
    return unicodedata.normalize('NFKC', text).casefold()


def identity(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:24]


class Store(ArtifactStore):
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            version = db.execute('pragma user_version').fetchone()[0]
            if version not in (0, 1):
                raise ValueError('Unsupported index version; preserve the index and use a compatible release')
            db.executescript('''
                create table if not exists tasks (
                  id text primary key, title text not null, category text not null default 'general',
                  status text not null default 'unreviewed', goal text not null default '',
                  corrections text not null default '', open_items text not null default '',
                  next_step text not null default '', verification text not null default '',
                  updated_at text not null);
                create table if not exists threads (thread_id text primary key,
                  task_id text not null references tasks(id));
                create table if not exists messages (id text primary key, thread_id text not null references threads(thread_id),
                  item_id text not null, role text not null, text text not null, search_text text not null,
                  time text not null, ordinal integer not null, source_hash text not null);
                create index if not exists messages_thread on messages(thread_id,time,ordinal);
                create table if not exists settings (key text primary key, value text not null);
                create table if not exists artifacts (id text primary key, task_id text not null references tasks(id),
                  path text not null, source_id text not null default '', kind text not null,
                  note text not null default '', accepted_hash text, accepted_at text, last_check text);
                pragma user_version=1;
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.create_function('fold', 1, normalized, deterministic=True)
        db.execute('pragma foreign_keys=on')
        try:
            with db:
                yield db
        finally:
            db.close()

    def import_records(self, records):
        inserted = skipped = 0
        total = 0
        with self.connect() as db:
            for index, raw in enumerate(records):
                if index >= 50000 or not isinstance(raw, dict):
                    raise ValueError('Import limited to 50,000 valid message records per batch')
                for key in ('thread_id', 'item_id', 'text', 'role'):
                    if not isinstance(raw.get(key), str) or not raw[key]:
                        raise ValueError('Each record needs nonempty thread_id, item_id, text and role')
                if raw['role'] not in ('user', 'assistant_final'):
                    raise ValueError('Only user and assistant_final records are supported')
                if max(len(raw['thread_id']), len(raw['item_id'])) > 300 or len(raw['text']) > 524288:
                    raise ValueError('Message or identifier exceeds import bounds')
                total += len(raw['text'].encode('utf-8'))
                if total > 64 * 1024 * 1024:
                    raise ValueError('Import text exceeds 64 MiB')
                text = redact(raw['text'])
                tid = identity('thread:' + raw['thread_id'])
                title = raw.get('title') or (text.splitlines()[0] if raw['role'] == 'user' else '待整理对话')
                if not isinstance(title, str):
                    raise ValueError('Title must be text')
                db.execute('insert or ignore into tasks(id,title,updated_at) values(?,?,?)',
                           (tid, redact(title)[:160], now()))
                db.execute('insert or ignore into threads values(?,?)', (raw['thread_id'], tid))
                mid = identity(raw['thread_id'] + '\0' + raw['role'] + '\0' + raw['item_id'])
                existing = db.execute('select text from messages where id=?', (mid,)).fetchone()
                if existing:
                    if existing['text'] != text:
                        raise ValueError('Source text changed for an existing item; retain the old index and inspect source')
                    skipped += 1
                    continue
                timestamp = raw.get('time') or ''
                ordinal = raw.get('ordinal', index)
                if not isinstance(timestamp, str) or not isinstance(ordinal, int):
                    raise ValueError('Invalid time or ordinal')
                db.execute('insert into messages values(?,?,?,?,?,?,?,?,?)',
                           (mid, raw['thread_id'], raw['item_id'], raw['role'], text,
                            normalized(text), timestamp[:80], ordinal, hashlib.sha256(text.encode()).hexdigest()))
                inserted += 1
        return {'inserted': inserted, 'skipped': skipped, 'redaction': 'best_effort_private_only'}

    def search(self, query='', category='', status='', limit=200):
        if not isinstance(query, str) or len(query) > 200:
            raise ValueError('Search query must be at most 200 characters')
        terms = normalized(query).split()
        if len(terms) > 8:
            raise ValueError('Search supports at most eight AND terms')
        if category and category not in CATEGORIES or status and status not in STATUSES:
            raise ValueError('Unknown category or status')
        clauses, args = [], []
        for term in terms:
            escaped = term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            clauses.append('''(fold(t.title || ' ' || t.goal || ' ' || t.corrections || ' ' || t.next_step || ' ' || t.open_items) like ? escape '\\'
              or exists(select 1 from messages m join threads h on h.thread_id=m.thread_id
                        where h.task_id=t.id and m.search_text like ? escape '\\'))''')
            args.extend(['%' + escaped + '%'] * 2)
        if category:
            clauses.append('t.category=?'); args.append(category)
        if status:
            clauses.append('t.status=?'); args.append(status)
        where = ' where ' + ' and '.join(clauses) if clauses else ''
        with self.connect() as db:
            rows = db.execute('''select t.*,
              (select min(thread_id) from threads where task_id=t.id) thread_id,
              (select count(*) from messages m join threads h on m.thread_id=h.thread_id where h.task_id=t.id) message_count
              from tasks t''' + where + ' order by t.updated_at desc,t.id limit ?',
                              args + [max(1, min(int(limit), 500))]).fetchall()
            return [dict(x) for x in rows]

    def detail(self, task_id):
        with self.connect() as db:
            row = db.execute('select * from tasks where id=?', (task_id,)).fetchone()
            if row is None:
                raise KeyError('Task not found')
            task = dict(row)
            task['threads'] = [x[0] for x in db.execute('select thread_id from threads where task_id=?', (task_id,))]
            task['messages'] = [dict(x) for x in db.execute('''select m.* from messages m join threads h
              on m.thread_id=h.thread_id where h.task_id=? order by m.time,m.ordinal,m.id''', (task_id,))]
            return task

    def edit(self, task_id, values):
        if not isinstance(values, dict) or not values or set(values) - EDITABLE:
            raise ValueError('Unknown or empty task fields')
        for key, value in values.items():
            if not isinstance(value, str) or len(value) > 100000:
                raise ValueError('Task field must be text, at most 100,000 characters')
            if key == 'status' and value not in STATUSES or key == 'category' and value not in CATEGORIES:
                raise ValueError('Unknown category or status')
            if key == 'title' and (not value.strip() or len(value) > 160):
                raise ValueError('Title needs 1–160 characters')
        self.detail(task_id)
        with self.connect() as db:
            db.execute('update tasks set ' + ','.join(key + '=?' for key in values) + ',updated_at=? where id=?',
                       list(values.values()) + [now(), task_id])
        return self.detail(task_id)

    def create(self, title):
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 160:
            raise ValueError('Title needs 1–160 characters')
        tid = uuid.uuid4().hex[:24]
        with self.connect() as db:
            db.execute('insert into tasks(id,title,updated_at) values(?,?,?)', (tid, title.strip(), now()))
        return self.detail(tid)

    def associate(self, task_id, thread_id):
        self.detail(task_id)
        with self.connect() as db:
            cur = db.execute('update threads set task_id=? where thread_id=?', (task_id, thread_id))
            if not cur.rowcount:
                raise KeyError('Thread not found')
            db.execute('''update artifacts set task_id=? where source_id in
              (select id from messages where thread_id=?)''', (task_id, thread_id))
        return self.detail(task_id)

    def setting(self, key, default=None):
        with self.connect() as db:
            row = db.execute('select value from settings where key=?', (key,)).fetchone()
            return json.loads(row[0]) if row else default

    def set_setting(self, key, value):
        with self.connect() as db:
            db.execute('insert or replace into settings values(?,?)', (key, json.dumps(value, ensure_ascii=False)))

    def backup(self, destination):
        destination = Path(destination).resolve()
        if destination.exists():
            raise ValueError('Backup destination must not exist')
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as source:
            target = sqlite3.connect(destination)
            try:
                source.backup(target)
            finally:
                target.close()
        return str(destination)
