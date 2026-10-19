# Security and privacy boundary

RelayDesk is a single-user, local application. Do not expose its port or run it as an internet service.

- API data needs a random process-scoped bearer token. Host/Origin checks, no CORS, no-store responses, CSP and text-only source rendering reduce browser-origin attacks.
- Import accepts only user messages and assistant final text. Source content is untrusted data, never commands. Importing old permissions does not renew authorization.
- Codex projections are read-only and schema checked. No auth/config files are read. Live snapshots across two databases are not guaranteed atomic with each other.
- Credential masking is best effort. Task notes, messages, paths, exports and backups remain private; no index encryption or full anonymization is provided.
- File checks use explicit canonical roots, reject network/device syntax and credential directories before/after resolution, validate actual opened handle destinations, reject nonregular handles and bound reads. Linux file operations require `/proc/self/fd`. Unsupported platforms fail closed for checks.
- Browser confirmation sends the displayed expected SHA256 and rechecks it, so it cannot silently confirm another byte version. The caller's manual claim of having checked content is still a trust assumption.
- Downloads use the same opened-handle validation, a document suffix allowlist, bounded bytes, digest comparison and attachment disposition. No file or shell execution is provided.
- Markdown source/metadata is emitted in dynamically sized literal blocks. Once you edit an exported document yourself or open it with another renderer, that program's behavior and plugins remain outside this application's control.
- Limitations: no hard OS memory quota, process sandbox, multi-user accounts, defense against a malicious process with your own filesystem/session access, or protection from browser extensions/sync software. Root authorization does not replace OS permissions. Imports and some file operations can take time.

Never commit a data directory or private acceptance record. `.gitignore` is a guard, not a publication audit. Report code issues without attaching personal history or credentials.
