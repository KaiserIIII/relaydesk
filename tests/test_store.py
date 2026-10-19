import json
from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path

from relaydesk.store import Store


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'index.sqlite'
        self.s = Store(self.path)

    def record(self, **kw):
        return dict(thread_id='course', item_id='u1', role='user',
                    text='中文公式整理，原题和答案都要', title='课程资料',
                    time='2026-10-01T09:00:00Z', **kw)

    def test_idempotent_import_preserves_original_source(self):
        self.s.import_records([self.record()])
        self.s.import_records([self.record()])
        task = self.s.search('中文')[0]
        detail = self.s.detail(task['id'])
        self.assertEqual(len(detail['messages']), 1)
        self.assertEqual(detail['messages'][0]['item_id'], 'u1')
        self.assertEqual(task['status'], 'unreviewed')

    def test_chinese_and_literal_percent_search(self):
        self.s.import_records([self.record(), dict(thread_id='other', item_id='p', role='user', text='100% 来源')])
        self.assertEqual([x['thread_id'] for x in self.s.search('中文 公式')], ['course'])
        self.assertEqual([x['thread_id'] for x in self.s.search('%')], ['other'])
        self.assertEqual(self.s.search("' OR 1=1 --"), [])

    def test_manual_goal_and_status_survive_refresh(self):
        self.s.import_records([self.record()])
        tid = self.s.search('中文')[0]['id']
        self.s.edit(tid, {'goal': '打印复习稿', 'status': 'active', 'next_step': '核对新增题'})
        self.s.import_records([self.record()])
        self.assertEqual(self.s.detail(tid)['goal'], '打印复习稿')
        self.assertEqual(self.s.detail(tid)['status'], 'active')

    def test_invalid_batch_is_atomic(self):
        with self.assertRaises(ValueError):
            self.s.import_records([self.record(), {'thread_id': 'bad', 'text': 'missing item'}])
        self.assertEqual(self.s.search(''), [])

    def test_refresh_cannot_silently_rewrite_original_message(self):
        self.s.import_records([self.record()])
        changed = self.record()
        changed['text'] = '改写历史'
        with self.assertRaises(ValueError):
            self.s.import_records([changed])
        self.assertEqual(len(self.s.search('中文')), 1)

    def test_credentials_redacted_before_database_write(self):
        row = self.record()
        row['text'] = '口令：not-a-real-secret\napi_key=sk-' + 'a' * 32 + '\n邮箱 demo@example.invalid'
        self.s.import_records([row])
        with closing(sqlite3.connect(self.path)) as db:
            text = db.execute('select text from messages').fetchone()[0]
        self.assertNotIn('not-a-real-secret', text)
        self.assertNotIn('a' * 32, text)
        self.assertNotIn('demo@example.invalid', text)

    def test_unknown_status_or_field_cannot_create_false_acceptance(self):
        self.s.import_records([self.record()])
        tid = self.s.search('中文')[0]['id']
        for update in ({'status': 'verified_by_AI'}, {'messages': []}):
            with self.assertRaises(ValueError):
                self.s.edit(tid, update)

    def test_unknown_task_is_not_an_empty_success(self):
        with self.assertRaises(KeyError):
            self.s.detail('not-present')

    def test_manual_notes_use_same_unicode_normalization_as_messages(self):
        self.s.import_records([self.record()])
        tid = self.s.search('中文')[0]['id']
        self.s.edit(tid, {'goal': '重新核对ＡＢＣ Straße CAFÉ'})
        for query in ('ＡＢＣ', 'abc', 'Straße', 'strasse', 'CAFÉ'):
            self.assertEqual([x['id'] for x in self.s.search(query)], [tid], query)


if __name__ == '__main__':
    unittest.main()
