"""Best-effort redaction. The result is still private data, never safe-to-publish."""
import re


def redact(text):
    text = re.sub(r'-----BEGIN (?:[A-Z ]+)?PRIVATE KEY-----[\s\S]*?-----END (?:[A-Z ]+)?PRIVATE KEY-----',
                  '[PRIVATE KEY REDACTED]', text)
    text = re.sub(r'(?im)^.*(?:密码|口令|(?:api[_ -]?key|password|passwd|access[_ -]?token|cookie)\s*[:：=]).*$',
                  '[SENSITIVE LINE REDACTED]', text)
    text = re.sub(r'(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|(?:ctx7)?sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,})',
                  '[TOKEN REDACTED]', text)
    return re.sub(r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b', '[EMAIL REDACTED]', text, flags=re.I)
