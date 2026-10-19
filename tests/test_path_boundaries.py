import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from relaydesk.files import check_file
from relaydesk.handoff import export_handoff
from relaydesk.store import Store


def link_directory(link, target):
    if os.name == 'nt':
        escaped_link = str(link).replace("'", "''")
        escaped_target = str(target).replace("'", "''")
        subprocess.run(['powershell','-NoProfile','-Command',
                        f"New-Item -ItemType Junction -Path '{escaped_link}' -Target '{escaped_target}' | Out-Null"],
                       check=True,capture_output=True,timeout=15)
    else:
        link.symlink_to(target, target_is_directory=True)


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.allowed = self.base / 'allowed'
        self.allowed.mkdir()

    def test_directory_alias_cannot_bypass_excluded_credential_component(self):
        hidden = self.allowed / '.ssh'
        hidden.mkdir()
        (hidden/'notes.txt').write_text('synthetic private data')
        alias = self.allowed/'alias'
        link_directory(alias,hidden)
        result = check_file(str(alias/'notes.txt'),[str(self.allowed)])
        self.assertEqual(result['state'],'blocked')
        self.assertIsNone(result['sha256'])

    def test_parent_swap_between_file_check_and_open_cannot_hash_outside_bytes(self):
        switch = self.allowed/'switch'
        switch.mkdir()
        (switch/'doc.txt').write_text('allowed bytes')
        outside = self.base/'outside'
        outside.mkdir()
        (outside/'doc.txt').write_text('outside private bytes')
        target = switch/'doc.txt'
        real_is_file = Path.is_file
        swapped = []
        def interleave(path):
            value = real_is_file(path)
            if path == target and not swapped:
                switch.rename(self.allowed/'original')
                link_directory(switch,outside)
                swapped.append(True)
            return value
        with patch.object(Path,'is_file',interleave):
            result = check_file(str(target),[str(self.allowed)])
        self.assertEqual(swapped,[True])
        self.assertNotEqual(result['state'],'exists')
        self.assertIsNone(result['sha256'])

    def test_handoff_metadata_is_literal_even_when_source_ids_contain_markdown(self):
        s = Store(self.base/'index.sqlite')
        payload = 't\n![tracking](https://example.invalid/metadata)'
        s.import_records([dict(thread_id=payload,item_id='i',role='user',text='source')])
        tid = s.search('source')[0]['id']
        s.add_artifact(tid,'![tracking](https://example.invalid/path)')
        out = export_handoff(s,tid)['markdown']
        self.assertIn('```text\nthread=t\n![tracking](https://example.invalid/metadata)',out)
        self.assertIn('```text\n![tracking](https://example.invalid/path)\n```',out)


if __name__ == '__main__':
    unittest.main()
