"""Dependency-free command line. No pip installation required."""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys

from . import __version__
from .codex import import_codex
from .demo import seed_demo
from .files import local_path
from .handoff import export_handoff
from .importers import import_jsonl
from .store import Store


def default_data_dir():
    base = Path(os.environ.get('LOCALAPPDATA', Path.home() / '.local' / 'share'))
    return base / 'RelayDesk'


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='RelayDesk 本地任务与成果接力台')
    parser.add_argument('--data-dir', type=Path, default=default_data_dir())
    parser.add_argument('--version', action='version', version=__version__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('demo', help='导入明确标注的虚构示例')
    codex = sub.add_parser('import-codex', help='只读导入本机 Codex 用户消息和最终回复')
    codex.add_argument('--home', type=Path, default=Path.home() / '.codex')
    imp = sub.add_parser('import-jsonl')
    imp.add_argument('path', type=Path)
    imp.add_argument('--role', choices=['user','assistant_final'], default='user')
    search = sub.add_parser('search')
    search.add_argument('query', nargs='?', default='')
    handoff = sub.add_parser('handoff')
    handoff.add_argument('task_id')
    handoff.add_argument('--format', choices=['markdown','json'], default='markdown')
    handoff.add_argument('--output', type=Path)
    backup = sub.add_parser('backup')
    backup.add_argument('destination', type=Path)
    root = sub.add_parser('allow-root')
    root.add_argument('path', type=Path)
    sub.add_parser('doctor')
    serve = sub.add_parser('serve')
    serve.add_argument('--port', type=int, default=8767)
    serve.add_argument('--no-browser', action='store_true')
    args = parser.parse_args(argv)
    try:
        data = args.data_dir.resolve()
        if data.is_relative_to(Path(__file__).resolve().parent.parent):
            raise ValueError('Keep private --data-dir outside the source checkout')
        store = Store(data / 'index.sqlite')
        if args.command == 'demo':
            result = seed_demo(store)
        elif args.command == 'import-codex':
            result = import_codex(store, args.home)
        elif args.command == 'import-jsonl':
            result = import_jsonl(store, args.path, args.role)
        elif args.command == 'search':
            result = store.search(args.query)
        elif args.command == 'allow-root':
            path = local_path(str(args.path.resolve()))
            if not path.is_dir():
                raise ValueError('Allowed root must be an existing local directory')
            roots = list(dict.fromkeys(store.setting('roots', []) + [str(path)]))
            store.set_setting('roots', roots)
            result = {'roots': roots}
        elif args.command == 'handoff':
            value = export_handoff(store, args.task_id)
            text = value['markdown'] if args.format == 'markdown' else json.dumps(value, ensure_ascii=False, indent=2)
            if args.output:
                with args.output.open('x', encoding='utf8') as target:
                    target.write(text)
                result = {'output': str(args.output)}
            else:
                print(text)
                return 0
        elif args.command == 'backup':
            result = {'backup': store.backup(args.destination), 'private': True}
        elif args.command == 'doctor':
            with store.connect() as db:
                check = db.execute('pragma quick_check').fetchone()[0]
            result = {'version': __version__, 'python': sys.version.split()[0], 'sqlite': sqlite3.sqlite_version,
                      'index_check': check, 'tasks': len(store.search('', limit=500)),
                      'network': 'loopback UI only; no cloud API', 'data_dir': str(data)}
            if check != 'ok':
                raise ValueError('Private index integrity check failed')
        else:
            from .server import serve_local
            serve_local(store, args.port, open_browser=not args.no_browser)
            return 0
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, KeyError, OSError, sqlite3.Error, UnicodeError) as ex:
        print(f'ERROR: {ex}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
