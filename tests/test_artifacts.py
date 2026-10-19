import hashlib
import tempfile
import unittest
from pathlib import Path

from relaydesk.files import check_file, extract_paths
from relaydesk.handoff import export_handoff
from relaydesk.store import Store


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.root = self.base / 'allowed'
        self.root.mkdir()
        self.doc = self.root / '中文讲义.md'
        self.doc.write_text('原题与解析', encoding='utf8')
        self.s = Store(self.base / 'index.sqlite')
        self.s.set_setting('roots', [str(self.root)])
        self.s.import_records([dict(thread_id='study', item_id='u1', role='user', text='新增题也要整理')])
        self.tid = self.s.search('新增题')[0]['id']

    def test_hash_checks_bytes_without_claiming_content_correctness(self):
        r = check_file(str(self.doc), [str(self.root)])
        self.assertEqual(r['state'], 'exists')
        self.assertEqual(r['sha256'], hashlib.sha256('原题与解析'.encode()).hexdigest())
        self.assertNotIn('verified', r)

    def test_unapproved_missing_and_device_paths_are_distinct(self):
        self.assertEqual(check_file(str(self.doc), [])['state'], 'outside_roots')
        self.assertEqual(check_file(str(self.root / 'missing.md'), [str(self.root)])['state'], 'missing')
        for path in ('../secret', '\\\\host\\private\\x', '\\\\?\\C:\\x'):
            self.assertEqual(check_file(path, [str(self.root)])['state'], 'blocked')

    def test_traversal_and_symlink_cannot_escape_roots(self):
        outside = self.base / 'outside.txt'
        outside.write_text('private')
        self.assertEqual(check_file(str(self.root / '..' / 'outside.txt'), [str(self.root)])['state'], 'outside_roots')
        link = self.root / 'link.txt'
        try:
            link.symlink_to(outside)
        except OSError:
            self.skipTest('Symlink creation unavailable; traversal assertion executed')
        self.assertEqual(check_file(str(link), [str(self.root)])['state'], 'outside_roots')

    def test_hashing_is_bounded_and_directories_are_not_files(self):
        self.assertEqual(check_file(str(self.doc), [str(self.root)], max_bytes=1)['state'], 'too_large')
        self.assertEqual(check_file(str(self.root), [str(self.root)])['state'], 'not_file')

    def test_accepted_version_becomes_stale_after_byte_change(self):
        a = self.s.add_artifact(self.tid, str(self.doc), kind='revision')
        self.s.accept_artifact(a['id'])
        self.assertEqual(self.s.check_artifacts(self.tid)[0]['acceptance'], 'accepted_snapshot')
        self.doc.write_text('老师更正了答案', encoding='utf8')
        self.assertEqual(self.s.check_artifacts(self.tid)[0]['acceptance'], 'stale')
        self.doc.unlink()
        self.assertEqual(self.s.check_artifacts(self.tid)[0]['acceptance'], 'unavailable')

    def test_missing_or_outside_file_cannot_be_accepted(self):
        a = self.s.add_artifact(self.tid, str(self.root / 'missing.txt'))
        with self.assertRaises(ValueError):
            self.s.accept_artifact(a['id'])

    def test_path_extraction_ignores_web_urls_and_deduplicates(self):
        text = '[a](</tmp/course notes/a.md:12>) and [b](/tmp/course notes/a.md) https://example.invalid/a.pdf'
        self.assertEqual(extract_paths(text), ['/tmp/course notes/a.md'])

    def test_handoff_keeps_unknown_and_original_provenance(self):
        self.s.edit(self.tid, {'goal': '核对课程资料', 'open_items': '新课件尚未检查'})
        self.s.add_artifact(self.tid, str(self.doc), kind='source')
        out = export_handoff(self.s, self.tid)
        self.assertIn('新课件尚未检查', out['markdown'])
        self.assertIn('u1', out['markdown'])
        self.assertIn('UNKNOWN', out['markdown'])
        self.assertEqual(out['task']['status'], 'unreviewed')
        self.assertEqual(out['artifacts'][0]['acceptance'], 'not_accepted')

    def test_backup_restores_manual_state_and_never_overwrites(self):
        self.s.edit(self.tid, {'next_step': '打印讲义'})
        path = self.base / 'backup.sqlite'
        self.s.backup(path)
        self.assertEqual(Store(path).detail(self.tid)['next_step'], '打印讲义')
        with self.assertRaises(ValueError):
            self.s.backup(path)

    def test_handoff_quotes_cannot_break_out_into_active_markdown(self):
        self.s.import_records([dict(thread_id='html',item_id='h',role='user',text='```\n<img src=x onerror=alert(1)>\n# forged')])
        tid = self.s.search('forged')[0]['id']
        text = export_handoff(self.s,tid)['markdown']
        self.assertIn('````text\n```\n<img src=x onerror=alert(1)>\n# forged\n````',text)


if __name__ == '__main__':
    unittest.main()
