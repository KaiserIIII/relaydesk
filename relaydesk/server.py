"""Authenticated, local-only UI. Not an internet-facing web service."""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import sqlite3
from urllib.parse import parse_qs, quote, urlsplit
import webbrowser

from . import __version__
from .codex import import_codex
from .files import check_file, safe_stream, DOCUMENT_SUFFIXES, MAX_FILE_BYTES
from .handoff import export_handoff

MAX_BODY = 8 * 1024 * 1024
WEB = Path(__file__).parent / 'web'
STATIC = {'/': ('index.html', 'text/html; charset=utf-8'),
          '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
          '/style.css': ('style.css', 'text/css; charset=utf-8')}
CSP = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"


def artifact_views(store, task_id):
    with store.connect() as db:
        rows = [dict(r) for r in db.execute('select * from artifacts where task_id=? order by kind,path', (task_id,))]
    for row in rows:
        check = json.loads(row['last_check']) if row['last_check'] else {'state': 'not_checked', 'sha256': None}
        row['check'] = check
        if not row['accepted_hash']:
            row['acceptance'] = 'not_accepted'
        elif check['state'] != 'exists':
            row['acceptance'] = 'unavailable'
        else:
            row['acceptance'] = 'accepted_snapshot' if check['sha256'] == row['accepted_hash'] else 'stale'
    return rows


