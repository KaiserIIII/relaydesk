"""Artifact operations mixed into Store; source ownership and acceptance remain explicit."""
import hashlib
import json

from .files import check_file, extract_paths

KINDS = {'source', 'full', 'revision', 'print', 'deliverable', 'evidence'}


class ArtifactStore:
    def add_artifact(self, task_id, path, source_id='', kind='deliverable'):
        task = self.detail(task_id)
        if not isinstance(path, str) or not 1 <= len(path) <= 4096 or kind not in KINDS:
            raise ValueError('Invalid artifact path or kind')
        if source_id and source_id not in {x['id'] for x in task['messages']}:
            raise ValueError('Artifact source must belong to this task')
        aid = hashlib.sha256((task_id + '\0' + path).encode()).hexdigest()[:24]
        with self.connect() as db:
            existing = db.execute('select * from artifacts where task_id=? and path=?', (task_id, path)).fetchone()
            if existing:
                return dict(existing)
            db.execute('insert or ignore into artifacts(id,task_id,path,source_id,kind) values(?,?,?,?,?)',
                       (aid, task_id, path, source_id, kind))
            return dict(db.execute('select * from artifacts where id=?', (aid,)).fetchone())

    def discover_artifacts(self, task_id):
        added = 0
        for message in self.detail(task_id)['messages']:
            for path in extract_paths(message['text']):
                self.add_artifact(task_id, path, source_id=message['id'])
                added += 1
                if added >= 200:
                    return {'references_examined': added, 'truncated': True}
        return {'references_examined': added, 'truncated': False}

    def artifact(self, artifact_id):
        with self.connect() as db:
            row = db.execute('select * from artifacts where id=?', (artifact_id,)).fetchone()
            if row is None:
                raise KeyError('Artifact not found')
            return dict(row)

    def check_artifacts(self, task_id):
        self.detail(task_id)
        with self.connect() as db:
            rows = [dict(x) for x in db.execute('select * from artifacts where task_id=? order by kind,path', (task_id,))]
        checked = []
        roots = self.setting('roots', [])
        for row in rows:
            r = check_file(row['path'], roots)
            if not row['accepted_hash']:
                acceptance = 'not_accepted'
            elif r['state'] != 'exists' or not r['sha256']:
                acceptance = 'unavailable'
            else:
                acceptance = 'accepted_snapshot' if r['sha256'] == row['accepted_hash'] else 'stale'
            row.update(check=r, acceptance=acceptance)
            with self.connect() as db:
                db.execute('update artifacts set last_check=? where id=?', (json.dumps(r, ensure_ascii=False), row['id']))
            checked.append(row)
        return checked

    def accept_artifact(self, artifact_id, expected_hash=None):
        row = self.artifact(artifact_id)
        r = check_file(row['path'], self.setting('roots', []))
        if r['state'] != 'exists' or not r['sha256']:
            raise ValueError('Acceptance requires an allowed, present file with a bounded SHA256 check')
        if expected_hash is not None and r['sha256'] != expected_hash:
            raise ValueError('File changed since the displayed check; inspect and check it again')
        with self.connect() as db:
            db.execute('update artifacts set accepted_hash=?,accepted_at=?,last_check=? where id=?',
                       (r['sha256'], r['checked_at'], json.dumps(r, ensure_ascii=False), artifact_id))
        return self.artifact(artifact_id)

    def edit_artifact(self, artifact_id, values):
        self.artifact(artifact_id)
        if not isinstance(values, dict) or not values or set(values) - {'kind', 'note'}:
            raise ValueError('Only kind and note can be edited')
        if 'kind' in values and values['kind'] not in KINDS:
            raise ValueError('Unknown artifact kind')
        if any(not isinstance(v, str) or len(v) > 10000 for v in values.values()):
            raise ValueError('Invalid artifact note')
        with self.connect() as db:
            db.execute('update artifacts set ' + ','.join(k + '=?' for k in values) + ' where id=?',
                       list(values.values()) + [artifact_id])
        return self.artifact(artifact_id)
