import http.client
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest

from relaydesk.server import make_server
from relaydesk.store import Store


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.s = Store(self.base / 'index.sqlite')
        self.s.import_records([dict(thread_id='c',item_id='u',role='user',text='中文资料 <script>alert(1)</script>',title='课程')])
        self.tid = self.s.search('中文')[0]['id']
        self.server = make_server(self.s, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def request(self, path, method='GET', data=None, headers=None, authorized=True):
        values = {'Authorization':'Bearer ' + self.server.token} if authorized else {}
        values.update(headers or {})
        body = json.dumps(data,ensure_ascii=False).encode() if data is not None else None
        if body is not None:
            values.setdefault('Content-Type','application/json')
        conn = http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        self.addCleanup(conn.close)
        conn.request(method,path,body=body,headers=values)
        response = conn.getresponse()
        return response.status, dict(response.getheaders()), response.read()

    def test_api_requires_token_and_valid_host_and_origin(self):
        self.assertEqual(self.request('/api/tasks',authorized=False)[0],401)
        self.assertEqual(self.request('/api/tasks',headers={'Host':'evil.invalid'})[0],403)
        self.assertEqual(self.request('/api/tasks',headers={'Origin':'https://evil.invalid'})[0],403)
        self.assertEqual(self.request('/api/tasks')[0],200)

    def test_get_does_not_mutate_task_and_search_returns_inert_original_text(self):
        code,headers,body = self.request('/api/tasks?q=%E4%B8%AD%E6%96%87')
        self.assertEqual(code,200)
        self.assertEqual(json.loads(body)['tasks'][0]['id'],self.tid)
        self.assertIn("default-src 'self'",headers['Content-Security-Policy'])
        self.assertEqual(self.request(f'/api/tasks/{self.tid}/check')[0],405)
        self.assertEqual(self.s.detail(self.tid)['status'],'unreviewed')

    def test_edit_and_handoff_use_same_persisted_state(self):
        code,_,_ = self.request(f'/api/tasks/{self.tid}','POST',{'goal':'中文打印','open_items':'待核对'})
        self.assertEqual(code,200)
        code,_,body = self.request(f'/api/tasks/{self.tid}/handoff','POST',{})
        self.assertEqual(code,200)
        self.assertIn('中文打印',json.loads(body)['markdown'])
        self.assertIn('UNKNOWN',json.loads(body)['markdown'])

    def test_oversized_and_invalid_bodies_fail_without_edits(self):
        self.assertEqual(self.request('/api/tasks','POST',{},headers={'Content-Length':'99999999'})[0],413)
        self.assertEqual(self.request('/api/tasks','POST',[])[0],400)
        self.assertEqual(self.request(f'/api/tasks/{self.tid}','POST',{'status':'AI_verified'})[0],400)
        self.assertEqual(self.s.detail(self.tid)['status'],'unreviewed')

    def test_file_download_requires_allowlisted_path_and_document_type(self):
        p = self.base / 'doc.md'
        p.write_text('中文内容',encoding='utf8')
        a = self.s.add_artifact(self.tid,str(p))
        url = f"/api/artifacts/{a['id']}/download"
        self.assertEqual(self.request(url)[0],400)
        self.s.set_setting('roots',[str(self.base)])
        code,headers,body = self.request(url)
        self.assertEqual(code,200)
        self.assertTrue(headers['Content-Disposition'].startswith('attachment;'))
        self.assertEqual(body.decode(),'中文内容')
        exe = self.base / 'never.exe'
        exe.write_bytes(b'not executable')
        a = self.s.add_artifact(self.tid,str(exe))
        self.assertEqual(self.request(f"/api/artifacts/{a['id']}/download")[0],400)

    def test_unknown_routes_and_bad_static_paths_do_not_expose_files(self):
        self.assertEqual(self.request('/../../anything')[0],404)
        self.assertEqual(self.request('/api/tasks/not-found')[0],404)
        code,headers,body = self.request('/',authorized=False)
        self.assertEqual(code,200)
        self.assertIn(b'RelayDesk',body)
        self.assertNotIn('Access-Control-Allow-Origin',headers)

    def test_acceptance_rejects_file_changed_since_displayed_hash(self):
        p = self.base / 'changing.md'
        p.write_bytes(b'checked version')
        self.s.set_setting('roots',[str(self.base)])
        a = self.s.add_artifact(self.tid,str(p))
        old_hash = hashlib.sha256(b'checked version').hexdigest()
        p.write_bytes(b'new unreviewed version')
        code,_,_ = self.request(f"/api/artifacts/{a['id']}/accept",'POST',{'expected_hash':old_hash})
        self.assertEqual(code,400)
        self.assertIsNone(self.s.artifact(a['id'])['accepted_hash'])


if __name__ == '__main__':
    unittest.main()
