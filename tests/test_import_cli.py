from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from relaydesk.codex import import_codex
from relaydesk.importers import import_jsonl
from relaydesk.store import Store


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.s = Store(self.base / 'target' / 'index.sqlite')

    def fixture(self):
        home = self.base / 'codex'
        home.mkdir()
        with closing(sqlite3.connect(home / 'state_5.sqlite')) as db:
            db.execute('create table threads(id,title,thread_source,source)')
            db.executemany('insert into threads values(?,?,?,?)', [('human','中文笔记','user','vscode'), ('agent','exclude','subagent','subagent'), ('delegate','exclude','agent_created_thread','vscode')])
            db.commit()
        with closing(sqlite3.connect(home / 'thread_history_1.sqlite')) as db:
            db.execute('create table thread_items(thread_id,item_id,item_type,item_json,created_at_ms,rollout_ordinal)')
            values = [('human','u','userMessage',{'content':[{'type':'text','text':'需要中文原题'}]},1),
                      ('human','f','agentMessage',{'phase':'final_answer','text':'历史完成主张'},2),
                      ('human','r','agentMessage',{'phase':'analysis','text':'must not import'},3),
                      ('human','c','userMessage',{'content':[{'type':'text','text':'# AGENTS.md instructions\nnot a request'}]},4),
                      ('agent','a','userMessage',{'content':[{'type':'text','text':'delegated'}]},5)]
            db.executemany('insert into thread_items values(?,?,?,?,?,?)', [(a,b,c,json.dumps(d),1700000000000,n) for a,b,c,d,n in values])
            db.commit()
        return home

    def test_native_adapter_reads_only_user_and_final_and_preserves_source(self):
        home = self.fixture()
        before = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in home.iterdir()}
        result = import_codex(self.s, home)
        self.assertEqual(result['inserted'], 2)
        task = self.s.search('中文')[0]
        self.assertEqual([m['role'] for m in self.s.detail(task['id'])['messages']], ['user','assistant_final'])
        self.assertEqual(self.s.search('must not import'), [])
        self.assertEqual(before, {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in home.iterdir()})
        self.assertEqual(import_codex(self.s, home)['skipped'], 2)

    def test_unknown_schema_fails_without_losing_index(self):
        self.s.import_records([dict(thread_id='old',item_id='o',role='user',text='保留资料')])
        home = self.base / 'bad'
        home.mkdir()
        for name in ('state_5.sqlite','thread_history_1.sqlite'):
            with closing(sqlite3.connect(home/name)) as db:
                db.execute('create table unknown(x)')
        with self.assertRaises(ValueError):
            import_codex(self.s, home)
        self.assertEqual(len(self.s.search('保留资料')), 1)

    def test_jsonl_malformed_record_rolls_back_entire_import(self):
        source = self.base / 'input.jsonl'
        source.write_text(json.dumps(dict(thread_id='c',item_id='x',role='user',text='临时记录'))+'\nNOT JSON\n',encoding='utf8')
        with self.assertRaises(ValueError):
            import_jsonl(self.s, source)
        self.assertEqual(self.s.search(''), [])

    def test_cli_demo_search_handoff_backup_and_invalid_input(self):
        data = self.base / 'appdata'
        def run(*args):
            return subprocess.run([sys.executable,'-m','relaydesk','--data-dir',str(data),*args],capture_output=True,encoding='utf8',timeout=20)
        self.assertEqual(run('demo').returncode, 0)
        result = run('search','中文')
        self.assertEqual(result.returncode, 0, result.stderr)
        task = json.loads(result.stdout)[0]
        report = run('handoff',task['id'])
        self.assertEqual(report.returncode, 0, report.stderr)
        self.assertIn('UNKNOWN', report.stdout)
        self.assertEqual(run('backup',str(self.base/'backup.sqlite')).returncode, 0)
        self.assertEqual(run('doctor').returncode, 0)
        self.assertNotEqual(run('handoff','missing').returncode, 0)

    def test_manual_association_is_explicit_and_preserves_source_thread(self):
        self.s.import_records([dict(thread_id='a',item_id='1',role='user',text='先前计划'),dict(thread_id='b',item_id='2',role='user',text='接着执行')])
        target = self.s.search('先前')[0]['id']
        self.s.associate(target,'b')
        self.assertEqual({m['thread_id'] for m in self.s.detail(target)['messages']}, {'a','b'})

    def test_association_moves_source_linked_artifacts_without_losing_notes(self):
        self.s.import_records([dict(thread_id='a',item_id='1',role='user',text='先前计划'),dict(thread_id='b',item_id='2',role='assistant_final',text='后续文件')])
        first = self.s.search('先前')[0]['id']
        other = self.s.search('后续')[0]['id']
        source_id = self.s.detail(other)['messages'][0]['id']
        a = self.s.add_artifact(other,str(self.base/'report.md'),source_id)
        self.s.edit_artifact(a['id'],{'note':'保留备注'})
        self.s.associate(first,'b')
        moved = self.s.check_artifacts(first)
        self.assertEqual(len(moved),1)
        self.assertEqual(moved[0]['source_id'],source_id)
        self.assertEqual(moved[0]['note'],'保留备注')
        self.assertEqual(self.s.check_artifacts(other),[])


if __name__ == '__main__':
    unittest.main()