class Handler(BaseHTTPRequestHandler):
    server_version = 'RelayDesk'
    sys_version = ''

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, *args):
        # Searches, filenames and session tokens must not enter access logs.
        pass

    def send(self, status, body, content_type='application/json; charset=utf-8', headers=None):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        for key, value in {'Content-Type': content_type, 'Content-Length': str(len(body)),
                           'Cache-Control': 'no-store', 'Content-Security-Policy': CSP,
                           'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer',
                           'X-Frame-Options': 'DENY', **(headers or {})}.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def valid_client(self):
        expected = f'127.0.0.1:{self.server.server_port}'
        if self.headers.get('Host') != expected or len(self.headers.get_all('Host', [])) != 1:
            self.send(403, {'error': 'Invalid loopback Host'})
            return False
        origin = self.headers.get('Origin')
        if origin is not None and origin != 'http://' + expected:
            self.send(403, {'error': 'Cross-origin access blocked'})
            return False
        return True

    def authenticated(self):
        if not secrets.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + self.server.token):
            self.send(401, {'error': '请通过启动程序显示的完整地址打开，或重新启动界面。'})
            return False
        return True

    def body(self):
        if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) != 1:
            raise ValueError('Exactly one Content-Length is required; chunked bodies unsupported')
        try:
            size = int(self.headers.get('Content-Length', '-1'))
        except ValueError as ex:
            raise ValueError('Invalid Content-Length') from ex
        if not 0 <= size <= MAX_BODY:
            self.send(413, {'error': 'Request body exceeds 8 MiB'})
            return None
        payload = self.rfile.read(size)
        if len(payload) != size:
            raise ValueError('Incomplete request body')
        if self.headers.get_content_type() != 'application/json':
            raise ValueError('Use application/json')
        try:
            result = json.loads(payload.decode('utf-8'))
        except (ValueError, UnicodeError) as ex:
            raise ValueError('Invalid UTF-8 JSON') from ex
        if not isinstance(result, dict):
            raise ValueError('Request must be a JSON object')
        return result

    def do_GET(self):
        self.dispatch('GET')

    def do_POST(self):
        self.dispatch('POST')

    def dispatch(self, method):
        self.close_connection = True
        if not self.valid_client():
            return
        try:
            url = urlsplit(self.path)
            path = url.path
            if method == 'GET' and path in STATIC:
                name, mime = STATIC[path]
                self.send(200, (WEB / name).read_bytes(), mime)
                return
            if not path.startswith('/api/'):
                self.send(404, {'error': 'Not found'})
                return
            if not self.authenticated():
                return
            store = self.server.store
            query = parse_qs(url.query)
            if method == 'GET' and path == '/api/tasks':
                tasks = store.search(query.get('q', [''])[0], query.get('category', [''])[0], query.get('status', [''])[0])
                with store.connect() as db:
                    counts = {key: db.execute('select count(*) from ' + table).fetchone()[0]
                              for key, table in [('tasks', 'tasks'), ('messages', 'messages'), ('artifacts', 'artifacts')]}
                self.send(200, {'tasks': tasks, 'counts': counts, 'version': __version__})
                return
            if method == 'GET' and path == '/api/settings':
                self.send(200, {'roots': store.setting('roots', []), 'codex_enabled': bool(store.setting('codex_home'))})
                return
            match = re.fullmatch(r'/api/tasks/([^/]+)', path)
            if method == 'GET' and match:
                task = store.detail(match[1])
                task['artifacts'] = artifact_views(store, match[1])
                self.send(200, task)
                return
            match = re.fullmatch(r'/api/artifacts/([^/]+)/download', path)
            if method == 'GET' and match:
                item = store.artifact(match[1])
                check = check_file(item['path'], store.setting('roots', []))
                if check['state'] != 'exists':
                    raise ValueError('File is missing, outside roots or cannot be checked')
                p = Path(check['resolved_path'])
                if p.suffix.casefold() not in DOCUMENT_SUFFIXES:
                    raise ValueError('This file type cannot be downloaded through the UI')
                with safe_stream(str(p), store.setting('roots', [])) as stream:
                    data = stream.read(MAX_FILE_BYTES + 1)
                if len(data) > MAX_FILE_BYTES or hashlib.sha256(data).hexdigest() != check['sha256']:
                    raise ValueError('File changed during download; check again')
                self.send(200, data, 'application/octet-stream',
                          {'Content-Disposition': "attachment; filename=artifact; filename*=UTF-8''" + quote(p.name, safe='')})
                return
            if method != 'POST':
                self.send(405 if re.fullmatch(r'/api/tasks/[^/]+/(check|discover|handoff|artifacts|associate)', path) else 404,
                          {'error': 'Use POST for actions' if path.count('/') > 3 else 'Not found'})
                return
            body = self.body()
            if body is None:
                return
            if path == '/api/tasks':
                result = store.create(body.get('title', ''))
            elif path == '/api/import-codex':
                result = import_codex(store, store.setting('codex_home', str(Path.home() / '.codex')))
            elif path == '/api/import-jsonl':
                result = store.import_records(body.get('records', []))
            else:
                task_match = re.fullmatch(r'/api/tasks/([^/]+)(?:/(check|discover|handoff|artifacts|associate))?', path)
                art_match = re.fullmatch(r'/api/artifacts/([^/]+)(?:/(accept))?', path)
                if task_match:
                    tid, action = task_match.groups()
                    if action is None:
                        result = store.edit(tid, body)
                    elif action == 'check':
                        result = {'artifacts': store.check_artifacts(tid)}
                    elif action == 'discover':
                        result = store.discover_artifacts(tid)
                    elif action == 'handoff':
                        result = export_handoff(store, tid)
                    elif action == 'associate':
                        result = store.associate(tid, body.get('thread_id', ''))
                    else:
                        result = store.add_artifact(tid, body.get('path', ''), body.get('source_id', ''), body.get('kind', 'deliverable'))
                elif art_match:
                    if art_match[2]:
                        expected = body.get('expected_hash')
                        if not isinstance(expected, str) or not re.fullmatch(r'[0-9a-f]{64}', expected):
                            raise ValueError('请先重新检查文件，再确认显示的版本')
                        result = store.accept_artifact(art_match[1], expected)
                    else:
                        result = store.edit_artifact(art_match[1], body)
                else:
                    self.send(404, {'error': 'Not found'})
                    return
            self.send(200, result)
        except KeyError:
            self.send(404, {'error': '记录不存在'})
        except (ValueError, TypeError, OSError, sqlite3.Error) as ex:
            self.send(400, {'error': str(ex)[:400]})


def make_server(store, port=8767):
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    server.store = store
    server.token = secrets.token_urlsafe(32)
    return server


def serve_local(store, port=8767, open_browser=True):
    server = make_server(store, port)
    url = f'http://127.0.0.1:{server.server_port}/#token={server.token}'
    print('RelayDesk 本地界面（地址含临时凭据，请勿分享）：\n' + url, flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n已停止；私人索引和备注已保留。')
    finally:
        server.server_close()
