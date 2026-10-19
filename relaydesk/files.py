"""Bounded local file checks. No execution, network paths or recursive scans."""
from datetime import datetime, timezone
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import re
import stat
from urllib.parse import unquote

MAX_FILE_BYTES = 25 * 1024 * 1024
DOCUMENT_SUFFIXES = {'.txt', '.md', '.pdf', '.docx', '.xlsx', '.csv', '.tsv', '.json', '.png', '.jpg', '.jpeg', '.webp'}


def path_syntax(raw):
    if not isinstance(raw, str) or not raw or any(ord(c) < 32 for c in raw):
        raise ValueError('Invalid local path')
    if raw.startswith(('\\\\', '//')) or '://' in raw:
        raise ValueError('Network/device paths are not permitted')
    path = Path(raw)
    if not path.is_absolute():
        raise ValueError('Use an absolute path')
    if any(p.casefold() in {'.git', '.codex', '.ssh', '.aws', '.azure'} for p in path.parts):
        raise ValueError('Credential/application internals are excluded')
    if path.name.casefold() in {'auth.json', 'credentials', 'credentials.json', 'id_rsa', 'id_ed25519'} or path.name.startswith('.env'):
        raise ValueError('Credential files are excluded')
    return path


def local_path(raw):
    path = path_syntax(raw).resolve()
    # Exclusions also apply to the destination of junctions and symlinks.
    return path_syntax(str(path))


class BoundaryError(ValueError):
    def __init__(self, state):
        self.state = state
        super().__init__('File access blocked: ' + state)


def authorized_path(raw, roots):
    path = local_path(raw)
    # Root strings are canonicalized when explicitly registered; do not follow
    # a newly substituted root junction and silently enlarge authorization.
    allowed = [path_syntax(os.path.abspath(x)) for x in roots]
    if not any(path.is_relative_to(root) for root in allowed):
        raise BoundaryError('outside_roots')
    return path


def opened_path(stream):
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        import msvcrt
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        func = kernel.GetFinalPathNameByHandleW
        func.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
        func.restype = wintypes.DWORD
        buf = ctypes.create_unicode_buffer(32768)
        n = func(msvcrt.get_osfhandle(stream.fileno()), buf, len(buf), 0)
        if not 0 < n < len(buf):
            raise OSError('Cannot validate opened file path')
        raw = buf.value
        if raw.startswith('\\\\?\\UNC\\'):
            raise BoundaryError('blocked')
        if raw.startswith('\\\\?\\'):
            raw = raw[4:]
    elif os.name == 'posix' and Path('/proc/self/fd').is_dir():
        raw = os.readlink('/proc/self/fd/' + str(stream.fileno()))
    else:
        raise BoundaryError('unreadable')
    return str(local_path(raw))


@contextmanager
def safe_stream(raw, roots):
    path = authorized_path(raw, roots)
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise BoundaryError('not_file')
        authorized_path(opened_path(stream), roots)
        yield stream
        authorized_path(opened_path(stream), roots)


def check_file(raw, roots, max_bytes=MAX_FILE_BYTES):
    result = {'path': raw, 'state': 'blocked', 'sha256': None,
              'checked_at': datetime.now(timezone.utc).isoformat()}
    try:
        path = authorized_path(raw, roots)
        result['resolved_path'] = str(path)
        if not path.exists():
            result['state'] = 'missing'
            return result
        if not path.is_file():
            result['state'] = 'not_file'
            return result
        with safe_stream(str(path), roots) as stream:
            before = os.fstat(stream.fileno())
            result['size'] = before.st_size
            if before.st_size > max_bytes:
                result['state'] = 'too_large'
                return result
            digest = hashlib.sha256()
            count = 0
            while chunk := stream.read(min(1024 * 1024, max_bytes + 1 - count)):
                count += len(chunk)
                if count > max_bytes:
                    result['state'] = 'too_large'
                    return result
                digest.update(chunk)
            after = os.fstat(stream.fileno())
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            result['state'] = 'changed_during_check'
            return result
        result.update(state='exists', sha256=digest.hexdigest(), modified_ns=after.st_mtime_ns)
    except BoundaryError as ex:
        result['state'] = ex.state
    except ValueError:
        result['state'] = 'blocked'
    except (OSError, RuntimeError):
        result['state'] = 'unreadable'
    return result


def extract_paths(text):
    candidates = [a or b for a, b in re.findall(r'\]\((?:<([^>]+)>|([^\n)]+))\)', text)]
    candidates += re.findall(r'`((?:[A-Za-z]:[\\/]|/)[^`\n]+)`', text)
    found = []
    for raw in candidates:
        path = re.sub(r':\d+(?::\d+)?$', '', unquote(raw.strip()))
        if '://' in path or not re.match(r'^(?:[A-Za-z]:[\\/]|/(?!/))', path):
            continue
        if path not in found:
            found.append(path)
    return found[:200]
